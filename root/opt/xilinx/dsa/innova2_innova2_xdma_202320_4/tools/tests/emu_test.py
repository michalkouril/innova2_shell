#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

"""rbdm EMU mode: which DDR buffers land in the 1 MB emulated window, and do they round-trip?
usage: sudo env PYTHONPATH=/opt/xilinx/xrt/python python3 emu_test.py <user BDF> <xclbin using bank0>
Allocates bank0 BOs of growing size (kept alive, so XRT must place them one after another), prints
each BO's device address, and checks a host->card->host round trip. Expectation in EMU mode:
BOs entirely below bank base + 1 MB round-trip; BOs beyond read back 0xBADCA1B0 (fenced; the write
to them takes xocl's 10 s DMA timeout and is dropped).
"""
import struct, sys, time, pyxrt
bdf, xclbin = sys.argv[1], sys.argv[2]
WIN = 1 << 20
dev = pyxrt.device(bdf); xb = pyxrt.xclbin(xclbin); dev.load_xclbin(xb)
mems = [(i, m.get_tag(), m.get_base_address()) for i, m in enumerate(xb.get_mems()) if m.get_used()]
bank = next((i for i, t, b in mems if t.startswith("bank")), None)
base = next((b for i, t, b in mems if t.startswith("bank")), None)
if bank is None: sys.exit("xclbin uses no bank0")
print("bank0 index %d base 0x%x ; window = [0x%x, 0x%x)" % (bank, base, base, base + WIN))
keep, res = [], []
for n in (4096, 64 << 10, 256 << 10, 256 << 10, 512 << 10, 1 << 20):
    bo = pyxrt.bo(dev, n, pyxrt.bo.normal, bank); keep.append(bo)
    a = bo.address(); inside = a >= base and a + n <= base + WIN
    pat = b"".join(struct.pack("<I", (0xE0000000 | (len(keep) << 24)) + i) for i in range(n // 4))
    bo.write(pat, 0); t0 = time.time()
    bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_TO_DEVICE, n, 0); tw = time.time() - t0
    bo.write(b"\0" * n, 0)
    bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_FROM_DEVICE, n, 0)
    got = bytes(bo.read(n, 0)); ok = got == pat
    nfill = sum(1 for i in range(0, n, 4) if got[i:i + 4] == struct.pack("<I", 0xBADCA1B0))
    verdict = ("PASS" if ok == inside else "FAIL")
    res.append(verdict == "PASS")
    print("%-5s BO %7d B @0x%x %-8s round-trip=%-5s fill=%d/%d write %.1fs" % (verdict, n, a, "inside" if inside else "OUTSIDE", ok, nfill, n // 4, tw), flush=True)
print("EMU-TEST %s" % ("PASS" if all(res) else "FAIL"))
