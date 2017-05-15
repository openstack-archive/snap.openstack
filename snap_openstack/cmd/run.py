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
import sys

from snap_openstack.base import OpenStackSnap

LOG = logging.getLogger(__name__)

CONFIG_FILE = 'snap-openstack.yaml'


def main():
    logging.basicConfig(level=logging.DEBUG)
    snap = os.environ.get('SNAP')
    if not snap:
        LOG.error('Not executing in snap environment, exiting')
        sys.exit(1)
    config_path = os.path.join(snap,
                               CONFIG_FILE)
    if os.path.exists(config_path):
        LOG.debug('Using snap wrapper: {}'.format(config_path))
        s_openstack = OpenStackSnap(config_path)
        s_openstack.setup()
        s_openstack.execute(sys.argv)
    else:
        LOG.error('Unable to find snap-openstack.yaml configuration file')
        sys.exit(1)
