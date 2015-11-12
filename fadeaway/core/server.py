#coding: utf8
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


class RPCFrontend(Handler):

    def __init__(self, port):
        super(RPCFrontend, self).__init__()
        self._mapper = {}
        self.flag = zmq.POLLIN  # overwrite the flag
        self._frontend = self.ctx.socket(zmq.ROUTER)
        self._frontend.bind('tcp://*:{port}'.format(port=port))
        IOLoop.instance().add_handler(self.sock(), self.handle, self.flag)

    def sock(self):
        return self._frontend

    def on_read(self):
        address, data = self.sock().recv_multipart()
        self.dispatch(address, data)

    def export(self, klass):
        class_name = klass.__name__
        self._mapper[class_name] = klass
        return klass

    def finish(self, address, rid, data, **kwargs):
        try:
            ret = {
                'id': rid,
                'jsonrpc': '2.0',
                'result': data
            }
            ret.update(kwargs)
            self.sock().send_multipart([address, json.dumps(ret)])
        except Exception as e:
            self.sock().send_multipart([address, data])

    def finish_with_error(self, address, rid, e, **kwargs):
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
        self.sock().send_multipart([address, json.dumps(ret)])

    def get_op_func(self, op):
        op = str(op)
        class_name, method_name = op.split('->')
        if class_name not in self._mapper:
            raise NoSuchOperation('not support operation[%s]' % op)
        clazz = self._mapper.get(class_name)
        instance = clazz()
        func = getattr(clazz, method_name)
        return functools.partial(func, instance)

    def dispatch(self, address, data):
        rid = None
        try:
            data_dict = json.loads(data)
            operation = data_dict.pop('method')
            rid = data_dict.get('id')
            func = self.get_op_func(operation)
            func.dispatch_context = {
                'address': address
            }
            executor.submit(_task_wrap, func, self, data_dict)
            Log.get_logger().debug('[request] from %r carrying [%s]', address, data)
        except Exception, e:
            Log.get_logger().exception(e)
            e.code = -32700
            if rid:
                self.finish_with_error(address, rid, e)


def _task_wrap(func, handler, data_dict):
    address = func.dispatch_context['address']
    params = data_dict.get('params')
    rid = data_dict.get('id')
    try:
        tik = time.time()
        res = func(*params)
        tok = time.time()
        costs = '%.5f' % (tok-tik)
        IOLoop.instance().add_callback(handler.finish, address, rid, res, costs=costs)
        Log.get_logger().debug('[response] to %r with [%s] takes [%s] seconds', address, res, costs)
    except Exception as e:
        IOLoop.instance().add_callback(handler.finish_with_error, address, rid, e)
        Log.get_logger().exception(e)
