<!--
SPDX-FileCopyrightText: 2026 the innova2 contributors

SPDX-License-Identifier: Apache-2.0
-->

# inn2x r10 (ert4) — release evidence (summary)

Build 2026-10-14 from the `innova2_shell_src` tree of branch `inn2x-r10` (development branch `ert` @ 542eeba), in the
`repro/` container, with `ROM_TS=1792512000 MIG_VARIANT=e6b750 CA_DRIVE=RDRV_60_60 KCLK0_MHZ=300 KCLK1_MHZ=500
BD_PINNED=0 IMPL_VARIANTS="Explore:AggressiveExplore AltSpreadLogic_high:AggressiveExplore"`. Vivado/Vitis v2023.2 SW
Build 4029153 / IP Build 4028589. ERT firmware sha256 `4504b854a3013dfd…` (XRT master 1ea5176db + ERT-BSP 2c7d31de6,
`fw/ert/build_fw.sh innova2`). The raw logs are kept by the maintainers and are not part of this package.

## Build

| check | result |
|---|---|
| shell timing | two implementations of the same synthesised design, every post-route gate on each: `Explore` WNS +0.002 / WHS +0.007 ns, **`AltSpreadLogic_high` WNS +0.044 / WHS +0.010 ns (kept)**; 0 gate failures |
| RP | 50,060 SLICE (400,480 LUT), 792 BRAM, 80 URAM, 1632 DSP; port list identical to the reference (174 ports) |
| ERT firmware gate | the released bitstream's ERT local memory holds exactly the pinned firmware (`ERT-ELF PASS`; a flipped `.text` byte is detected: negative control). The firmware rebuilt from freshly fetched sources on 2026-10-15 has the same sha256 |
| identity | VBNV `innova2_innova2_xdma_202320_4`, ROM_TS 1792512000, interface UUID `ed6205e413c8221a04c57b146228aa11` (from the static bitstream) |
| flash images | the BOPE `.bin` files are byte-identical to the MCS payloads (0 differing bytes per chip); the MCS pair is the one flashed on both test cards |
| reproducibility | **bit-identical rebuilds** (2026-10-15, `repro_check.py`: `REPRO-IDENTICAL`): one in the release's environment, two from the published `inn2x-r10` tree with `repro/build_release.sh` on other CPU cores (the last at its defaults, every gate on). Static and partial bitstreams (configuration data), User-slot MCS pair, interface UUID, ROM_TS and impl directives all match |

### Link gates (kernels linked against this platform)

| link | DATA_CLK (id0) | KERNEL_CLK (id1) | axi_aclk (id3) | result |
|---|---|---|---|---|
| `verify` | 300 MHz, WNS +0.030 | 500 MHz, WNS +0.571 | WNS +0.116 | PASS |
| `bandwidth` | 300 MHz, WNS +0.006 | 500 MHz, WNS +0.391 | WNS +0.116 | PASS |
| `regress_plram` (4 `lat_probe` CUs on bank0 / PLRAM0-2) | 300 MHz, WNS +0.035 | 500 MHz, WNS +0.571 | WNS +0.116 | PASS |

**Linked against the shipped dev platform** (`innova2_shell_dev`'s `hw.xsa`, unmodified): the `vadd` example, 41 min,
DATA_CLK 300 MHz / KERNEL_CLK 500 MHz, WNS +0.017 / WHS +0.010 ns, ROM timestamp 1792512000; on hpy440's card it loaded
and passed (4096 elements, 0 mismatches) in ERT mode (2026-10-15).

## Hardware (2026-10-14; XRT 2.27 on Ubuntu 26.04, kernel 7.0)

**hpy440, card MT1935X08569** (User slot flashed, cold cycle):
* `xrt-smi validate`: all tests PASSED; DMA host->card 6512 MB/s, card->host 6593 MB/s; DDR bandwidth kernel 15,968 MB/s.
* ERT mode (xocl with the sleep patch): one MSI-X per command; 1 ms commands 1047.6 us mean (max 1075.6 us); a 5 s
  command 0.02 busy cores, the CU thread 0%.
* **Stock XRT 2.27** (with only the second-card fix, no innova2 patch): the card binds, `xrt-smi validate` passes (DDR
  bandwidth 16,009 MB/s), ERT mode with one MSI-X per command (1 ms commands 1029 us mean), 64k / 109k commands/s at
  depth 1 / 4 with 4 CUs.
* Network examples over the ConnectX-5 with P2P (8 GB BAR, `innova2_peermem`, the B7 fix): ZUC 15 cases, 0 mismatches,
  0 DMA errors (INTEG 8191 B 19.4 Gb/s); memcached 10/10 checks, 35k GET/s, 0 drops.

**x440-1, card MT1935X08327 (slot 2)** (User slot flashed, cold cycle; the host's second card ran r9 throughout):
* `xrt-smi validate`: every test PASSED except the bandwidth test, whose script (`/opt/xilinx/xrt/test/23_bandwidth.py`)
  that host's XRT 2.27 build does not install.
* ERT mode: `kds_stat` interrupt mode `ert`.
* The 20-example Vitis suite: **20/20 TEST PASSED**, 0 firewall trips, 0 "DMA failed". 9 of the 20 (the OpenCL ones whose
  `xrt.ini` enables device profiling) then exit with code 139: an XRT 2.27 teardown bug (`xdp` HAL plugin), independent
  of the shell; with profiling off they exit 0.

Both hosts: graceful reboots with the card returning Device Ready (the xocl patch installs), and `innova2-smi` reads
the register map as r9's (OBS_ID `0x0B5E000C`).
