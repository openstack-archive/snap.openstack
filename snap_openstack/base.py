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

DEFAULT_OWNER = "root:root"
DEFAULT_DIR_MODE = 0o750
DEFAULT_FILE_MODE = 0o640


def _render_templates(templates, snap_env, file_mode, user, group):
    '''Render file templates using snap environment variables

    Render provided dictionary of templates using snap_env,
    ensuring that the rendered files have the required ownership
    and permissions.

    @templates: dict of key value pairs mapping template -> target
    @snap_env: dict of environment variables to use for rendering
    @file_mode: mode to create any files (provided as hex)
    @user: user ownership for files
    @group: group ownership for files
    '''

    renderer = SnapFileRenderer()
    utils = SnapUtils()

    for template in templates:
        target = templates[template]
        target_file = target.format(**snap_env)
        utils.ensure_dir(target_file, is_file=True)
        LOG.debug('Rendering {} to {}'.format(template,
                                              target_file))
        with open(target_file, 'w') as tf:
            tf.write(renderer.render(template, snap_env))
        utils.chmod(target_file, file_mode)
        utils.chown(target_file, user, group)


def _get_os_config_files(entry_point, key_name):
    '''Get OpenStack config files from dictionary and convert to CLI format

    If a config file path doesn't exist on disk, it won't be added to the
    options array.

    @entry_point: entry_point dictionary
    @key_name: key name (either config-files or config-files-override)
    @return options: array of CLI '--config-file' options
    '''
    utils = SnapUtils()
    options = []

    for cfile in entry_point.get(key_name, []):
        cfile = cfile.format(**utils.snap_env)
        if os.path.exists(cfile):
            options.append('--config-file={}'.format(cfile))
        else:
            LOG.debug('Configuration file {} not found'
                      ', skipping'.format(cfile))
    return options


def _get_os_config_dirs(entry_point, key_name):
    '''Get OpenStack config dirs from dictionary and convert to CLI format

    If a config file path doesn't exist on disk, it won't be added to the
    options array.

    @entry_point: entry_point dictionary
    @key_name: key name (either config-dirs or config-dirs-override)
    @return options: array of CLI '--config-file' options
    '''
    utils = SnapUtils()
    options = []

    for cdir in entry_point.get(key_name, []):
        cdir = cdir.format(**utils.snap_env)
        if os.path.exists(cdir):
            options.append('--config-dir={}'.format(cdir))
        else:
            LOG.debug('Configuration directory {} not found'
                      ', skipping'.format(cdir))
    return options


def _get_os_log_file(entry_point):
    '''Get OpenStack log file from dictionary and convert to CLI format

    @entry_point: entry_point dictionary
    @return options: string containing CLI '--log-file' option
    '''
    utils = SnapUtils()
    option = None

    log_file = entry_point.get('log-file', [])
    if log_file:
        log_file = log_file.format(**utils.snap_env)
        option = '--log-file={}'.format(log_file)
    return option


class OpenStackSnap(object):
    '''Main executor class for snap-openstack'''

    def __init__(self, config_file):
        with open(config_file, 'r') as config:
            self.configuration = yaml.load(config)

    def setup(self):
        '''Perform any pre-execution snap setup

        Run this method prior to use of the execute method.
        '''
        utils = SnapUtils()
        setup = self.configuration['setup']
        LOG.debug(setup)
        lock_file = "{snap_data}/snap-openstack".format(**utils.snap_env)

        with lockutils.lock('setup.lock', external=True,
                            lock_path=lock_file):
            if 'users' in setup.keys():
                for user, groups in setup['users'].items():
                    home = os.path.join(
                        "{snap_common}".format(**utils.snap_env),
                        "lib", user
                    )
                    utils.add_user(user, groups, home)

            default_owner = setup.get('default-owner', DEFAULT_OWNER)
            default_user, default_group = default_owner.split(':')
            default_dir_mode = setup.get('default-dir-mode',
                                         DEFAULT_DIR_MODE)
            default_file_mode = setup.get('default-file-mode',
                                          DEFAULT_FILE_MODE)

            for directory in setup.get('dirs', []):
                dir_name = directory.format(**utils.snap_env)
                utils.ensure_dir(dir_name, perms=default_dir_mode)
                utils.rchmod(dir_name, default_dir_mode, default_file_mode)
                utils.rchown(dir_name, default_user, default_group)

            if 'copyfiles' in setup.keys():
                for source, target in setup['copyfiles'].items():
                    source_dir = source.format(**utils.snap_env)
                    dest_dir = target.format(**utils.snap_env)
                    for source_name in os.listdir(source_dir):
                        s_file = os.path.join(source_dir, source_name)
                        d_file = os.path.join(dest_dir, source_name)
                        if not os.path.isfile(s_file):
                            continue
                        LOG.debug('Copying file {} to {}'.format(s_file,
                                                                 d_file))
                        shutil.copy2(s_file, d_file)
                        utils.chmod(d_file, default_file_mode)
                        utils.chown(d_file, default_user, default_group)

            _render_templates(setup.get('templates', []), utils.snap_env,
                              default_file_mode, default_user, default_group)

            for target in setup.get('rchown', []):
                target_path = target.format(**utils.snap_env)
                user, group = setup['rchown'][target].split(':')
                utils.rchown(target_path, user, group)

            for target in setup.get('chmod', []):
                target_path = target.format(**utils.snap_env)
                if os.path.exists(target_path):
                    mode = setup['chmod'][target]
                    utils.chmod(target_path, mode)
                else:
                    LOG.debug('Path not found: {}'.format(target_path))

            for target in setup.get('chown', []):
                target_path = target.format(**utils.snap_env)
                if os.path.exists(target_path):
                    user, group = setup['chown'][target].split(':')
                    utils.chown(target_path, user, group)
                else:
                    LOG.debug('Path not found: {}'.format(target_path))

    def execute(self, argv):
        '''Execute snap command building out configuration and log options'''
        utils = SnapUtils()
        setup = self.configuration['setup']

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
            cmd = [entry_point['binary'].format(**utils.snap_env)]

            cfiles = _get_os_config_files(entry_point, 'config-files-override')
            if not cfiles:
                cfiles = _get_os_config_files(entry_point, 'config-files')
            if cfiles:
                cmd.extend(cfiles)

            cdirs = _get_os_config_dirs(entry_point, 'config-dirs')
            if cdirs:
                cmd.extend(cdirs)

            log_file = _get_os_log_file(entry_point)
            if log_file:
                cmd.append(log_file)

            # Ensure any arguments passed to wrapper are propagated
            cmd.extend(other_args)

        elif cmd_type == UWSGI_EP_TYPE:
            cmd = ["{snap}/bin/uwsgi".format(**utils.snap_env)]
            defaults = [d.format(**utils.snap_env) for d in DEFAULT_UWSGI_ARGS]
            cmd.extend(defaults)
            pyargv = []
            uwsgi_override = False

            uwsgi_dir_o = entry_point.get('uwsgi-dir-override')
            if uwsgi_dir_o:
                uwsgi_dir_o = uwsgi_dir_o.format(**utils.snap_env)
                for f in os.listdir(uwsgi_dir_o):
                    # Override is activated if a file exists in override dir
                    if os.path.isfile(os.path.join(uwsgi_dir_o, f)):
                        uwsgi_override = True
                        cmd.append(uwsgi_dir_o)
                        break

            if not uwsgi_override:
                uwsgi_dir = entry_point.get('uwsgi-dir')
                if uwsgi_dir:
                    uwsgi_dir = uwsgi_dir.format(**utils.snap_env)
                    cmd.append(uwsgi_dir)

            uwsgi_log = entry_point.get('uwsgi-log')
            if uwsgi_log:
                uwsgi_log = uwsgi_log.format(**utils.snap_env)
                cmd.extend(['--logto', uwsgi_log])

            cfiles = _get_os_config_files(entry_point, 'config-files-override')
            if not cfiles:
                cfiles = _get_os_config_files(entry_point, 'config-files')
            if cfiles:
                pyargv.extend(cfiles)

            cdirs = _get_os_config_dirs(entry_point, 'config-dirs')
            if cdirs:
                pyargv.extend(cdirs)

            log_file = _get_os_log_file(entry_point)
            if log_file:
                pyargv.append(log_file)

            # NOTE(jamespage): Pass dynamically built pyargv into
            #                  context for template generation.
            snap_env = utils.snap_env
            if pyargv:
                snap_env['pyargv'] = ' '.join(pyargv)
                LOG.debug('Setting pyargv to: {}'.format(' '.join(pyargv)))

            default_owner = setup.get('default-owner', DEFAULT_OWNER)
            default_user, default_group = default_owner.split(':')
            default_file_mode = setup.get('default-file-mode',
                                          DEFAULT_FILE_MODE)

            _render_templates(entry_point.get('templates', []), snap_env,
                              default_file_mode, default_user, default_group)

        elif cmd_type == NGINX_EP_TYPE:
            cmd = ["{snap}/usr/sbin/nginx".format(**utils.snap_env)]
            cmd.extend(DEFAULT_NGINX_ARGS)

            cfile = entry_point.get('config-file-override')
            if cfile:
                cfile = cfile.format(**utils.snap_env)
                if os.path.exists(cfile):
                    cmd.extend(['-c', '{}'.format(cfile)])
                else:
                    cfile = None

            if not cfile:
                cfile = entry_point.get('config-file')
                if cfile:
                    cfile = cfile.format(**utils.snap_env)
                    if os.path.exists(cfile):
                        cmd.extend(['-c', '{}'.format(cfile)])
                    else:
                        LOG.debug('Configuration file {} not found'
                                  ', skipping'.format(cfile))

        if 'run-as' in entry_point.keys():
            user, groups = list(entry_point['run-as'].items())[0]
            utils.drop_privileges(user, groups)

        LOG.debug('Executing command {}'.format(' '.join(cmd)))
        os.execvp(cmd[0], cmd)
