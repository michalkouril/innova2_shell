# innova2_shell — run the Innova-2 as an XRT accelerator (inn2x r10, ERT shell, 2026-10-15)

The minimal package: what a host needs to boot the card as an XRT device and validate it. Related repositories:

| repository | for |
|---|---|
| **innova2_shell** (this) | a card owner: flash the shell, install the host files, validate |
| `innova2_shell_src` | rebuilding the shell from source (`repro/build_release.sh`), the XRT 2.27 patches and the RDMA peer-memory module |
| `innova2_shell_dev` | the Vitis development platform (`hw_dev.xsa`) to link your own kernels against |
| `innova2_py_app` | managing the card: burning flash, image select, JTAG grant, health; and `innova2-smi`, the query and test tool for this shell |
| `innova2_flex` | the Flex-slot image that dispatches boots to this shell |

| | |
|---|---|
| Shell | **inn2x r10 (ert4)**: r9 (fp8c rc1) plus a **classic ERT** (a MicroBlaze running XRT's own command scheduler, `sched.bin` from XRT 2.27, in the static region) and **CU completion interrupts** (`cu_intc`, platform version 202320.4). XRT drives the kernels through the ERT, as on the Alveo cards. Built from `innova2_shell_src` branch `inn2x-r10`. See `RELEASE_inn2x_r10.md` and `EVIDENCE.md` |
| Platform (VBNV) | **`innova2_innova2_xdma_202320_4`** (r9: `innova2_innova2_xdma_202320_3`) |
| Interface UUID | `ed6205e413c8221a04c57b146228aa11` |
| ROM_TS | 1792512000 (`0x6ad79000`), the key of the boot xsabin |
| Memory | DDR4-2666 bank0, 8 GB usable, 72-bit with ECC; PLRAM0/1/2 (128 KB / 128 KB / 1 MB); optional 1 MB on-chip window (EMU or HYBRID mode); host RAM through XRT host-memory buffers (needs the `innova2_devices.patch` xocl patch) |
| Host link | PCIe Gen3 x8 via the card's ConnectX-5 switch |
| Validated board | MNV303212A-ADLT rev A7 (the tools warn on any other; see "Board check") |

Every file here belongs to this one build, and they must be installed together. XRT identifies this shell only by its
feature-ROM timestamp, and this release has a new one. Kernels built for earlier shells (r3 ... r9) are refused with
-95. Link kernels against `innova2_shell_dev`'s `hw_dev.xsa` (or a platform rebuilt from `innova2_shell_src` branch
`inn2x-r10`), and don't carry old xclbins over.

Never give two different shell builds the same ROM timestamp. XRT would then load a kernel linked for another static
region, which corrupts it and can take the host off the network.

`dpkg -V innova2-xdma` / `rpm -V innova2-xdma` (or the tarball's `install.sh --check`) tells you whether a host still
matches this package.

**Requirements:**
* XRT 2.27 (tested: master `1ea5176db` on Ubuntu 26.04, kernel 7.0). The shell runs on stock XRT; the xocl patches in
  `tools/xrt/` add host memory, a second card on kernel >= 6.18, P2P buffers on kernel >= 6.17, and stop the ERT's CU
  threads from spinning a CPU core (see "Things to know").
* Root.
* The `innova2_py_app` package, for flashing from the Flex image and for `innova2-smi` (1.3.23 or later).

## Install (release packages)

| system | command |
|---|---|
| Debian / Ubuntu | `sudo apt install ./innova2-xdma_202320.4.0-1_all.deb` |
| RHEL / Rocky / Fedora | `sudo dnf install ./innova2-xdma-202320.4.0-1.noarch.rpm` |
| anything else | `tar xzf innova2-xdma-202320.4.0-1.tar.gz && sudo innova2-xdma-202320.4.0-1/install.sh` (`--check` compares only) |

`packaging/build_packages.sh` builds the three from this tree (see below). All three install the same files. None of
them flashes the card: that stays a deliberate step.

| installed path | what |
|---|---|
| `/lib/firmware/xilinx/10ee-{788f,7890,6a9f,6aa0}-4351-000000006ad79000.xsabin` | boot firmware; xclmgmt loads it by the card's ROM timestamp |
| `/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_{primary,secondary}.mcs` (+ `.prm`) | the User-slot image, one file per QSPI chip, for flashing from a running XRT shell (`innova2_flash_user`) |
| `/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_bope_{primary,secondary}.bin` (+ `.prm`) | the same User-slot image as per-chip binaries, for the Flex image's burn endpoint (`innova2_app -b`); byte-identical to the MCS contents |
| `/lib/firmware/xilinx/innova2_innova2_xdma_202320_4.bit` | the same design as a bitstream, for a volatile JTAG load |
| `/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/test/` | `verify.xclbin`, `bandwidth.xclbin` and `platform.json`, which `xrt-smi validate` needs |
| `/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/` | `innova2_flash_user.sh`, on `PATH` as `innova2_flash_user` (with its helpers `xbflash.probe` and `qspi_scan.py`); `innova2_ddr_mode.py`, also on `PATH` as `innova2_ddr_mode`; `xrt/` (the XRT 2.27 xocl patches, how to apply them, `innova2_host_retag.sh`); `tests/` has host-side test scripts (P2P, BAR↔DMA, emulated DDR, per-mode temperature) |
| `/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/` | LICENSE (Apache-2.0) / COPYRIGHT. Our work is Apache-2.0; the binaries also contain AMD IP cores under AMD terms (`LicenseRef-AMD-IP`) and the ERT firmware under its own notices (COPYRIGHT). |
| `/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/doc/` | this README, the release notes (`RELEASE_inn2x_r10.md`) and the evidence summary (`EVIDENCE.md`). Not under `/usr/share/doc`, which minimized Ubuntu images exclude. |

## Flash the card and validate

1. Install the package, above.
2. **Flash the User slot.** Which way depends on what the card is running:
   * **Card already running an XRT shell with both flash chips wired** (rbds, rbdm, inn2x): run
     `sudo innova2_flash_user`. Add `--card <mgmt BDF>` when the host has several cards. It needs only this package
     and XRT. It:
     1. probes both flash chips first (read-only), and refuses unless both answer with a Micron ID;
     2. scans the card's Factory region;
     3. writes the User partition with XRT's `xbflash.qspi`;
     4. scans Factory again, and fails if any block changed.

     `innova2_app --batch burn-inshell` (in `innova2_py_app`) does the same without the Factory check.
   * **Card running the Flex image:** use the vendor burn flow with the BOPE images:
     ```
     cd /lib/firmware/xilinx
     sudo innova2_app -b innova2_innova2_xdma_202320_4_bope_primary.bin,0 \
                      -b innova2_innova2_xdma_202320_4_bope_secondary.bin,1
     ```
     (or `innova2_app` menu 6 "Burn of customer User image", then 7).
   * **Card running an old shell** (drp … rbdf, flash chip 1 unwired): use the Flex route. Never burn from those
     shells: they would write half an image.
3. **Select the User image and COLD cycle** (power off, then on). The FPGA reads flash only at power-on.
4. **Validate:** `xrt-smi validate -d <user BDF> -r all` must pass. Then run `innova2-smi check` (or
   `sudo innova2_ddr_mode status`): DDR calibrated, 0 uncorrectable ECC errors, live temperature, validated board.
   `grep 'Interrupt mode' /sys/bus/pci/devices/<user BDF>/kds_stat` reads `ert` once an xclbin is loaded.

**Rollback:** install the previous package (inn2x r9, 202320.3.7-1) and flash it the same way. The two releases have
different ROM timestamps, so their boot xsabins have different names and can coexist. The test kernels in
`/opt/xilinx/dsa/…/test/` must come from whichever release the card runs (each release has its own directory, named
by its VBNV).

## Repository layout and building the packages

```
root/         the payload, exactly as it lands on the host
packaging/    build_packages.sh (-> dist/*.deb *.rpm *.tar.gz + SHA256SUMS), install_from_tarball.sh,
              IDENTITY.sh (uuid / ROM_TS / VBNV), VERSION
```

`packaging/build_packages.sh` needs `dpkg-deb` and `rpmbuild`. It stages under `dist/` (git-ignored), never
`/tmp`. Set `MAINTAINER="Name <email>"` for the packages' maintainer field; the default is
`Michal Kouril <xmkouril@gmail.com>`.

## The ERT

The static region holds a MicroBlaze (`ert_mb`) running XRT 2.27's own ERT firmware (`sched.bin`, built from XRT's
`src/runtime_src/ert/scheduler` and AMD's ERT-BSP by `innova2_shell_src`'s `fw/ert/`), baked into its local memory:
no driver loads firmware. It answers XRT's XGQ protocol at the standard addresses, so XRT runs this shell the way it
runs an Alveo card: `xrt-smi examine` lists the ERT, commands go through the command queue, and each completion
raises one MSI-X. The firmware's sha256 is in `innova2_shell_src`'s `platform/ERT_SCHED_ELF_SHA256`, and the build
fails unless the bitstream's local memory holds exactly that image.

* **Measured (hpy440, XRT 2.27 + the sleep patch):** 1 ms commands complete in ~1.05 ms with one MSI-X each; a 5 s
  command uses 0.01-0.02 busy CPU cores. Throughput with 4 CUs is ~100k commands/s, the same as host-driven CU mode,
  as long as the program does not share a CPU with the ERT's interrupt (all completions arrive on one MSI-X vector;
  where the program ran on that vector's CPU, the rate halved to ~52k/s). Pin the program, or the vector
  (`/proc/irq/<n>/smp_affinity_list`), apart.
* **CU mode instead of ERT** (host-driven CUs) is possible but must be chosen at boot, before any xclbin loads:
  `echo cu > /sys/bus/pci/devices/<user BDF>/kds_interrupt`, then run with an `xrt.ini` holding `[Runtime] ert=false`.
  Writing `cu` after an xclbin has loaded in ERT mode cuts the ERT's interrupts and every command then completes on a
  500 ms timer; a graceful reboot restores ERT mode.

## DDR modes

A 2-bit register selects how the shell treats DDR. It resets to `on` at every power-up.

| mode | DDR | memory controller | XRT's calibration bit | use |
|---|---|---|---|---|
| `on` | real DDR | running | real calibration | normal cards |
| `off` | fenced: reads return `0xBADCA1B0`, writes fail | held in reset (lower power) | forced 1 | PLRAM-only kernels, on any card |
| `emu` | bottom 1 MB of bank0 served from on-chip UltraRAM; the rest fenced | held in reset | forced 1 | small DDR kernels on a card with broken DDR |
| `hybrid` | bottom 1 MB of bank0 from on-chip UltraRAM, everything above from real DDR | running | real calibration | rings and doorbell records shared by a NIC and kernels (low latency) |

```
sudo innova2_ddr_mode status | on | off | emu | hybrid
```

**For a card whose DDR does not calibrate:** in `on`, XRT refuses every DDR *and* PLRAM xclbin (the error is a
misleading "Can't reach out to mgmt"). Set `off` or `emu` after every cold boot, before loading anything; a
systemd unit is the natural place.

## Health, ECC, throttle: `innova2_ddr_mode` and `innova2-smi`

The shell's `ddr_health` block (mgmt PF BAR0 + 0x36000, the r9 register map, OBS_ID `0x0B5E000C`) reports DDR, ECC,
link and thermal state. Two tools read it.

**`innova2_ddr_mode`** ships in this package (root; `--bdf <mgmt BDF>` selects a card):

| command | what |
|---|---|
| `status` | DDR mode and calibration; ECC corrected / uncorrectable counts with the first failing addresses; link-downs and recalibration; fenced accesses (and how many fell inside a link-down window); lock losses; live temperature and the throttle tier; the board check |
| `on` / `off` / `emu` / `hybrid` | set the DDR mode |
| `throttle` | show the throttle; `throttle force on\|off`, `level 2\|4`, `enable on\|off`, `gate data\|kernel\|both`, `thresholds <on C> <off C>` (tier 1), `thresholds2 <on C> <off C>` (tier 2), `tierlevel 1\|2 2\|4`, `failsafe on\|off` |
| `recorder [N]` | decode the last N flight-recorder records (all if N is omitted) |
| `clear` | zero the observability counters (not the ECC/link-down counts, the uptime, the throttle settings or the recorder) |

**`innova2-smi`** (in `innova2_py_app`) is the full tool: `list`, `status`, `check` (passive; exit 0 OK / 1 WARN /
2 FAIL, for cron), `ddr`, `memory`, `counters [--watch N]`, `recorder`, `throttle ...`, `ecc-baseline`, and active
tests (`test NAME|all`). This build reads as "unlisted build (ROM_TS 1792512000), fp8c rc1 layout": the register map
is r9's, so every check applies.

**Throttle defaults:** tier 1 at 80.4 C (off below 70.4 C) halves `DATA_CLK` and `KERNEL_CLK`; tier 2 at 90.3 C (back
to tier 1 below 80.4 C) quarters them; a temperature that stops updating for 1 s engages tier 2 as a fail-safe. The
DDR, PCIe and management clocks are never throttled.

**ECC after a warm reboot.** A warm reboot (or `xrt-smi reset`) drops the PCIe link, and the shell then resets and
recalibrates the DDR: **DDR contents are lost**. A buffer read back without being rewritten can show stale ECC errors.
Rewrite buffers after a warm reboot; `innova2-smi ecc-baseline` records the counts so that `check` judges only new
errors.

## Board check

The DDR4 is soldered down, has no SPD EEPROM, and DDR4 has no manufacturer-ID register, so nothing on the card reports
the memory part. The board part number and revision, read from the VPD of the ConnectX-5 on the same card, are the
proxy. `innova2_ddr_mode status` and `innova2-smi status` print them (part number, revision, serial) and warn on any
board other than **MNV303212A-ADLT rev A7**, the only one this shell is validated on. Its memory controller targets
Micron MT40A1G16KNR-075. On a warning, read the DRAM chip marking and report it.

Cards of the validated board still differ: at the memory controller's default command/address drive, different cards
failed at different DDR speeds. Since r9 the shell runs DDR4-2666 with the CA pins at 60 ohm, the one setting clean on
every card tested.

## Things to know

* **XRT 2.27 patches (`tools/xrt/`).** Stock XRT 2.27 runs this shell. Apply the patches you need (all four on the
  tested hosts): `innova2_devices.patch` for **host memory** (without it, host-memory xclbins fail to load with
  `No such device`, although `xrt-smi configure --host-mem enable` reports success); `xocl_dev_minor_6_18.patch` for
  **a second card** on kernel >= 6.18; `innova2_p2p_mmap_xocl_drm.patch` for **CPU access to P2P buffers** on kernel
  >= 6.17; `innova2_ert_sleep_cu_xgq.patch` so the ERT's per-CU kernel threads **sleep instead of spinning a core**
  while a command runs (with it, on a host without a CPU idle-latency limit, 1 ms and 10 ms commands take ~110-140 us
  longer, from deep C-state wakeups).
* **Host-memory tag case:** link with `sp=...:HOST` against a platform built by `innova2_shell_src`'s `kernels` stage
  (`:host` there fails with CFGEN 83-2287), or `sp=...:host` against `hw_dev.xsa`; then retag
  (`tools/xrt/innova2_host_retag.sh`).
* **OpenCL programs with device profiling crash at exit on XRT 2.27** (exit code 139 after a passed test) when their
  `xrt.ini` sets `device_trace` or `device_counters`: an XRT teardown-order bug, independent of the shell. Run without
  device profiling.
* **`xrt-smi validate`'s bandwidth test** needs `/opt/xilinx/xrt/test/23_bandwidth.py`, which some XRT 2.27 builds
  do not install; the test then fails with "Failed to find", and the others pass.
* **NIC-visible PLRAM (2 MB window, from r8)** is off at reset. A host program enables it through user-PF BAR0 +
  0x102000; until then P2P behaves as without it. The window is 2 MB, 2 MB-aligned in the P2P BAR: PLRAM0 at +0, PLRAM1
  at +128 KB, PLRAM2 (1 MB) at +1 MB; **+256 KB .. +1 MB is an unmapped hole that must not be touched.** Registers:
  0x00 ID `PALI`, 0x04 CTRL (bit 0 request, bit 8 in force), 0x08/0x0C window BAR offset (writable only while
  disabled), 0x20/0x24 write/read hit counters.
* **PCI IDs:** mgmt `10ee:788f`, user `10ee:6a90`, subsystem `10ee:4351` are entries in stock XRT's device tables,
  used so that an unmodified XRT binds the card. This is not an AMD product and is not endorsed by AMD.
* **`xrt::bo::sync` hides DMA errors.** A write to fenced DDR, or a read that hits an uncorrectable ECC error, takes
  xocl's 10 s DMA timeout and logs "DMA failed" in dmesg, but the application sees success. This is an upstream XRT
  bug, not the shell.
* **In `emu`, XRT still believes bank0 is 8 GB.** Buffers work while their total fits in 1 MB: XRT allocates from
  the bottom (measured). A buffer that straddles the window is fenced exactly past 1 MB.
* **In `off`/`emu`, `mig_calibration` reads 1 by design.** Use `innova2_ddr_mode status` for the real state.
* **8 GB P2P:** `xrt-smi configure --p2p enable`, then a **warm** reboot, which is what makes the new BAR size take
  effect. A cold cycle resets it to 256 MB. Only on hosts whose BIOS can place an 8 GB BAR (HP Z440 BIOS 2.61/2.62
  can). Run `xrt-smi validate -r p2p` only with the 8 GB BAR: with the small one an XRT bug can wedge the host.
* **HP Z440:** after a PCIe change the BIOS stops at "press F1"; remote power control cannot always clear it.
* **Do not verify flash through `/dev/xfpga`**: chip 1 reads back as zeros. Trust a cold boot, or `rawspi.py`.

## Evidence

`/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/doc/EVIDENCE.md` summarises the checks behind this release: the build
gates, timing per clock, the link gates of the validate kernels, the reproducibility check, and the hardware runs per
card. The raw logs are kept by the maintainers.
