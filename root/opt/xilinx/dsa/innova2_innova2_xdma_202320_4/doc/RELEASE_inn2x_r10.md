<!--
SPDX-FileCopyrightText: 2026 the innova2 contributors

SPDX-License-Identifier: Apache-2.0
-->

# innova2 XDMA shell — release 202320.4.0-1 (inn2x r10, ert4)

| package | what | Debian/Ubuntu | RHEL/Rocky/Fedora | other |
|---|---|---|---|---|
| `innova2-xdma` | deployment: boot firmware, User-slot flash images (MCS for in-shell flashing, BOPE `.bin` for the Flex burn path), validate kernels, DDR mode tool, the XRT 2.27 xocl patches | `.deb` | `.rpm` | `.tar.gz` + `install.sh` |
| `innova2-xdma-dev` | the Vitis platform to link kernels against (`innova2_shell_dev`, private: it holds AMD IP as a checkpoint) | `.deb` | `.rpm` | `.tar.gz` |

| | |
|---|---|
| Platform (VBNV) | **`innova2_innova2_xdma_202320_4`** (r9: `innova2_innova2_xdma_202320_3`) |
| Build | ert4 (OBS_ID `0x0B5E000C`, r9's register map) |
| Interface UUID | `ed6205e413c8221a04c57b146228aa11` |
| ROM timestamp | 1792512000 (`0x6ad79000`) |
| Source | `innova2_shell_src` branch `inn2x-r10`; rebuild with `repro/build_release.sh` |

## What is new (vs inn2x r9, 202320.3.7-1)

### The ERT

A MicroBlaze in the static region runs XRT's own embedded runtime (ERT) command scheduler: `sched.bin` built from XRT
2.27's `src/runtime_src/ert/scheduler` and AMD's ERT-BSP, baked into its local memory (no driver loads firmware). XRT
drives the card as it drives an Alveo card with an ERT: commands go through the XGQ command queue, the ERT starts the
CUs and completes each command with one MSI-X.

* The ERT status registers (`ert_csr`, ours) answer at user BAR0 0x110000 and at stock XRT's 0x180000, so the shell
  runs on **unpatched XRT 2.27** (validated: stock XRT plus only the second-card fix).
* The firmware differs from XRT's stock `sched.bin` only in its load address (0x400000, because the user BAR map puts
  the CUs at 0x0) and its clock counter (read from `ert_csr` + 0x200 instead of address 0). Its sha256 is pinned in the
  source tree and the build fails unless the bitstream holds exactly that image.
* CU mode (host-driven CUs) is still possible, chosen at boot before any xclbin loads (README, "The ERT").

### CU completion interrupts (platform version 202320.4)

`cu_intc` and `cfg_gpio` in the static region; each CU's `interrupt` reaches input n for CU id n; XDMA user interrupts
on the user PF.

### A larger dynamic region

50,060 SLICE (400,480 LUT), 792 BRAM, 80 URAM, 1632 DSP (r9: 47,900 SLICE / 383,200 LUT, 768 BRAM, 1536 DSP). The
data-path and control SmartConnects became AXI crossbars (with `axi_id_strip`), with 32 outstanding transactions on
every port.

### XRT 2.27 patches (`tools/xrt/`)

r9 shipped one optional patch for XRT 2.19. r10 ships the four xocl patches the test hosts run with XRT 2.27 on
kernel 7.0: host memory (board entries), a second card on kernel >= 6.18, CPU access to P2P buffers on kernel >= 6.17,
and the ERT CU threads sleeping instead of spinning. See `tools/xrt/README.md`.

### Unchanged from r9

DDR4-2666 with ECC and the 60 ohm command/address drive, `ddr_health` (counters, ECC, flight recorder), the live
temperature and two-tier thermal throttle, the DDR modes, PEER windows, host memory, the NIC-visible PLRAM window, the
board check, `innova2_ddr_mode`, `innova2_flash_user`.

## Known issues

* **Thin timing margins:** the shell closed at WNS +0.044 ns / WHS +0.010 ns; the validate kernels' links at
  +0.006 ns (bandwidth) and +0.030 ns (verify) on `DATA_CLK`.
* **ERT throughput depends on CPU placement.** All completions arrive on one MSI-X vector. A program that runs on that
  vector's CPU gets about half the command rate (52k vs ~100k commands/s with 4 CUs); pin one or the other.
* **The ERT sleep patch adds latency on hosts without a CPU idle-latency limit** (1 ms and 10 ms commands ~110-140 us
  longer: the woken thread leaves a deep C-state). Without the patch each CU's kernel thread spins a core instead.
* **DDR varies by card** (as r9). If `innova2-smi check` reports uncorrectable ECC errors outside a warm-reboot window,
  report the card's board revision and serial.
* **ECC after a warm reboot.** The link-down reset loses the data in DDR; rewrite buffers after a warm reboot.
* **XRT (upstream, not the shell):**
  * OpenCL programs whose `xrt.ini` enables device profiling (`device_trace`, `device_counters`) crash at exit with
    code 139 after finishing (XRT 2.27 `xdp` teardown order). Run without device profiling.
  * `xrt::bo::sync` discards DMA errors: a failed transfer returns success after a 10 s timeout. Check dmesg for
    "DMA failed".
  * `xrt-smi validate -r p2p` can wedge the host if the P2P BAR is smaller than the bank. Enable the 8 GB P2P BAR first.
  * `xrt-smi configure --host-mem enable` reports success on a device without the address translator.
  * Some XRT 2.27 builds do not install `/opt/xilinx/xrt/test/23_bandwidth.py`, so validate's bandwidth test fails
    with "Failed to find".
  * Without `xocl_dev_minor_6_18.patch`, a second card does not probe on kernel >= 6.18; without
    `innova2_p2p_mmap_xocl_drm.patch`, mapping a P2P buffer SIGBUSes on kernel >= 6.17.
* **Corrected PCIe errors on an x1 riser link** (one test slot; carried over). No uncorrectable errors.

## Upgrading from inn2x r9 (or earlier)

1. Install the XRT 2.27 patches you need (`tools/xrt/README.md`) and reboot gracefully.
2. Install the package. It replaces r9's files (different paths, same package name).
3. Flash the card, using one of:
   * `sudo innova2_flash_user`, on a card running an XRT shell with both flash chips wired;
   * the BOPE images with `innova2_app`, on a card running the Flex image (see the README).

   Then select the User image and **cold** cycle.
4. Run `xrt-smi validate -d <user BDF> -r all`, then `innova2-smi check` (or `innova2_ddr_mode status`).
5. Relink your kernels against `innova2_shell_dev`'s platform (or one rebuilt from `innova2_shell_src` branch
   `inn2x-r10`). The memory map and interfaces are r9's; the boundary adds the CU interrupt bus, so a relink is all
   that is needed.

**Rollback:** install the r9 package (202320.3.7-1) and flash its images. Its boot xsabins carry a different ROM
timestamp in their names, so they can coexist with r10's.

**Tested:** see `EVIDENCE.md`.
