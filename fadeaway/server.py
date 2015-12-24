# coding: utf8
import time
import functools

import zmq
from core import protocol
from core.error import *

from concurrent import futures

from core.main import Handler
from core.main import IOLoop
from core.log import Log

WASTE_GAP = 0
MAX_WORKERS = 16
executor = futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)


class ThreadedHandler(Handler):
    def export(self, klass):
        class_name = klass.__name__
        self._mapper[class_name] = klass
        return klass

    def __init__(self):
        super(ThreadedHandler, self).__init__()
        self._mapper = {}
        self.flag = zmq.POLLIN  # overwrite the flag

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

    def on_read(self):
        frame = self.sock().recv_multipart()
        self.dispatch(frame)

    def get_ref(self, klass, method, args, kwargs):
        if klass not in self._mapper:
            raise RefNotFound('"%s" not found' % klass)
        clazz = self._mapper.get(klass)
        instance = clazz()
        func = getattr(clazz, method)
        return functools.partial(func, instance, *args, **kwargs)

    def dispatch(self, frame):
        data = frame[-1]
        frame.remove(data)
        try:
            request = protocol.Request.loads(data)
            executor.submit(_async_run, self, request, self.send, frame)
            Log.get_logger().debug('[request] mid: %s call_at: %f expire_at: %f ***** %s.%s(%s, %s)', request.mid,
                                   request.call_at,
                                   request.expire_at, request.klass, request.method, request.args, request.kwargs)
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
        call_at = request.call_at
        if WASTE_GAP and tik - call_at > WASTE_GAP:
            # 设置WASTE_GAP意味着被调用请求到收到请求耗时超过WASTE_GAP秒，则不处理了
            Log.get_logger().debug('[abandon] mid: %s call_at: hands_on_at: %f',
                                   response.mid, request.call_at, tik)
            return
        func = handler.get_ref(klass, method, args, kwargs)
        res = func()
        tok = time.time()
        costs = tok - tik
        response.set_result(res)
        response.set_costs(costs)

        if tok > expire_at > 0:
            Log.get_logger().debug('[timeout] mid: %s call_at: %f expire_at: %f hands_on_at: %f done_at: %f costs: %f',
                                   response.mid, request.call_at, request.expire_at, tik, tok, costs)
            return
        Log.get_logger().debug('[response] mid: %s status: %d costs: %f', response.mid, response.status, costs)
    except Exception as e:
        tok = time.time()
        costs = tok - tik
        response.set_error(e)
        response.set_costs(costs)
        Log.get_logger().exception(e)
    frame.append(response.box())
    IOLoop.instance().add_callback(callback, frame)
