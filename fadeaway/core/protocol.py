# coding: utf8
import uuid
import time
from error import *

try:
    import ujson as json
except ImportError:
    import json


class Request(object):
    __slots__ = ['mid', 'klass', 'method', 'args', 'kwargs', 'call_at', 'expire_at']

    @classmethod
    def new(cls, klass, method, args, kwargs):
        self = cls()
        self.mid = str(uuid.uuid4())  # mid strategy
        self.klass = klass
        self.method = method
        self.args = args
        self.kwargs = kwargs
        self.call_at = time.time()
        self.expire_at = -1
        return self

    @classmethod
    def loads(cls, s):
        self = cls()
        attrs = json.loads(s)
        self.mid = attrs.get('mid')
        self.klass = attrs.get('class')
        self.method = attrs.get('method')
        self.args = attrs.get('args')
        self.kwargs = attrs.get('kwargs')
        self.call_at = attrs.get('call_at')
        self.expire_at = attrs.get('expire_at')
        return self

    def box(self):
        ret = {
            'mid': self.mid,
            'class': self.klass,
            'method': self.method,
            'args': self.args,
            'kwargs': self.kwargs,
            'call_at': self.call_at,
            'expire_at': self.expire_at
        }
        return json.dumps(ret)


class Response(object):

    __slots__ = ['mid', 'status', 'result', 'error', 'costs']

    @classmethod
    def to(cls, request):
        self = cls()
        self.mid = request.mid
        self.status = OK
        self.result = None
        self.error = None
        self.costs = 0.0
        return self

    @classmethod
    def loads(cls, s):
        self = cls()
        attrs = json.loads(s)
        self.mid = attrs.get('mid')
        self.status = attrs.get('status')
        self.result = attrs.get('result')
        self.error = attrs.get('error')
        self.costs = attrs.get('costs')
        return self

    def set_error(self, error):
        self.status = GENERAL if not hasattr(error, 'code') else error.code
        self.error = str(error)

    def set_result(self, result):
        self.result = result

    def set_costs(self, costs):
        self.costs = costs

    def box(self):
        ret = {
            'mid': self.mid,
            'status': self.status,
            'result': self.result,
            'error': self.error,
            'costs': self.costs
        }
        return json.dumps(ret)