# coding: utf8
import time
import threading
from collections import deque

import zmq

from core import protocol
from core.main import Handler
from core.main import IOLoop
from core.main import Timeout
from fadeaway.monitor import Supervisor
from core.error import *


try:
    import ujson as json
except ImportError:
    import json

Sync = 0
Async = 1


class SyncRPCClient(Handler):
    def __init__(self):
        super(SyncRPCClient, self).__init__()
        self._client = self.ctx.socket(zmq.REQ)

    def sock(self):
        return self._client

    def connect(self, protocol):
        self._client.connect(protocol)

    def send(self, request):
        self.sock().send(request.box())

    def recv(self):
        s = self.sock().recv()
        response = protocol.Response.loads(s)
        if response.error:
            e = indexes[response.status](response.error) if indexes.get(response.status) else Exception(
                    response.error)
            raise e
        return response.result


class AsyncRPCClient(Handler):
    def __init__(self):
        super(AsyncRPCClient, self).__init__()
        self.flag = zmq.POLLIN
        self._callbacks = {}
        self._buffer = deque()
        self._ioloop = IOLoop.instance()
        self._client = self.ctx.socket(zmq.XREQ)
        self._ioloop.add_handler(self)

    def set_flag(self, flag):
        if flag != self.flag:
            self.flag = flag
            self._ioloop.add_callback(self._ioloop.update_handler, self)

    def add_callback(self, mid, func, **kwargs):
        timeout = kwargs.get('timeout')
        timer = None
        if timeout:
            at = time.time() + timeout
            timer = Timeout(at, self.callback_timeout, mid)
        self._callbacks[mid] = (func, timer)

    def callback_timeout(self, mid):
        if self._callbacks.get(mid):
            callback, timer = self._callbacks.pop(mid)
            timer.cancelled = True
            callback(None, error=CallTimeout('time out'))

    def connect(self, protocol):
        self._client.connect(protocol)

    def sock(self):
        return self._client

    def request(self, req, callback, **conf):
        mid = req.mid
        timeout = conf.get('timeout')
        timer = None
        if timeout:
            at = time.time() + timeout
            timer = Timeout(at, self.callback_timeout, mid)
            req.expire_at = at
        self._callbacks[mid] = (callback, timer)
        s = req.box()
        self._buffer.append(s)
        if not zmq.POLLOUT & self.flag:
            self.set_flag(self.flag | zmq.POLLOUT)

    def on_read(self):
        s = self.sock().recv()
        response = protocol.Response.loads(s)
        if self._callbacks.get(response.mid):
            e = None
            callback, timer = self._callbacks.pop(response.mid)
            if response.error:
                e = indexes[response.status](response.error) if indexes.get(response.status) else Exception(
                    response.error)
            callback(response.result, error=e)

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send(buf)
        except IndexError as ex:
            self.set_flag(self.flag - zmq.POLLOUT)


class SyncMethodIllusion(object):
    _lock = threading.Lock()  # Due to zeromq, read/write operations must be thread safe

    def __init__(self, rpclient, klass, method):
        self._rpclient = rpclient
        self._klass = klass
        self._method = method

    def __call__(self, *args, **kwargs):
        mid = str(time.time())
        request = protocol.Request.new(self._klass, self._method, args, kwargs)
        with SyncMethodIllusion._lock:
            self._rpclient.send(request)
            return self._rpclient.recv()

    def __del__(self):
        pass


class SyncClientIllusion(object):
    def __init__(self, rpclient, klass):
        self._klass = klass
        self._rpclient = rpclient

    def __call__(self):
        return self

    def __getattr__(self, name):
        return SyncMethodIllusion(self._rpclient, self._klass, name)


class SyncServerProxy(object):
    def __init__(self, host, port, configs):
        self._rpclient = SyncRPCClient()
        for config, value in configs.iteritems():
            self._rpclient.sock().setsockopt(config, value)
        self._rpclient.connect('tcp://{host}:{port}'.format(host=host, port=port))

    def __getattr__(self, name):
        return SyncClientIllusion(self._rpclient, name)


class AsyncMethodIllusion(object):
    _lock = threading.Lock()  # Due to zeromq read/write operations must be thread safe

    def __init__(self, rpclient, klass, method):
        self._method = method
        self._klass = klass
        self._rpclient = rpclient

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    def then(self, func, **kwargs):
        '''callback'''
        request = protocol.Request.new(self._klass, self._method, self.args, self.kwargs)
        self._rpclient.request(request, func, **kwargs)


class AsyncClientIllusion(object):
    def __init__(self, rpclient, klass):
        self._rpclient = rpclient
        self._klass = klass

    def __call__(self):
        return self

    def __getattr__(self, method):
        return AsyncMethodIllusion(self._rpclient, self._klass, method)


class AsyncServerProxy(object):
    def __init__(self, host, port, configs={}):
        self.host = host
        self.port = port
        self.configs = configs
        self._deployed = False
        self._monitored = False
        self._lock = threading.Lock()
        self._rpclient = AsyncRPCClient()
        self._supervisor = Supervisor()
        self.event = zmq.EVENT_CONNECTED | zmq.EVENT_DISCONNECTED
        for config, value in self.configs.iteritems():
            self._rpclient.sock().setsockopt(config, value)
        self._rpclient.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
        self._ioloop = IOLoop.instance()

    def deploy(self):
        if not self._ioloop.is_running():
            with self._lock:
                if not self._ioloop.is_running():
                    threading.Thread(target=lambda: IOLoop.instance().start()).start()
        self._deployed = True

    def monitor(self, prot, available_cb, unavailable_cb):
        assert not self._deployed
        with self._lock:
            assert not self._deployed
            self._rpclient.sock().monitor('inproc://{prot}.mo'.format(prot=prot), self.event)
            self._supervisor.connect(prot)
            if available_cb:
                self._supervisor.available_cb = available_cb
            if unavailable_cb:
                self._supervisor.unavailable_cb = unavailable_cb
            self._monitored = True

    def quit(self):
        if self._monitored:
            self._ioloop.remove_handler(self._supervisor)
            del self._supervisor
        if self._deployed:
            self._ioloop.remove_handler(self._rpclient)
            del self._rpclient
        del self

    def __getattr__(self, klass):
        return AsyncClientIllusion(self._rpclient, klass)


class ServerProxy(object):
    def __new__(cls, mode, host, port, configs={}):
        if mode == Async:
            return AsyncServerProxy(host, port, configs)
        elif mode == Sync:
            return SyncServerProxy(host, port, configs)


