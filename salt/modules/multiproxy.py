# -*- coding: utf-8 -*-
'''
Manage multiproxies.
'''
from __future__ import absolute_import

# Import python libs
import re
import logging

# Import salt libs
import salt.utils.itertools
from salt.exceptions import CommandExecutionError

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)  # pylint: disable=C0103


def add(id):
    '''
    Add a target for a multiproxy
    Note: requires support in minion.py
    '''
    return True
