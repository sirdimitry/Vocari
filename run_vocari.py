"""PyInstaller entry point for the packaged .exe — see vocari.spec."""
import multiprocessing
import os
import sys

# vocari.spec builds with console=False (a windowed app, no terminal) — on
# Windows that means the process gets no console at all, so sys.stdout/
# sys.stderr are None, not just a stream nobody reads. Most of our own code
# never touches them, but torch.hub does (it writes download progress with
# a bare sys.stdout.write(), no None-check), which crashed Silero's model
# download with AttributeError: 'NoneType' object has no attribute 'write'.
# Redirecting to os.devnull here, before anything else runs, gives every
# later import a real, writable (if silent) file object instead.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from vocari.main import main

if __name__ == "__main__":
    # Required for any frozen (PyInstaller) app on Windows that might touch
    # multiprocessing anywhere in its dependency tree (torch does) - without
    # this, Windows' "spawn" start method re-executes this same .exe for a
    # worker process, and without freeze_support() that re-execution runs
    # the *whole app* again (a second tray icon, a second overlay window)
    # instead of just the worker function.
    multiprocessing.freeze_support()
    main()
