"""OCF resource agent actions"""

from collections import namedtuple, defaultdict

ActionDescriptor = namedtuple('ActionDescriptor', ['name', 'interval',
                                                   'timeout', 'role',
                                                   'enabled'])

def action(name=None, interval=None, timeout=None, role=None, enabled=True):
    """Decorate method as an OCF resource agent action"""
    def wrap(func):
        """Wrap decorated method"""
        if not hasattr(func, 'actions'):
            func.actions = []
        desc = ActionDescriptor(name, interval, timeout, role, enabled)
        func.actions.append(desc)
        return func
    return wrap


class ActionRole(object):
    """An OCF resource agent action per-role property"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, interval=None, timeout=None):
        self.interval = interval
        self.timeout = timeout

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.interval,
                               self.timeout)


class ActionRoles(defaultdict):
    """An OCF resource agent action per-role property dictionary"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, cls=ActionRole):
        super(ActionRoles, self).__init__(cls)

    def __repr__(self):
        return "{%s}" % ', '.join("%r: %r" % (k, v) for k, v in self.items())

class Action(object):
    """An OCF resource agent action"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, method=None, enabled=True, roles=None):
        self.method = method
        self.enabled = enabled
        self.roles = ActionRoles()
        if roles is not None:
            self.roles.update(roles)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (self.__class__.__name__, self.method,
                                   self.enabled, self.roles)
