"""systemcloud resource agents"""

import subprocess
import ocf


class ResourceAgent(ocf.ResourceAgent):
    """A resource agent for a systemd service"""

    @property
    def service(self):
        """Service name"""
        raise NotImplementedError

    def reconfigure(self):
        """Reconfigure service

        This will be called on every start, stop, promote, demote, or
        notify action.
        """
        pass

    def systemctl(self, action, unit=None):
        """Perform an action via systemctl"""
        if unit is None:
            unit = self.service
        command = ('systemctl', action, unit)
        try:
            output = subprocess.check_output(command, stderr=subprocess.STDOUT)
            return output.rstrip('\n')
        except subprocess.CalledProcessError as e:
            raise ocf.GenericError(e.output or e.returncode)

    def systemctl_is_active(self, unit=None):
        """Check activity of a service via systemctl"""
        return self.systemctl('is-active', unit)

    def systemctl_status(self, unit=None):
        """Get service status via systemctl"""
        return self.systemctl('status', unit)

    def systemctl_start(self, unit=None):
        """Start a service via systemctl"""
        return self.systemctl('start', unit)

    def systemctl_stop(self, unit=None):
        """Stop a service via systemctl"""
        return self.systemctl('stop', unit)

    def service_start(self):
        """Start service"""
        self.systemctl_start(self.service)

    def service_stop(self):
        """Stop service"""
        self.systemctl_stop(self.service)

    @property
    def service_is_running(self):
        """Check if service is running"""
        try:
            self.systemctl_is_active(self.service)
            return True
        except ocf.GenericError:
            return False

    def action_monitor(self):
        """Monitor resource"""
        self.action_validate()
        if self.service_is_running:
            return ocf.SUCCESS
        else:
            return ocf.NOT_RUNNING

    def action_notify(self):
        """Notify resource of changes"""
        notification = self.notification
        self.logger.info("Notifying %s: %s", notification,
                         ','.join(notification.unames))
        self.reconfigure()
        return ocf.SUCCESS

    def action_start(self):
        """Start resource"""
        self.logger.info("Starting")
        if self.service_is_running:
            self.service_stop()
        self.reconfigure()
        self.service_start()
        return ocf.SUCCESS

    def action_stop(self):
        """Stop resource"""
        self.logger.info("Stopping")
        self.action_validate()
        self.reconfigure()
        self.service_stop()
        return ocf.SUCCESS


class MultiStateResourceAgent(ResourceAgent):
    """A multi-state (master-slave) resource agent for a systemd service"""
    # pylint: disable=locally-disabled, abstract-method

    @property
    def master_service(self):
        """Master service name"""
        return self.service

    def master_start(self):
        """Start master service"""
        self.systemctl_start(self.master_service)

    def master_stop(self):
        """Stop master service"""
        self.systemctl_stop(self.master_service)

    @property
    def master_is_running(self):
        """Check if master service is running"""
        try:
            self.systemctl_is_active(self.master_service)
            return True
        except ocf.GenericError:
            return False

    def action_validate(self):
        """Validate configuration"""
        if not self.is_master_slave:
            raise ocf.ConfiguredError("Must be a master/slave resource")
        if not self.meta_notify:
            raise ocf.ConfiguredError("Must have notifications enabled")
        if self.meta_master_node_max > 1:
            raise ocf.ConfiguredError("Must have only one master per node")
        if self.meta_master_max <= 1:
            raise ocf.ConfiguredError("Must have more than one master")
        return ocf.SUCCESS

    def action_monitor(self):
        """Monitor resource"""
        self.action_validate()
        if self.service_is_running:
            if self.master_is_running:
                return ocf.RUNNING_MASTER
            else:
                return ocf.SUCCESS
        else:
            return ocf.NOT_RUNNING

    def action_promote(self):
        """Promote resource"""
        self.logger.info("Promoting")
        if self.master_is_running:
            self.master_stop()
        self.reconfigure()
        self.master_start()
        return ocf.SUCCESS

    def action_demote(self):
        """Demote resource"""
        self.logger.info("Demoting")
        self.reconfigure()
        self.master_stop()
        return ocf.SUCCESS


class BootstrappingAgent(MultiStateResourceAgent):
    """A resource agent using a bootstrap node"""
    # pylint: disable=locally-disabled, abstract-method

    started = ocf.NodeInstanceNameAttribute('started', bool, lifetime='reboot')

    @property
    def is_bootstrap(self):
        """Check if this is the bootstrap node"""
        return (not self.meta_notify_master_unames and
                self.node in self.meta_notify_promote_unames)

    def choose_bootstrap(self):
        """Choose bootstrap node"""
        raise NotImplementedError

    def trigger_promote_bootstrap(self):
        """Trigger promotion of bootstrap node (if any)"""
        bootstrap = self.choose_bootstrap()
        if bootstrap:
            self.logger.info("Triggering promotion of %s", bootstrap.node)
            bootstrap.trigger_promote()

    def trigger_promote_all(self):
        """Trigger promotion of all other nodes"""
        self.logger.info("Triggering promotion of all peers")
        for peer in self.meta_notify_all_peers:
            if peer != self:
                peer.trigger_promote()

    def action_monitor(self):
        """Monitor resource"""
        self.action_validate()
        # Check for the explicit "started" attribute (with reboot
        # lifetime) to ensure that the node has gone through the
        # normal start/promote sequence
        if not self.started:
            return ocf.NOT_RUNNING
        # Get service status
        status = super(BootstrappingAgent, self).action_monitor()
        # If we are still waiting for bootstrapping to complete, then
        # redo the bootstrap calculation to pick up any changes to the
        # cluster topology.  Do not allow bootstrapping recalculation
        # to break status monitoring
        if status == ocf.SUCCESS:
            # pylint: disable=locally-disabled, broad-except
            try:
                self.trigger_promote_bootstrap()
            except Exception as e:
                self.logger.exception(str(e))
        return status

    def action_start(self):
        """Start resource"""
        # Start slave service
        super(BootstrappingAgent, self).action_start()
        # Prevent automatic promotion on restart
        self.trigger_demote()
        # Join existing cluster or bootstrap new cluster, as applicable
        if self.current_master_unames:
            self.logger.info("Triggering promotion")
            self.trigger_promote()
        else:
            self.trigger_promote_bootstrap()
        # Record as started
        self.started = True
        return ocf.SUCCESS

    def action_promote(self):
        """Promote resource"""
        # Start master service
        super(BootstrappingAgent, self).action_promote()
        # Trigger promotion of all remaining nodes, if applicable
        if self.is_bootstrap:
            self.trigger_promote_all()
        return ocf.SUCCESS

    def action_stop(self):
        """Stop resource"""
        # Stop slave service
        super(BootstrappingAgent, self).action_stop()
        # Record as not started
        del self.started
        return ocf.SUCCESS
