# coding: utf8
import time
import zmq

from collections import deque
from fadeaway.core import error
from fadeaway.core import main
from fadeaway.core import protocol


class NoAvailableWorker(Exception):
    pass





class WorkerList(object):

    def __init__(self):
        pass

    def next(self):
        pass



class Frontend(main.Handler):

    def __init__(self, broker):
        super(Frontend, self).__init__()
        self._ioloop = main.IOLoop.instance()
        self.broker = broker
        self._buffer = deque()
        self._sock = self.ctx.socket(zmq.ROUTER)
        self._sock.bind('tcp://*:{frontend_port}'.format(frontend_port=self.broker.frontend_port))
        self._ioloop.add_handler(self)

    def set_flag(self, flag):
        if flag != self.flag:
            self.flag = flag
            self._ioloop.add_callback(self._ioloop.update_handler, self)

    def send(self, frame):
        try:
            self._buffer.append(frame)
            if not zmq.POLLOUT & self.flag:
                self.set_flag(self.flag | zmq.POLLOUT)
        except Exception as e:
            pass

    def on_read(self):
        frame = self._sock.recv_multipart()
        try:
            worker = self.broker.workers.next()
            frame = worker.ident + frame
        except NoAvailableWorker:
            request = protocol.Request.loads(frame[-1])
            response = protocol.Response.to(request)
            response.set_error(error.CallUnavailable('service unavailable'))
            frame = frame[:-1] + response.box()
            self.send(frame)
        self.broker.backend.send(frame)

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send_multipart(buf)
        except IndexError as ex:
            self.set_flag(self.flag - zmq.POLLOUT)

class Backend(main.Handler):

    def __init__(self, broker):
        super(Backend, self).__init__()
        self._ioloop = main.IOLoop.instance()
        self.broker = broker
        self._buffer = deque()
        self._sock = self.ctx.socket(zmq.ROUTER)
        self._sock.bind('tcp://*:{backend_port}'.format(backend_port=self.broker.backend_port))
        self._ioloop.add_handler(self)


    def set_flag(self, flag):
        if flag != self.flag:
            self.flag = flag
            self._ioloop.add_callback(self._ioloop.update_handler, self)

    def send(self, frame):
        try:
            self._buffer.append(frame)
            if not zmq.POLLOUT & self.flag:
                self.set_flag(self.flag | zmq.POLLOUT)
        except Exception as e:
            pass

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send_multipart(buf)
        except IndexError as ex:
            self.set_flag(self.flag - zmq.POLLOUT)

    def on_read(self):
        frame = self._sock.recv_multipart()

