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
            return self.default
        if self not in agent.parameter_cache:
            value = agent.param(self.name, self.type, self.default)
            agent.parameter_cache[self] = value
        return agent.parameter_cache[self]
