# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
test_snap_openstack
----------------------------------

Tests for `snap_openstack` module.
"""

import os
import sys

from mock import call
from mock import mock_open
from mock import patch

from snap_openstack import base
from snap_openstack.tests import base as test_base

TEST_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        'data')

MOCK_SNAP_ENV = {
    'snap_common': '/var/snap/keystone/common',
    'snap_data': '/var/snap/keystone/x1',
    'snap': '/snap/keystone/current',
}


class TestOpenStackSnapExecute(test_base.TestCase):

    @classmethod
    def mock_exists(cls, path):
        '''Test helper for os.path.exists'''
        paths = {
            '/snap/keystone/current/etc/keystone/keystone.conf': True,
            '/var/snap/keystone/common/etc/keystone/keystone.conf.d': True,
            '/var/snap/keystone/common/etc/nginx/snap/nginx.conf': True,
            '/var/snap/keystone/common/etc/uwsgi/snap/keystone.ini': True,
        }
        return paths.get(path, False)

    def mock_exists_overrides(cls, path):
        '''Test helper for os.path.exists'''
        paths = {
            '/snap/keystone/current/etc/keystone/keystone.conf': True,
            '/var/snap/keystone/common/etc/keystone/keystone.conf.d': True,
            '/var/snap/keystone/common/etc/keystone/keystone.conf': True,
            '/var/snap/keystone/common/etc/nginx/snap/nginx.conf': True,
            '/var/snap/keystone/common/etc/nginx/nginx.conf': True,
            '/var/snap/keystone/common/etc/uwsgi/snap/keystone.ini': True,
            '/var/snap/keystone/common/etc/uwsgi/keystone.ini': True,
        }
        return paths.get(path, False)

    def mock_snap_utils(self, mock_utils):
        '''Mock SnapUtils code'''
        mock_utils_obj = mock_utils.return_value
        mock_utils_obj.snap_env = MOCK_SNAP_ENV
        return mock_utils_obj

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config(self, mock_os, mock_utils,
                              mock_renderer):
        '''Ensure wrapped binary called with full args list'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        mock_os.path.basename.side_effect = 'keystone.conf'
        snap.execute(['snap-openstack',
                      'keystone-manage'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/bin/keystone-manage',
            ['/snap/keystone/current/bin/keystone-manage',
             '--config-file=/snap/keystone/current/etc/keystone/keystone.conf',
             '--config-dir=/var/snap/keystone/common/etc/keystone/'
             'keystone.conf.d']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_override(self, mock_os, mock_utils,
                                       mock_renderer):
        '''Ensure wrapped binary called with full args list'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists_overrides
        mock_os.path.basename.side_effect = 'keystone.conf'
        snap.execute(['snap-openstack',
                      'keystone-manage'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/bin/keystone-manage',
            ['/snap/keystone/current/bin/keystone-manage',
             '--config-file=/var/snap/keystone/common/etc/keystone/'
             'keystone.conf',
             '--config-dir=/var/snap/keystone/common/etc/keystone/'
             'keystone.conf.d']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_no_logging(self, mock_os, mock_utils,
                                         mock_renderer):
        '''Ensure wrapped binary called correctly with no logfile'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        mock_os.path.basename.side_effect = 'keystone.conf'
        snap.execute(['snap-openstack',
                      'keystone-manage',
                      'db', 'sync'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/bin/keystone-manage',
            ['/snap/keystone/current/bin/keystone-manage',
             '--config-file=/snap/keystone/current/etc/keystone/keystone.conf',
             '--config-dir=/var/snap/keystone/common/etc/keystone/'
             'keystone.conf.d',
             'db', 'sync']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_missing_entry_point(self, mock_os, mock_utils,
                                                  mock_renderer):
        '''Ensure ValueError raised for missing entry_point'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        self.assertRaises(ValueError,
                          snap.execute,
                          ['snap-openstack',
                           'keystone-api'])

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_uwsgi(self, mock_os, mock_utils,
                                    mock_renderer):
        '''Ensure wrapped binary of uwsgi called with correct arguments'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        mock_os.path.basename.side_effect = 'keystone.conf'
        builtin = '__builtin__'
        if sys.version_info > (3, 0):
            builtin = 'builtins'
        with patch('{}.open'.format(builtin), mock_open(), create=True):
            snap.execute(['snap-openstack',
                          'keystone-uwsgi'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/bin/uwsgi',
            ['/snap/keystone/current/bin/uwsgi', '--master',
             '--die-on-term', '-H', '/snap/keystone/current/usr',
             '--emperor', '/var/snap/keystone/common/etc/uwsgi/snap',
             '--logto', '/var/snap/keystone/common/log/uwsgi.log']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_uwsgi_override(self, mock_os, mock_utils,
                                             mock_renderer):
        '''Ensure wrapped binary of uwsgi called with correct arguments'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists_overrides
        mock_os.path.basename.side_effect = 'keystone.conf'
        mock_os.listdir.side_effect = (
            '/var/snap/keystone/common/etc/uwsgi/config.ini'
        )
        builtin = '__builtin__'
        if sys.version_info > (3, 0):
            builtin = 'builtins'
        with patch('{}.open'.format(builtin), mock_open(), create=True):
            snap.execute(['snap-openstack',
                          'keystone-uwsgi'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/bin/uwsgi',
            ['/snap/keystone/current/bin/uwsgi', '--master',
             '--die-on-term', '-H', '/snap/keystone/current/usr',
             '--emperor', '/var/snap/keystone/common/etc/uwsgi',
             '--logto', '/var/snap/keystone/common/log/uwsgi.log']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_nginx(self, mock_os, mock_utils,
                                    mock_renderer):
        '''Ensure wrapped binary of nginx called with correct arguments'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        snap.execute(['snap-openstack',
                      'keystone-nginx'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/usr/sbin/nginx',
            ['/snap/keystone/current/usr/sbin/nginx', '-g',
             'daemon on; master_process on;',
             '-c', '/var/snap/keystone/common/etc/nginx/snap/nginx.conf']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_nginx_override(self, mock_os, mock_utils,
                                             mock_renderer):
        '''Ensure wrapped binary of nginx called with correct arguments'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists_overrides
        snap.execute(['snap-openstack',
                      'keystone-nginx'])
        mock_os.execvp.assert_called_with(
            '/snap/keystone/current/usr/sbin/nginx',
            ['/snap/keystone/current/usr/sbin/nginx', '-g',
             'daemon on; master_process on;',
             '-c', '/var/snap/keystone/common/etc/nginx/nginx.conf']
        )

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_invalid_ep_type(self, mock_os, mock_utils,
                                              mock_renderer):
        '''Ensure endpoint types are correctly validated'''
        self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        self.assertRaises(ValueError,
                          snap.execute,
                          ['snap-openstack',
                           'keystone-broken'])


class TestOpenStackSnapSetup(test_base.TestCase):

    def mock_snap_utils(self, mock_utils):
        '''Mock SnapUtils code'''
        mock_utils_obj = mock_utils.return_value
        mock_utils_obj.snap_env = MOCK_SNAP_ENV
        mock_utils_obj.ensure_dir.return_value = None
        mock_utils_obj.chmod.return_value = None
        mock_utils_obj.chown.return_value = None
        return mock_utils_obj

    @patch.object(base, 'SnapFileRenderer')
    @patch('snap_openstack.base.SnapUtils')
    @patch('oslo_concurrency.lockutils.lock')
    @patch.object(base, 'os')
    def test_base_setup(self, mock_os, mock_lock, mock_utils, mock_renderer):
        '''Ensure setup method handles snap-openstack.yaml keys/values'''
        mock_utils_obj = self.mock_snap_utils(mock_utils)
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        builtin = '__builtin__'
        if sys.version_info > (3, 0):
            builtin = 'builtins'
        with patch('{}.open'.format(builtin), mock_open(), create=True):
            snap.setup()
        mock_lock.assert_called_once_with(
            'setup.lock', external=True,
            lock_path='/var/snap/keystone/x1/snap-openstack')
        mock_utils_obj.chmod.assert_called_with(
            '/var/snap/keystone/common/lib', 0o755)
        mock_utils_obj.chown.assert_called_with(
            '/var/snap/keystone/common/lib', 'root', 'root')
        expected = [
            call('/var/snap/keystone/common/etc/keystone/keystone.conf.d',
                 perms=488),
            call('/var/snap/keystone/common/etc/nginx/sites-enabled',
                 perms=488),
            call('/var/snap/keystone/common/etc/nginx/snap/sites-enabled',
                 perms=488),
            call('/var/snap/keystone/common/etc/uwsgi/snap',
                 perms=488),
            call('/var/snap/keystone/common/etc/keystone/keystone.conf.d/'
                 'keystone-snap.conf',
                 is_file=True),
            call('/var/snap/keystone/common/etc/nginx/snap/sites-enabled/'
                 'keystone.conf',
                 is_file=True),
            call('/var/snap/keystone/common/etc/nginx/snap/nginx.conf',
                 is_file=True)
        ]
        mock_utils_obj.ensure_dir.assert_has_calls(expected, any_order=True)
