# XRT host memory on Innova-2 (inn2x r9 / fp8c; also the r6-r8 shells)

**r9 ships a NEW version of this patch.** The r6-r8 packages carried a patch that recognises only the old platform
name `xilinx_innova2_xdma_202320_3`. From r9 (fp8c) the card reports `innova2_innova2_xdma_202320_3`, and xocl matches
the name exactly (`strncmp` over the whole ROM VBNV field). With the old patch an r9 card silently loses host memory:
xocl creates no `address_translator`, `xbutil configure --host-mem enable` still prints success, and every xclbin with
a `HOST[0]` bank fails to load with `err = -19` ("No such device"). The shell itself is fine.

`innova2_hostmem_devices_h.patch` adds the address translator (`shell_utils_addr_remap` at user-PF BAR0 + 0x101000,
metadata node `ep_remap_data_c2h_00`) to xocl's static user profile, for this card only. The card is selected by its
VBNV. There are three entries, all typed `XOCL_DSAMAP_DYNAMIC`, because XRT 2.19's VBNV-map test is inverted:

| VBNV | shells |
|---|---|
| `xilinx_innova2_xdma_202320_3` | inn2x r6, r7, r8 (the r6 patch's entry, unchanged) |
| `innova2_innova2_xdma_202320_3` | **inn2x r9 (fp8c) and later** |
| `innova2_innova2_noddr_202320_3` | the no-DDR shell variant (not released yet; the entry is harmless without it) |

Nothing else changes: the same `XOCL_BOARD_USER_XDMA_INNOVA2` profile, the same translator. The patch applies to
XRT 2.19.0 `driver/xocl/devices.h` (stock md5 `143b5eb819f0e64f3f66d8f58ac3b4ad`; patched md5
`d44a61025892009fedcefbcc42759962`).

## Install

**Fresh host (stock XRT 2.19.0).** Keep a copy of the original tree. Do not `rmmod xocl`; reboot gracefully instead.

    sudo cp -a /usr/src/xrt-2.19.0 /usr/src/xrt-2.19.0.orig-innova2
    sudo patch -d /usr/src/xrt-2.19.0/driver/xocl -p0 < innova2_hostmem_devices_h.patch
    sudo dkms remove  xrt/2.19.0 --all
    sudo dkms build   xrt/2.19.0 -k $(uname -r)       # repeat build + install for every installed kernel
    sudo dkms install xrt/2.19.0 -k $(uname -r)
    sudo reboot

**Host that already has the r6-r8 patch.** Add only the two new entries, then rebuild as above:

    sudo patch -d /usr/src/xrt-2.19.0/driver/xocl -p0 < innova2_hostmem_upgrade_from_r6.diff

Both routes produce the same file (md5 `d44a6102...`).

**Check after the reboot.** Do not rely on xocl's `srcversion`: on some kernels it does not change when only
`devices.h` changes.

    strings /lib/modules/$(uname -r)/updates/dkms/xocl.ko | grep -c '^innova2_innova2_xdma_202320_3$'   # 1
    ls /sys/bus/pci/devices/<user BDF>/ | grep address_translator
    sudo journalctl -k | grep addr_translator_probe       # "... max_slot_nums 256"

**Where it is safe.** The `xilinx_innova2_xdma_202320_3` entry also matches the shells older than r6, which have no
translator; on those, xocl would probe an unmapped address. Install the patch only on hosts whose cards all run r6 or
later. Any r9 card is fine.

## Use

1. **Link.** Against the platform that `innova2_shell_src`'s `kernels` stage builds (`platform_full`), write
   `sp=<cu>.<port>:HOST`. From r9 that platform names the tag in upper case, and v++ matches tags case-sensitively:
   `:host` fails there with CFGEN 83-2287. Against the dev platform (`release/hw_dev.xsa`), which renames the tag,
   write `sp=<cu>.<port>:host`.
2. **Retag.** `./innova2_host_retag.sh in.xclbin out.xclbin` renames the bank to `HOST[0]` in MEM_TOPOLOGY and
   GROUP_TOPOLOGY. xocl requires this name. The script accepts either spelling of the tag.
3. **Enable and run.** `xbutil configure --host-mem enable --size 1G`, then run. Enabling host memory unloads the
   current xclbin.

Measured on an fp8c development build (E7a3 with CA drive 48 ohm; the host-memory path is the same as in this
release), on one host (x8 Gen3, XRT 2.19 + this patch): Vitis `host_memory_bandwidth_xrt` read 6.35 GB/s,
write 6.40 GB/s, concurrent 11.9 GB/s. `host_memory_simple_xrt` and `host_memory_copy_kernel_xrt` pass. On a second
host both cards get the translator, and `host_memory_simple_xrt` passes.
