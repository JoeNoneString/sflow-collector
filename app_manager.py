import inspect
import itertools
import logging
import sys
import os
import gc

import utils

#from oslo.config import cfg
from oslo_config import cfg

LOG = logging.getLogger('ryu.base.app_manager')

SERVICE_BRICKS = {}

def unregister_app(app):
    SERVICE_BRICKS.pop(app.name)


class RyuApp(object):

    def __init__(self, *_args, **_kwargs):
        super(RyuApp, self).__init__()
        self.name = self.__class__.__name__
        self.event_handlers = {}        # ev_cls -> handlers:list
        self.observers = {}     # ev_cls -> observer-name -> states:set
        self.threads = []
        self.events = utils.Queue(128)
        if hasattr(self.__class__, 'LOGGER_NAME'):
            self.logger = logging.getLogger(self.__class__.LOGGER_NAME)
        else:
            self.logger = logging.getLogger(self.name)
        self.CONF = cfg.CONF

        self.is_active = True

    def start(self):
        self.threads.append(utils.spawn(self._event_loop))

    def stop(self):
        self.is_active = False
        self._send_event(self._event_stop, None)
        utils.joinall(self.threads)


    def get_handlers(self, ev, state=None):
        ev_cls = ev.__class__
        handlers = self.event_handlers.get(ev_cls, [])
        if state is None:
            return handlers

        def test(h):
            if not hasattr(h, 'callers') or ev_cls not in h.callers:
                # dynamically registered handlers does not have
                # h.callers element for the event.
                return True
            states = h.callers[ev_cls].dispatchers
            if not states:
                # empty states means all states
                return True
            return state in states

        return filter(test, handlers)

    def _event_loop(self):
        while self.is_active or not self.events.empty():
            ev, state = self.events.get()
            if ev == self._event_stop:
                continue
            handlers = self.get_handlers(ev, state)
            for handler in handlers:
                handler(ev)

    def _send_event(self, ev, state):
        self.events.put((ev, state))

    def close(self):
        pass


class AppManager(object):
    # singletone
    _instance = None

    @staticmethod
    def get_instance():
        if not AppManager._instance:
            AppManager._instance = AppManager()
        return AppManager._instance

    def __init__(self):
        self.applications_cls = {}
        self.applications = {}
        self.contexts_cls = {}
        self.contexts = {}

    def load_app(self, name):
        mod = utils.import_module(name)
        clses = inspect.getmembers(mod,
                                   lambda cls: (inspect.isclass(cls) and
                                                issubclass(cls, RyuApp) and
                                                mod.__name__ ==
                                                cls.__module__))
        if clses:
            return clses[0][1]
        return None

    def load_apps(self, app_lists):
        app_lists = [app for app
                     in itertools.chain.from_iterable(app.split(',')
                                                      for app in app_lists)]
        while len(app_lists) > 0:
            app_cls_name = app_lists.pop(0)

            context_modules = map(lambda x: x.__module__,
                                  self.contexts_cls.values())
            if app_cls_name in context_modules:
                continue

            LOG.info('loading app %s', app_cls_name)

            cls = self.load_app(app_cls_name)
            if cls is None:
                continue

            self.applications_cls[app_cls_name] = cls

    def _instantiate(self, app_name, cls, *args, **kwargs):
        LOG.info('instantiating app %s of %s', app_name, cls.__name__)

        if app_name is not None:
            assert app_name not in self.applications
        app = cls(*args, **kwargs)
        assert app.name not in self.applications
        self.applications[app.name] = app
        return app

    def instantiate_apps(self, *args, **kwargs):
        for app_name, cls in self.applications_cls.items():
            self._instantiate(app_name, cls, *args, **kwargs)

        threads = []
        for app in self.applications.values():
            t = app.start()
            if t is not None:
                threads.append(t)
        return threads

    def uninstantiate(self, name):
        app = self.applications.pop(name)
        unregister_app(app)
        for app_ in SERVICE_BRICKS.values():
            app_.unregister_observer_all_event(name)
        app.stop()
        self._close(app)
        events = app.events
        if not events.empty():
            app.logger.debug('%s events remians %d', app.name, events.qsize())

    @staticmethod
    def _close(app):
        close_method = getattr(app, 'close', None)
        if callable(close_method):
            close_method()

    def close(self):
        def close_all(close_dict):
            for app in close_dict.values():
                self._close(app)
            close_dict.clear()

        for app_name in list(self.applications.keys()):
            self.uninstantiate(app_name)
        assert not self.applications
        close_all(self.contexts)
