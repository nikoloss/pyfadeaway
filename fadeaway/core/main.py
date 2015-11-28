# coding: utf8
import thread
import threading
import functools
import zmq
import numbers
import heapq
import time

from log import Log

context = zmq.Context()


class Handler(object):
    def __init__(self):
        self.flag = zmq.POLLIN | zmq.POLLOUT
        self.ctx = context
        self.stack_context = {}

    def sock(self):
        raise NotImplementedError()

    def on_read(self):
        raise NotImplementedError()

    def on_write(self):
        raise NotImplementedError()

    def on_error(self):
        raise NotImplementedError()

    def handle(self, event):
        if event & zmq.POLLIN:
            self.on_read()
        elif event & zmq.POLLOUT:
            self.on_write()
        elif event & zmq.POLLERR:
            self.on_error()

    def __del__(self):
        if self.sock():
            self.sock().close()


class Waker(Handler):
    def __init__(self):
        super(Waker, self).__init__()
        self.flag = zmq.POLLIN  # overwrite the flag
        self._reader = self.ctx.socket(zmq.PULL)
        self._writer = self.ctx.socket(zmq.PUSH)
        self._reader.bind('inproc://waker')
        self._writer.connect('inproc://waker')

    def sock(self):
        return self._reader

    def wake_up(self):
        try:
            self._writer.send('x')
        except IOError:
            pass

    def on_read(self):
        try:
            self._reader.recv()
        except IOError:
            pass


class Timeout(object):
    __slots__ = ['deadline', 'callback', 'cancelled']

    def __init__(self, deadline, callback, *args, **kwargs):
        if not isinstance(deadline, numbers.Real):
            raise TypeError("Unsupported deadline %r" % deadline)
        self.deadline = deadline
        self.callback = functools.partial(callback, *args, **kwargs)
        self.cancelled = False
        IOLoop.instance().add_callback(IOLoop.instance().add_timeout, self)

    def cancel(self):
        self.cancelled = True

    def __le__(self, other):
        return self.deadline <= other.deadline

    def __lt__(self, other):
        return self.deadline < other.deadline


class IOLoop(object):
    _instance_lock = threading.Lock()
    _local = threading.local()

    @staticmethod
    def instance():
        """Returns a global `IOLoop` instance.
        """
        if not hasattr(IOLoop, "_instance"):
            with IOLoop._instance_lock:
                if not hasattr(IOLoop, "_instance"):
                    # New instance after double check
                    IOLoop._instance = IOLoop()
        return IOLoop._instance

    @staticmethod
    def is_running():
        return IOLoop.instance()._running

    @staticmethod
    def initialized():
        """Returns true if the singleton instance has been created."""
        return hasattr(IOLoop, "_instance")

    def __init__(self):
        self._handlers = {}
        self._callbacks = []
        self._callback_lock = threading.Lock()
        self._timeouts = []
        self._idle_call = lambda: None
        self._ctx = zmq.Context()
        self._poller = zmq.Poller()
        self._running = False
        self._shutdown = False
        self._idle_timeout = 3600.0
        self._waker = Waker()
        self._thread_ident = -1
        self.add_handler(self._waker)

    def get_zmq_context(self):
        return self._ctx

    def add_handler(self, handler):
        sock = handler.sock()
        self._handlers[sock] = handler.handle
        self._poller.register(sock, handler.flag | zmq.POLLERR)

    def update_handler(self, handler):
        sock = handler.sock()
        self._poller.modify(sock, handler.flag)

    def remove_handler(self, handler):
        sock = handler.sock()
        self._handlers.pop(sock)
        self._poller.unregister(sock)

    def add_callback(self, callback, *args, **kwargs):
        with self._callback_lock:
            is_empty = not self._callbacks
            self._callbacks.append(functools.partial(callback, *args, **kwargs))
            if is_empty and self._thread_ident != thread.get_ident():
                # not on loop thread may need to wake up poller
                self._waker.wake_up()

    def _run_callback(self, callback):
        try:
            callback()
        except Exception, e:
            Log.get_logger().exception(e)

    def shutdown(self):
        self._shutdown = True

    def add_timeout(self, timeout):
        heapq.heappush(self._timeouts, timeout)

    def set_idle(self, timeout, idle_callback):
        self._idle_timeout = timeout
        self._idle_call = idle_callback

    def start(self):

        with IOLoop._instance_lock:
            assert not self._running
            self._running = True

        self._thread_ident = thread.get_ident()

        while not self._shutdown:

            poll_time = self._idle_timeout

            with self._callback_lock:
                callbacks = self._callbacks
                self._callbacks = []

            for callback in callbacks:
                self._run_callback(callback)
            # 为什么把超时列表放到callbacks执行之后读取?
            # 因为:
            # 1.add_timeout的动作也是通过add_callback来完成的,callbacks执行可能会影响到timeouts长度
            # 2.callback在执行的时候也会耽误一些时间, 在callbacks执行之后判断timeout才是比较准确的
            due_timeouts = []
            now = time.time()
            while self._timeouts:
                lastest_timeout = heapq.heappop(self._timeouts)
                if not lastest_timeout.cancelled:
                    if lastest_timeout.deadline <= now:
                        due_timeouts.append(lastest_timeout)
                    else:
                        # 拿多了, 推进去, 顺便把poll()的时间确定出来
                        heapq.heappush(self._timeouts, lastest_timeout)
                        poll_time = lastest_timeout.deadline - time.time()  # 这个值有可能是负数,
                        poll_time = poll_time if poll_time > 0 else 0.0  # 为负数的话变为0
                        break
            for timeout in due_timeouts:
                self._run_callback(timeout.callback)

            if self._callbacks:
                poll_time = 0.0

            sockets = dict(self._poller.poll(poll_time * 1000))
            if sockets:
                for sock, event in sockets.iteritems():
                    handler = self._handlers[sock]
                    try:
                        handler(event)
                    except Exception as e:
                        Log.get_logger().exception(e)
            else:
                self._idle_call()

        self._running = False
