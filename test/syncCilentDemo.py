# coding: utf8
from fadeaway.core.client import ServerProxy
from fadeaway.core.client import Sync


if __name__ == '__main__':
    ss = ServerProxy(mode=Sync, host='localhost', port=9151).deploy()
    h = ss.Demo()
    print h.hello('billy')
    print h.hello('rowland')
    print h.hi('lucy')