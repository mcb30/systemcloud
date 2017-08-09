"""OCF types"""


def from_ocf(value, type):
    """Convert value from an OCF string variable"""
    # pylint: disable=locally-disabled, redefined-builtin
    interpreters = {
        bool: lambda x: x.lower() in ('yes', 'true', 'on', '1', 'ja'),
        list: lambda x: x.split(),
    }
    return interpreters.get(type, type)(value)


def to_ocf(value):
    """Convert value to an OCF string variable"""
    interpreters = {
        bool: int,
        list: ' '.join,
    }
    return str(interpreters.get(value.__class__, lambda x: x)(value))
