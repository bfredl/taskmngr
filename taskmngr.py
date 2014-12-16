import zmq
from zmq.eventloop import ioloop, zmqstream
from itertools import chain
from collections import defaultdict
ioloop.install()
import os
import json
import traceback

import Xlib
from Xlib import X, Xatom, Xutil, display
from Xlib.protocol import event
class NS:
    def __init__(self, dct={}, **kwargs):
        self.__dict__.update(dct)
        self.__dict__.update(kwargs)
    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def join(self, other):
        return SN(self.__dict__, **kwargs)

SN = SimpleNamespace

atoms = [
        "_NET_CLIENT_LIST",
        "_NET_CLIENT_LIST_STACKING",
        "_NET_WM_NAME",
        "_NET_WM_DESKTOP",
        "_NET_ACTIVE_WINDOW",
        "_NET_CURRENT_DESKTOP",
        "_NET_WM_STATE",
        "_NET_WM_STATE_HIDDEN",
        ]

class WindowManager(object):
    def __init__(self):
        self.disp = display.Display()
        self.scr = self.disp.screen()
        self.root = self.scr.root
        self.clients = {}
        self.order = []

    def get_state(self):
        return [ dict(kind="task", tid="wm:wid/204262", label="% ~") ]

    def activate(self, tid):
        wid = stripoff(tid,"wm:wid/")
        print("ACTIVATE", wid)

class TaskManager:
    def __init__(self):
        ctx = zmq.Context.instance()
        rtd = os.environ["XDG_RUNTIME_DIR"]
        self._sock = ctx.socket(zmq.ROUTER)
        self._sock.bind("ipc://{}/taskmgr".format(rtd))
        self.sock = zmqstream.ZMQStream(self._sock)
        self.sock.on_recv(self.on_msg)

        self.sourceState = {}
        self.localSources = {"wm": WindowManager()}

    def on_msg(self, msg):
        addr = msg[0]
        data = msg[1]
        print("recv:", repr(msg))
        try:
            call = json.loads(data)
            meth, args = call[0], call[1:]
        except Exception:
            traceback.print_exc()
            return self.reply_error(addr, "malformed json") 

        try:
            if meth == "get_state":
                res = self.get_state()
            else:
                raise ValueError("no such method")

        except Exception:
            traceback.print_exc()
            return self.reply_error(addr, "error in call")
        self.sock.send_multipart([addr, json.dumps([True, res])])

    def reply_error(self, addr, msg):
        self.sock.send_multipart([addr, json.dumps([False, msg])])

    def get_state(self):
        # ideally `localSources` will be removed, all data will be pushed to TM
        for name,src in self.localSources.items():
            self.sourceState[name] = src.get_state()

        tasks = defaultdict(dict)
        for t in chain(*self.sourceState.values()):
            if t['kind'] == "task":
                tasks[t['tid']].update(t)

        return tasks.values()

if __name__ == '__main__':
    t = TaskManager()
    print(t.get_state())
    ioloop.IOLoop.instance().start()

