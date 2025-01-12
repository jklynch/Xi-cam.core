import inspect
import logging
import faulthandler
import signal
import sys
import os
import time
from typing import Any
import traceback
import threading
from collections import defaultdict
from qtpy.QtCore import QTimer
from xicam.core import paths

"""
This module provides application-wide logging tools. Unhandled exceptions are hooked into the log. Messages and progress
can be displayed in the main Xi-cam window using showProgress and showMessage.

"""

# TODO: Add logging for images
# TODO: Add icons in GUI reflection


# GUI widgets are registered into these slots to display messages/progress
statusbar = None
progressbar = None
os.makedirs(os.path.join(paths.user_cache_dir, "logs"), exist_ok=True)
logging.basicConfig(filename=os.path.join(paths.user_cache_dir, "logs", "out.log"), level=logging.DEBUG)

blacklist = [
    "fabio.edfimage",
    "ipykernel.inprocess.ipkernel",
    "pyFAI.azimuthalIntegrator",
    "traitlets",
    "fabio.openimage",
    "fabio.fabioutils",
    "PyQt5.uic.uiparser",
    "yapsy",
    "caproto.threading.client",
    "caproto._circuit",
    "caproto",
]

for modname in blacklist:
    logging.getLogger(modname).setLevel(logging.ERROR)
stdch = logging.StreamHandler()

# Log levels constants
DEBUG = logging.DEBUG  # 10
INFO = logging.INFO  # 20
WARNING = logging.WARNING  # 30
ERROR = logging.ERROR  # 40
CRITICAL = logging.CRITICAL  # 50

levels = {DEBUG: "DEBUG", INFO: "INFO", WARNING: "WARNING", ERROR: "ERROR", CRITICAL: "CRITICAL"}

trayicon = None
if "qtpy" in sys.modules:
    from qtpy.QtWidgets import QApplication

    if QApplication.instance():
        from qtpy.QtWidgets import QSystemTrayIcon
        from qtpy.QtGui import QIcon, QPixmap
        from xicam.gui.static import path

        trayicon = QSystemTrayIcon(QIcon(QPixmap(str(path("icons/cpu.png")))))  # TODO: better icon

_thread_count = 0


def _increment_thread():
    global _thread_count
    _thread_count += 1
    return _thread_count


threadIds = defaultdict(_increment_thread)


def showProgress(value: int, minval: int = 0, maxval: int = 100):
    """
    Displays the progress value on the subscribed QProgressBar (set as the global progressbar)

    Parameters
    ----------
    value   : int
        Progress value.
    minval  : int
        Minimum value (default: 0)
    maxval  : int
        Maximum value (default: 100)

    """
    if progressbar:
        from .. import threads  # must be a late import

        threads.invoke_in_main_thread(progressbar.show)
        threads.invoke_in_main_thread(progressbar.setRange, minval, maxval)
        threads.invoke_in_main_thread(progressbar.setValue, value)


def showBusy():
    """
     Displays a busy indicator on the subscribed QProgressBar (set as the global progressbar)

    """
    if progressbar:
        from .. import threads  # must be a late import

        threads.invoke_in_main_thread(progressbar.show)
        threads.invoke_in_main_thread(progressbar.setRange, 0, 0)


def hideBusy():
    """
    Stops a busy indicator on the subscribed QProgressBar (set as the global progressbar)

    """
    if progressbar:
        progressbar.hide()
        progressbar.setRange(0, 100)


# aliases
showReady = hideBusy
hideProgress = hideBusy


def notifyMessage(*args, timeout=8000, title="", level: int = INFO):
    """
    Same as logMessage, but displays to the subscribed notification system with a timeout.

    Parameters
    ----------
    args        :   tuple(str)
        See logMessage...
    timeout     :   int
        How long the message is displayed. If set 0, the message is persistent.
    kwargs      :   dict
        See logMessage...
    Returns
    -------

    """
    global trayicon
    if trayicon:
        icon = None
        if level in [INFO, DEBUG]:
            icon = trayicon.Information
        if level == WARNING:
            icon = trayicon.Warning
        if level in [ERROR, CRITICAL]:
            icon = trayicon.Critical
        if icon is None:
            raise ValueError("Invalid message level.")
        trayicon.show()
        from .. import threads  # must be a late import

        threads.invoke_in_main_thread(trayicon.showMessage, title, "".join(args), icon, timeout)
        threads.invoke_in_main_thread(lambda *_: QTimer.singleShot(timeout, trayicon.hide))
        # trayicon.showMessage(title, ''.join(args), icon, timeout)  # TODO: check if title and message are swapped?

    logMessage(*args)


def showMessage(*args, timeout=5, **kwargs):
    """
    Same as logMessage, but displays to the subscribed statusbar with a timeout.

    Parameters
    ----------
    args        :   tuple(str)
        See logMessage...
    timeout     :   int
        How long the message is displayed. If set 0, the message is persistent.
    kwargs      :   dict
        See logMessage...
    Returns
    -------

    """
    s = " ".join(args)
    if statusbar is not None:
        statusbar.showMessage(s, timeout * 1000)

    logMessage(*args, **kwargs)


def logMessage(*args: Any, level: int = INFO, loggername: str = None, timestamp: str = None, suppressreprint: bool = False):
    """
    Logs messages to logging log. Gui widgets can be subscribed to the log with:
        logging.getLogger().addHandler(callable)


    Parameters
    ----------
    args            : tuple[str]
        Similar to python 3's print(), any number of objects that can be cast as str. These are joined and printed as
        one line.
    level           : int
        Logging level; one of msg.DEBUG, msg.INFO, msg.WARNING, msg.ERROR, msg.CRITICAL. Default is INFO
    loggername      : str
        The name of the log to post the message into. Typically left blank, and populated by inspection.
    timestamp       : str
        The message timestamp, typically left blank.
    suppressreprint : bool
        Allows suppressing output to stdout.

    """

    # Join the args to a string
    s = " ".join(map(str, args))

    # ATTENTION: loggername is 'intelligently' determined with inspect. You probably want to leave it None.
    if not loggername:
        loggername = inspect.stack()[1][3]
    logger = logging.getLogger(loggername)
    logger.setLevel(DEBUG)

    # Set the logging level
    try:
        stdch.setLevel(level)
    except ValueError:
        level = logging.CRITICAL
        logger.log("Unrecognized logger level for following message...", level)
    logger.addHandler(stdch)

    # Make timestamp
    if timestamp is None:
        timestamp = time.asctime()

    # Lookup levelname from level
    levelname = levels[level]

    if threading.current_thread() is threading.main_thread():
        thread = "M"
    else:
        thread = str(threadIds[threading.get_ident()])

    # LOG IT!
    logger.log(level, f"{timestamp} - {loggername} - {levelname} - {thread} - {s}")

    # Also, print message to stdout
    # try:
    #     if not suppressreprint: print(f'{timestamp} - {loggername} - {levelname} - {s}')
    # except UnicodeEncodeError:
    #     print('A unicode string could not be written to console. Some logging will not be displayed.')


def clearMessage():
    """
    Clear messages from the statusbar
    """
    statusbar.clearMessage()


def logError(exception: Exception, value=None, tb=None, **kwargs):
    """
    Logs an exception with traceback. All uncaught exceptions get hooked here

    """

    if not value:
        value = exception
    if not tb:
        tb = exception.__traceback__
    kwargs["level"] = ERROR
    if 'loggername' not in kwargs:
        kwargs['loggername'] = inspect.stack()[1][3]
    logMessage("\n", "The following error was handled safely by Xi-cam. It is displayed here for debugging.", **kwargs)
    try:
        logMessage("\n", *traceback.format_exception(exception, value, tb), **kwargs)
    except AttributeError:
        logMessage("\n", *traceback.format_exception_only(exception, value), **kwargs)


import sys

sys._excepthook = sys.excepthook = logError

try:
    faulthandler.enable()
except RuntimeError:
    faulthandler.enable(file=open(os.path.join(paths.user_cache_dir, "logs", "crash_log.log"), 'w'))

# The above enables printing tracebacks during hard crashes. To see it in action, try the following lines
# import ctypes
# ctypes.string_at(0)
