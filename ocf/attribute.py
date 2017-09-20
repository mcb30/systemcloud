"""OCF resource agent attributes"""

from ocf.crm import ClusterResourceManager as crm


class Attribute(object):
    """An OCF resource agent attribute"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, name, type=str, default=None):
        # pylint: disable=locally-disabled, redefined-builtin
        self.name = name
        self.type = type
        self.default = default

    def attribute_name(self, _agent):
        """Calculate attribute full name"""
        return self.name

    def __get__(self, agent, _owner, **kwargs):
        if agent is None:
            return self
        if self not in agent.attribute_cache:
            value = crm.query(self.attribute_name(agent), type=self.type,
                              default=self.default, **kwargs)
            agent.attribute_cache[self] = value
        return agent.attribute_cache[self]

    def __set__(self, agent, value, **kwargs):
        agent.attribute_cache.pop(self, None)
        crm.update(self.attribute_name(agent), value, **kwargs)
        agent.attribute_cache[self] = value

    def __delete__(self, agent, **kwargs):
        agent.attribute_cache.pop(self, None)
        crm.delete(self.attribute_name(agent), **kwargs)
        agent.attribute_cache[self] = None

    def __repr__(self):
        return "%s(%r, %s, %r)" % (self.__class__.__name__, self.name,
                                   self.type.__name__, self.default)


class NodeAttribute(Attribute):
    """An OCF resource agent per-node attribute"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, name, type=str, default=None, lifetime='forever'):
        # pylint: disable=locally-disabled, redefined-builtin
        super(NodeAttribute, self).__init__(name, type, default)
        self.lifetime = lifetime

    def __get__(self, agent, owner):
        if agent is None:
            return self
        return super(NodeAttribute, self).__get__(agent, owner, node=agent.node,
                                                  lifetime=self.lifetime)

    def __set__(self, agent, value):
        super(NodeAttribute, self).__set__(agent, value, node=agent.node,
                                           lifetime=self.lifetime)

    def __delete__(self, agent):
        super(NodeAttribute, self).__delete__(agent, node=agent.node,
                                              lifetime=self.lifetime)

    def __repr__(self):
        return "%s(%r, %s, %r, %r)" % (self.__class__.__name__, self.name,
                                       self.type.__name__, self.default,
                                       self.lifetime)


class InstanceNameAttribute(Attribute):
    """An OCF resource agent per-instance attribute

    The attribute will be named using the <instance>-<name> naming
    scheme.
    """
    # pylint: disable=locally-disabled, too-few-public-methods

    def attribute_name(self, agent):
        """Calculate attribute full name"""
        return '%s-%s' % (agent.instance, self.name)


class NameInstanceAttribute(Attribute):
    """An OCF resource agent per-instance attribute

    The attribute will be named using the <name>-<instance> naming
    scheme.
    """
    # pylint: disable=locally-disabled, too-few-public-methods

    def attribute_name(self, agent):
        """Calculate attribute full name"""
        return '%s-%s' % (self.name, agent.instance)


class NodeInstanceNameAttribute(NodeAttribute, InstanceNameAttribute):
    """An OCF resource agent per-node, per-instance attribute

    The attribute will be named using the <instance>-<name> naming
    scheme.
    """
    # pylint: disable=locally-disabled, too-few-public-methods
    pass


class NodeNameInstanceAttribute(NodeAttribute, NameInstanceAttribute):
    """An OCF resource agent per-node, per-instance attribute

    The attribute will be named using the <name>-<instance> naming
    scheme.
    """
    # pylint: disable=locally-disabled, too-few-public-methods
    pass
