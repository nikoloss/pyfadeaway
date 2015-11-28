# coding: utf8
from fadeaway.client import ServerProxy
from fadeaway.client import Async

def connected():
    print 'connected!'

def disconnected():
    print 'disconnected!'

if __name__ == '__main__':
    ss = ServerProxy(Async, 'localhost', 9151)
    ss.monitor('wo', connected, disconnected)
    ss.deploy()
