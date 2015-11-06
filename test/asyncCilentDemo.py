# coding: utf8
from fadeaway.core.client import ServerProxy
from fadeaway.core.client import Async

def callback(res, error=None):
    '''error will be set if there is an error while calling'''
    if not error:
        print '[callback]', res
    else:
        print error

def callback_for_mix(num_arg, str_arg, list_arg, dict_arg, error=None):
    if not error:
        print '[mix callback]', num_arg, str_arg, list_arg, dict_arg
    else:
        print error

if __name__ == '__main__':
    ss = ServerProxy(Async, 'localhost', 9151).deploy()
    d = ss.Demo()
    d.hello('billy').then(callback)
    d.hello('rowland').then(callback)
    d.test_mix(-1, 'greetings', ['a', 'b', 'c'], {"abc": 123}).then(callback)
