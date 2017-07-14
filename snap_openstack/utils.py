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

import grp
import logging
import os
import pwd
import subprocess

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


class SnapUtils(object):
    '''Class for common utilities'''

    def __init__(self):
        self._snap_env = self._collect_snap_env()

    def _collect_snap_env(self):
        '''Collect SNAP* environment variables

        @return dict of all SNAP* environment variables indexed in lower case
        '''
        _env = {}
        for key in SNAP_ENV:
            _env[key.lower()] = os.environ.get(key)
        LOG.info('Snap environment: {}'.format(_env))
        return _env

    @property
    def snap_env(self):
        '''Return SNAP* environment variables

        @return dict of all SNAP* environment variables indexed in lower case
        '''
        return self._snap_env

    def ensure_dir(self, path, is_file=False, perms=0o750):
        '''Ensure a directory exists

        Ensure that the directory structure to support the provided file or
        directory exists.

        @param path: string containing full path to file or directory
        @param is_file: true if directory name needs to be determined for file
        '''
        dir_name = path
        if is_file:
            dir_name = os.path.dirname(path)
        if not os.path.exists(dir_name):
            LOG.info('Creating directory {}'.format(dir_name))
            os.makedirs(dir_name, perms)

    def chown(self, path, user, group):
        '''Change the owner of the specified file'''
        LOG.debug('Changing owner of {} to {}:{}'.format(path, user, group))
        uid = pwd.getpwnam(user).pw_uid
        gid = grp.getgrnam(group).gr_gid
        os.chown(path, uid, gid)

    def chmod(self, path, mode):
        '''Change the file mode bits of the specified file'''
        LOG.debug('Changing file mode of {} to {}'.format(path, oct(mode)))
        os.chmod(path, mode)
