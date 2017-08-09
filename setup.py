#!/usr/bin/env python
"""Installation script"""

import textwrap
from setuptools import setup
from ocf.setuptools import ResourceAgentInstall, ResourceAgentInstallScripts

setup(
    name="systemcloud",
    version="0.1",
    license="GPLv2+",
    author="Michael Brown",
    author_email="mbrown@fensystems.co.uk",
    description="OCF resource agents for building clustered systemd services",
    long_description=textwrap.dedent("""
    systemcloud provides a Python framework for building OCF resource
    agents, and a set of OCF resource agents for managing distributed
    services as part of a pacemaker+corosync cluster.
    """).lstrip(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved '
        ':: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: System :: Clustering',
        'Topic :: System :: Systems Administration',
    ],
    cmdclass={
        'install': ResourceAgentInstall,
        'install_scripts': ResourceAgentInstallScripts,
    },
    packages=['ocf', 'systemcloud'],
    entry_points={
        'resource_agents': [
        ],
    },
)
