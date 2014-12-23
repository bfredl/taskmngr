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
        return NS(self.__dict__, **kwargs)

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
        for a in atoms:
            setattr(self, a, self.disp.intern_atom(a))
        self.clients = {}
        self.order = []

    # TODO: listen to events from server instead
    def update_state(self):
        tasks = self.root.get_full_property(self._NET_CLIENT_LIST_STACKING, Xatom.WINDOW).value
        self.order = tasks
        self.clients = {}
        for wid in tasks:
            o = self.disp.create_resource_object("window", wid)
            name = o.get_full_property(self._NET_WM_NAME, 0)
            if not name:
                name = o.get_full_property(Xatom.WM_NAME, 0)
            title = name.value
            desktop = o.get_full_property(self._NET_WM_DESKTOP, Xatom.CARDINAL).value[0]
            self.clients[wid] = NS(title=title, desktop=desktop)

    #TODO: push updates instead
    def get_state(self):
        self.update_state()
        tasks = []
        d = 0
        for i,wid in enumerate(self.order):
            c = self.clients[wid]
            tid = "wm:wid/{}".format(wid)
            gid = "wm:ws/{}".format(c.desktop)
            d = max(d,c.desktop)
            tasks.append( dict(kind="window", tid=tid, parent=gid, title=c.title, order=i))
        for i in range(d+1):
            # FIXME: proper names
            tasks.append( dict(kind="desktop", tid="wm:ws/{}".format(i), title="Workspace {}".format(i+1)))
        return tasks

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
            if 'tid' in t:
                tasks[t['tid']].update(t)

        return tasks.values()

if __name__ == '__main__':
    t = TaskManager()
    print(t.get_state())
    ioloop.IOLoop.instance().start()

