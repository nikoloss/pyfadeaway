# coding: utf8
import uuid

try:
    import ujson as json
except ImportError:
    import json


class Request(object):
    __slots__ = ['mid', 'klass', 'method', 'args', 'kwargs', 'expire_at']

    @classmethod
    def new(cls, klass, method, args, kwargs):
        self = cls()
        self.mid = uuid.uuid4()  # mid strategy
        self.klass = klass
        self.method = method
        self.args = args
        self.kwargs = kwargs,
        self.expire_at = -1
        return self

    def box(self):
        ret = {
            'class': self.klass,
            'method': self.method,
            'args': self.args,
            'kwargs': self.kwargs,
            'expire_at': self.expire_at
        }
        return json.dumps(ret)

    def unbox(self, raw_str):
        package = json.loads(raw_str)
        self.mid = package.get('mid')
        self.klass = package.get('class')
        self.method = package.get('method')
        self.args = package.get('args')
        self.kwargs = package.get('kwargs')
        self.expire_at = package.get('expire_at')


class Response(object):

    def __init__(self):
        pass