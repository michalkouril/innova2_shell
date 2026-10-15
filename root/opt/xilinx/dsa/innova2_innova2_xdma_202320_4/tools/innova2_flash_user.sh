#!/bin/bash
# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

# innova2_flash_user -- write the installed shell into the User partition of an Innova-2 card, over PCIe.
#
#   sudo innova2_flash_user [--card <mgmt BDF>] [--yes] [--skip-factory-check]
#
# For a card that is ALREADY running an XRT shell with both flash chips wired (rbds, rbdm, inn2x). The image
# written is the one this package installed: /lib/firmware/xilinx/innova2_innova2_xdma_202320_4_{primary,secondary}.mcs.
# It is guard-aware: its payload lands at 0x01000000 (the User slot); Factory (0x0) and Flex (0x03000000) are not
# written. Steps:
#   1. find the card (refuses to guess when there are several);
#   2. READ-ONLY probe: both flash chips must answer RDID with a Micron ID -- older shells (drp ... rbdf) never wired
#      the second chip, and writing from them would leave half an image (they cannot be told apart by ROM timestamp);
#   3. scan the Factory region (0x0..0xFFFFFF, both chips) of THIS card;
#   4. write both chips with XRT's stock xbflash.qspi through the shell's own quad-SPI controller;
#   5. scan Factory again: every block must be unchanged.
# The card keeps running the old image until the next COLD power cycle; select the User image first if needed.
set -u
DIR=$(dirname "$(readlink -f "$0")")
VBNV=innova2_innova2_xdma_202320_4
MCS=/lib/firmware/xilinx/$VBNV
XBFLASH=${XBFLASH:-/opt/xilinx/xrt/bin/xbflash.qspi}
PROBE=$DIR/xbflash.probe
SCAN=$DIR/qspi_scan.py
WORK=${INNOVA2_FLASH_WORK:-/var/tmp/innova2_flash}     # persistent scratch (not /tmp)
CARD=""; YES=0; FACTORY=1
while [ $# -gt 0 ]; do case "$1" in
  --card) CARD=$2; shift 2;; --yes) YES=1; shift;; --skip-factory-check) FACTORY=0; shift;;
  -h|--help) sed -n '/^# innova2_flash_user --/,/^# The card keeps/p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
  *) echo "*** unknown argument $1 (see --help)"; exit 1;; esac; done
die(){ echo "*** $*"; exit 1; }
[ "$(id -u)" = 0 ] || die "run as root"
for f in "$MCS"_primary.mcs "$MCS"_secondary.mcs "$XBFLASH" "$PROBE" "$SCAN"; do [ -e "$f" ] || die "missing $f"; done

# 1. the card: the management PF (10ee:788f) of a running shell
if [ -z "$CARD" ]; then
  mapfile -t C < <(for d in /sys/bus/pci/devices/*; do [ "$(cat $d/vendor)" = 0x10ee ] && [ "$(cat $d/device)" = 0x788f ] && basename $d; done)
  [ ${#C[@]} -eq 0 ] && die "no Innova-2 running an XRT shell found (no 10ee:788f device). A card on the Flex image is flashed with innova2_app's burn menu instead."
  [ ${#C[@]} -gt 1 ] && die "several cards found: ${C[*]} -- choose one with --card <BDF>"
  CARD=${C[0]}
fi
case "$CARD" in *:*:*) ;; *) CARD=0000:$CARD;; esac
D=/sys/bus/pci/devices/$CARD
[ -e "$D/resource0" ] || die "$CARD: not present or no BAR0"
[ "$(cat $D/device)" = 0x788f ] || die "$CARD is not an Innova-2 management PF (10ee:788f)"
INST=$(cat $D/instance 2>/dev/null); FDEV=/dev/xfpga/flash.m$INST.0
BAROFF=$(cat $D/flash.m.*/bar_off 2>/dev/null)
[ -z "$BAROFF" ] || [ "$BAROFF" = 262144 ] || die "$CARD: flash controller at BAR0+$BAROFF, expected 0x40000 -- not an innova2 shell?"
mkdir -p "$WORK"; LOG=$WORK/flash_user_$(echo $CARD | tr : _)_$(date +%Y%m%d_%H%M%S).log
exec > >(tee -a "$LOG") 2>&1
echo "=== innova2_flash_user: card $CARD  image ${MCS}_{primary,secondary}.mcs  log $LOG"
echo "    running shell: $(/opt/xilinx/xrt/bin/xbmgmt examine -d $CARD 2>/dev/null | grep -m1 -oE '\[0000:[^|]*\|[^|]*\|[^|]*\|' | tr -s ' ')"

# 2. read-only probe of both flash chips
echo "### 1. probing both flash chips (read-only)"
P=$(cd "$DIR" && XBFLASH_PROBE_BOTH=1 FLASH_VIA_USER=1 "$PROBE" --primary "$MCS"_primary.mcs --secondary "$MCS"_secondary.mcs \
      --card "$CARD" --bar 0 --bar-offset 0x40000 --force 2>&1)
echo "$P" | grep -E "RDID raw" | sed 's/^/    /'
# match the JEDEC ID bytes only; byte 0 is a command echo that differs between the chips
S0=$(echo "$P" | grep -cE "slave=0 RDID raw = [0-9A-F]{2} 20 BB 20"); S1=$(echo "$P" | grep -cE "slave=1 RDID raw = [0-9A-F]{2} 20 BB 20")
[ "$S0" -ge 1 ] && [ "$S1" -ge 1 ] || die "both flash chips must answer with a Micron ID (chip0=$S0 chip1=$S1). A shell without the second chip wired (drp ... rbdf) must be flashed from the Flex image instead. NOTHING was written."

scan(){ FLASH_DEV=$FDEV python3 "$SCAN" 0x0 0x1000000 0x10000 "$1" 2>&1 | tail -1 | sed 's/^/    /'; [ -s "$1" ]; }
if [ $FACTORY = 1 ]; then
  [ -e "$FDEV" ] || die "no $FDEV for the Factory check (xclmgmt not bound?). Use --skip-factory-check to proceed without it."
  echo "### 2. Factory region scan before writing ($FDEV)"
  scan "$WORK/factory_before.txt" || die "Factory scan failed; nothing written"
fi

# 3. write
if [ $YES = 0 ]; then
  read -r -p "Write the User partition of $CARD now? [y/N] " a; case "$a" in y|Y|yes) ;; *) echo "aborted, nothing written"; exit 1;; esac
fi
echo "### 3. writing both chips (xbflash.qspi, via the shell's quad-SPI controller; a few minutes)"
( cd "$(dirname "$MCS")" && FLASH_VIA_USER=1 "$XBFLASH" --primary "$(basename "$MCS")_primary.mcs" --secondary "$(basename "$MCS")_secondary.mcs" \
    --card "$CARD" --bar 0 --bar-offset 0x40000 --force ) 2>&1 | grep -vE "^\s*$" | sed 's/^/    /'
[ "${PIPESTATUS[0]}" = 0 ] || die "xbflash.qspi failed -- do NOT power cycle into this image; re-run, or recover from the Flex image"

# 4. Factory must be untouched
if [ $FACTORY = 1 ]; then
  echo "### 4. Factory region scan after writing"
  scan "$WORK/factory_after.txt" || die "Factory scan after writing failed -- verify before power cycling"
  N=$(python3 -c "
import sys
L=lambda p:{(a,b):c for a,b,c,*_ in (l.split() for l in open(p))}
a,b=L(sys.argv[1]),L(sys.argv[2]); print(sum(1 for k in a if a[k]!=b.get(k)), len(a))" "$WORK/factory_before.txt" "$WORK/factory_after.txt")
  set -- $N
  [ "$1" = 0 ] && echo "    Factory unchanged: 0 of $2 blocks differ" || die "Factory CHANGED: $1 of $2 blocks differ -- stop and inspect before power cycling"
fi
echo "FLASH-USER-DONE: the User partition of $CARD holds $VBNV ($(basename "$MCS")_*.mcs)."
echo "Next: make sure the User image is selected (innova2_app -d <ConnectX BDF> --batch image-sel user),"
echo "then COLD cycle the host (power off, then on). The FPGA reads flash only at power-on."
