# coding: utf8
import time
import functools

import zmq

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


class NotPortSpecified(Exception):
    pass


class RedefineError(Exception):
    pass


class NoSuchOperation(Exception):
    pass


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

    def finish(self, frame, rid, data, **kwargs):
        ff = frame
        try:
            ret = {
                'id': rid,
                'jsonrpc': '2.0',
                'result': data
            }
            ret.update(kwargs)
            ff.append(json.dumps(ret))
            self.sock().send_multipart(ff)
        except Exception as e:
            frame.append(data)
            self.sock().send_multipart(frame)

    def finish_with_error(self, frame, rid, e, **kwargs):
        ret = {
            'id': rid,
            'jsonrpc': '2.0',
            'error': {
                'code': -32600,
                'message': str(e)
            }
        }
        ret['error'].update(e.__dict__)
        ret.update(kwargs)
        frame.append(json.dumps(ret))
        self.sock().send_multipart(frame)

    def get_op_func(self, op):
        op = str(op)
        class_name, method_name = op.split('->')
        if class_name not in self._mapper:
            raise NoSuchOperation('not support operation[%s]' % op)
        clazz = self._mapper.get(class_name)
        instance = clazz()
        func = getattr(clazz, method_name)
        return functools.partial(func, instance)

    def dispatch(self, frame):
        rid = None
        data = frame[-1]
        frame.remove(data)
        try:
            data_dict = json.loads(data)
            operation = data_dict.pop('method')
            rid = data_dict.get('id')
            func = self.get_op_func(operation)
            executor.submit(_task_wrap, func, self, frame, data_dict)
            Log.get_logger().debug('[request] %r', data)
        except Exception, e:
            Log.get_logger().exception(e)
            e.code = -32700
            if rid:
                self.finish_with_error(frame, rid, e)


def _task_wrap(func, handler, frame, data_dict):
    params = data_dict.get('params')
    rid = data_dict.get('id')
    try:
        tik = time.time()
        res = func(*params)
        tok = time.time()
        costs = '%.5f' % (tok - tik)
        IOLoop.instance().add_callback(handler.finish, frame, rid, res, costs=costs)
        Log.get_logger().debug('[response] [%s] takes [%s] seconds', res, costs)
    except Exception as e:
        IOLoop.instance().add_callback(handler.finish_with_error, frame, rid, e)
        Log.get_logger().exception(e)
