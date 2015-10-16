import types


class AbsHook(object):

    def hook(self, func):
        return func


def wrap(func):
    def _wrap(*args, **kwargs):
        plugins = args[0].installed_plugins
        res = {}
        for plugin in [p for p in plugins if issubclass(p, AbsHook)]:
            hook_res = plugin().hook(func)(*args, **kwargs)
            if isinstance(hook_res, types.DictionaryType):
                res.update(hook_res)
        return res or func(*args, **kwargs)
    return _wrap


class HackedMeta(type):

    def __new__(mcs, _, fathers, attrs):
        for name, value in attrs.iteritems():
            if type(value) == types.FunctionType and not name.startswith('_'):
                attrs[name] = wrap(value)
        return super(HackedMeta, mcs).__new__(mcs, _, fathers, attrs)


class Pluggable(object):
    __metaclass__ = HackedMeta
    installed_plugins = []


def wish(**kwargs):
    def _(obj):
        installed = []
        installs = kwargs.get('install_hook')
        if isinstance(installs, types.ListType):
            installed = installs
        elif issubclass(installs, AbsHook):
            installed.append(installs)
        if type(obj) == HackedMeta:
            obj.installed_plugins = installed
            return obj
        elif type(obj) == types.FunctionType:
            def _hook(*args, **kwargs):
                res = {}
                for plugin in [p for p in installed if issubclass(p, AbsHook)]:
                    hook_res = plugin().hook(obj)(*args, **kwargs)
                    if isinstance(hook_res, types.DictionaryType):
                        res.update(hook_res)
                return res
            return _hook
    return _
