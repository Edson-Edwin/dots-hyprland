#!/usr/bin/env python3
"""Stop the microphone recorder if its owning Voice & Chat process dies."""
import ctypes
import os
import signal
import sys
parent=os.getppid()
libc=ctypes.CDLL(None,use_errno=True)
if libc.prctl(1,signal.SIGTERM,0,0,0)!=0:raise SystemExit('Unable to bind recorder lifetime to the controller')
if os.getppid()!=parent:raise SystemExit(1)
os.execv('/usr/bin/pw-record',['pw-record',*sys.argv[1:]])
