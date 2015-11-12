# coding: utf8
from fadeaway.core.client import ServerProxy
from fadeaway.core.client import Sync
import zmq

if __name__ == '__main__':
    ss = ServerProxy(Sync, 'localhost', 9151,  {zmq.RCVTIMEO: 5000}).deploy()
    d = ss.Demo()
    print d.test_string('lucy')
    print d.test_number(1)
    print d.test_array([1, '2', 3.14, 4])
    print d.test_dict({"name": "Billy"})
    print d.test_mix(-1, 'greetings', ['a', 'b', 'c'], {"abc": 123})