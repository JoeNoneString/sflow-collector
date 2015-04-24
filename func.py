#!/usr/bin/env python

# NOTE: this modifies sys.path and thus affects the following imports.
# eg. oslo.config.cfg.

import utils
utils.patch(thread=False)

import sys
import logging

#from oslo.config import cfg
from oslo_config import cfg
from app_manager import AppManager

CONF = cfg.CONF
CONF.register_cli_opts([
    cfg.ListOpt('app-lists', default=[],
                help='application module name to run'),
    cfg.MultiStrOpt('app', positional=True, default=[],
                    help='application module name to run'),
])


def main(args=None, prog=None):
    try:
        CONF(args=args, prog=prog,
             project='func', version='func %s' % '2.2.2',
             default_config_files=['/etc/func.conf'])
    except cfg.ConfigFilesNotFoundError:
        CONF(args=args, prog=prog,
             project='func', version='func %s' % '2.2.2')

    app_lists = CONF.app_lists + CONF.app
    # app_lists = ['manager.py']
    print app_lists


    app_mgr = AppManager.get_instance()
    app_mgr.load_apps(app_lists)
    #contexts = app_mgr.create_contexts()
    services = []
    services.extend(app_mgr.instantiate_apps())

    try:
        utils.joinall(services)
    finally:
        app_mgr.close()


if __name__ == "__main__":
    main()

