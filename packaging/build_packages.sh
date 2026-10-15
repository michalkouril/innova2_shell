#!/bin/bash

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

# Build the release artifacts of the innova2 deployment package from root/:
#   dist/innova2-xdma_<ver>-<rel>_all.deb      Debian/Ubuntu
#   dist/innova2-xdma-<ver>-<rel>.noarch.rpm   RHEL/Rocky/Fedora
#   dist/innova2-xdma-<ver>-<rel>.tar.gz       anything else: root/ tree + install script
#   dist/SHA256SUMS
# Needs dpkg-deb, fakeroot (optional) and rpmbuild.   usage: packaging/build_packages.sh
#   MAINTAINER="Name <email>" sets the maintainer field (default: Michal Kouril <xmkouril@gmail.com>).
set -eu
REPO=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
. "$REPO/packaging/IDENTITY.sh"; . "$REPO/packaging/VERSION"
NAME=innova2-xdma
MAINTAINER=${MAINTAINER:-"Michal Kouril <xmkouril@gmail.com>"}
DIST=$REPO/dist; rm -rf "$DIST"; mkdir -p "$DIST"
W=$DIST/.work; mkdir -p "$W"; trap 'rm -rf "$W"' EXIT      # inside the repo (git-ignored), never /tmp
SUMMARY="Innova-2 XDMA shell $RELEASE: boot firmware, flash images, validate kernels"
DESC="Deployment package for the Mellanox Innova-2 Flex card running the inn2x XRT shell
(platform $VBNV, interface UUID $UUID, ROM timestamp $ROM_TS). Installs the boot xsabin xclmgmt loads,
the User-slot flash images, the xbutil validate kernels and the DDR mode tool. Flashing the card is a
separate, deliberate step (see the post-install message)."
POSTMSG="innova2-xdma $PKGVER-$PKGREL ($RELEASE) installed.
The card is NOT flashed by this package. To flash a card already running rbds/rbdm/inn2x:
  sudo innova2_flash_user            (--card <mgmt BDF> when there are several cards)
It probes both flash chips, writes the User partition and checks Factory is unchanged.
Then select the User image and COLD cycle.
Validate afterwards:  xbutil validate -d <user BDF> -r all"

# ---- stage: the payload exactly as it lands on the host
ST=$W/stage; mkdir -p "$ST"; cp -a "$REPO/root/." "$ST/"
mkdir -p "$ST/opt/xilinx/dsa/$VBNV/doc"; cp -a "$REPO/README.md" "$ST/opt/xilinx/dsa/$VBNV/doc/README.md"   # /usr/share/doc may be path-excluded by dpkg
find "$ST" -type d -exec chmod 0755 {} +; find "$ST" -type f -exec chmod 0644 {} +
find "$ST" -type f \( -name "*.py" -o -name "*.sh" -o -name "xbflash.probe" \) -exec chmod 0755 {} +
( cd "$ST" && find . -type f -print0 | sort -z | xargs -0 sha256sum ) > "$W/payload.sha256"
( cd "$ST" && find . -type f -o -type l ) | sed 's#^\.##' | sort > "$W/files.txt"
# directories this package owns (so rpm -e removes them); shared system/XRT directories are left alone
( cd "$ST" && find . -mindepth 1 -type d ) | sed 's#^\.##' | sort \
  | grep -vxE '/lib|/lib/firmware|/lib/firmware/xilinx|/opt|/opt/xilinx|/opt/xilinx/dsa|/opt/xilinx/platforms|/usr|/usr/bin|/usr/share|/usr/share/doc' > "$W/dirs.txt"

# ---- .deb
D=$W/deb; mkdir -p "$D"; cp -a "$ST/." "$D/"; mkdir -p "$D/DEBIAN"
cat > "$D/DEBIAN/control" <<EOF
Package: $NAME
Version: $PKGVER-$PKGREL
Architecture: all
Maintainer: $MAINTAINER
Depends: xrt (>= 2.17)
Section: devel
Priority: optional
Description: $SUMMARY
$(sed 's/^/ /' <<<"$DESC")
EOF
printf '#!/bin/sh\ncat <<"MSG"\n%s\nMSG\nexit 0\n' "$POSTMSG" > "$D/DEBIAN/postinst"; chmod 0755 "$D/DEBIAN/postinst"
( cd "$D" && find . -path ./DEBIAN -prune -o -type f -print0 | xargs -0 md5sum | sed 's#  \./#  #' ) > "$D/DEBIAN/md5sums"
dpkg-deb --root-owner-group -Zxz --build "$D" "$DIST/${NAME}_${PKGVER}-${PKGREL}_all.deb" >/dev/null

# ---- .rpm
R=$W/rpm; mkdir -p "$R"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}
{
  # tools/xbflash.probe is an x86-64 ELF (the flash-ID probe innova2_flash_user runs first). XRT, which this package
  # needs, exists only for x86-64, so a noarch package carrying it is still correct in practice.
  echo "%define _binaries_in_noarch_packages_terminate_build 0"
  echo "Name: $NAME"; echo "Version: $PKGVER"; echo "Release: $PKGREL"; echo "Summary: $SUMMARY"
  echo "License: Apache-2.0 AND LicenseRef-AMD-IP"
  echo "BuildArch: noarch"; echo "Requires: xrt >= 2.17"; echo "AutoReqProv: no"
  echo "%description"; echo "$DESC"
  echo "%install"; echo "mkdir -p %{buildroot}"; echo "cp -a $ST/. %{buildroot}/"
  echo "%post"; echo "cat <<'MSG'"; echo "$POSTMSG"; echo "MSG"
  echo "%files"; sed 's#^#%dir "#; s#$#"#' "$W/dirs.txt"; sed 's#^#"#; s#$#"#' "$W/files.txt"
} > "$R/SPECS/$NAME.spec"
rpmbuild --quiet --define "_topdir $R" --define "_build_id_links none" --define "__os_install_post %{nil}" -bb "$R/SPECS/$NAME.spec"
cp "$R"/RPMS/noarch/*.rpm "$DIST/"

# ---- .tar.gz: the tree + installer + manifest, for distributions without dpkg/rpm
T=$W/tar/$NAME-$PKGVER-$PKGREL; mkdir -p "$T"; cp -a "$ST" "$T/root"
cp "$REPO/packaging/install_from_tarball.sh" "$T/install.sh"; cp "$REPO/packaging/IDENTITY.sh" "$T/"; cp "$REPO/README.md" "$T/"
cp "$W/payload.sha256" "$T/SHA256SUMS"
tar -C "$W/tar" -czf "$DIST/$NAME-$PKGVER-$PKGREL.tar.gz" "$NAME-$PKGVER-$PKGREL"

rm -rf "$W"; trap - EXIT
( cd "$DIST" && sha256sum *.deb *.rpm *.tar.gz ) > "$DIST/SHA256SUMS"
ls -la "$DIST"
