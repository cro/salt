# -*- coding: utf-8 -*-
'''
Support for iocage (jails tools on FreeBSD)
'''
from __future__ import absolute_import
import logging
log = logging.getLogger(__name__)

def _property(name, value, jail, **kwargs):
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    try:
        old_value = __salt__['iocage.get_property'](name, jail, **kwargs)
    except:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'jail option %s does not seem to exist' % (name,)
        else:
            ret['result'] = False
            ret['comment'] = 'jail option %s does not exist' % (name,)
    else:
        if value != old_value:
            ret['changes'] = {'new': value, 'old': old_value}

            if not __opts__['test']:
                try:
                    __salt__['iocage.set_property'](jail, **{name: value})
                except:
                    ret['result'] = False
                else:
                    ret['result'] = True
            else:
                ret['result'] = None
        else:
            if __opts__['test']:
                ret['result'] = None
            else:
                ret['result'] = True

    return ret


def property(name, value, jail, **kwargs):

    return _property(name, value, jail, **kwargs)


def managed(name, properties=None, jail_type="full", source=None, template_id=None, **kwargs):
    import pudb; pu.db
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': False}

    # test if a jail already exists
    # if it does not exist, a create command will be launch
    try:
        jail_exists = False

        jails = __salt__['iocage.list_jails']()['jails']
        templates = __salt__['iocage.list_templates']()['templates']
        jails = jails + templates
        for jail in jails:
            if jail['tag'] == name or jail['uuid'] == name:
                jail_exists = True
                break
    except (CommandExecutionError, SaltInvocationError) as e:
        log.debug("########## UNABLE TO CHECK IF JAIL EXISTS OR NOT ")
        log.debug(e)
        if __opts__['test']:
            ret['result'] = None
        ret['comment'] = 'An error occurred when trying to check the existence of the jail.'

        return ret

    try:
        # get jail's properties if exists or defaults
        if jail_exists:
            _name = name
        jail_properties = __salt__['iocage.list_properties'](_name, **kwargs)['properties']
    except (CommandExecutionError, SaltInvocationError):
        jail_properties = None

    if (jail_properties is not None
            and properties is not None
            and len(properties) > 0):
        if jail_exists:
            # set new value for each property
            try:
                changes = {}
                new_value = {}
                for prop_name, prop_value in properties.items():
                    if jail_properties.get(prop_name, False) == prop_value:
                        changes[prop_name] = {'new': prop_value,
                                              'old': jail_properties[prop_name]}
                        new_values[prop_name] = prop_value

                if not __opts__['test']:
                    property_result = __salt__['iocage.set_property'](name, new_values)
                else:
                    property_result = {}

                if len(changes) > 0:
                    ret['changes'] = changes
                    ret['comment'] = 'Updated jail properties for {0}'.format(name)
                else:
                    if len(new_values) == 0:
                        ret['comment'] = 'No changes'
            except (CommandExecutionError, SaltInvocationError) as e:
                ret['result'] = False
                ret['comment'] = ''.format(e)

            if __opts__['test']:
                ret['result'] = None
            else:
                ret['result'] = True
        else:
            # install / create the jail
            try:
                if not __opts__['test']:
                    if properties is not None:
                        __salt__['iocage.create'](tag=name, jail_type=jail_type, template_id=template_id, **properties)
                    else:
                        __salt__['iocage.create'](tag=name, **kwargs)
            except (CommandExecutionError, SaltInvocationError) as e:
                log.debug('####### FAIL INSTALLING NEW JAIL')
                log.debug(e)
                ret['result'] = False
                ret['comment'] = 'Creating new jail {0} failed with {1}'.format(name, e)
            else:
                if __opts__['test']:
                    ret['result'] = None
                else:
                    ret['result'] = True
                ret['comment'] = 'New jail %s installed' % (name,)

    return ret


if __name__ == "__main__":
    __salt__ = ''
    __opts__ = ''

    import sys
    sys.exit(0)
