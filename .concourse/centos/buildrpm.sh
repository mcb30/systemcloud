#!/usr/bin/env bash
# Cargo-culted and adapted from https://github.com/drahnr/oregano
set -x
set -e

pwd 2>&1
RPMBUILD_DIR="$(pwd)/${1}/rpmbuild"

#mkdir -p ${RPMBUILD_DIR}/{SOURCES,BUILD,RPMS,SRPMS,SPECS}
#cp -v systemcloud.spec ${RPMBUILD_DIR}/SPECS/
#cp -v oregano*.tar.xz ${RPMBUILD_DIR}/SOURCES/

cd ${RPMBUILD_DIR}

rpmbuild \
--define "_topdir %(pwd)" \
--define "_builddir %{_topdir}/BUILD" \
--define "_rpmdir %{_topdir}/RPMS" \
--define "_srcrpmdir %{_topdir}/SRPMS" \
--define "_specdir %{_topdir}/SPECS" \
--define "_sourcedir  %{_topdir}/SOURCES" \
-ba SPECS/systemcloud.spec || exit 1

#mkdir -p $(pwd)/${1}/{,s}rpm/
#rm -vf ${RPMBUILD_DIR}/RPMS/x86_64/systemcloud-*debug*.rpm
#cp -vf ${RPMBUILD_DIR}/RPMS/x86_64/systemcloud-*.rpm $(pwd)/${1}/rpm/
#cp -vf ${RPMBUILD_DIR}/SRPMS/systemcloud-*.src.rpm $(pwd)/${1}/srpm/
