#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

"""Die temperature per rbdm DDR mode (the only power proxy on Innova2: no current sensors).
usage (on the target, root, no kernels running): temp_modes.py [settle_s] [sample_s] [mode ...]
Sets each mode with innova2_ddr_mode.py, waits settle_s, then averages SYSMON temperature (mgmt BAR0
0xA0400, SYSMONE4 transfer function) at 10 Hz for sample_s. Repeating a mode in the sequence exposes
drift (heatsink time constant, room). Leaves the card in the last mode of the sequence.
"""
import mmap, os, struct, subprocess, sys, time, statistics
settle = int(sys.argv[1]) if len(sys.argv) > 1 else 180
sample = int(sys.argv[2]) if len(sys.argv) > 2 else 120
seq = sys.argv[3:] or ["on", "off", "emu", "on", "off"]
here = os.path.dirname(os.path.abspath(__file__))
bdf = os.environ.get("BDF") or next(d for d in sorted(os.listdir("/sys/bus/pci/devices")) if d.endswith(".0")
        and open("/sys/bus/pci/devices/%s/vendor" % d).read().strip() == "0x10ee" and open("/sys/bus/pci/devices/%s/device" % d).read().strip() == "0x788f")
print("mgmt function %s" % bdf, flush=True)
f = os.open("/sys/bus/pci/devices/%s/resource0" % bdf, os.O_RDONLY | os.O_SYNC)
m = mmap.mmap(f, 0x100000, mmap.MAP_SHARED, mmap.PROT_READ)
rd = lambda o: struct.unpack("<I", m[o:o + 4])[0]
T = lambda r: (r & 0xFFFF) * 509.3140064 / 65536 - 280.23087870
res = []
for mode in seq:
    tool = next(p for p in (os.path.join(here, "innova2_ddr_mode.py"), os.path.join(here, "..", "innova2_ddr_mode.py")) if os.path.exists(p))
    out = subprocess.run([sys.executable, tool, mode], capture_output=True, text=True).stdout
    line = [l for l in out.splitlines() if l.startswith("DDR mode in force")]
    print("%s set %-4s -> %s" % (time.strftime("%H:%M:%S"), mode, line[0] if line else out.strip()[:80]), flush=True)
    time.sleep(settle)
    v, t0 = [], time.time()
    while time.time() - t0 < sample:
        v.append(T(rd(0xA0400))); time.sleep(0.1)
    mu, sd = statistics.mean(v), statistics.pstdev(v)
    res.append((mode, mu, sd / len(v) ** 0.5))
    print("%s %-4s  %.2f C  (sd %.2f, n=%d, sem %.3f)" % (time.strftime("%H:%M:%S"), mode, mu, sd, len(v), sd / len(v) ** 0.5), flush=True)
print("TEMP-MODES " + "  ".join("%s=%.2f" % (a, b) for a, b, c in res))
