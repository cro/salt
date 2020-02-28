# -*- coding: utf-8 -*-
'''
Interface with a Junos device via proxy-minion. To connect to a junos device \
via junos proxy, specify the host information in the pillar in '/srv/pillar/details.sls'

.. code-block:: yaml

    proxy:
      proxytype: junos
      host: <ip or dns name of host>
      username: <username>
      port: 830
      password: <secret>

In '/srv/pillar/top.sls' map the device details with the proxy name.

.. code-block:: yaml

    base:
      'vmx':
        - details

After storing the device information in the pillar, configure the proxy \
in '/etc/salt/proxy'

.. code-block:: yaml

    master: <ip or hostname of salt-master>

Run the salt proxy via the following command:

.. code-block:: bash

    salt-proxy --proxyid=vmx


'''
from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import 3rd-party libs
try:
    HAS_JUNOS = True
    import jnpr.junos
    import jnpr.junos.utils
    import jnpr.junos.utils.config
    import jnpr.junos.utils.sw
    from jnpr.junos.exception import RpcTimeoutError, ConnectClosedError,\
        RpcError, ConnectError, ProbeError, ConnectAuthError,\
        ConnectRefusedError, ConnectTimeoutError
    from ncclient.operations.errors import TimeoutExpiredError
except ImportError:
    HAS_JUNOS = False

__proxyenabled__ = ['junos']

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'junos'


def __virtual__():
    '''
    Only return if all the modules are available
    '''
    if not HAS_JUNOS:
        return False, 'Missing dependency: The junos proxy minion requires the \'jnpr\' Python module.'

    return __virtualname__


def init(opts):
    '''
    Open the connection to the Junos device, login, and bind to the
    Resource class
    '''
    return __utils__['junos.init'](opts)


def initialized():
    return __utils__['junos.initialized']()


def conn():
    return __utils__['junos.conn']()


def alive(opts):
    '''
    Validate and return the connection status with the remote device.

    .. versionadded:: 2018.3.0
    '''
    return __utils__['junos.alive'](opts)


def ping():
    '''
    Ping?  Pong!
    '''
    return __utils__['junos.ping']()


def _rpc_file_list(dev):
    return __utils__['junos.rpc_file_list'](dev)


def proxytype():
    '''
    Returns the name of this proxy
    '''
    return __utils__['junos.proxytype']()


def get_serialized_facts():
    return __utils__['junos.get_serialized_facts']()


def shutdown(opts):
    '''
    This is called when the proxy-minion is exiting to make sure the
    connection to the device is closed cleanly.
    '''
    return __utils__['junos.shutdown'](opts)
