# coding: utf8
import logging
import logging.config


class Log(object):
    fy_logger = None

    @staticmethod
    def get_logger():
        if not Log.fy_logger:
            Log.fy_logger = logging.getLogger('fadeaway')
        return Log.fy_logger

