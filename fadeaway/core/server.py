# coding: utf8
import time
import functools

import zmq
import protocol
from error import *
try:
    import ujson as json
except ImportError:
    import json
from concurrent import futures

from main import Handler
from main import IOLoop
from log import Log

MAX_WORKERS = 16
executor = futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)



class RemoteSrv(Handler):
    def __init__(self):
        super(RemoteSrv, self).__init__()
        self._mapper = {}
        self.flag = zmq.POLLIN  # overwrite the flag
        self._rpcsrv = self.ctx.socket(zmq.XREP)
        IOLoop.instance().add_handler(self)

    def listen(self, port):
        self._rpcsrv.bind('tcp://*:{port}'.format(port=port))

    def connect(self, pairs):
        host, port = pairs
        self._rpcsrv.connect('tcp://{host}:{port}'.format(host=host, port=port))

    def sock(self):
        return self._rpcsrv

    def on_read(self):
        frame = self.sock().recv_multipart()
        self.dispatch(frame)

    def export(self, klass):
        class_name = klass.__name__
        self._mapper[class_name] = klass
        return klass

    def finish(self, frame):
        try:
            self.sock().send_multipart(frame)
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
            executor.submit(_async_run, self, request, self.finish, frame)
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
