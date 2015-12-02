# coding: utf8

import zmq
import struct
from core.main import IOLoop
from core.main import Handler
from core.log import Log


class Supervisor(Handler):
    def __init__(self):
        super(Supervisor, self).__init__()
        self.flag = zmq.POLLIN
        self._visor = self.ctx.socket(zmq.PAIR)
        IOLoop.instance().add_handler(self)

    def connect(self, prot):
        self._visor.connect('inproc://{prot}.mo'.format(prot=prot))

    def sock(self):
        return self._visor

    def on_read(self):
        try:
            bevent, endpoint = self._visor.recv_multipart()
            event, _ = struct.unpack('=hi', bevent)
            if event & zmq.EVENT_CONNECTED:
                Log.get_logger().debug('[%s] connection available' % endpoint)
                if hasattr(self, 'available_cb'):
                    self.available_cb()
            if event & zmq.EVENT_DISCONNECTED:
                Log.get_logger().debug('[%s] connection unavailable' % endpoint)
                if hasattr(self, 'unavailable_cb'):
                    self.unavailable_cb()
        except Exception as e:
            Log.get_logger().debug(e)
