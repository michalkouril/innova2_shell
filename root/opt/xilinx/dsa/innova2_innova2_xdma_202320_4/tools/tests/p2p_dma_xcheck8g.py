#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

# BAR-vs-DMA cross-check across the 8 GB P2P window (rbar shell, P2P enabled, BAR4 = 8 GB).
#
# p2p_bar_test8g.py proves BAR4 offsets do not alias; it cannot prove that BAR4 offset X is DDR
# address 0x2_0000_0000 + X. This does: XDMA (normal BOs, sync) and BAR4 (raw mmap) must see the SAME
# bytes at the same DDR address, in both directions, at several points spread over the bank.
# Device-only filler BOs push later test BOs up the address space without allocating host RAM.
# Derived from rebuild/p2p_verify.sh's cross-check (256 MB era). Independent of xbutil's p2p test.
#   usage: sudo python3 p2p_dma_xcheck8g.py <user BDF> <xclbin that uses bank0>
import sys, os, mmap, ctypes, random
sys.path.insert(0, "/opt/xilinx/xrt/python")
import pyxrt

BDF, XCLBIN = sys.argv[1], sys.argv[2]
BANK_BASE = 0x200000000
GB, MB = 1 << 30, 1 << 20
RES = f"/sys/bus/pci/devices/{BDF}/resource4"
SZ = os.path.getsize(RES)
if SZ != 8 * GB:
    print(f"XCHECK REFUSED: BAR4 is {SZ >> 20} MB, not 8192 MB"); sys.exit(2)

d = pyxrt.device(BDF)   # exactly the card whose BAR4 is tested -- never fall back to another device
xb = pyxrt.xclbin(XCLBIN)
G = None
for m in xb.get_mems():
    if m.get_tag() == "bank0" and m.get_used():
        G = m.get_index()
if G is None:
    print("XCHECK REFUSED: xclbin does not use bank0"); sys.exit(2)
d.load_xclbin(xb)
print(f"  loaded {os.path.basename(XCLBIN)}; bank0 = group {G}")

fd = os.open(RES, os.O_RDWR | os.O_SYNC)
bar = mmap.mmap(fd, SZ, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
def bar_rd(o): return ctypes.c_uint32.from_buffer(bar, o).value
def bar_wr(o, v):
    ctypes.memmove(ctypes.addressof(ctypes.c_uint32.from_buffer(bar, o)), ctypes.byref(ctypes.c_uint32(v)), 4)

TEST = 2 * MB
keep, results = [], []
# test BO, filler, test BO, filler, test BO: lands low, around the middle and near the top
plan = ["test", 3900 * MB, "test", 3900 * MB, "test"]
rnd = random.Random(0xC0FFEE)
for step, item in enumerate(plan):
    if item != "test":
        f = pyxrt.bo(d, item, pyxrt.bo.flags.device_only, G); keep.append(f)
        print(f"  filler {item >> 20} MB at device 0x{f.address():x}")
        continue
    bo = pyxrt.bo(d, TEST, pyxrt.bo.flags.normal, G); keep.append(bo)
    addr = bo.address(); off = addr - BANK_BASE
    words = TEST // 4
    hb = (ctypes.c_uint32 * words).from_buffer(bo.map())
    tag = 0xA0000000 | (step << 24)
    idx = sorted(set([0, 1, words - 1] + [rnd.randrange(words) for _ in range(254)]))
    # direction 1: DMA writes, BAR reads
    for i in range(words): hb[i] = tag | (i & 0xFFFFFF)
    bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_TO_DEVICE, TEST, 0)
    bad1 = sum(1 for i in idx if bar_rd(off + 4 * i) != (tag | (i & 0xFFFFFF)))
    # direction 2: BAR writes, DMA reads
    tag2 = 0x5B000000 | (step << 16)
    for i in idx: bar_wr(off + 4 * i, tag2 | (i & 0xFFFF))
    bar.flush()
    bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_FROM_DEVICE, TEST, 0)
    bad2 = sum(1 for i in idx if hb[i] != (tag2 | (i & 0xFFFF)))
    results.append((addr, off, bad1, bad2, len(idx)))
    print(f"  test BO at device 0x{addr:x} (BAR4 +0x{off:09x}, {off / GB:.2f} GB): "
          f"DMA->BAR mismatches {bad1}/{len(idx)}, BAR->DMA mismatches {bad2}/{len(idx)}")

bar.close(); os.close(fd)
top = max(r[1] for r in results)
ok = all(r[2] == 0 and r[3] == 0 for r in results)
covers_high = any(r[1] >= 4 * GB for r in results)
print(f"  highest tested BAR offset: {top / GB:.2f} GB; crossed 4 GB: {covers_high}")
print("P2P-DMA-XCHECK", "PASS" if ok and covers_high else ("FAIL" if not ok else "INCOMPLETE (did not reach 4 GB)"))
