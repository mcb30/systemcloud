"""OCF exceptions"""

import sys
import ocf.constants

class OcfError(Exception):
    """An OCF error"""

    exit_rc = ocf.constants.ERR_GENERIC

    def exit(self):
        """Exit and report exit reason"""
        lines = (x for x in str(self).split('\n') if x)
        sys.stderr.write('ocf-exit-reason:%s\n' % ' | '.join(lines))
        sys.exit(self.exit_rc)

class GenericError(OcfError):
    """Generic or unspecified error"""
    exit_rc = ocf.constants.ERR_GENERIC

class UnimplementedError(OcfError):
    """Unimplemented feature"""
    exit_rc = ocf.constants.ERR_UNIMPLEMENTED

class PermError(OcfError):
    """User had insufficient privilege"""
    exit_rc = ocf.constants.ERR_PERM

class InstalledError(OcfError):
    """Program is not installed"""
    exit_rc = ocf.constants.ERR_INSTALLED

class ConfiguredError(OcfError):
    """Program is not configured"""
    exit_rc = ocf.constants.ERR_CONFIGURED
