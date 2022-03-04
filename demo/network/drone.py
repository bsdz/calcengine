import rpyc
from rpyc.utils.server import ThreadedServer

class CEService(rpyc.Service):
    def exposed_call_ce_func(self, ce_cache, ce_module, ce_func, ce_args, ce_kwds):
        pass

if __name__ == "__main__":
    server = ThreadedServer(CEService, port = 18812)
    server.start()
