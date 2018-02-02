==============
snap.openstack
==============

Helpers for writing Snaps for OpenStack

This project provides a wrapper for automatically wrapping openstack
commands in snaps, building out appropriate Oslo configuration and
logging options on the command line.

This wrapper is used by including a snap-openstack.yaml configuration file
into the root of a snap.

Setup is executed for all entry points prior to execution snap-openstack
will assure that templated files are in place and that any directory
structure in $SNAP_COMMON is created.

.. code-block:: yaml

    setup:
      dirs:
        - "{snap_common}/etc/nova.conf.d"
        - "{snap_common}/etc/nova"
        - "{snap_common}/logs"
      templates:
        "nova-snap.conf.j2": "{snap_common}/etc/nova.conf.d/nova-snap.conf"

snap-openstack.yaml should also declare entry points for the snap:

.. code-block:: yaml

    entry_points:
      nova-manage:
        binary: nova-manage
        config-files:
          - "{snap}/etc/nova/nova.conf"
          - "{snap_common}/etc/nova/nova.conf"
        config-dirs:
          - "{snap_common}/etc/nova.conf.d"
        log-file: "{snap_common}/logs/nova-manage.log"

Executes the following:

.. code-block:: bash

    nova-manage --config-file=$SNAP/etc/nova/nova,conf \
                --config-file=$SNAP_COMMON/etc/nova/nova.conf \
                --config-dir=$SNAP_COMMON/etc/nova.conf.d \
                --log-file=$SNAP_COMMON/logs/nova-manage.log

entry points are designed to be executed from the snapcraft.yaml apps section
using:

.. code-block:: yaml

    command: snap-openstack nova-manage

any additional arguments provided will be passed to the underlying binary.

* Free software: Apache license
* Source: http://git.openstack.org/cgit/openstack/snap.openstack
* Bugs: http://bugs.launchpad.net/snap.openstack

Features
--------

* Support for classic mode snap use
