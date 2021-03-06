#!/usr/bin/python
#From https://gist.github.com/svdgraaf/198e2c0cf4cf0a031c84
import pygraphviz as pgv
import threading

from janitoo.options import JNTOptions
from janitoo_solarpump.solarpump import SolarpumpBus

bus = SolarpumpBus(options=JNTOptions({}))
fsm = bus.create_fsm()
fsm.show_graph(fname='rst/images/fsm_bus.png', prog='dot')
