"""OCF resource agent parameters"""


class Parameter(object):
    """An OCF resource agent parameter"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, name, type=str, default=None):
        # pylint: disable=locally-disabled, redefined-builtin
        self.name = name
        self.type = type
        self.default = default

    def __get__(self, agent, _owner):
        if agent is None:
            return self
        if self not in agent.parameter_cache:
            value = agent.param(self.name, self.type, self.default)
            agent.parameter_cache[self] = value
        return agent.parameter_cache[self]

    def __repr__(self):
        return "%s(%r, %s, %r)" % (self.__class__.__name__, self.name,
                                   self.type.__name__, self.default)
