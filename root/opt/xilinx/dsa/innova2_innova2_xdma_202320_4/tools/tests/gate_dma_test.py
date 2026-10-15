#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

"""XDMA into UNCALIBRATED DDR through the calibration gate (2026-09-26).
usage: sudo -E python3 gate_dma_test.py <user BDF> <xclbin linked against THIS shell>
Loads the xclbin (PR), writes a 1 MB pattern to bank0 by DMA, reads it back by DMA.
Expected with the gate closed: both DMAs COMPLETE (no hang, no error) and every word read back is
the gate's fill 0xbadca1b0 (the write was discarded)."""
import sys, struct, pyxrt
bdf, xclbin = sys.argv[1], sys.argv[2]
FILL = 0xBADCA1B0
dev = pyxrt.device(bdf)
xb = pyxrt.xclbin(xclbin)
uuid = dev.load_xclbin(xb)
print("loaded", xclbin, "uuid", uuid.to_string())
bank = None
for i, m in enumerate(xb.get_mems()):
    if m.get_tag() == "bank0" and m.get_used():
        bank = i
if bank is None:
    sys.exit("GATE-DMA *** no used bank0 in this xclbin")
N = 1 << 20
bo = pyxrt.bo(dev, N, pyxrt.bo.normal, bank)
pat = b"".join(struct.pack("<I", 0x13570000 + i) for i in range(N // 4))
bo.write(pat, 0)
bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_TO_DEVICE, N, 0)
print("DMA host->card completed")
bo.write(b"\0" * N, 0)
bo.sync(pyxrt.xclBOSyncDirection.XCL_BO_SYNC_BO_FROM_DEVICE, N, 0)
print("DMA card->host completed")
back = bytes(bo.read(N, 0))
words = struct.unpack("<%dI" % (N // 4), back)
nfill = sum(1 for w in words if w == FILL)
npat = sum(1 for i, w in enumerate(words) if w == 0x13570000 + i)
print("bo device addr 0x%x: %d/%d words = fill, %d = written pattern" % (bo.address(), nfill, len(words), npat))
print("GATE-DMA PASS" if nfill == len(words) else "GATE-DMA FAIL")
