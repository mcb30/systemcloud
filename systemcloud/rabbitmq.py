#!/usr/bin/python
"""systemcloud RabbitMQ agent

This agent controls a cluster of RabbitMQ instances, each individually
managed as a normal systemd service on the node.  The agent manages
only the cluster-specific aspects of the service (such as constructing
the cluster_nodes list); all other configuration is performed using
the standard distribution configuration files.

The agent does not modify the standard rabbitmq.config file.  The list
of cluster nodes is passed in via the SERVER_START_ARGS environment
variable.
"""

import os
import stat
from datetime import datetime

import ocf
from systemcloud.agent import ResourceAgent

DEFAULT_SERVICE = "rabbitmq-server.service"
DEFAULT_CONFIG = "/etc/rabbitmq/rabbitmq-systemcloud.conf"

METADATA = """<?xml version="1.0"?>
<!DOCTYPE resource-agent SYSTEM "ra-api-1.dtd">
<resource-agent name="rabbitmq">

  <version>1.0</version>

  <longdesc lang="en">
    Resource script for managing RabbitMQ through systemd
  </longdesc>

  <shortdesc lang="en">
    Manage a RabbitMQ resource
  </shortdesc>

  <parameters>

    <parameter name="service" unique="0" required="0">
      <shortdesc lang="en">
	Underlying RabbitMQ service name
      </shortdesc>
      <content type="string" default="%(service)s" />
    </parameter>

    <parameter name="config" unique="0" required="0">
      <shortdesc lang="en">
	Configuration file fragment path
      </shortdesc>
      <content type="string" default="%(config)s" />
    </parameter>

  </parameters>

  <actions>
    <action name="meta-data" timeout="5" />
    <action name="validate-all" timeout="5" />
    <action name="monitor" interval="20" timeout="30" />
    <action name="notify" timeout="5" />
    <action name="start" timeout="30" />
    <action name="stop" timeout="30" />
  </actions>

</resource-agent>
""" % {
    'service': DEFAULT_SERVICE,
    'config': DEFAULT_CONFIG,
}


class RabbitAgent(ResourceAgent):
    """A RabbitMQ resource agent"""

    metadata = METADATA

    service = ocf.Parameter('service', str, DEFAULT_SERVICE)
    config = ocf.Parameter('config', str, DEFAULT_CONFIG)

    def reconfigure(self):
        """Reconfigure service"""
        cluster_nodes = "{[%s],disc}" % ','.join(
            "'rabbit@%s'" % x for x in self.future_active_unames
        )
        self.logger.info("Cluster nodes: %s", cluster_nodes)
        config = [
            "# Autogenerated by systemcloud - do not edit\n",
            "#\n",
            "# Last regenerated: %s\n" % datetime.now(),
            "#\n",
            "SERVER_START_ARGS=\"-rabbit cluster_nodes %s\"\n" % cluster_nodes,
        ]
        with open(self.config, 'wb') as f:
            f.writelines(config)
            os.fchmod(f.fileno(), (stat.S_IRUSR | stat.S_IWUSR |
                                   stat.S_IRGRP | stat.S_IROTH))

    def action_validate(self):
        """Validate configuration"""
        if not self.meta_notify:
            raise ocf.ConfiguredError("Must have notifications enabled")
        return ocf.SUCCESS
