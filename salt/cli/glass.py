# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys

# Import Salt libs
import salt.utils.job
from salt.ext.six import string_types
from salt.utils import parsers, print_cli
from salt.utils.args import yamlify_arg
from salt.utils.verify import verify_log
from salt.exceptions import (
        SaltClientError,
        SaltInvocationError,
        EauthAuthenticationError
        )
# Import 3rd-party libs
import salt.ext.six as six
import salt.config
import salt.runner
import salt.wheel

import urwid
import tornado.ioloop


def format_keys(keys):
    listitems = []
    for k, v in keys.iteritems():
        if k == 'local':
            continue
        for minion in v:
            listitems.append(
                urwid.AttrMap(urwid.SelectableIcon(minion),
                              attr_map=k,
                              focus_map='focus'))

    return listitems


def retrieve_keys(opts):

    wheel = salt.wheel.WheelClient(opts)
    keys = wheel.call_func('key.list_all')
    return format_keys(keys)


class Pane(parsers.SaltCMDOptionParser):
    '''
    Creation of the pane of glass starts here.
    '''
    def __init__(self):
        self.key_lw = urwid.SimpleFocusListWalker([])
        self.key_lb = urwid.ListBox(self.key_lw)
        self.job_lw = urwid.SimpleFocusListWalker([])
        self.work_area_lw = urwid.SimpleFocusListWalker([])
        self.work_area_lb = urwid.ListBox(self.work_area_lw)
        self.command_line_lw = urwid.SimpleFocusListWalker([])
        self.opts = salt.config.client_config('/etc/salt/master')


    def minion_key_column(self):
        key_header = ('pack', urwid.Text('Minions'))
        return urwid.Pile([key_header, ('weight', 1, self.key_lb)])

    def job_list_column(self):
        job_header = ('pack',urwid.Text('Jobs'))
        job_list = urwid.ListBox(self.job_lw)
        return urwid.Pile([job_header, ('weight', 1, job_list)])

    def command_line(self):
        command_header = ('pack', urwid.Text('command:'))
        # command_header = urwid.AttrMap(command_header, 'bright')
        command_list = urwid.AttrMap(urwid.ListBox(self.command_line_lw),
                                     attr_map='listbox',
                                     focus_map='focus')
        return urwid.Pile([command_header, command_list])

    def work_area(self):
        work_area_header = ('pack',urwid.Text('salt-glass'))
        return urwid.Pile([work_area_header, ('weight', 1, self.work_area_lb)])

    def start(self):

        def input_filter(keys):
            if 'f12' in keys:
                raise urwid.ExitMainLoop
            if ' ' in keys:
                self.work_area_lw.append(urwid.Text(str(top.body.focus)))
                self.work_area_lb.focus_position = len(self.work_area_lw) - 1

            if 'x' in keys:
                self.work_area_lw.append(urwid.Text(keys))
                self.work_area_lb.focus_position = len(self.work_area_lw) - 1


        wd_work_area = self.work_area()
        wd_key = self.minion_key_column()
        wd_job = self.job_list_column()
        wd_command_line = self.command_line()

        top = urwid.Frame(
            urwid.Pile(
                [urwid.Columns([wd_work_area,
                                urwid.Pile([('weight', 1, wd_key),
                                            ('weight', 1, wd_job)])],
                               dividechars=1),
                 wd_command_line]
            )
        )
        evl = urwid.TornadoEventLoop(tornado.ioloop.IOLoop())
        loop = urwid.MainLoop(top, [
            ('header', 'black', 'dark cyan', 'standout'),
            ('key', 'yellow', 'dark blue', 'bold'),
            ('listbox', 'light gray', 'black' ),
            ('minions', 'light green', 'black'),
            ('minions_denied', 'dark red', 'black'),
            ('minions_pre', 'dark blue', 'black'),
            ('minions_rejected', 'light red', 'black'),
            ('focus', 'standout', '', '', '', '')
            ], unhandled_input=input_filter, event_loop=evl)

        # try:
            # old = screen.tty_signal_keys('undefined','undefined',
            #     'undefined','undefined','undefined')
        keys = retrieve_keys(self.opts)

        pos = 0
        for key in keys:
            self.key_lw.insert(pos, key)
            self.key_lb.focus_position = pos
            pos = pos + 1

        top.focus_position = 'body'
        loop.run()
        # finally:
        #     screen.tty_signal_keys(*old)


