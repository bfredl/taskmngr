import zmq
ctx = zmq.Context.instance()

rtd = os.environ["XDG_RUNTIME_DIR"]
s = ctx.socket(zmq.DEALER)
s.connect("ipc://{}/taskmgr".format(rtd))

s.send_json(["get_state", 0])
s.recv_json()
