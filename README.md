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
