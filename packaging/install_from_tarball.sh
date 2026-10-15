#!/bin/bash

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

# Install the innova2-xdma tarball on a distribution without dpkg/rpm.   Run as root, from the unpacked folder.
#
#   sudo ./install.sh            verify root/ against SHA256SUMS, back up what it replaces, copy root/ into /
#   ./install.sh --check         compare the installed files with this tarball; change nothing
#
# The files are exactly those of the .deb/.rpm. Replaced files are saved in /var/backups/innova2-xdma/<date>/.
# Flashing the card is a separate, deliberate step (see the message at the end).
set -eu
HERE=$(dirname "$(readlink -f "$0")")
. "$HERE/IDENTITY.sh"
cd "$HERE/root"

if [ "${1:-}" = --check ]; then
  echo "tarball: $RELEASE (uuid $UUID, ROM_TS $ROM_TS)"
  bad=0
  while read -r sum f; do
    t=/${f#./}
    if [ ! -e "$t" ]; then echo "missing   $t"; bad=1
    elif [ "$(sha256sum "$t" | awk '{print $1}')" != "$sum" ]; then echo "DIFFERENT $t"; bad=1; fi
  done < "$HERE/SHA256SUMS"
  [ $bad = 0 ] && echo "all files installed and identical"; exit 0
fi

[ "$(id -u)" = 0 ] || { echo "*** run as root"; exit 1; }
sha256sum -c --quiet "$HERE/SHA256SUMS" || { echo "*** tarball contents do not match SHA256SUMS -- refusing"; exit 1; }
B=/var/backups/innova2-xdma/$(date +%Y%m%d_%H%M%S)
while read -r sum f; do
  t=/${f#./}
  if [ -e "$t" ] && [ "$(sha256sum "$t" | awk '{print $1}')" != "$sum" ]; then mkdir -p "$B$(dirname "$t")"; cp -a "$t" "$B$t"; fi
done < "$HERE/SHA256SUMS"
# tar, not cp: on merged-/usr systems /lib (and /bin) are symlinks into /usr, and cp -a refuses to replace them with
# directories ("cannot overwrite non-directory '/./lib'"); --keep-directory-symlink follows them instead
tar -cf - . | tar -C / -xf - --keep-directory-symlink --no-same-owner
[ -d "$B" ] && echo "replaced files saved in $B"
cat <<MSG
innova2-xdma ($RELEASE) installed. The card is NOT flashed. To flash a card already running rbds/rbdm/inn2x:
  sudo innova2_flash_user            (--card <mgmt BDF> when there are several cards)
then select the User image and COLD cycle, and validate:  xbutil validate -d <user BDF> -r all
MSG
