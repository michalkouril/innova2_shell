#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

"""READ-ONLY flash scanner. Dumps per-block SHA1 over a range, both slaves.
Usage: qspi_scan.py <start_hex> <end_hex> <blocksize_hex> [outfile]
Writes "slave off sha1" lines. Nothing is written to flash (O_RDONLY)."""
import os, sys, hashlib, time
# The flash subdev node is named after the mgmt subdevice's id, which CHANGES with the shell
# (flash.m3584.0 before, flash.m1792.0 today). A hard-coded name does not fail loudly: the scan
# dies, the caller writes an EMPTY file, and a comparison over zero blocks reports "0 blocks
# differ" -- which reads as a pass. That nearly authorised a Flex-slot overwrite against an
# unverified restore target (TASKS 568). Discover it, and refuse if absent.
import glob as _glob
_c = sorted(_glob.glob("/dev/xfpga/flash.m*"))
if not _c:
    sys.stderr.write("qspi_scan: no /dev/xfpga/flash.m* node -- is an XRT platform running?\n")
    sys.exit(2)
DEV = os.environ.get("FLASH_DEV") or _c[0]   # FLASH_DEV: pick the card (two-card hosts; names sort, first is not "card 0")
start = int(sys.argv[1], 16); end = int(sys.argv[2], 16); bs = int(sys.argv[3], 16)
out = open(sys.argv[4], "w") if len(sys.argv) > 4 else sys.stdout
fd = os.open(DEV, os.O_RDONLY)
t0 = time.time(); nb = 0
try:
    for slave in (0, 1):
        off = start
        while off < end:
            os.lseek(fd, (slave << 56) | off, os.SEEK_SET)
            buf = b""
            while len(buf) < bs:
                c = os.read(fd, bs - len(buf))
                if not c: break
                buf += c
            nb += len(buf)
            out.write("%d 0x%08X %s %d\n" % (slave, off, hashlib.sha1(buf).hexdigest(), len(buf)))
            out.flush()
            off += bs
finally:
    os.close(fd)
sys.stderr.write("read %d B in %.1f s (%.2f MB/s)\n" % (nb, time.time()-t0, nb/1e6/(time.time()-t0)))
