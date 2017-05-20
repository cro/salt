# -*- coding: utf-8 -*-
'''
Support for iocage (jails tools on FreeBSD)
'''
from __future__ import absolute_import

# Import python libs
# import os

import logging
import os
# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

log = logging.getLogger(__name__)

__virtualname__ = 'iocage'


def __virtual__():
    '''
    Module load only if iocage is installed
    '''
    if salt.utils.which('iocage'):
        return __virtualname__
    else:
        return False


def _format_ret(return_dict):
    '''
    Handle different situations--e.g. retcode != 0 but no stderr,
    retcode == 0 but stderr shows something wrong, etc.
    '''
    msg = ''
    if 'stderr' in return_dict and len(return_dict['stderr']) > 0:
        msg = msg + '{0} '.format(return_dict['stderr'])

    if 'stdout' in return_dict and len(return_dict['stdout']) > 0:
        msg = msg + '{0} '.format(return_dict['stderr'])

    if 'retcode' in return_dict:
        msg = msg + '({0})'.format(return_dict['retcode'])

    return msg


def _option_exists(name, **kwargs):
    '''
    Check if a given property `name` is in the all properties list
    '''
    return name in list_properties(name, **kwargs)


def _exec(cmd, output='stdout'):
    '''
    Execute command `cmd` and returns output `output` (by default returns the
    stdout)
    '''
    cmd_ret = __salt__['cmd.run_all'](cmd, env=[{'LANG': 'en_US.UTF-8'},
                                                {'LC_ALL': 'en_US.UTF-8'}])
    if (cmd_ret['retcode'] != 0) or ('stderr' in cmd_ret and len(cmd_ret['stderr']) > 0):
        cmd_ret['success'] = False
    else:
        cmd_ret['success'] = True

    if cmd_ret['success'] == False:
        raise CommandExecutionError(_format_ret(cmd_ret))

    return cmd_ret


def _list_properties(jail_name, **kwargs):
    '''
    Returns result of iocage get all or iocage defaults (according to the
    jail name)
    '''
    cmd = 'iocage get all %s' % (jail_name,)

    propdict = {}
    ret = _exec(cmd)

    props = ret['stdout'].split('\n')

    for p in props:
        ptuple = p.split(':')
        propdict[ptuple[0]] = ptuple[1]

    return {'properties': propdict}


def _parse_properties(**kwargs):
    '''
    Returns a rendered properties string used by iocage command line properties
    argument
    '''
    if 'jail' in kwargs.keys():
        name = kwargs.pop('jail')

        default_properties = [p.split(':')[0] for p in _list_properties(name)]
        default_properties.append('pkglist')

        for prop in kwargs.keys():
            if not prop.startswith('__') and prop not in default_properties:
                raise SaltInvocationError('Unknown property %s' % (prop,))

    return ' '.join(
        ['%s="%s"' % (k, v) for k, v in kwargs.items() if not k.startswith('__')])


def _list(option=None, **kwargs):
    '''
    Returns list of jail templates or jails
    '''
    if option == '-t':
        cmd = 'iocage list --header -t'
    else:
        cmd = 'iocage list --header'

    jails = []
    ret = _exec(cmd, **kwargs)
    lines = ret['stdout'].split('\n')

    if len(lines) > 0:
        for l in lines:
            # omit all non-iocage jails
            if l == '--- non iocage jails currently active ---':
                break
            onejail = l.split('\t')
            jails.append({'jid': onejail[0],
                          'uuid': onejail[1],
                          'state': onejail[2],
                          'tag': onejail[3],
                          'release': onejail[4],
                          'ip4': onejail[5]})
    else:
        raise CommandExecutionError(
            'Error in command "%s" : no results found' % (cmd, ))

    if option == '-t':
        return {'templates': jails}
    else:
        return {'jails': jails}


def _list_releases(**kwargs):
    '''
    Returns list of jail releases
    '''
    cmd = 'iocage list --header -r'
    ret = _exec(cmd, **kwargs)

    lines = ret['stdout'].split('\n')

    if len(lines) > 0:
        jails = []
        for l in lines:
            # omit all non-iocage jails
            if l == '--- non iocage jails currently active ---':
                break
            jails.append(l)

    else:
        raise CommandExecutionError(
            'Error in command "%s" : no results found' % (cmd, ))

    return {'releases': jails}


def _list_snapshots(uuid_or_tag):
    '''
    Returns list of jail snapshots
    '''
    cmd = 'iocage snaplist -h {0}'.format(uuid_or_tag)
    ret = _exec(cmd)

    lines = ret['stdout'].split('\n')

    if len(lines) > 0:
        snaps = []
        for l in lines:
            snap = {}
            fields = l.split('\t')
            if len(fields) < 4:
                continue
            snap['name'] = fields[0]
            snap['created'] = fields[1]
            snap['rsize'] = fields[2]
            snap['used'] = fields[3]
            snaps.append(snap)
        return snaps
    else:
        raise CommandExecutionError(
            'Error in command "%s" : no results found' % (cmd, ))


def _display_list(items_list):
    '''
    Format display for the list of jails, templates or releases
    '''
    ret = []

    for item in items_list:
        ret.append(','.join(['%s=%s' % (k, v) for k, v in item.items()]),)

    return '\n'.join(ret)


def _manage_state(state, jail_name, **kwargs):
    '''
    Start / Stop / Reboot / Destroy a jail `jail_name`
    '''
    existing_jails = _list()
    for jail in existing_jails['jails']:
        if jail_name == jail['uuid'] or jail_name == jail['tag']:
            if ((state == 'start' and jail['state'] == 'down')
                    or (state == 'stop' and jail['state'] == 'up')
                    or state == 'restart'
                    or state == 'destroy'):
                return _exec('iocage %s %s' % (state, jail_name))
            else:
                if state == 'start':
                    raise SaltInvocationError(
                        'jail %s is already started' % (jail_name,))
                else:
                    raise SaltInvocationError(
                        'jail %s is already stopped' % (jail_name,))

    raise SaltInvocationError('jail uuid or tag does not exist' % (jail_name,))


def list_snapshots(uuid_or_tag):
    '''
    List existing snapshots
    '''
    if not uuid_or_tag:
        raise CommandExecutionError('Missing uuid or tag')

    return _list_snapshots(uuid_or_tag)


def rollback(uuid_or_tag, name):
    '''
    Rollback to a snapshot
    '''
    cmd = 'iocage rollback -f -n {0} {1}'.format(name, uuid_or_tag)
    ret = _exec(cmd)
    return {'rollback': {uuid_or_tag: True}}


def snapremove(uuid_or_tag, name):
    '''
    Remove a snapshot.
    Name can be 'ALL' to remove all snapshots
    '''
    if name == 'ALL':
        snaps = _list_snapshots(uuid_or_tag)
    else:
        snaps = [{'name': name}]

    snapremove = {}
    for snap in snaps:
        cmd = 'iocage snapremove -n {0} {1}'.format(snap['name'], uuid_or_tag)
        try:
            ret = _exec(cmd)
            snapremove[snap['name']] = {}
            snapremove[snap['name']['success']]= True
        except CommandExecutionError as msg:
            snapremove[snap['name']] = {}
            snapremove[snap['name']['success']]= False
            snapremove[snap['name']['error']] = msg

    return {'snapremove': snapremove}


def snapshot(uuid_or_tag, name=None):
    '''
    Take a snapshot
    '''
    cmd = 'iocage snapshot'
    if name:
        cmd = cmd + ' -n ' + name
    cmd = cmd + ' ' + uuid_or_tag

    ret = _exec(cmd)
    return {'snapshot': {uuid_or_tag: {name: True}}}


def list_jails(**kwargs):
    '''
    Get list of jails

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.list_jails
    '''
    return _list()


def list_templates(**kwargs):
    '''
    Get list of template jails

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.list_templates
    '''
    return _list('-t')


def list_releases(**kwargs):
    '''
    Get list of downloaded releases

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.list_releases
    '''
    return _list_releases()


def list_properties(jail_name, **kwargs):
    '''
    List all properies for a given jail or defaults value

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.list_properties <jail_name>
        salt '*' iocage.list_properties defaults
    '''
    return _list_properties(jail_name)


def get_property(property_name, jail_name, **kwargs):
    '''
    Get property value for a given jail (or default value)

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.get_property <property> <jail_name>
        salt '*' iocage.get_property all <jail_name>
    '''
    if property_name == 'all':
        return _list_properties(jail_name, **kwargs)
    else:
        return _list_properties(jail_name)['properties'][property_name]


def set_property(jail_name, **kwargs):
    '''
    Set property value for a given jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.set_property <jail_name> [<property=value>]
    '''
    result = {}
    for k, v in kwargs:
        try:
            ret = __exec('iocage set {0}={1} {2}'.format(k, v, jail_name))
            result[k] = True
        except CommandExecutionError as msg:
            result[jail_name][k] = msg

    return {jail_name: result} 


def fetch(release=None, **kwargs):
    '''
    Download or update/patch release

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.fetch
        salt '*' iocage.fetch <release>
    '''
    if release is None:
        current_release = _exec('uname -r')
        release_str = current_release['stdout'].strip()
    else:
        release_str = release

    fetch_ret = _exec('iocage fetch -r %s' % (release_str,))
    return {'fetch': release_str}


def create(jail_type="full", template_id=None, **kwargs):
    '''
    Create a new jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.create [<option>] [<property=value>]
    '''
    _options = ['full', 'base', 'empty', 'template']

    if jail_type not in _options:
        raise SaltInvocationError('Unknown option %s' % (jail_type,))

    # check template exists for cloned template
    if jail_type == 'template':
        if template_id == None:
            raise SaltInvocationError('template_id not specified for cloned template')
        templates = __salt__['iocage.list_templates']()
        tmpl_exists = False
        for tmpl in templates['templates']:
            if tmpl['tag'] == template_id or tmpl['uuid'] == template_id:
                tmpl_exists = True
                break
        if tmpl_exists == False:
            raise SaltInvocationError('Template id %s does not exist' % (template_id,))


    if 'release' in kwargs.keys():
        rel = kwargs.pop('release')
    else:
        rel = ''

    # stringify the kwargs dict into iocage create properties format
    properties = _parse_properties(**kwargs)

    # if we would like to specify a tag value for the jail
    # check if another jail have not the same tag
    if 'tag' in kwargs.keys():
        existing_jails = _list()['jails']

        if kwargs['tag'] in [k['tag'] for k in existing_jails]:
            raise SaltInvocationError(
                'Tag %s already exists' % (kwargs['tag'],))

    pre_cmd = 'iocage create'
    if jail_type == 'base':
        pre_cmd = 'iocage create -b'
    if jail_type == 'empty':
        pre_cmd = 'iocage create -e'
    if jail_type == 'template':
        pre_cmd = 'iocage create -t %s' % (template_id)

    # fetch a release if it's the first install
    existing_releases = list_releases()['releases']
    # fetch a specific release if not present
    if rel:
        pre_cmd = pre_cmd + ' -r {0}'.format(rel)
        if rel not in existing_releases:
            fetch(release=rel)

    if not rel and len(existing_releases) == 0:
        fetch()

    if not rel and jail_type in ['full', 'base', 'empty']:
        rel = existing_releases[0]
        pre_cmd = pre_cmd + ' -r {0}'.format(rel)

    if len(properties) > 0:
        cmd = '{0} {1}'.format(pre_cmd, properties)
    else:
        cmd = '{0} {1}'.format(pre_cmd, properties)
    create_ret = _exec(cmd)

    if kwargs.get('tag'):
        return {'create':{kwargs['tag']:True}}
    else:
        return {'create':{create_ret['stdout']: True}}


def start(jail_name, **kwargs):
    '''
    Start a jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.start <jail_name>
    '''
    return _manage_state('start', jail_name, **kwargs)


def stop(jail_name, **kwargs):
    '''
    Stop a jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.stop <jail_name>
    '''
    return _manage_state('stop', jail_name, **kwargs)


def restart(jail_name, **kwargs):
    '''
    Restart a jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.restart <jail_name>
    '''
    return _manage_state('restart', jail_name, **kwargs)


def destroy(jail_name, **kwargs):
    '''
    Destroy a jail

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.destroy <jail_name>
    '''
    return _manage_state('destroy', jail_name, **kwargs)


def update(jail_name):
    '''
    Run freebsd-update to upgrade a specified jail to the latest patch level.
    Note this is different from iocage.upgrade, which runs freebsd-update to
    upgrade a jail to a specific release.

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.update <jail_name>

    '''

    ret = _exec('iocage update {0}'.format(jail_name))

    return ret


def upgrade(jail_name, release):
    '''
    Run freebsd-update to upgrade a specified jail to the latest patch level.
    Note this is different from iocage.upgrade, which runs freebsd-update to
    upgrade a jail to a specific release.

    CLI Example:

    .. code-block:: bash

        salt '*' iocage.update <jail_name>

    '''

    ret = _exec('iocage upgrade {0} -r {1}'.format(jail_name, release))

    return ret


def export(jail_name, suspend=True):
    '''
    Export a jail.
    '''
    try:
        ret = _exec('iocage export {0}'.format(jail_name))
    except CommandExecutionError as msg:
        if 'stop the jail' in ret['stdout'] and suspend:
            __salt__['iocage.stop'](jail_name)
            ret = _exec('iocage export {0}'.format(jail_name))
            __salt__['iocage.start'](jail_name)
        else:
            raise

    for l in ret['stdout'].splitlines():
        if l.startswith('Exported: '):
            return {'export':zipfilename}

def transfer(zipfile):
    '''
    Transfer an exported jail to the master,
    place in /var/cache/salt/master/minion/minion-id/jails
    Note this function needs ``file_recv:`` True in the master config
    and probably needs a higher value for file_recv_max_size as well.

    CLI Example:

    .. code-block:: bash

        salt fbsd transfer /iocage/images/1d4b4044-9474-43fd-913b-0c46e083ff16_2017-05-19_firstjail.zip

    '''
    return __salt__['cp.push'](zipfile)


def export_and_transfer(jail_name, suspend=True):
    '''
    Convenience method for exporting then transferring a jail to the master.

    CLI Example:

    .. code-block:: bash

        salt fbsd export_and_transfer /iocage/images/1d4b4044-9474-43fd-913b-0c46e083ff16_2017-05-19_firstjail.zip

    '''


if __name__ == "__main__":
    __salt__ = ''

    import sys
    sys.exit(0)
