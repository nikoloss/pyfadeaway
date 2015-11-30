# coding: utf8

OK = 0
GENERAL = 1

indexes = {}


def remote_raise(klass):
    indexes[klass.code] = klass
    return klass


@remote_raise
class GeneralError(Exception):
    code = 1


@remote_raise
class CallTimeout(Exception):
    code = 10


@remote_raise
class ClassBlockedTooLong(Exception):
    code = 20


@remote_raise
class RefNotFound(Exception):
    code = 30


@remote_raise
class CallUnavailable(Exception):
    code = 40


@remote_raise
class NoAvailableWorker(Exception):
    code = 50
