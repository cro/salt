# -*- coding: utf-8 -*-

# Import python libs
from __future__ import absolute_import, print_function
import os
import sys
import multiprocessing
import pickle
# Import Salt libs
import salt.utils.event
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

# start thread
#  thread retrieves keys
#  thread checks minions alive
#  thread retrieves active jobs
#  thread retrieves completed jobs
#  thread signals done

# When thread done
#  set alarm to update keys
#  set alarm to update minions
#  set alarm to update active jobs
#  set alarm to update completed jobs

# When all jobs are done, set alarm to restart thread


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


def format_jobs(jobs):
    jobitems = []
    for k in jobs.keys():
        job = '{0}: {1}'.format(jobs[k]['Target'], jobs[k]['Function'])
        jobitems.append(urwid.AttrMap(urwid.SelectableIcon(job),
                                      attr_map=k,
                                      focus_map='focus'))
    return jobitems


def format_event(evt):
    return urwid.AttrMap(urwid.SelectableIcon(
        '%s: %s (%s)'.format(ret['data']['id'],
                             ret['data']['return'],
                             ret['data']['success'])),
        focus_map='focus')


def key_worker(opts, fd):
    wheel = salt.wheel.WheelClient(opts)
    wheel.print_func = None
    keys = wheel.cmd('key.list_all')
    formatted_keys = format_keys(keys)
    pickled_keys = pickle.dumps(formatted_keys)
    os.write(fd, pickled_keys)


def job_worker(opts, fd):
    runner = salt.runner.RunnerClient(opts)
    jobs = runner.cmd('jobs.list_jobs')
    formatted_jobs = format_jobs(jobs)
    pickled_jobs = pickle.dumps(formatted_jobs)
    os.write(fd, pickled_jobs)


def event_worker(opts, fd):
    '''
    Attach to the pub socket and grab messages
    '''
    event = salt.utils.event.get_event(
        None,
        sock_dir=opts['sock_dir'],
        transport=opts['transport'],
        opts=opts,
        listen=True
    )
    while True:
        ret = event.get_event(full=True)
        if ret is None or not ret['tag'].startswith('salt/job'):
            continue
        if ret['data']['fun'] == 'saltutil.find_job':
            continue

        pickled_ret = pickle.dumps(format_event(ret))
        os.write(fd, pickled_ret)


class Pane(parsers.SaltCMDOptionParser):
    '''
    Creation of the pane of glass starts here.
    '''
    def __init__(self):

        def input_filter(keys):
            if 'f12' in keys:
                raise urwid.ExitMainLoop
            if ' ' in keys:
                self.work_area_lw.append(urwid.Text(str(top.body.focus)))
                self.work_area_lb.focus_position = len(self.work_area_lw) - 1

            if 'x' in keys:
                self.work_area_lw.append(urwid.Text(keys))
                self.work_area_lb.focus_position = len(self.work_area_lw) - 1

        self.key_lw = urwid.SimpleFocusListWalker([])
        self.key_lb = urwid.ListBox(self.key_lw)
        self.job_lw = urwid.SimpleFocusListWalker([])
        self.job_lb = urwid.ListBox(self.job_lw)
        self.work_area_lw = urwid.SimpleFocusListWalker([])
        self.work_area_lb = urwid.ListBox(self.work_area_lw)
        self.command_line_lw = urwid.SimpleFocusListWalker([])
        self.opts = salt.config.client_config('/etc/salt/master')

        self.wd_work_area = self.work_area()
        self.wd_key = self.minion_key_column()
        self.wd_job = self.job_list_column()
        self.wd_command_line = self.command_line()

        self.top = urwid.Frame(
            urwid.Pile(
                [urwid.Columns([self.wd_work_area,
                                urwid.Pile([('weight', 1, self.wd_key),
                                            ('weight', 1, self.wd_job)])],
                               dividechars=1),
                 self.wd_command_line]
            )
        )
        self.evl = urwid.TornadoEventLoop(tornado.ioloop.IOLoop())
        self.loop = urwid.MainLoop(self.top, [
            ('header', 'black', 'dark cyan', 'standout'),
            ('key', 'yellow', 'dark blue', 'bold'),
            ('listbox', 'light gray', 'black' ),
            ('minions', 'light green', 'black'),
            ('minions_denied', 'dark red', 'black'),
            ('minions_pre', 'dark blue', 'black'),
            ('minions_rejected', 'light red', 'black'),
            ('focus', 'standout', '', '', '', '')
        ], unhandled_input=input_filter, event_loop=self.evl)


    def minion_key_column(self):
        key_header = ('pack', urwid.Text('Minions'))
        return urwid.Pile([key_header, ('weight', 1, self.key_lb)])

    def job_list_column(self):
        job_header = ('pack',urwid.Text('Jobs'))
        return urwid.Pile([job_header, ('weight', 1, self.job_lb)])

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

        def update_keys(pipe_data):
            keys_from_pipe = pickle.loads(pipe_data)
            pos = 0
            for key in keys_from_pipe:
                self.key_lw.insert(pos, key)
                self.key_lb.focus_position = pos
                pos = pos + 1

        def update_jobs(pipe_data):
            jobs_from_pipe = pickle.loads(pipe_data)
            pos = 0
            for key in jobs_from_pipe:
                self.job_lw.insert(pos, key)
                self.job_lb.focus_position = pos
                pos = pos + 1

        def update_status(pipe_data):
            ret_from_pipe = pickle.loads(pipe_data)
            self.work_area_lw.insert(0, ret_from_pipe)

        self.top.focus_position = 'body'

        key_pipe = self.loop.watch_pipe(update_keys)
        job_pipe = self.loop.watch_pipe(update_jobs)
        workarea_pipe = self.loop.watch_pipe(update_status)

        key_process = multiprocessing.Process(target=key_worker, args=(self.opts, key_pipe,))
        key_process.start()
        job_process = multiprocessing.Process(target=job_worker, args=(self.opts, job_pipe,))
        job_process.start()
        workarea_process = multiprocessing.Process(target=event_worker, args=(self.opts, workarea_pipe,))
        workarea_process.start()

        self.loop.run()

        key_process.join()
        job_process.join()
        workarea_process.terminate()


        # finally:
        #     screen.tty_signal_keys(*old)


