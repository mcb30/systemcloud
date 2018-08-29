# systemcloud

systemcloud provides a Python framework for building OCF resource
agents, and a set of OCF resource agents for managing distributed
services as part of a pacemaker+corosync cluster.

## Building

Really, your CI system should do this.

Get the spec file from:

https://git.unipart.io/unipkg/systemcloud

Put it in ~/rpmbuild/SPECS

Download the release tgz into ~/rpmbuild/SOURCES and run rpmbuild:

 rpmbuild -ba SPECS/systemcloud.spec

## Creating Pacemaker Resources

Once installed, you'll need to create resources. If the Erlang Cookie is not synchronised across hosts, you will run into errors. Doing this properly is left as an exercise for the reader.

### RabbitMQ
 [root@node1:~]# pcs resource create rabbitmq ocf:systemcloud:rabbitmq master notify=true master-max=2

### MariaDB+Galera

1. Install systemcloud-galera-0.1-1.el7.centos.noarch.rpm, this will pull in the mariadb packages and default config
2. Create the Galera resource:
 [root@node1:~]# pcs resource create galera_openstack ocf:systemcloud:galera master notify=true master-max=999 galera_openstack-uuid=a1bf1f8c-4452-4b1f-a7f7-20fe1677bb97
