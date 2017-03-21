#!/usr/bin/env python

# Copyright 2017 Canonical UK Limited
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

import contextlib
import errno
import fcntl
import logging
import time

LOG = logging.getLogger(__name__)


@contextlib.contextmanager
def locked():
    '''Execute code within the context of a file lock

    Ensures that only one OpenStack snap process can execute code.

    This is a factory function that is used in a with statement, where the
    block of code nested under the with statement is executed within the
    context of the file lock.
    '''
    lock_file = '/var/lock/snap-openstack.lock'

    with open(lock_file, 'w') as f:
        timeout = 60
        for i in range(timeout * 10):
            try:
                fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError as exception:
                if exception.errno != errno.EWOULDBLOCK:
                    raise
            time.sleep(0.1)
        else:
            _msg = 'Lock attempt of file {} timed out.'.format(lock_file)
            LOG.error(_msg)
            raise IOError(_msg)

        LOG.info('Lock file {} locked. Begin execution.'.format(lock_file))
        yield
        LOG.info('Lock file {} unlocked. End execution.'.format(lock_file))
