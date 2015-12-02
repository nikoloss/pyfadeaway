# coding: utf8
# Reliable Patterns
# Projects in "worker" folder covered advanced uses of fadeaway
#
#     **********             **********              **********
#     * client *             * client *              * client *
#     *  XREQ  *             *  XREQ  *              *  XREQ  *
#     **********             **********              **********
#          \                     |                       /
#            \                   |                     /
#              ------------------|--------------------
#                                |
#                         ****************
#                         *    ROUTER    *
#                         * workers heap *
#                         *   heartbeat  *
#                         *    ROUTER    *
#                         ****************
#                                |
#              ------------------|-------------------
#            /                   |                    \
#          /                     |                      \
#     **********            **********               **********
#     * DEALER *            * DEALER *               * DEALER *
#     * Worker *            * Worker *               * Worker *
#     **********            **********               **********
#
# Broker detects worker, so if a worker dies while idle, the Broker
# removes it from its worker queue until the worker sends it anything(
# response or heartbeat).
# But notice it may takes a while detecting worker dies, the requests
# at that time will be abandoned

import time
import zmq
import heapq
from collections import deque
from fadeaway.core import error
from fadeaway.core import main
from fadeaway.core import protocol
from fadeaway.server import MAX_WORKERS


HEARTBEAT = 1
RESPONSE = 2


class Worker(object):
    def __init__(self, ident, capacity):
        self.ident = ident
        self.ready_at = time.time()
        self.capacity = capacity

    def __le__(self, other):
        # 把小顶堆变成大顶堆
        return other.capacity <= self.capacity

    def __lt__(self, other):
        return other.capacity < self.capacity


class WorkerList(object):
    _HEARTBEAT_CC = 3.0  # 心跳周期


    def __init__(self):
        self.workers = []

    def next(self):
        now = time.time()
        for x in range(len(self.workers)):
            worker = heapq.heappop(self.workers)
            if (now - worker.ready_at) < 2 * WorkerList._HEARTBEAT_CC:
                if worker.capacity > 0:
                    worker.capacity -= 1
                    heapq.heappush(self.workers, worker)
                    return worker
                else:
                    heapq.heappush(self.workers, worker)
        if self.workers:
            raise error.NoAvailableWorker('all busy')
        else:
            raise error.NoAvailableWorker('no worker')

    def get_ready(self, ident, flag=HEARTBEAT):
        for worker in self.workers:
            if worker.ident == ident:
                if flag & HEARTBEAT:
                    worker.ready_at = time.time()
                if flag & RESPONSE:
                    worker.capacity += 1
                break
        else:
            heapq.heappush(self.workers, Worker(ident, MAX_WORKERS))


class Frontend(main.Handler):
    def __init__(self, broker):
        super(Frontend, self).__init__()
        self._ioloop = main.IOLoop.instance()
        self.broker = broker
        self._buffer = deque()
        self._sock = self.ctx.socket(zmq.ROUTER)
        self._sock.bind('tcp://*:{frontend_port}'.format(frontend_port=self.broker.frontend_port))
        self._ioloop.add_handler(self)

    def sock(self):
        return self._sock

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
            frame = [worker.ident] + frame
        except error.NoAvailableWorker as e:
            request = protocol.Request.loads(frame[-1])
            response = protocol.Response.to(request)
            response.set_error(e)
            frame = frame[:-1] + [response.box()]
            self.send(frame)
        self.broker.backend.send(frame)

    def on_write(self):
        try:
            buf = self._buffer.popleft()
            self.sock().send_multipart(buf)
        except IndexError:
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

    def sock(self):
        return self._sock

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
        except IndexError:
            self.set_flag(self.flag - zmq.POLLOUT)

    def on_read(self):
        frame = self._sock.recv_multipart()
        ident = frame[0]
        frame.remove(ident)
        if len(frame) == 1:
            # heartbeat
            if frame[0] == 'ready':
                self.broker.workers.get_ready(ident)
            else:
                capacity = int(frame[0])
                self.broker.workers.get_ready(ident, capacity)
        else:
            # any sign from worker means it's ready
            self.broker.workers.get_ready(ident)
            self.broker.frontend.send(frame)


class Broker(object):
    def __init__(self, port_pair):
        self.frontend_port, self.backend_port = port_pair
        self.frontend = Frontend(self)
        self.backend = Backend(self)
        self.workers = WorkerList()
        self.ioloop = main.IOLoop.instance()

    def start(self):
        self.ioloop.start()


if __name__ == '__main__':
    Broker((9151, 9152)).start()
