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

VALID_EP_TYPES = (DEFAULT_EP_TYPE, UWSGI_EP_TYPE)

DEFAULT_UWSGI_ARGS = ["--master",
                      "--die-on-term",
                      "--emperor"]


class OpenStackSnap(object):
    '''Main executor class for snap-openstack'''

    def __init__(self, config_file):
        with open(config_file, 'r') as config:
            self.configuration = yaml.load(config)

    def _setup_single(self, setup):
        '''Perform pre-execution snap setup for a single setup dictionary

        This method gets executed for each setup_* key in snap-openstack.yaml.
        There can be multiple such keys, each defining setup that is specific
        to a single user and service.
        '''
        renderer = SnapFileRenderer()
        utils = SnapUtils()
        LOG.debug(setup)

        if not setup['user'] or not setup['group']:
            _msg = 'A user and group are required in order to drop privileges'
            LOG.error(_msg)
            raise ValueError(_msg)

        user = setup['user']
        group = setup['group']
        utils.add_user(user, group)

        root = 'root'
        default_dir_mode = 0o750
        default_file_mode = 0o640

        if 'dirs' in setup.keys():
            for directory in setup['dirs']:
                dir_name = directory.format(**utils.snap_env)
                utils.ensure_dir(dir_name)
                utils.rchmod(dir_name, default_dir_mode, default_file_mode)
                utils.rchown(dir_name, root, group)

        if 'symlinks' in setup.keys():
            for link_target in setup['symlinks']:
                link = setup['symlinks'][link_target]
                target = link_target.format(**utils.snap_env)
                if not os.path.exists(link):
                    LOG.debug('Creating symlink {} to {}'.format(link, target))
                    os.symlink(target, link)

        if 'templates' in setup.keys():
            for template in setup['templates']:
                target = setup['templates'][template]
                target_file = target.format(**utils.snap_env)
                utils.ensure_dir(target_file, is_file=True)
                LOG.debug('Rendering {} to {}'.format(template, target_file))
                with open(target_file, 'w') as tf:
                    tf.write(renderer.render(template, utils.snap_env))
                utils.chmod(target_file, default_file_mode)
                utils.chown(target_file, root, group)

        if 'copyfiles' in setup.keys():
            for source in setup['copyfiles']:
                source_dir = source.format(**utils.snap_env)
                dest_dir = setup['copyfiles'][source].format(**utils.snap_env)
                for source_name in os.listdir(source_dir):
                    s_file = os.path.join(source_dir, source_name)
                    d_file = os.path.join(dest_dir, source_name)
                    if not os.path.isfile(s_file) or os.path.exists(d_file):
                        continue
                    LOG.debug('Copying file {} to {}'.format(s_file, d_file))
                    shutil.copy2(s_file, d_file)
                    utils.chmod(d_file, default_file_mode)
                    utils.chown(d_file, root, group)

        if 'chmod' in setup.keys():
            for target in setup['chmod']:
                target_path = target.format(**utils.snap_env)
                mode = setup['chmod'][target]
                utils.chmod(target_path, mode)

        if 'chown' in setup.keys():
            for target in setup['chown']:
                target_path = target.format(**utils.snap_env)
                user = setup['chown'][target].split(':')[0]
                group = setup['chown'][target].split(':')[1]
                utils.chown(target_path, user, group)

        if 'rchown' in setup.keys():
            for target in setup['rchown']:
                target_path = target.format(**utils.snap_env)
                user = setup['rchown'][target].split(':')[0]
                group = setup['rchown'][target].split(':')[1]
                utils.rchown(target_path, user, group)

    @lockutils.synchronized('setup.lock', external=True,
                            lock_path="/var/lock/snap-openstack")
    def setup(self):
        '''Perform all pre-execution snap setup

        Run this method prior to use of the execute method.
        '''
        for key in self.configuration:
            if key.startswith('setup_'):
                self._setup_single(self.configuration[key])

    def execute(self, argv):
        '''Execute snap command building out configuration and log options'''
        utils = SnapUtils()

        entry_point = self.configuration['entry_points'].get(argv[1])
        if not entry_point:
            _msg = 'Unable to find entry point for {}'.format(argv[1])
            LOG.error(_msg)
            raise ValueError(_msg)

        if not entry_point['run-as']:
            _msg = 'A user:group must be specified in order to drop privileges'
            LOG.error(_msg)
            raise ValueError(_msg)
        user = entry_point['run-as'].split(':')[0]
        group = entry_point['run-as'].split(':')[1]

        other_args = argv[2:]
        LOG.debug(entry_point)

        # Build out command to run
        cmd_type = entry_point.get('type', DEFAULT_EP_TYPE)

        if cmd_type not in VALID_EP_TYPES:
            _msg = 'Invalid entry point type: {}'.format(cmd_type)
            LOG.error(_msg)
            raise ValueError(_msg)

        if cmd_type == DEFAULT_EP_TYPE:
            cmd = [entry_point['binary']]
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
            cmd = [UWSGI_EP_TYPE]
            cmd.extend(DEFAULT_UWSGI_ARGS)

            uwsgi_dir = entry_point.get('uwsgi-dir')
            if uwsgi_dir:
                uwsgi_dir = uwsgi_dir.format(**utils.snap_env)
                cmd.append(uwsgi_dir)

            log_file = entry_point.get('log-file')
            if log_file:
                log_file = log_file.format(**utils.snap_env)
                cmd.extend(['--logto', log_file])

        utils.drop_privileges(user, group)

        LOG.debug('Executing command {}'.format(' '.join(cmd)))
        os.execvp(cmd[0], cmd)
