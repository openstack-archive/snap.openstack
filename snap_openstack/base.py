#!/usr/bin/env python

# Copyright 2016 Canonical UK Limited
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging
import os
import shutil
import yaml

from oslo_concurrency import lockutils

from snap_openstack.renderer import SnapFileRenderer
from snap_openstack.utils import SnapUtils

LOG = logging.getLogger(__name__)


DEFAULT_EP_TYPE = 'simple'
UWSGI_EP_TYPE = 'uwsgi'
NGINX_EP_TYPE = 'nginx'

VALID_EP_TYPES = (DEFAULT_EP_TYPE, UWSGI_EP_TYPE, NGINX_EP_TYPE)

DEFAULT_UWSGI_ARGS = ["--master",
                      "--die-on-term",
                      "-H", "{snap}/usr",
                      "--emperor"]

DEFAULT_NGINX_ARGS = ["-g",
                      "daemon on; master_process on;"]


class OpenStackSnap(object):
    '''Main executor class for snap-openstack'''

    def __init__(self, config_file):
        with open(config_file, 'r') as config:
            self.configuration = yaml.load(config)

    @lockutils.synchronized('setup.lock', external=True,
                            lock_path="/var/lock/snap-openstack")
    def setup(self):
        '''Perform any pre-execution snap setup

        Run this method prior to use of the execute method.
        '''
        setup = self.configuration['setup']
        renderer = SnapFileRenderer()
        utils = SnapUtils()
        LOG.debug(setup)

        default_user = "root"
        default_group = "root"
        default_dir_mode = 0750
        default_file_mode = 0640

        if 'users' in setup.keys():
            for user, groups in setup['users'].items():
                home = os.path.join("{snap_common}".format(**utils.snap_env),
                                    "lib", user)
                utils.add_user(user, groups, home)

        if 'default_owner' in setup.keys():
            default_user = setup['default_owner'].split(':')[0]
            default_group = setup['default_owner'].split(':')[1]

        if 'default_dir_mode' in setup.keys():
            default_dir_mode = setup['default_dir_mode']

        if 'default_file_mode' in setup.keys():
            default_file_mode = setup['default_file_mode']

        if 'dirs' in setup.keys():
            for directory in setup['dirs']:
                dir_name = directory.format(**utils.snap_env)
                utils.ensure_dir(dir_name)
                utils.rchmod(dir_name, default_dir_mode, default_file_mode)
                utils.rchown(dir_name, default_user, default_group)

        if 'templates' in setup.keys():
            for template in setup['templates']:
                target = setup['templates'][template]
                target_file = target.format(**utils.snap_env)
                utils.ensure_dir(target_file, is_file=True)
                if not os.path.isfile(target_file):
                    LOG.debug('Rendering {} to {}'.format(template,
                                                          target_file))
                    with open(target_file, 'w') as tf:
                        tf.write(renderer.render(template, utils.snap_env))
                    utils.chmod(target_file, default_file_mode)
                    utils.chown(target_file, default_user, default_group)

        if 'copyfiles' in setup.keys():
            for source, target in setup['copyfiles'].items():
                source_dir = source.format(**utils.snap_env)
                dest_dir = target.format(**utils.snap_env)
                for source_name in os.listdir(source_dir):
                    s_file = os.path.join(source_dir, source_name)
                    d_file = os.path.join(dest_dir, source_name)
                    if not os.path.isfile(s_file) or os.path.exists(d_file):
                        continue
                    LOG.debug('Copying file {} to {}'.format(s_file, d_file))
                    shutil.copy2(s_file, d_file)
                    utils.chmod(d_file, default_file_mode)
                    utils.chown(d_file, default_user, default_group)

        if 'rchown' in setup.keys():
            for target in setup['rchown']:
                target_path = target.format(**utils.snap_env)
                user = setup['rchown'][target].split(':')[0]
                group = setup['rchown'][target].split(':')[1]
                utils.rchown(target_path, user, group)

        if 'chmod' in setup.keys():
            for target in setup['chmod']:
                target_path = target.format(**utils.snap_env)
                if os.path.exists(target_path):
                    mode = setup['chmod'][target]
                    utils.chmod(target_path, mode)
                else:
                    LOG.debug('Path not found: {}'.format(target_path))

        if 'chown' in setup.keys():
            for target in setup['chown']:
                target_path = target.format(**utils.snap_env)
                if os.path.exists(target_path):
                    user = setup['chown'][target].split(':')[0]
                    group = setup['chown'][target].split(':')[1]
                    utils.chown(target_path, user, group)
                else:
                    LOG.debug('Path not found: {}'.format(target_path))

    def execute(self, argv):
        '''Execute snap command building out configuration and log options'''
        utils = SnapUtils()

        entry_point = self.configuration['entry_points'].get(argv[1])
        if not entry_point:
            _msg = 'Unable to find entry point for {}'.format(argv[1])
            LOG.error(_msg)
            raise ValueError(_msg)

        if 'run-as' in entry_point.keys():
            user, groups = list(entry_point['run-as'].items())[0]

        other_args = argv[2:]
        LOG.debug(entry_point)

        # Build out command to run
        cmd_type = entry_point.get('type', DEFAULT_EP_TYPE)

        if cmd_type not in VALID_EP_TYPES:
            _msg = 'Invalid entry point type: {}'.format(cmd_type)
            LOG.error(_msg)
            raise ValueError(_msg)

        if cmd_type == DEFAULT_EP_TYPE:
            cmd = [entry_point['binary'].format(**utils.snap_env)]
            for cfile in entry_point.get('config-files', []):
                cfile = cfile.format(**utils.snap_env)
                if os.path.exists(cfile):
                    cmd.append('--config-file={}'.format(cfile))
                else:
                    LOG.debug('Configuration file {} not found'
                              ', skipping'.format(cfile))

            for cdir in entry_point.get('config-dirs', []):
                cdir = cdir.format(**utils.snap_env)
                if os.path.exists(cdir):
                    cmd.append('--config-dir={}'.format(cdir))
                else:
                    LOG.debug('Configuration directory {} not found'
                              ', skipping'.format(cdir))

            log_file = entry_point.get('log-file')
            if log_file:
                log_file = log_file.format(**utils.snap_env)
                cmd.append('--log-file={}'.format(log_file))

            # Ensure any arguments passed to wrapper are propagated
            cmd.extend(other_args)

        elif cmd_type == UWSGI_EP_TYPE:
            cmd = ["{snap}/bin/uwsgi".format(**utils.snap_env)]
            defaults = [d.format(**utils.snap_env) for d in DEFAULT_UWSGI_ARGS]
            cmd.extend(defaults)

            uwsgi_dir = entry_point.get('uwsgi-dir')
            if uwsgi_dir:
                uwsgi_dir = uwsgi_dir.format(**utils.snap_env)
                cmd.append(uwsgi_dir)

            log_file = entry_point.get('log-file')
            if log_file:
                log_file = log_file.format(**utils.snap_env)
                cmd.extend(['--logto', log_file])

        elif cmd_type == NGINX_EP_TYPE:
            cmd = ["{snap}/usr/sbin/nginx".format(**utils.snap_env)]
            cmd.extend(DEFAULT_NGINX_ARGS)

            cfile = entry_point.get('config-file')
            if cfile:
                cfile = cfile.format(**utils.snap_env)
                if os.path.exists(cfile):
                    cmd.extend(['-c', '{}'.format(cfile)])
                else:
                    LOG.debug('Configuration file {} not found'
                              ', skipping'.format(cfile))

        if 'run-as' in entry_point.keys():
            utils.drop_privileges(user, groups)

        LOG.debug('Executing command {}'.format(' '.join(cmd)))
        os.execvp(cmd[0], cmd)
