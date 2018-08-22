# systemcloud

systemcloud provides a Python framework for building OCF resource
agents, and a set of OCF resource agents for managing distributed
services as part of a pacemaker+corosync cluster.

## Creating Pacemaker Resources

### RabbitMQ
 pcs resource create rmq-openstack ocf:systemcloud:rabbitmq master notify=true master-max=2

### MariaDB+Galera
