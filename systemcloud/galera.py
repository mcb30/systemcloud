#!/usr/bin/python
"""systemcloud Galera agent

This agent controls a cluster of Galera instances, each individually
managed as a normal systemd service on the node.  The agent manages
only the cluster-specific aspects of the service (such as constructing
the wsrep_cluster_address and controlling the bootstrap sequence); all
other configuration is performed using the standard distribution
configuration files found in /etc/my.cnf.d/*.cnf.

The agent maintains the following cluster attributes:

* Cluster-wide attributes:

  **<instance>-uuid**
    This is the Galera cluster UUID.  It is used to prevent mismatched
    nodes from attempting to join the wrong cluster (which could
    result in silent data loss).

* Per-node attributes:

  **<instance>-state**

    This is the Galera state UUID and sequence number, as extracted
    from the *grastate.dat* file on the node (or from the post-crash
    recovery process).

    A UUID consisting of all zeros indicates a new node that has not
    yet joined the cluster for the first time.

    A seqno of zero indicates a new node with a database that does not
    yet contain any committed transactions.

    A seqno of minus one indicates a node that is either currently
    running, or has crashed without being able to write out an updated
    *grastate.dat* file.

  **<instance>-started**

    This flag indicates that the instance has been started on this
    node.

  **master-<instance>**

    This is the master score for the node.  It is maintained
    automatically by the agent in order to trigger the correct
    sequence for bootstrapping the cluster.

Note that the "slave" state is used only to determine the per-node
attributes and to select a bootstrap node.  The bootstrap node will be
promoted to become the first master node, and will then promote all
remaining nodes.  The underlying database service is running and ready
to accept connections only once the node is in the "master" state.

"""

import os
import re
import stat
from datetime import datetime
from uuid import UUID, uuid4

import ocf
from systemcloud.agent import BootstrappingAgent

ZERO_UUID_STRING = str(UUID(int=0))

DEFAULT_SERVICE = "mariadb.service"
DEFAULT_CONFIG = "/etc/my.cnf.d/mysql-systemcloud.cnf"
DEFAULT_DATADIR = "/var/lib/mysql"

METADATA = """<?xml version="1.0"?>
<!DOCTYPE resource-agent SYSTEM "ra-api-1.dtd">
<resource-agent name="galera">

  <version>1.0</version>

  <longdesc lang="en">
    Resource script for managing Galera through systemd
  </longdesc>

  <shortdesc lang="en">
    Manage a Galera resource
  </shortdesc>

  <parameters>

    <parameter name="service" unique="0" required="0">
      <shortdesc lang="en">
	Underlying database service name
      </shortdesc>
      <content type="string" default="%(service)s" />
    </parameter>

    <parameter name="config" unique="0" required="0">
      <shortdesc lang="en">
	Configuration file path
      </shortdesc>
      <content type="string" default="%(config)s" />
    </parameter>

    <parameter name="datadir" unique="0" required="0">
      <shortdesc lang="en">
	Data directory
      </shortdesc>
      <content type="string" default="%(datadir)s" />
    </parameter>

  </parameters>

  <actions>
    <action name="meta-data" timeout="5" />
    <action name="validate-all" timeout="5" />
    <action name="monitor" interval="20" timeout="30" />
    <action name="monitor" interval="10" timeout="30" role="Master" />
    <action name="monitor" interval="30" timeout="30" role="Slave" />
    <action name="notify" timeout="5" />
    <action name="start" timeout="120" />
    <action name="stop" timeout="120" />
    <action name="promote" timeout="300" />
    <action name="demote" timeout="120" />
  </actions>

</resource-agent>
""" % {
    'service': DEFAULT_SERVICE,
    'config': DEFAULT_CONFIG,
    'datadir': DEFAULT_DATADIR,
}


class GaleraState(object):
    """Galera database state"""
    # pylint: disable=locally-disabled, too-few-public-methods

    def __init__(self, string=None, uuid=None, seqno=None):
        if string is not None:
            try:
                (uuid, seqno) = string.split(':')
            except ValueError:
                raise ValueError("Malformed state %s" % string)
        try:
            UUID(uuid)
            self.uuid = uuid
        except ValueError:
            raise ValueError("Malformed UUID %s" % uuid)
        try:
            self.seqno = int(seqno)
        except ValueError:
            raise ValueError("Malformed sequence number %s" % seqno)
        # Work around an apparent Galera bug
        if self.seqno == ((1 << 64) - 1):
            self.seqno = -1

    def __str__(self):
        return '%s:%d' % (self.uuid, self.seqno)

    def __bool__(self):
        return self.seqno != -1

    __nonzero__ = __bool__


class GaleraAgent(BootstrappingAgent):
    """A Galera resource agent"""

    metadata = METADATA

    service = ocf.Parameter('service', str, DEFAULT_SERVICE)
    config = ocf.Parameter('config', str, DEFAULT_CONFIG)
    datadir = ocf.Parameter('datadir', str, DEFAULT_DATADIR)

    cluster_uuid = ocf.InstanceNameAttribute('uuid', str)
    state = ocf.NodeInstanceNameAttribute('state', GaleraState)

    @property
    def my_cnf_d_file(self):
        """MySQL configuration fragment file path"""
        return self.config

    @property
    def grastate_file(self):
        """Galera state file path"""
        return os.path.join(self.datadir, 'grastate.dat')

    @property
    def uuid(self):
        """Galera state UUID"""
        if self.state is not None:
            return self.state.uuid

    @property
    def seqno(self):
        """Commit sequence number"""
        if self.state is not None:
            return self.state.seqno

    def reconfigure(self, wsrep_recovery_log=None):
        """Reconfigure service"""
        # pylint: disable=locally-disabled, arguments-differ
        masters = self.current_master_unames
        promoting = self.meta_name == 'promote'
        wsrep_peers = (masters if promoting or self.node in masters
                       else ('--NOT-ALLOWED--',))
        config = [
            "# Autogenerated by systemcloud - do not edit\n",
            "#\n",
            "# Last regenerated: %s\n" % datetime.now(),
            "#\n",
            "# This node: %s\n" % self.node,
            "# All nodes: %s\n" % ' '.join(self.meta_notify_all_unames),
            "# Master nodes: %s\n" % ' '.join(masters),
            "#\n",
            "[mysqld]\n",
            "wsrep_cluster_address=gcomm://%s\n" % ','.join(wsrep_peers),
        ]
        if self.state:
            config.extend((
                "wsrep_start_position=%s\n" % self.state,
            ))
        if wsrep_recovery_log is not None:
            config.extend((
                "wsrep_recover=on\n",
                "log_error=%s" % wsrep_recovery_log,
            ))
        with open(self.my_cnf_d_file, 'wb') as f:
            f.writelines(config)
            os.fchmod(f.fileno(), (stat.S_IRUSR | stat.S_IWUSR |
                                   stat.S_IRGRP | stat.S_IROTH))
        if promoting and not masters:
            self.force_safe_to_bootstrap()

    def force_safe_to_bootstrap(self):
        """Update Galera state file to set safe_to_bootstrap flag

        Override a "safe_to_bootstrap: 0" within the Galera state
        file, to allow Galera to start up as a new cluster.  The file
        is modified in place to preserve ownership, permissions,
        selinux contexts, and other metadata.

        If the file does not exist then it will not be created, since
        a nonexistent file acts as an implicit "safe_to_bootstrap: 1"
        anyway.
        """
        try:
            f = open(self.grastate_file, 'r+b')
        except IOError:
            return
        with f:
            while True:
                pos = f.tell()
                line = f.readline()
                if not line:
                    break
                (line, changed) = re.subn(r'^\s*safe_to_bootstrap:\s*(\S+)\s*$',
                                          lambda m: '1'.ljust(len(m.group(0))),
                                          line)
                if changed:
                    f.seek(pos)
                    f.write(line)
                    break

    def read_grastate(self):
        """Read state from Galera state file"""
        raw = {}
        try:
            f = open(self.grastate_file, 'rb')
        except IOError:
            self.logger.error("Missing state file %s" % self.grastate_file)
            return None
        with f:
            for lineno, line in enumerate(f, start=1):
                if re.match(r'^\s*(#.*)?$', line):
                    continue
                m = re.match(r'^\s*(?P<key>\w+):\s*(?P<value>.*?)\s*$', line)
                if not m:
                    raise ocf.GenericError("Corrupt %s on line %d" %
                                           (self.grastate_file, lineno))
                raw[m.group('key')] = m.group('value')
        uuid = raw.get('uuid')
        seqno = raw.get('seqno')
        if uuid is None:
            raise ocf.GenericError("Missing UUID in %s" % self.grastate_file)
        if seqno is None:
            raise ocf.GenericError("Missing sequence number in %s" %
                                   self.grastate_file)
        try:
            state = GaleraState(uuid=uuid, seqno=seqno)
        except ValueError as e:
            raise ocf.GenericError("%s in %s" % (str(e), self.grastate_file))
        self.logger.info("Found %s in %s", state, self.grastate_file)
        return state

    def recover_grastate(self):
        """Recover UUID and sequence number

        There is no clean way to recover the database state (i.e. UUID
        and sequence number).  The only viable way to retrieve this
        information is by parsing the log created from running with
        wsrep_recover=on.
        """
        logfile = os.path.join(self.datadir, 'wsrep-recovery-%s.log' % uuid4())
        self.logger.info("Attempting recovery to %s", logfile)
        self.reconfigure(wsrep_recovery_log=logfile)
        self.systemctl_start(self.service)
        # Service should have stopped immediately after performing
        # recovery, but force a stop just in case.
        self.systemctl_stop(self.service)
        pattern = re.compile(r'^.*Recovered position:\s*(?P<state>\S+)$')
        with open(logfile, 'rb') as f:
            try:
                m = next(m for m in (pattern.match(line) for line in f) if m)
            except StopIteration:
                raise ocf.GenericError("Recovery failed: see %s" % logfile)
        try:
            state = GaleraState(m.group('state'))
        except ValueError as e:
            raise ocf.GenericError("%s: see %s" % (str(e), logfile))
        self.logger.info("Recovered %s from %s", state, logfile)
        os.remove(logfile)
        return state

    def choose_bootstrap(self):
        """Choose a bootstrap node

        Choose a bootstrap node based on the highest recorded commit
        sequence number.  A bootstrap node will be selected only once
        all nodes have recorded their commit sequence numbers.

        If multiple bootstrap nodes have the same highest commit
        sequence number, then the node name will be used as a
        tie-breaker to ensure that the same choice is made when
        multiple nodes execute this code in parallel.
        """
        peers = self.meta_notify_all_peers
        unreported = [x for x in peers if x.state is None]
        if unreported:
            self.logger.info("Waiting for reported state from %s",
                             ' '.join(x.node for x in unreported))
            return None
        if self.cluster_uuid is not None:
            uuid = self.cluster_uuid
            self.logger.info("Cluster UUID is %s", uuid)
        else:
            uuids = set(x.uuid for x in peers if x.uuid != ZERO_UUID_STRING)
            if len(uuids) > 1:
                raise ocf.ConfiguredError("Multiple UUIDs in new cluster")
            uuid = (uuids.pop() if uuids else ZERO_UUID_STRING)
            self.logger.info("Assuming new cluster UUID %s", uuid)
        members = [x for x in peers if x.uuid == uuid]
        if not members:
            raise ocf.ConfiguredError("No peers match cluster UUID %s", uuid)
        if uuid != ZERO_UUID_STRING:
            unknown = [x for x in members if not x.state]
            if unknown:
                self.logger.info("Waiting for known state from %s",
                                 ' '.join(x.node for x in unknown))
                return None
        bootstrap = max(members, key=lambda x: (x.seqno, x.node))
        self.logger.info("Bootstrapping %s" % bootstrap.node)
        return bootstrap

    def service_start(self):
        """Start slave service"""
        # Record state parameters (performing recovery if needed)
        self.state = self.read_grastate() or self.recover_grastate()
        # Check that UUID matches cluster UUID, if already set
        if self.cluster_uuid is not None:
            if self.uuid not in (ZERO_UUID_STRING, self.cluster_uuid):
                raise ocf.GenericError("UUID does not match cluster UUID")

    @property
    def service_is_running(self):
        """Check is slave service is running"""
        # Nothing actually runs while in the slave state
        return self.started

    def master_start(self):
        """Start master service"""
        # Check that UUID matches cluster UUID, if already set
        if self.cluster_uuid is not None:
            if self.uuid not in (ZERO_UUID_STRING, self.cluster_uuid):
                raise ocf.GenericError("UUID does not match cluster UUID")
        # Start service (in normal mode)
        self.logger.info("Beginning at %s", self.state)
        self.systemctl_start(self.service)
        # Validate and update recorded state
        state = self.read_grastate()
        if state is None:
            raise ocf.GenericError("Unable to determine state after promotion")
        if self.uuid not in (ZERO_UUID_STRING, state.uuid):
            raise ocf.GenericError("UUID changed unexpectedly after promotion")
        self.state = state
        # Record cluster UUID if not already set
        if self.cluster_uuid is None:
            self.logger.info("Set new cluster UUID %s", self.uuid)
            self.cluster_uuid = self.uuid

    def master_stop(self):
        """Stop master service"""
        # Stop service
        self.systemctl_stop(self.service)
        # Record state parameters
        state = self.read_grastate()
        if state is not None:
            self.state = state
