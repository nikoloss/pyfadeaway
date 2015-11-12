# coding: utf8
import thread
import threading
import functools

import zmq

from log import Log

context = None

def get_global_context():
    global context
    if not context:
        context = zmq.Context()
    return context

class Handler(object):

    def __init__(self):
        self.flag = zmq.POLLIN | zmq.POLLOUT
        self.ctx = get_global_context()
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

    def __init__(self, **kwargs):
        self._handlers = {}
        self._callbacks = []
        self._callback_lock = threading.Lock()
        self._ctx = zmq.Context()
        self._poller = zmq.Poller()
        self._running = False
        self._waker = Waker()
        self._thread_ident = -1
        self.add_handler(self._waker)

    def get_zmq_context(self):
        return self._ctx

    def add_handler(self, handler):
        sock = handler.sock()
        self._handlers[sock] = handler.handle
        self._poller.register(sock, handler.flag | zmq.POLLERR)

    def update_handler(self, fd, events):
        self._poller.modify(fd, events)

    def remove_handler(self, fd):
        self._handlers.pop(fd)
        self._poller.unregister(fd)

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

    def start(self):

        with IOLoop._instance_lock:
            assert not self._running
            self._running = True

        self._thread_ident = thread.get_ident()

        while 1:
            with self._callback_lock:
                callbacks = self._callbacks
                self._callbacks = []
            for callback in callbacks:
                callback()
            sockets = dict(self._poller.poll(360000))
            for fd, event in sockets.iteritems():
                handler = self._handlers[fd]
                try:
                    handler(event)
                except Exception as e:
                    Log.get_logger().exception(e)



