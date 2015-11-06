# coding : utf8
import time
from fadeaway.core import server

rpc = server.RPCFrontend()

@rpc.export
class Demo(object):
    def hello(self, name):
        time.sleep(5)
        return "Hello, %s" % name

    def test_string(self, arg):
        try:
            arg + "x"
            return arg
        except:
            raise Exception('str or unicode expected')

    def test_number(self, arg):
        try:
            arg - 0
            return arg
        except TypeError:
            raise Exception('number expected')
    
    def test_array(self, arg):
        try:
            assert type(arg) is list
            return arg
        except AssertionError:
            raise Exception('List expected')

    def test_dict(self, arg):
        try:
            assert type(arg) is dict
            return arg
        except AssertionError:
            raise Exception('Dict expected')

    def test_mix(self, num_arg, str_arg, array_arg, dict_arg):
        try:
            num_arg - 0
            str_arg + "x"
            assert type(array_arg) is list
            assert type(dict_arg) is dict
            return num_arg, str_arg, array_arg, dict_arg
        except:
            raise Exception('demand not satisfied')


app = server.Application()
rpc.bind(9151)
app.register(rpc)
app.serv_forever()

