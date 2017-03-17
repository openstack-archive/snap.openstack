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

import errno
import grp
import logging
import os
import pwd
import shutil
import subprocess
import yaml

from snap_openstack.renderer import SnapFileRenderer

LOG = logging.getLogger(__name__)


SNAP_ENV = ['SNAP_NAME',
            'SNAP_VERSION',
            'SNAP_REVISION',
            'SNAP_ARCH',
            'SNAP_LIBRARY_PATH',
            'SNAP',
            'SNAP_DATA',
            'SNAP_COMMON',
            'SNAP_USER_DATA',
            'SNAP_USER_COMMON',
            'TMPDIR']

DEFAULT_EP_TYPE = 'simple'
UWSGI_EP_TYPE = 'uwsgi'

VALID_EP_TYPES = (DEFAULT_EP_TYPE, UWSGI_EP_TYPE)

DEFAULT_UWSGI_ARGS = ["--master",
                      "--die-on-term",
                      "--emperor"]


def snap_env():
    '''Grab SNAP* environment variables

    @return dict of all SNAP* environment variables indexed in lower case
    '''
    _env = {}
    for key in SNAP_ENV:
        _env[key.lower()] = os.environ.get(key)
    return _env


class OpenStackSnap(object):
    '''Main executor class for snap-openstack'''

    def __init__(self, config_file):
        with open(config_file, 'r') as config:
            self.configuration = yaml.load(config)
        self.snap_env = snap_env()

    def _ensure_dir(self, path, is_file=False):
        '''Ensure a directory exists

        Ensure that the directory structure to support the provided file or
        directory exists.

        @param path: string containing full path to file or directory
        @param is_file: true if directory name needs to be determined for file
        '''
        dir_name = path
        if is_file:
            dir_name = os.path.dirname(path)
        LOG.info('Creating directory {}'.format(dir_name))
        try:
            os.makedirs(dir_name, 0o750)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                raise

    def _add_user(self, user, group):
        '''Add user and group to the system'''
        try:
            grp.getgrnam(group)
        except KeyError:
            LOG.debug('Adding group {} to system'.format(group))
            cmd = ['addgroup', '--system', group]
            subprocess.check_call(cmd)

        try:
            pwd.getpwnam(user)
        except KeyError:
            home = os.path.join("{snap_common}/lib/".format(**self.snap_env),
                                user)
            self._ensure_dir(home)
            LOG.debug('Adding user {} to system'.format(user))
            cmd = ['adduser', '--quiet', '--system', '--home', home,
                   '--no-create-home', '--ingroup', group, '--shell',
                   '/bin/false', user]
            subprocess.check_call(cmd)

    def _chown(self, path, user, group):
        '''Change the owner of the specified file'''
        LOG.debug('Changing owner of {} to {}:{}'.format(path, user, group))
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        os.chown(path, uid, gid)

    def _chmod(self, path, mode):
        '''Change the file mode bits of the specified file'''
        LOG.debug('Changing file mode bits of {} to {}'.format(path, mode))
        os.chmod(path, mode)

    def setup(self):
        '''Perform any pre-execution snap setup

        Run this method prior to use of the execute method.
        '''
        setup = self.configuration['setup']
        renderer = SnapFileRenderer()
        LOG.debug(setup)

        if not setup['user']:
            _msg = 'A user must be specified in order to drop privileges'
            LOG.error(_msg)
            raise ValueError(_msg)

        user = setup['user'].split(':')[0]
        group = setup['user'].split(':')[1]
        self._add_user(user, group)

        for directory in setup['dirs']:
            dir_name = directory.format(**self.snap_env)
            self._ensure_dir(dir_name)
            self._chown(dir_name, user, group)

        for link_target in setup['symlinks']:
            link = setup['symlinks'][link_target]
            target = link_target.format(**self.snap_env)
            if not os.path.exists(link):
                LOG.debug('Creating symlink {} to {}'.format(link, target))
                os.symlink(target, link)
            self._chmod(dir_name, 0o750)
            self._chown(link, user, group)

        for template in setup['templates']:
            target = setup['templates'][template]
            target_file = target.format(**self.snap_env)
            self._ensure_dir(target_file, is_file=True)
            LOG.debug('Rendering {} to {}'.format(template, target_file))
            with open(target_file, 'w') as tf:
                tf.write(renderer.render(template, self.snap_env))
            self._chmod(target_file, 0o640)
            self._chown(target_file, user, group)

        for source in setup['copyfiles']:
            source_dir = source.format(**self.snap_env)
            dest_dir = setup['copyfiles'][source].format(**self.snap_env)
            for source_name in os.listdir(source_dir):
                s_file = os.path.join(source_dir, source_name)
                d_file = os.path.join(dest_dir, source_name)
                if not os.path.isfile(s_file) or os.path.exists(d_file):
                    continue
                LOG.debug('Copying file {} to {}'.format(s_file, d_file))
                shutil.copy2(s_file, d_file)
                self._chmod(d_file, 0o640)
                self._chown(d_file, user, group)

        LOG.debug('Switching process to run under user {}'.format(user))
        pw = pwd.getpwnam(user)
        os.setuid(pw.pw_uid)

    def execute(self, argv):
        '''Execute snap command building out configuration and log options'''
        entry_point = self.configuration['entry_points'].get(argv[1])
        if not entry_point:
            _msg = 'Unable to find entry point for {}'.format(argv[1])
            LOG.error(_msg)
            raise ValueError(_msg)

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
                cfile = cfile.format(**self.snap_env)
                if os.path.exists(cfile):
                    cmd.append('--config-file={}'.format(cfile))
                else:
                    LOG.debug('Configuration file {} not found'
                              ', skipping'.format(cfile))

            for cdir in entry_point.get('config-dirs', []):
                cdir = cdir.format(**self.snap_env)
                if os.path.exists(cdir):
                    cmd.append('--config-dir={}'.format(cdir))
                else:
                    LOG.debug('Configuration directory {} not found'
                              ', skipping'.format(cdir))

            log_file = entry_point.get('log-file')
            if log_file:
                log_file = log_file.format(**self.snap_env)
                cmd.append('--log-file={}'.format(log_file))

            # Ensure any arguments passed to wrapper are propagated
            cmd.extend(other_args)

        elif cmd_type == UWSGI_EP_TYPE:
            cmd = [UWSGI_EP_TYPE]
            cmd.extend(DEFAULT_UWSGI_ARGS)

            uwsgi_dir = entry_point.get('uwsgi-dir')
            if uwsgi_dir:
                uwsgi_dir = uwsgi_dir.format(**self.snap_env)
                cmd.append(uwsgi_dir)

            log_file = entry_point.get('log-file')
            if log_file:
                log_file = log_file.format(**self.snap_env)
                cmd.extend(['--logto', log_file])

        LOG.debug('Executing command {}'.format(' '.join(cmd)))
        os.execvp(cmd[0], cmd)
