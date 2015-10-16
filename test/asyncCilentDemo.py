# coding: utf8
from fadeaway.core.client import ServerProxy
from fadeaway.core.client import Async

def callback(res, error=None):
    print '[callback]', res

if __name__ == '__main__':
    ss = ServerProxy(Async).deploy()
    h = ss.Demo()
    h.hello('billy').on(callback)
    h.hello('rowland').on(callback)
    h.hi('lucy').on(callback)