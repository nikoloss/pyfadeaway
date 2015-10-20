# coding: utf8
from fadeaway.core.client import ServerProxy
from fadeaway.core.client import Async

def callback(res, error=None):
    '''error will be set if there is an error while calling'''
    if not error:
        print '[callback]', res
    else:
        print error

if __name__ == '__main__':
    ss = ServerProxy(Async).deploy()
    h = ss.Demo()
    h.hello('billy').then(callback)
    h.hello('rowland').then(callback)
    h.hi('lucy').then(callback)
