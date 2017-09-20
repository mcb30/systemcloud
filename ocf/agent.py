"""OCF resource agents"""

import argparse
import logging
import logging.handlers
import os
import sys
from collections import defaultdict
from lxml import etree

from ocf.constants import SUCCESS, NOT_RUNNING
from ocf.types import from_ocf
from ocf.exceptions import OcfError, GenericError, UnimplementedError
from ocf.attribute import NodeNameInstanceAttribute
from ocf.parameter import Parameter
from ocf.crm import ClusterResourceManager as crm
from ocf.action import action, Action

DOCTYPE = '<!DOCTYPE resource-agent SYSTEM "ra-api-1.dtd">'

_stderr = logging.StreamHandler()
_syslog = logging.handlers.SysLogHandler(address='/dev/log')
_syslog.setFormatter(logging.Formatter('%(name)s: %(message)s'))

def meta_notify_resources_property(label):
    """Construct property for notification resources"""
    return property(lambda self: self.meta_notify_resources(label))

def meta_notify_unames_property(label):
    """Construct property for notification node names"""
    return property(lambda self: self.meta_notify_unames(label))

def meta_notify_peers_property(label):
    """Construct property for notification peers"""
    return property(lambda self: self.meta_notify_peers(label))

def future_resources_property(label, add, remove):
    """Construct property for future resources"""
    return property(lambda self: self.future_resources(label, add, remove))

def future_unames_property(label, add, remove):
    """Construct property for future node names"""
    return property(lambda self: self.future_unames(label, add, remove))

def future_peers_property(label, add, remove):
    """Construct property for future peers"""
    return property(lambda self: self.future_peers(label, add, remove))

def current_resources_property(label, add, remove):
    """Construct property for current resources"""
    return property(lambda self: self.current_resources(label, add, remove))

def current_unames_property(label, add, remove):
    """Construct property for current node names"""
    return property(lambda self: self.current_unames(label, add, remove))

def current_peers_property(label, add, remove):
    """Construct property for current peers"""
    return property(lambda self: self.current_peers(label, add, remove))

active_add_remove = ('active', 'start', 'stop')
master_add_remove = ('master', 'promote', 'demote')


class Notification(object):
    """An OCF resource agent notification"""

    def __init__(self, agent):
        self.agent = agent

    def __str__(self):
        return '%s-%s' % (self.type, self.operation)

    @property
    def operation(self):
        """Notification operation"""
        return self.agent.meta_notify_operation

    @property
    def type(self):
        """Notification type"""
        return self.agent.meta_notify_type

    @property
    def is_pre(self):
        """Notification is before operation takes place"""
        return self.type == 'pre'

    @property
    def is_post(self):
        """Notification is after operation takes place"""
        return self.type == 'post'

    @property
    def resources(self):
        """Notification resources"""
        return self.agent.meta_notify_resources(self.operation)

    @property
    def unames(self):
        """Notification node names"""
        return self.agent.meta_notify_unames(self.operation)

    @property
    def peers(self):
        """Notification peers"""
        return self.agent.meta_notify_peers(self.operation)


class ResourceAgent(object):
    """An OCF resource agent"""
    # pylint: disable=locally-disabled, too-many-instance-attributes

    description = ''
    metadata = ''

    score = NodeNameInstanceAttribute('master', int)

    def __init__(self, environ=None, node=None):
        self.environ = (environ if environ is not None else os.environ)
        self.node = (node if node is not None else self.meta_on_node)
        self.parameter_cache = {}
        self.attribute_cache = {}
        self.all_unames_cache = None
        self._logger = None

    def __repr__(self):
        return '%s[%s](%s)' % (self.name, self.instance, self.node)

    @property
    def name(self):
        """Agent name"""
        return self.__class__.__name__

    @property
    def version(self):
        """Agent version"""
        return "0"

    def peer(self, node):
        """Get a peer node agent object"""
        if node == self.node:
            return self
        environ = {k: self.environ.get(k) for k in ('OCF_RESOURCE_INSTANCE',)}
        return self.__class__(environ=environ, node=node)

    @property
    def logger(self):
        """Log writer"""
        if self._logger is None:
            log_name = (('%s[%s]' % (self.name, self.instance))
                        if self.instance is not None else self.name)
            self._logger = logging.getLogger(log_name)
            self._logger.setLevel(logging.DEBUG)
            self._logger.addHandler(_stderr)
            self._logger.addHandler(_syslog)
        return self._logger

    @property
    def parameters(self):
        """Dictionary of all parameters (keyed by attribute name)"""
        parameters = {}
        for cls in reversed(self.__class__.__mro__):
            for name, value in cls.__dict__.items():
                if isinstance(value, Parameter):
                    parameters[name] = value
        return parameters

    @property
    def actions(self):
        """Dictionary of all actions (keyed by action name)"""
        by_name = {}
        by_method = defaultdict(Action)
        for cls in reversed(self.__class__.__mro__):
            for name in cls.__dict__:
                value = getattr(cls, name)
                if hasattr(value, 'actions'):
                    for desc in value.actions:
                        act = by_method[name]
                        act.method = name
                        act.enabled = desc.enabled
                        if desc.interval is not None:
                            act.roles[desc.role].interval = desc.interval
                        if desc.timeout is not None:
                            act.roles[desc.role].timeout = desc.timeout
                        if desc.name is not None:
                            by_name[desc.name] = name
        return {k: by_method[v] for k, v in by_name.items()}

    @property
    def instance(self):
        """Instance name"""
        instance_index = self.environ.get('OCF_RESOURCE_INSTANCE')
        if instance_index is None:
            return None
        return instance_index.split(':')[0]

    def param(self, name, type=str, default=None):
        """Get resource parameter"""
        # pylint: disable=locally-disabled, redefined-builtin
        value = self.environ.get('OCF_RESKEY_%s' % name)
        if value is None:
            return default
        return from_ocf(value, type)

    def meta(self, name, type=str, default=None):
        """Get meta resource parameter"""
        # pylint: disable=locally-disabled, redefined-builtin
        return self.param(('CRM_meta_%s' % name), type, default)

    @property
    def meta_clone(self):
        """Cloned resource instance number"""
        return self.meta('clone', int)

    @property
    def meta_clone_max(self):
        """Maximum number of clones"""
        return self.meta('clone_max', int)

    @property
    def meta_clone_node_max(self):
        """Maximum number of clones on a single node"""
        return self.meta('clone_node_max', int)

    @property
    def meta_globally_unique(self):
        """Resource is globally unique"""
        return self.meta('globally_unique', bool)

    @property
    def meta_interval(self):
        """Interval between recurring operations

        This is generally meaningful only for monitor operations,
        where a zero value indicates that this is an initial probe.
        """
        return self.meta('interval', int)

    @property
    def meta_master_max(self):
        """Maximum number of masters"""
        return self.meta('master_max', int)

    @property
    def meta_master_node_max(self):
        """Maximum number of masters on a single node"""
        return self.meta('master_node_max', int)

    @property
    def meta_name(self):
        """Operation name"""
        return self.meta('name', str)

    @property
    def meta_notify(self):
        """Notifications are enabled"""
        return self.meta('notify', bool)

    @property
    def meta_notify_operation(self):
        """Notification operation"""
        return self.meta('notify_operation', str)

    @property
    def meta_notify_type(self):
        """Notification type"""
        return self.meta('notify_type', str)

    @property
    def meta_on_node(self):
        """Local node"""
        return self.meta('on_node', str)

    @property
    def meta_on_node_uuid(self):
        """Local node unique identifier

        Note that this is not a standard 128-bit UUID.
        """
        return self.meta('on_node_uuid', str)

    @property
    def meta_timeout(self):
        """Timeout for this operation (in milliseconds)"""
        return self.meta('timeout', int)

    def meta_notify_resources(self, label):
        """Notification resources"""
        return self.meta('notify_%s_resource' % label, list)

    def meta_notify_unames(self, label):
        """Notification node names"""
        return self.meta('notify_%s_uname' % label, list)

    def meta_notify_peers(self, label):
        """Notification peers"""
        unames = self.meta_notify_unames(label)
        if unames is None:
            return None
        return [self.peer(x) for x in unames]

    def future_resources(self, label, add, remove):
        """Future resources

        This is the list of resources that will be in effect once the
        current operation has completed.
        """
        labelled = self.meta_notify_resources(label)
        added = self.meta_notify_resources(add)
        removed = self.meta_notify_resources(remove)
        if labelled is None and added is None and removed is None:
            return None
        return sorted(list((set(labelled) | set(added)) - set(removed)))

    def future_unames(self, label, add, remove):
        """Future node names

        This is the list of node names that will be in effect once the
        current operation has completed.
        """
        labelled = self.meta_notify_unames(label)
        added = self.meta_notify_unames(add)
        removed = self.meta_notify_unames(remove)
        if labelled is None and added is None and removed is None:
            return None
        return sorted(list((set(labelled) | set(added)) - set(removed)))

    def future_peers(self, label, add, remove):
        """Future peers

        This is the list of node names that will be in effect once the
        current operation has completed.
        """
        unames = self.future_unames(label, add, remove)
        if unames is None:
            return None
        return [self.peer(x) for x in unames]

    def current_resources(self, label, add, remove):
        """Current resources

        This list is corrected for the effects of post-operation
        notifications.
        """
        if self.meta_notify_type == 'post':
            return self.future_resources(label, add, remove)
        resources = self.meta_notify_resources(label)
        if resources is None:
            return None
        return sorted(resources)

    def current_unames(self, label, add, remove):
        """Current node names

        This list is corrected for the effects of post-transition
        notifications.
        """
        if self.meta_notify_type == 'post':
            return self.future_unames(label, add, remove)
        unames = self.meta_notify_unames(label)
        if unames is None:
            return None
        return sorted(unames)

    def current_peers(self, label, add, remove):
        """Current peers

        This list is corrected for the effects of post-transition
        notifications.
        """
        unames = self.current_unames(label, add, remove)
        if unames is None:
            return None
        return [self.peer(x) for x in unames]

    meta_notify_active_resources = meta_notify_resources_property('active')
    meta_notify_active_unames = meta_notify_unames_property('active')
    meta_notify_active_peers = meta_notify_peers_property('active')
    meta_notify_all_unames = meta_notify_unames_property('all')
    meta_notify_all_peers = meta_notify_peers_property('all')
    meta_notify_available_unames = meta_notify_unames_property('available')
    meta_notify_available_peers = meta_notify_peers_property('available')
    meta_notify_demote_resources = meta_notify_resources_property('demote')
    meta_notify_demote_unames = meta_notify_unames_property('demote')
    meta_notify_demote_peers = meta_notify_peers_property('demote')
    meta_notify_inactive_resources = meta_notify_resources_property('inactive')
    meta_notify_master_resources = meta_notify_resources_property('master')
    meta_notify_master_unames = meta_notify_unames_property('master')
    meta_notify_master_peers = meta_notify_peers_property('master')
    meta_notify_promote_resources = meta_notify_resources_property('promote')
    meta_notify_promote_unames = meta_notify_unames_property('promote')
    meta_notify_promote_peers = meta_notify_peers_property('promote')
    meta_notify_slave_resources = meta_notify_resources_property('slave')
    meta_notify_slave_unames = meta_notify_unames_property('slave')
    meta_notify_slave_peers = meta_notify_peers_property('slave')
    meta_notify_start_resources = meta_notify_resources_property('start')
    meta_notify_start_unames = meta_notify_unames_property('start')
    meta_notify_start_peers = meta_notify_peers_property('start')
    meta_notify_stop_resources = meta_notify_resources_property('stop')
    meta_notify_stop_unames = meta_notify_unames_property('stop')
    meta_notify_stop_peers = meta_notify_peers_property('stop')

    future_active_resources = future_resources_property(*active_add_remove)
    future_active_unames = future_unames_property(*active_add_remove)
    future_active_peers = future_peers_property(*active_add_remove)
    future_master_resources = future_resources_property(*master_add_remove)
    future_master_unames = future_unames_property(*master_add_remove)
    future_master_peers = future_peers_property(*master_add_remove)

    current_active_resources = current_resources_property(*active_add_remove)
    current_active_unames = current_unames_property(*active_add_remove)
    current_active_peers = current_peers_property(*active_add_remove)
    current_master_resources = current_resources_property(*master_add_remove)
    current_master_unames = current_unames_property(*master_add_remove)
    current_master_peers = current_peers_property(*master_add_remove)

    @property
    def notification(self):
        """Notification object"""
        if self.meta_notify_type:
            return Notification(self)

    @property
    def all_unames(self):
        """Get all node names"""
        if self.all_unames_cache is None:
            # Use notification name list if available, otherwise query CRM
            self.all_unames_cache = self.meta_notify_all_unames
            if self.all_unames_cache is None:
                self.all_unames_cache = crm.all_unames()
        return self.all_unames_cache

    @property
    def all_peers(self):
        """Get all peers"""
        return [self.peer(x) for x in self.all_unames]

    @property
    def is_master_slave(self):
        """Resource is configured as a master/slave multistate resource"""
        return self.meta_master_max > 0

    def trigger_promote(self, score=100):
        """Trigger promotion by updating the master score"""
        self.score = score

    def trigger_demote(self):
        """Trigger demotion by clearing the master score"""
        del self.score

    @action('meta-data', timeout=5)
    def action_metadata(self):
        """Show resource metadata"""
        xml = etree.Element('resource-agent', name=self.name)
        etree.SubElement(xml, 'version').text = self.version
        if self.__doc__:
            longdesc = self.__doc__
            shortdesc = self.__doc__.splitlines()[0]
            etree.SubElement(xml, 'longdesc', lang='en').text = longdesc
            etree.SubElement(xml, 'shortdesc', lang='en').text = shortdesc
        xml_params = etree.SubElement(xml, 'parameters')
        for parameter in sorted(self.parameters.values(), key=lambda x: x.name):
            xml_param = etree.SubElement(xml_params, 'parameter',
                                         name=parameter.name,
                                         unique=str(int(parameter.unique)),
                                         required=str(int(parameter.required)))
            if parameter.description is not None:
                etree.SubElement(xml_param, 'shortdesc',
                                 lang='en').text = parameter.description
            xml_content = etree.SubElement(xml_param, 'content', type='string')
            if parameter.default is not None:
                xml_content.set('default', parameter.default)
        xml_actions = etree.SubElement(xml, 'actions')
        actions = self.actions
        for name in sorted(actions):
            if actions[name].enabled:
                for role, details in actions[name].roles.items():
                    xml_action = etree.SubElement(xml_actions, 'action',
                                                  name=name)
                    if role is not None:
                        xml_action.set('role', role)
                    if details.interval is not None:
                        xml_action.set('interval', str(details.interval))
                    if details.timeout is not None:
                        xml_action.set('timeout', str(details.timeout))
        sys.stdout.write(etree.tostring(xml, xml_declaration=True,
                                        encoding='utf-8', doctype=DOCTYPE,
                                        pretty_print=True).decode())
        return SUCCESS

    @staticmethod
    @action('validate-all', timeout=5)
    def action_validate():
        """Validate configuration"""
        return SUCCESS

    @staticmethod
    @action('notify', timeout=5, enabled=False)
    def action_notify():
        """Notify resource of changes"""
        return SUCCESS

    @staticmethod
    @action('monitor', timeout=10, interval=20)
    def action_monitor():
        """Monitor resource"""
        return NOT_RUNNING

    @staticmethod
    @action('start', timeout=120)
    def action_start():
        """Start resource"""
        raise UnimplementedError("No start method")

    @staticmethod
    @action('promote', timeout=120, enabled=False)
    def action_promote():
        """Promote resource"""
        raise UnimplementedError("No promote method")

    @staticmethod
    @action('demote', timeout=120, enabled=False)
    def action_demote():
        """Demote resource"""
        raise UnimplementedError("No demote method")

    @staticmethod
    @action('stop', timeout=120)
    def action_stop():
        """Stop resource"""
        raise UnimplementedError("No stop method")

    def dispatch(self, args):
        """Invoke action based on command line arguments, and exit

        Invoke an action based on the OCF-specified command line
        arguments (i.e. a single argument which is the name of an
        action), and exit the executable in accordance with the OCF
        standards for exit codes and exit reason messages.
        """
        # pylint: disable=locally-disabled, broad-except
        actions = self.actions
        parser = argparse.ArgumentParser(description=self.description)
        parser.add_argument('action',
                            choices=sorted(k for k, v in actions.items()
                                           if v.enabled))
        arg = parser.parse_args(args)
        try:
            method = getattr(self, actions[arg.action].method)
            rc = method()
        except OcfError as e:
            self.logger.error(str(e))
            e.exit()
        except Exception as e:
            self.logger.exception(str(e))
            GenericError(str(e)).exit()
        sys.exit(rc)

    @classmethod
    def main(cls):
        """Invoke as main program"""
        cls().dispatch(sys.argv[1:])
