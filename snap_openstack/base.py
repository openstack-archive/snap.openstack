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

import os
import subprocess
import yaml
import logging

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


def snap_env():
    '''Grab SNAP* environment variables

    @return dict of all SNAP* environment variables indexed in lower case
    '''
    _env = {}
    for key in SNAP_ENV:
        _env[key.lower()] = os.environ.get(key)
    return _env


def ensure_dir(filepath):
    '''Ensure that the directory structure to support a give file path exists'''
    dir_name = os.path.dirname(filepath)
    if not os.path.exists(dir_name):
        LOG.info('Creating directory {}'.format(dir_name))
        os.makedirs(dir_name, 0o750)


class OpenStackSnap():
    '''Main executor class for snap-openstack'''

    def __init__(self, config_file):
        with open(config_file, 'r') as config:
            self.configuration = yaml.load(config)
        self.snap_env = snap_env()

    def setup(self):
        '''Perform any pre-execution snap setup

        Run this method prior to use of the execute metho
        '''
        setup = self.configuration['setup']
        renderer = SnapFileRenderer()
        LOG.info(setup)

        for dir in setup['dirs']:
            LOG.info('Ensuring directory {} exists'.format(dir))
            dir_name = dir.format(**self.snap_env)
            ensure_dir(dir_name)

        for template in setup['templates']:
            target = setup['templates'][template]
            target_file = target.format(**self.snap_env)
            ensure_dir(target_file)
            LOG.info('Rendering {} to {}'.format(template,
                                                 target_file))
            with open(target_file, 'w') as tf:
                os.fchmod(tf.fileno(), 0o640)
                tf.write(renderer.render(template,
                                         self.snap_env))

    def execute(self, argv):
        '''Execute snap command building out configuration and log options'''
        entry_point = self.configuration['entry_points'].get(argv[1])
        if not entry_point:
            _msg = 'Enable to find entry point for {}'.format(argv[1])
            LOG.error(_msg)
            raise ValueError(_msg)

        other_args = argv[:2]
        LOG.info(entry_point)
        # Build out command to run
        cmd = [entry_point['binary']]

        for cfile in entry_point.get('config-files', []):
            cfile = cfile.format(**self.snap_env)
            if os.path.exists(cfile):
                cmd.append('--config-file={}'.format(cfile))
            else:
                LOG.warning('Configuration file {} not found'
                            ', skipping'.format(cfile))

        for cdir in entry_point.get('config-dirs', []):
            cdir = cdir.format(**self.snap_env)
            if os.path.exists(cdir):
                cmd.append('--config-dir={}'.format(cdir))
            else:
                LOG.warning('Configuration directory {} not found'
                            ', skipping'.format(cdir))

        log_file = entry_point.get('log-file')
        if log_file:
            log_file = log_file.format(**self.snap_env)
            cmd.append('--log-file={}'.format(log_file))

        # Ensure any arguments passed to wrapper are propagated
        cmd.extend(other_args)
        subprocess.check_call(cmd)
