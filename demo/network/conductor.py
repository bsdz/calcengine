

from calcengine import CalcEngine

# since module path can vary based on whether
# tests are run as module or as single file
# we hard code a prefix here.
PATH = "test."

ce = CalcEngine()
#ce.install_plugin("calcengine.network")


from functools import wraps
from calcengine.function_helper import find_calls
from rpyc.utils.teleportation import export_function
import rpyc
import socket
def net_wrap(host):
    def _net_wrap(func):

        @wraps(func)
        def wrapper_func(*args, **kwargs):
            if socket.gethostname() == host:
                # we're on the host, the cache
                # should be ready so just call
                # function.
                func(*args, **kwargs)
            else:
                # call dependants early to populate
                # cache
                found = find_calls(func.__wrapped__)
                for f, args_, kwds_ in found:
                    _ = f(*args_, **kwds_)
                # now we transfer cache to host
                # and remote execute function
                c = rpyc.connect(host, 18812)
                c.root.call_ce_func(
                    ce.cache, 
                    func.__wrapped__.__code__.co_filename, 
                    "ce_func", 
                    "ce_args", 
                    "ce_kwds"
                )
        return wrapper_func
    return _net_wrap


@ce.watch(path=PATH)
def a():
    return 100


@ce.watch(path=PATH)
def b():
    return a()


#@ce.watch(path=PATH, network={"drone-1"})
# transfer graph to drone-1, calc c(x,y) and
# transfer new node result here, inject into
# graph and continue.
@ce.watch(path=PATH)
def c(x, y):
    return 2 * a() + x * y


@net_wrap(host="drone-1")
@ce.watch(path=PATH)
def d(x, y=0):
    return 3 * b() + x - y


@ce.watch(path=PATH)
def e():
    _x = d(5, y=-3)
    return c(2, 3) - 5 + _x


@ce.watch(path=PATH)
def f():
    return d(0) + e()


if __name__ == "__main__":
    print("hello from conductor")
    foo = f()
    print(foo)

    from time import sleep
    while True:
        sleep(1)

