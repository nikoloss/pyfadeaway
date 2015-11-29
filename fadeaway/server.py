# coding: utf8
import time
import functools

import zmq
from collections import deque
from core import protocol
from core.error import *
try:
    import ujson as json
except ImportError:
    import json
from concurrent import futures

from core.main import Handler
from core.main import IOLoop
from core.log import Log

MAX_WORKERS = 16
executor = futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)



class ThreadedHandler(Handler):

    def export(self, klass):
        class_name = klass.__name__
        self._mapper[class_name] = klass
        return klass

    def __init__(self):
        super(ThreadedHandler, self).__init__()
        self._buffer = deque()
        self._mapper = {}
        self.flag = zmq.POLLIN  # overwrite the flag
        self._ioloop = IOLoop.instance()

    def set_sock(self, sock):
        self._sock = sock

    def listen(self, port):
        self._sock = self.ctx.socket(zmq.XREP)
        self._sock.bind('tcp://*:{port}'.format(port=port))
        self._ioloop.add_handler(self)

    def connect(self, pairs, impl=None):
        host, port = pairs
        if not impl:
            self._sock = self.ctx.socket(zmq.XREP)
            self._sock.connect('tcp://{host}:{port}'.format(host=host, port=port))
            self._ioloop.add_handler(self)

    def sock(self):
        return self._sock

    def set_flag(self, flag):
        if flag != self.flag:
            self.flag = flag
            self._ioloop.add_callback(self._ioloop.update_handler, self)

    def on_read(self):
        frame = self.sock().recv_multipart()
        self.dispatch(frame)

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send_multipart(buf)
        except IndexError as ex:
            self.set_flag(self.flag - zmq.POLLOUT)

    def send(self, frame):
        try:
            self._buffer.append(frame)
            if not zmq.POLLOUT & self.flag:
                self.set_flag(self.flag | zmq.POLLOUT)
        except Exception as e:
            pass

    def get_ref(self, klass, method, args, kwargs):
        if klass not in self._mapper:
            raise RefNotFound('"%s" not found' % klass)
        clazz = self._mapper.get(klass)
        instance = clazz()
        func = getattr(clazz, method)
        return functools.partial(func, instance, *args, **kwargs)

    def dispatch(self, frame):
        rid = None
        data = frame[-1]
        frame.remove(data)
        try:
            request = protocol.Request.loads(data)
            executor.submit(_async_run, self, request, self.send, frame)
            Log.get_logger().debug('[request] %r', data)
        except Exception, e:
            Log.get_logger().exception(e)


def _async_run(handler, request, callback, frame):
    tik = time.time()
    response = protocol.Response.to(request)
    try:
        klass = request.klass
        method = request.method
        args = request.args
        kwargs = request.kwargs
        expire_at = request.expire_at
        if tik > expire_at > 0:
            return
        func = handler.get_ref(klass, method, args, kwargs)
        res = func()
        tok = time.time()
        costs = tok - tik
        response.set_result(res)
        response.set_costs(costs)
        Log.get_logger().debug('[response] [%s] takes [%s] seconds', res, costs)
        if tok > expire_at > 0:
            return
    except Exception as e:
        tok = time.time()
        costs = tok - tik
        response.set_error(e)
        response.set_costs(costs)
        Log.get_logger().exception(e)
    frame.append(response.box())
    IOLoop.instance().add_callback(callback, frame)
