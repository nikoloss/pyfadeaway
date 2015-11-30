# coding: utf8
import zmq
import functools
from fadeaway import server
from fadeaway.core import main

HEARTBEAT_CC = 3.0  # 心跳周期


class Worker(object):
    def __init__(self, pair):
        self.host, self.port = pair
        self._ioloop = main.IOLoop.instance()

    def register_handler(self, handler, ident=None):
        self.handler = handler
        sock = self.handler.ctx.socket(zmq.DEALER)
        if ident:
            sock.setsockopt(zmq.IDENTITY, ident)
        sock.connect('tcp://{host}:{port}'.format(host=self.host, port=self.port))
        self.handler.set_sock(sock)
        sock.send(str(server.MAX_WORKERS))
        self._ioloop.add_callback(self._ioloop.add_handler, self.handler)

    def start(self):
        self._ioloop.set_idle(HEARTBEAT_CC,
                              functools.partial(self.handler.send, ['ready']))
        self._ioloop.start()


rpc = server.ThreadedHandler()


@rpc.export
class A(object):
    def hi(self, name):
        return 'Hi, ' + name


if __name__ == '__main__':
    worker = Worker(('localhost', 9152))
    worker.register_handler(rpc, '115')
    worker.start()
