%global srcname systemcloud
%global agentdir /usr/lib/ocf/resource.d/%{srcname}
%global unitdir /usr/lib/systemd/system

%if 0%{?fedora}
%define with_py3 1
%endif

Name:		{{{ git_dir_name }}}
Version:	{{{ git_dir_version }}}
Release:	1%{?dist}
Summary:	OCF resource agents for building clustered systemd services
License:	GPLv2+
URL:		http://github.com/mcb30/%{srcname}
VCS:		{{{ git_dir_vcs }}}
Source:		{{{ git_dir_pack }}}
BuildArch:	noarch
%if 0%{?fedora}
BuildRequires:	python2-devel python3-devel
BuildRequires:	python2-setuptools python3-setuptools
BuildRequires:	python2-lxml python3-lxml
%endif
%if 0%{?rhel}
BuildRequires:	python-devel
BuildRequires:	python-setuptools
BuildRequires:	python-lxml
%endif
%if 0%{?with_py3}
Requires:	python3-%{srcname} == %{version}-%{release}
%else
Requires:	python2-%{srcname} == %{version}-%{release}
%endif
Requires:	pacemaker
Requires:	corosync

%description
systemcloud provides a Python framework for building OCF resource
agents, and a set of OCF resource agents for managing distributed
services as part of a pacemaker+corosync cluster.

%package -n %{srcname}-galera
Summary:	systemcloud resource agent for MariaDB Galera
Requires:	%{srcname} == %{version}-%{release}
Requires:	mariadb-server-galera

%description -n %{srcname}-galera
systemcloud resource agent for MariaDB Galera

%package -n %{srcname}-rabbitmq
Summary:	systemcloud resource agent for RabbitMQ
Requires:	%{srcname} == %{version}-%{release}
Requires:	rabbitmq-server

%description -n %{srcname}-rabbitmq
systemcloud resource agent for RabbitMQ

%package -n python2-%{srcname}
Summary:	OCF resource agents for building clustered systemd services
%{?python_provide:%python_provide python2-%{srcname}}

%description -n python2-%{srcname}
systemcloud provides a Python framework for building OCF resource
agents, and a set of OCF resource agents for managing distributed
services as part of a pacemaker+corosync cluster.

%if 0%{?with_py3}
%package -n python3-%{srcname}
Summary:	OCF resource agents for building clustered systemd services
%{?python_provide:%python_provide python3-%{srcname}}
%endif

%if 0%{?with_py3}
%description -n python3-%{srcname}
systemcloud provides a Python framework for building OCF resource
agents, and a set of OCF resource agents for managing distributed
services as part of a pacemaker+corosync cluster.
%endif

%prep
%autosetup -n %{srcname}-%{version}

%build
%py2_build
%{?with_py3:%py3_build}

%install
%py2_install
%{?with_py3:%py3_install}

%files
%{_libexecdir}/systemcloud-check-freshness

%files -n %{srcname}-galera
%{agentdir}/galera
%{unitdir}/mariadb.service.d/systemcloud-common.conf

%files -n %{srcname}-rabbitmq
%{agentdir}/rabbitmq
%{unitdir}/rabbitmq-server.service.d/systemcloud-common.conf
%{unitdir}/rabbitmq-server.service.d/systemcloud.conf
%{_sysconfdir}/rabbitmq/rabbitmq-systemcloud.conf

%files -n python2-%{srcname}
%license COPYING
%doc README.rst
%{python2_sitelib}/*

%if 0%{?with_py3}
%files -n python3-%{srcname}
%license COPYING
%doc README.rst
%{python3_sitelib}/*
%endif

%changelog
{{{ git_dir_changelog }}}
