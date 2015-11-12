# coding: utf8
import zmq
import time
import threading, uuid
from collections import deque
from main import Handler
from main import IOLoop

try:
    import ujson as json
except ImportError:
    import json

Sync = 0
Async = 1

APPLICATION_ERROR = -32500


class SyncRPCClient(Handler):
    def __init__(self):
        super(SyncRPCClient, self).__init__()
        self._client = self.ctx.socket(zmq.XREQ)

    def sock(self):
        return self._client

    def connect(self, protocol):
        self._client.connect(protocol)

    def send(self, klass, method, mid, *args, **kwargs):
        data = {
            'id': mid,
            'method': '{klass}->{method}'.format(klass=klass, method=method),
            'params': args,
            'ex_params': kwargs
        }
        s_data = json.dumps(data)
        self.sock().send(s_data)

    def recv(self):
        s_data = self.sock().recv()
        data = json.loads(s_data)
        if data.get('error'):
            error = data['error']
            e = Exception(error.get('message'))
            e.code = error['code'] if error.get('code') else APPLICATION_ERROR
            raise e
        return data.get('result')


class AsyncRPCClient(Handler):
    def __init__(self):
        super(AsyncRPCClient, self).__init__()
        self.flag = zmq.POLLIN
        self._callbacks = {}
        self._buffer = deque()
        self._ioloop = IOLoop.instance()
        self._client = self.ctx.socket(zmq.XREQ)
        self._ioloop.add_handler(self.sock(), self.handle, self.flag)

    def add_callback(self, mid, func):
        self._callbacks[mid] = func

    def connect(self, protocol):
        self._client.connect(protocol)

    def sock(self):
        return self._client

    def send(self, klass, method, mid, *args, **kwargs):
        data = {
            'id': mid,
            'method': '{klass}->{method}'.format(klass=klass, method=method),
            'params': args,
            'ex_params': kwargs
        }
        s_data = json.dumps(data)
        self._buffer.append(s_data)
        if not zmq.POLLOUT & self.flag:
            self.flag |= zmq.POLLOUT
            # IOLoop.instance().update_handler(self.sock(), self.flag)
            self._ioloop.add_callback(self._ioloop.update_handler, self.sock(), self.flag)

    def on_read(self):
        s_data = self.sock().recv()
        data = json.loads(s_data)
        mid = data.get('id')
        callback = self._callbacks.pop(mid)
        e = None
        if data.get('error'):
            error = data['error']
            e = Exception(error.get('message'))
            e.code = error['code'] if error.get('code') else APPLICATION_ERROR
        callback(data.get('result'), error=e)

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send(buf)
        except IndexError as ex:
            self.flag -= zmq.POLLIN
            IOLoop.instance().update_handler(self.sock(), self.flag)


class SyncMethodIllusion(object):
    _lock = threading.Lock()  # Due to zeromq, read/write operations must be thread safe

    def __init__(self, rpclient, klass, method):
        self._rpclient = rpclient
        self._klass = klass
        self._method = method

    def __call__(self, *args, **kwargs):
        mid = str(time.time())
        with SyncMethodIllusion._lock:
            self._rpclient.send(self._klass, self._method, mid, *args, **kwargs)
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
    def __init__(self, host, port):
        self._rpclient = SyncRPCClient()
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
        self.params = args
        self.ex_params = kwargs
        return self

    def then(self, func):
        '''callback'''
        mid = str(uuid.uuid4())
        self._rpclient.add_callback(mid, func)
        self._rpclient.send(self._klass, self._method, mid, *self.params, **self.ex_params)


class AsyncClientIllusion(object):
    def __init__(self, rpclient, klass):
        self._rpclient = rpclient
        self._klass = klass

    def __call__(self):
        return self

    def __getattr__(self, method):
        return AsyncMethodIllusion(self._rpclient, self._klass, method)


class AsyncServerProxy(object):

    _lock = threading.Lock()

    def __init__(self, host, port):
        self._rpclient = AsyncRPCClient()
        self._rpclient.connect('tcp://{host}:{port}'.format(host=host, port=port))
        self._ioloop = IOLoop.instance()

        if not self._ioloop.is_running():
            with AsyncServerProxy._lock:
                if not self._ioloop.is_running():
                    threading.Thread(target=lambda: IOLoop.instance().start()).start()

    def __getattr__(self, klass):
        return AsyncClientIllusion(self._rpclient, klass)


class ServerProxy(object):
    def __init__(self, mode, host, port):
        self.host = host
        self.port = port
        self.mode = mode

    def deploy(self):
        if self.mode == Async:
            return AsyncServerProxy(self.host, self.port)
        elif self.mode == Sync:
            return SyncServerProxy(self.host, self.port)


