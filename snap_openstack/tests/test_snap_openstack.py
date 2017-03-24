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

from mock import patch

from snap_openstack import base
from snap_openstack.tests import base as test_base

TEST_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                        'data')

MOCK_SNAP_ENV = {
    'snap_common': '/var/snap/test/common',
    'snap': '/snap/common',
}


class TestOpenStackSnapExecute(test_base.TestCase):

    @classmethod
    def mock_exists(cls, path):
        '''Test helper for os.path.exists'''
        paths = {
            '/etc/nova/nova.conf': True,
            '/etc/nova/conf.d': True,
        }
        return paths.get(path, False)

    @patch('snap_openstack.utils.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config(self, mock_os, mock_snap_utils):
        '''Ensure wrapped binary called with full args list'''
        mock_snap_utils.snap_env.return_value = MOCK_SNAP_ENV
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        snap.execute(['snap-openstack',
                      'nova-scheduler'])
        mock_os.execvp.assert_called_with(
            'nova-scheduler',
            ['nova-scheduler',
             '--config-file=/etc/nova/nova.conf',
             '--config-dir=/etc/nova/conf.d',
             '--log-file=/var/log/nova/scheduler.log']
        )

    @patch('snap_openstack.utils.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_no_logging(self, mock_os,
                                         mock_snap_utils):
        '''Ensure wrapped binary called correctly with no logfile'''
        mock_snap_utils.snap_env.return_value = MOCK_SNAP_ENV
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        snap.execute(['snap-openstack',
                      'nova-manage',
                      'db', 'sync'])
        mock_os.execvp.assert_called_with(
            'nova-manage',
            ['nova-manage',
             '--config-file=/etc/nova/nova.conf',
             '--config-dir=/etc/nova/conf.d',
             'db', 'sync']
        )

    @patch('snap_openstack.utils.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_missing_entry_point(self, mock_os,
                                                  mock_snap_utils):
        '''Ensure ValueError raised for missing entry_point'''
        mock_snap_utils.snap_env.return_value = MOCK_SNAP_ENV
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        self.assertRaises(ValueError,
                          snap.execute,
                          ['snap-openstack',
                           'nova-api'])

    @patch('snap_openstack.utils.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_uwsgi(self, mock_os,
                                    mock_snap_utils):
        '''Ensure wrapped binary of uwsgi called with correct arguments'''
        mock_snap_utils.snap_env.return_value = MOCK_SNAP_ENV
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        snap.execute(['snap-openstack',
                      'keystone-api'])
        mock_os.execvp.assert_called_with(
            'uwsgi',
            ['uwsgi', '--master',
             '--die-on-term', '--emperor',
             '/etc/uwsgi',
             '--logto', '/var/log/keystone/keystone.log']
        )

    @patch('snap_openstack.utils.SnapUtils')
    @patch.object(base, 'os')
    def test_base_snap_config_invalid_ep_type(self, mock_os,
                                              mock_snap_utils):
        '''Ensure endpoint types are correctly validated'''
        mock_snap_utils.snap_env.return_value = MOCK_SNAP_ENV
        snap = base.OpenStackSnap(os.path.join(TEST_DIR,
                                               'snap-openstack.yaml'))
        mock_os.path.exists.side_effect = self.mock_exists
        self.assertRaises(ValueError,
                          snap.execute,
                          ['snap-openstack',
                           'nova-broken'])
