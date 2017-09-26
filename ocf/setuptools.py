"""Support for OCF resource agents in setuptools"""

from __future__ import absolute_import
import os.path
import textwrap
from pkg_resources import EntryPoint
from setuptools.command.install import install
from setuptools.command.install_scripts import install_scripts
try:
    from setuptools.command.easy_install import ScriptWriter
    get_script_header = ScriptWriter.get_header
except ImportError:
    from setuptools.command.easy_install import get_script_header

AGENTDIR = os.path.join('lib', 'ocf', 'resource.d')


class ResourceAgentInstall(install):
    """Custom install class to add support for OCF resource agents"""
    # pylint: disable=locally-disabled, attribute-defined-outside-init

    user_options = install.user_options + [
        ('install-agents=', None,
         "installation directory for resource agents"),
    ]

    def initialize_options(self):
        install.initialize_options(self)
        self.install_agents = None


class ResourceAgentInstallScripts(install_scripts):
    """Custom install_scripts class to add support for OCF resource agents"""
    # pylint: disable=locally-disabled, attribute-defined-outside-init

    user_options = install_scripts.user_options + [
        ('install-agents=', None,
         "installation directory for resource agents"),
    ]

    agent_template = textwrap.dedent("""
    from %(module)s import %(class)s
    %(method)s()
    """)

    def initialize_options(self):
        install_scripts.initialize_options(self)
        self.install_agents = None
        self.install_agents_base = None

    def finalize_options(self):
        install_scripts.finalize_options(self)
        self.set_undefined_options('install',
                                   ('install_data', 'install_agents_base'),
                                   ('install_agents', 'install_agents'))
        if self.install_agents is None:
            self.install_agents = os.path.join(self.install_agents_base,
                                               AGENTDIR)

    def run(self):
        install_scripts.run(self)
        orig_install_dir = self.install_dir
        self.install_dir = self.install_agents
        eps = EntryPoint.parse_map(self.distribution.entry_points)
        header = get_script_header('')
        for ep in eps.get('resource_agents', {}).values():
            filename = os.path.join(*(ep.name.split('.')))
            contents = header + self.agent_template % {
                'module': ep.module_name,
                'class': ep.attrs[0],
                'method': '.'.join(ep.attrs),
            }
            self.write_script(filename, contents)
        self.install_dir = orig_install_dir
