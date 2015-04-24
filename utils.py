import os
import sys
import socket
import eventlet
import greenlet
import traceback


patch = eventlet.monkey_patch
Queue = eventlet.queue.Queue

def spawn(*args, **kwargs):
    def _launch(func, *args, **kwargs):
        # mimic gevent's default raise_error=False behaviour
        # by not propergating an exception to the joiner.
        try:
            func(*args, **kwargs)
        except greenlet.GreenletExit:
            pass
        except:
            # log uncaught exception.
            # note: this is an intentional divergence from gevent
            # behaviour.  gevent silently ignores such exceptions.
            LOG.error('Uncaught Exception: %s',
                      traceback.format_exc())

    return eventlet.spawn(_launch, *args, **kwargs)


def joinall(threads):
    for t in threads:
        # this try-except is necessary when killing an inactive
        # greenthread
        try:
            t.wait()
        except greenlet.GreenletExit:
            pass


def kill(thread):
    thread.kill()

def chop_py_suffix(p):
    for suf in ['.py', '.pyc', '.pyo']:
        if p.endswith(suf):
            return p[:-len(suf)]
    return p


def _likely_same(a, b):
    try:
        # Samefile not availible on windows
        if sys.platform == 'win32':
            if os.stat(a) == os.stat(b):
                return True
        else:
            if os.path.samefile(a, b):
                return True
    except OSError:
        # m.__file__ is not always accessible.  eg. egg
        return False
    if chop_py_suffix(a) == chop_py_suffix(b):
        return True
    return False


def _find_loaded_module(modpath):
    # copy() to avoid RuntimeError: dictionary changed size during iteration
    for k, m in sys.modules.copy().iteritems():
        if k == '__main__':
            continue
        if not hasattr(m, '__file__'):
            continue
        if _likely_same(m.__file__, modpath):
            return m
    return None

def import_module(modname):
    try:
        __import__(modname)
    except:
        abspath = os.path.abspath(modname)
        mod = _find_loaded_module(abspath)
        if mod:
            return mod
        opath = sys.path
        sys.path.append(os.path.dirname(abspath))
        name = os.path.basename(modname)
        if name.endswith('.py'):
            name = name[:-3]
        __import__(name)
        sys.path = opath
        return sys.modules[name]
    return sys.modules[modname]

