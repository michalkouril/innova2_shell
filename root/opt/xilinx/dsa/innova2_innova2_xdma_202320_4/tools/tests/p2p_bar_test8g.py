#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

# P2P BAR test for the rbar shell AFTER a successful resize: write through BAR4 across the FULL
# window and read back, and prove no two offsets alias (XLAT_MASK 0x1FFFFFFFF must be a bijection
# BAR offset -> bank0 offset when the BAR is 8 GB and 8 GB-aligned).
# Derived from work/logs/p2p_bar_test.py (TASKS 417). ctypes MMIO: python mmap slice writes land
# twice on these hosts (glibc memcpy).
#   usage: sudo python3 p2p_bar_test8g.py <user-PF BDF> [expected_bytes]
import mmap, os, ctypes, sys, random
BDF = sys.argv[1]
WANT = int(sys.argv[2], 0) if len(sys.argv) > 2 else 8 << 30
RES = f"/sys/bus/pci/devices/{BDF}/resource4"
SZ = os.path.getsize(RES)
print(f"  {RES}: {SZ} bytes ({SZ >> 20} MB)")
if SZ != WANT:
    print(f"P2P-BAR-TEST8G REFUSED: BAR4 is {SZ >> 20} MB, expected {WANT >> 20} MB")
    sys.exit(2)
fd = os.open(RES, os.O_RDWR | os.O_SYNC)
mm = mmap.mmap(fd, SZ, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
def wr(off, val):
    ctypes.memmove(ctypes.addressof(ctypes.c_uint32.from_buffer(mm, off)), ctypes.byref(ctypes.c_uint32(val)), 4)
def rd(off):
    return ctypes.c_uint32.from_buffer(mm, off).value
GB, MB = 1 << 30, 1 << 20
offs = {0, 4, 0x1000}
for b in (256 * MB, 512 * MB, 1 * GB, 2 * GB, 4 * GB, 6 * GB):   # both sides of every boundary
    offs |= {b - 16, b, b + 4}
offs |= {SZ - 16, SZ - 4}
rnd = random.Random(0x7E57)
offs |= {rnd.randrange(0, SZ // 4) * 4 for _ in range(64)}
offs = sorted(offs)
vals = {o: (0x5A000000 | (i << 8) | (o >> 30)) & 0xFFFFFFFF for i, o in enumerate(offs)}
for o in offs:
    wr(o, vals[o])
mm.flush()
bad = 0
for o in offs:
    got = rd(o)
    if got != vals[o]:
        bad += 1
        if bad <= 12:
            print(f"  *** BAR4+0x{o:09X}: wrote 0x{vals[o]:08X} read 0x{got:08X}")
readback = [rd(o) for o in offs]
distinct = len(set(readback))
print(f"  {len(offs)} offsets from 0 to 0x{offs[-1]:09X}: {len(offs) - bad} read back correctly, "
      f"{distinct}/{len(offs)} distinct")
mm.close(); os.close(fd)
print("P2P-BAR-TEST8G", "PASS" if (bad == 0 and distinct == len(offs)) else "FAIL")
