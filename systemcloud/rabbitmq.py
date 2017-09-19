#!/usr/bin/python
"""systemcloud RabbitMQ agent

This agent controls a cluster of RabbitMQ instances, each individually
managed as a normal systemd service on the node.  The agent manages
only the cluster-specific aspects of the service (such as the cluster
membership); all other configuration is performed using the standard
distribution configuration files.
"""

import re
import subprocess
from collections import namedtuple

import ocf
from systemcloud.agent import BootstrappingAgent

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
    <action name="promote" timeout="300" />
    <action name="demote" timeout="120" />
  </actions>

</resource-agent>
""" % {
    'service': DEFAULT_SERVICE,
    'config': DEFAULT_CONFIG,
}


class RabbitVersion(namedtuple('RabbitVersion', ['major', 'minor'])):
    """RabbitMQ table version number"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __str__(self):
        return '{%d,%d}' % (self.major, self.minor)

EmptyVersion = RabbitVersion(0, 0)


class RabbitState(object):
    """RabbitMQ node state"""
    # pylint: disable=locally-disabled, too-few-public-methods

    @staticmethod
    def _rabbits(string):
        return [x.strip() for x in string.split(',')] if string else []

    def __init__(self, string):
        m = re.match(r'^\s*\{\s*'
                     r'\{\s*(?P<major>\d+)\s*,\s*(?P<minor>\d+)\s*\}\s*,\s*'
                     r'\[\s*(?P<known>.*?)\s*\]\s*,\s*'
                     r'\[\s*(?P<running>.*?)\s*\]\s*\}\s*$', string)
        if not m:
            raise ValueError("Malformed state %s" % string)
        self.version = RabbitVersion(int(m.group('major')),
                                     int(m.group('minor')))
        self.known = self._rabbits(m.group('known'))
        self.running = self._rabbits(m.group('running'))
        if not set(self.running) <= set(self.known):
            raise ValueError("Unknown running nodes in %s", self)

    def __str__(self):
        return '{%s,[%s],[%s]}' % (self.version, ','.join(self.known),
                                   ','.join(self.running))

    def __bool__(self):
        return self.version > EmptyVersion

    __nonzero__ = __bool__


class RabbitAgent(BootstrappingAgent):
    """A RabbitMQ resource agent"""

    metadata = METADATA

    service = ocf.Parameter('service', str, DEFAULT_SERVICE)
    config = ocf.Parameter('config', str, DEFAULT_CONFIG)

    state = ocf.NodeInstanceNameAttribute('state', RabbitState)

    @property
    def rabbit(self):
        """RabbitMQ name for this node"""
        return 'rabbit@%s' % self.node.split('.')[0]

    @property
    def known_rabbits(self):
        """RabbitMQ names for all known nodes

        This property exists only while the application is stopped,
        and so reflects the list as at the state of the most recent
        shutdown (or crash).
        """
        if self.state is not None:
            return self.state.known

    @property
    def running_rabbits(self):
        """RabbitMQ names for all running nodes

        This property exists only while the application is stopped,
        and so reflects the list as at the state of the most recent
        shutdown (or crash).
        """
        if self.state is not None:
            return self.state.running

    @property
    def schema_version(self):
        """Schema version

        This property exists only while the application is stopped,
        and so reflects the version as at the state of the most recent
        shutdown (or crash).
        """
        if self.state is not None:
            return self.state.version

    @staticmethod
    def rabbitmqctl(*args):
        """Perform an action via rabbitmqctl"""
        command = ('rabbitmqctl',) + args
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT)
            return output.rstrip('\n')
        except subprocess.CalledProcessError as e:
            raise ocf.GenericError(e.output or e.returncode)

    def rabbitmqctl_eval(self, erl):
        """Evaluate Erlang code via rabbitmqctl"""
        return self.rabbitmqctl('eval', erl)

    def rabbitmqctl_force_boot(self):
        """Force boot via rabbitmqctl"""
        self.rabbitmqctl('force_boot')

    def rabbitmqctl_forget_cluster_node(self, cluster_node):
        """Forget permanently offline cluster node via rabbitmqctl"""
        self.rabbitmqctl('forget_cluster_node', cluster_node)

    def rabbitmqctl_join_cluster(self, cluster_node):
        """Join cluster via rabbitmqctl"""
        self.rabbitmqctl('join_cluster', cluster_node)

    def rabbitmqctl_reset(self):
        """Reset all state via rabbitmqctl"""
        self.rabbitmqctl('reset')

    def rabbitmqctl_start_app(self):
        """Start application via rabbitmqctl"""
        self.rabbitmqctl('start_app')

    def rabbitmqctl_stop_app(self):
        """Stop application via rabbitmqctl"""
        self.rabbitmqctl('stop_app')

    def rabbitmqctl_update_cluster_nodes(self, cluster_node):
        """Fetch updated cluster definition from a single (sic) node"""
        self.rabbitmqctl('update_cluster_nodes', cluster_node)

    @property
    def app_is_running(self):
        """Check if application is running via rabbitmqctl"""
        return self.rabbitmqctl_eval('rabbit:is_running().') == 'true'

    def read_state(self):
        """Get schema version and cluster nodes via rabbitmqctl"""
        erl = """
        try
            Known = rabbit_mnesia:cluster_nodes(all),
            Running = rabbit_mnesia:cluster_nodes(running),
            mnesia:start(),
            Version = mnesia_schema:version(),
            {Version, Known, Running}
        catch
            throw:{error, {corrupt_or_missing_cluster_files, _, _}} ->
                {{0,0},[],[]}
        after
            mnesia:stop()
        end.
        """
        state = RabbitState(self.rabbitmqctl_eval(erl))
        self.logger.info("State is %s" % state)
        return state

    def ensure_application_loaded(self, application='rabbit'):
        """Ensure that application is loaded"""
        erl = """
        case application:load(%s) of
            ok                           -> ok;
            {error, {already_loaded, _}} -> ok
        end.
        """ % application
        self.rabbitmqctl_eval(erl)

    def ensure_mnesia_dir(self):
        """Ensure that Mnesia database directory exists"""
        self.rabbitmqctl_eval('rabbit_mnesia:ensure_mnesia_dir().')

    def reset_cluster_status(self):
        """Reset cluster status files"""
        self.rabbitmqctl_eval('rabbit_node_monitor:reset_cluster_status().')

    def join(self, rabbit):
        """Join cluster

        This joins a virgin node into a new cluster
        """
        self.logger.info("Joining via %s", rabbit)
        self.ensure_application_loaded()
        self.ensure_mnesia_dir()
        self.reset_cluster_status()
        self.rabbitmqctl_join_cluster(rabbit)

    def rejoin(self, rabbit):
        """Rejoin cluster

        This rejoins a node into its existing cluster (via a possibly
        new cluster peer).
        """
        self.logger.info("Rejoining via %s", rabbit)
        self.ensure_application_loaded()
        self.rabbitmqctl_update_cluster_nodes(rabbit)

    def forget(self, rabbit):
        """Forget cluster peer"""
        self.logger.info("Forgetting %s", rabbit)
        self.rabbitmqctl_forget_cluster_node(rabbit)

    def choose_bootstrap(self):
        """Choose a bootstrap node"""
        peers = self.all_peers
        unreported = [x for x in peers if x.state is None]
        if unreported:
            self.logger.info("Waiting for reported state from %s",
                             ' '.join(x.node for x in unreported))
            return None
        bootstrap = max(peers, key=lambda x: (x.schema_version,
                                              -len(x.running_rabbits),
                                              x.node))
        self.logger.info("Bootstrapping %s" % bootstrap.node)
        return bootstrap

    def service_start(self):
        """Start slave service"""
        # Start service
        self.systemctl_start(self.service)
        # Ensure application is stopped
        if self.app_is_running:
            self.rabbitmqctl_stop_app()
        # Record state
        self.state = self.read_state()

    def master_start(self):
        """Start master service"""
        # Start or join/rejoin cluster as needed
        if self.is_bootstrap:
            if self.state:
                self.logger.info("Forcing boot")
                self.rabbitmqctl_force_boot()
        else:
            master = self.current_master_peers[0]
            if self.state:
                self.rejoin(master.rabbit)
            else:
                self.join(master.rabbit)
        # Start application
        self.rabbitmqctl_start_app()
        # Forget any stale cluster nodes, if applicable
        if self.is_bootstrap:
            old = set(self.known_rabbits)
            new = set(peer.rabbit for peer in self.all_peers)
            forget = (old - new)
            for rabbit in forget:
                self.forget(rabbit)
        # Clear stored state
        del self.state

    def master_stop(self):
        """Stop master service"""
        # Stop application
        if self.app_is_running:
            self.rabbitmqctl_stop_app()
        # Record state
        self.state = self.read_state()

    @property
    def master_is_running(self):
        return self.service_is_running and self.app_is_running
