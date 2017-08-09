"""Cluster resource manager"""

import subprocess
from ocf.constants import ERR_CONFIGURED
from ocf.exceptions import GenericError
from ocf.types import from_ocf, to_ocf


class ClusterResourceManager(object):
    """Cluster resource manager"""

    @staticmethod
    def _crm_attribute(name, node, lifetime, *args):
        """Invoke crm_attribute to query/update/delete attribute

        This should be reimplemented using a native Python API, once
        suitable bindings are available.
        """
        command = ('crm_attribute', '--quiet', '--name', name)
        if node is not None:
            command = command + ('--node', node)
        if lifetime is not None:
            command = command + ('--lifetime', lifetime)
        command = command + args
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT)
            return output.rstrip('\n')
        except subprocess.CalledProcessError as e:
            if e.returncode == ERR_CONFIGURED:
                return None
            raise GenericError(e.output or e.returncode)

    @classmethod
    def query(cls, name, type=str, default=None, node=None, lifetime=None):
        """Query attribute value"""
        # pylint: disable=locally-disabled, redefined-builtin
        # pylint: disable=locally-disabled, too-many-arguments
        value = cls._crm_attribute(name, node, lifetime, '--query')
        if value is None:
            return default
        return from_ocf(value, type)

    @classmethod
    def update(cls, name, value, node=None, lifetime=None):
        """Update attribute value"""
        cls._crm_attribute(name, node, lifetime, '--update', to_ocf(value))

    @classmethod
    def delete(cls, name, node=None, lifetime=None):
        """Delete attribute"""
        cls._crm_attribute(name, node, lifetime, '--delete')
