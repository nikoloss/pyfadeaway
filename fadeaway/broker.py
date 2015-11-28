# coding: utf8

import zmq


class QueueBroker(object):
    def __init__(self, fan_in_port, fan_out_port):
        ctx = zmq.Context()
        front = ctx.socket(zmq.XREP)
        back = ctx.socket(zmq.XREQ)
        front.bind('tcp://*:{port}'.format(port=int(fan_in_port)))
        back.bind('tcp://*:{port}'.format(port=int(fan_out_port)))
        zmq.device(zmq.QUEUE, front, back)

class ReadyQueueBroker(object):
    pass