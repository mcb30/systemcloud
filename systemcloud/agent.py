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

    def action_monitor(self):
        """Monitor resource"""
        self.action_validate()
        try:
            self.systemctl_is_active()
            return ocf.SUCCESS
        except ocf.GenericError:
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
        self.reconfigure()
        output = self.systemctl_start()
        if output:
            self.logger.info(output)
        return ocf.SUCCESS

    def action_stop(self):
        """Stop resource"""
        self.action_validate()
        self.logger.info("Stopping")
        self.reconfigure()
        output = self.systemctl_stop()
        if output:
            self.logger.info(output)
        return ocf.SUCCESS
