# Licence audit — innova2_shell (2026-10-15, inn2x r10)

Every file in this repository, classified by provenance. Classes and what they mean are at the end.

**Provenance notes:** the flash images (MCS and BOPE per-chip .bin), bitstream and boot xsabins are the inn2x r10 shell
(ert4, 2026-10-14): Vivado output containing AMD IP cores (our own PF demux; our IP cores carry VLNV vendor `innova2`).
The static bitstream, and so the MCS/BOPE images, also holds the ERT firmware in the MicroBlaze's local memory: XRT's
command scheduler (Copyright (C) 2016-2019 Xilinx, Inc., Apache-2.0, with our 4-line change) linked with the start-up
code of AMD's ERT-BSP, whose notices (Xilinx MIT licence, Cygnus Support, DornerWorks, Milos/Fraser) the package ships
verbatim as `LicenseRef-ERT-BSP.txt` (repository `LICENSES/` and the installed `license/` directory). The boot xsabins
and the validate xclbins carry no firmware (metadata and partial bitstreams). The validate xclbins contain AMD IP
(HLS output, interconnect); `bandwidth.xclbin`'s kernel source is Xilinx's (Apache-2.0). `tools/xrt/*.patch` are our
changes to XRT's GPL-2.0 xocl driver (`devices.h` is dual Apache-2.0 / GPL-2.0 upstream; we offer all four as
GPL-2.0-only), and the package ships the GPL text. Content check 2026-10-15 (`provenance.py`): nothing beyond licence
texts and file-format lines. Local-path check: no `/home`/`/nobackup` strings in any text file, xclbin or xsabin.
`reuse lint`: compliant (46/46).

| file | class | licence evidence in the file |
|---|---|---|
| `.gitignore` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `LICENSE` | Licence text | Apache License; Apache License to your work, attac; Apache License to your work.; Copyrigh |
| `LICENSES/Apache-2.0.txt` | Licence text | Apache License; Apache License to your work, attac; Apache License to your work.; Copyrigh |
| `LICENSES/GPL-2.0-only.txt` | Licence text | Copyright (C) 1989, 1991 Free Software Foundation, Inc.,; GNU GENERAL PUBLIC LICENSE; copy |
| `LICENSES/LicenseRef-AMD-IP.txt` | Licence text | — |
| `LICENSES/LicenseRef-ERT-BSP.txt` | Licence text | COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTI; |
| `LICENSE_AUDIT.md` | Ours | Apache License  /; Apache License;; Apache License to your work.; Copy; Apache License; Ap |
| `NOTICE` | Ours | Copyright (C) 2016-2019 Xilinx, Inc.,; Copyright (C) 2019-2021 Xilinx, Inc., Apache-2.0.;  |
| `README.md` | Ours | COPYRIGHT). /; COPYRIGHT. Our work is Apache-2.0; the binaries also contain AMD IP cores u |
| `REUSE.toml` | Ours | COPYRIGHT", "root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/LICENSE", "root/op; |
| `packaging/IDENTITY.sh` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `packaging/VERSION` | Ours | — |
| `packaging/build_packages.sh` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `packaging/install_from_tarball.sh` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/lib/firmware/xilinx/10ee-6a9f-4351-000000006ad79000.xsabin` | Vivado-built binary containing AMD IP | binary |
| `root/lib/firmware/xilinx/10ee-6aa0-4351-000000006ad79000.xsabin` | Vivado-built binary containing AMD IP | binary |
| `root/lib/firmware/xilinx/10ee-788f-4351-000000006ad79000.xsabin` | Vivado-built binary containing AMD IP | binary |
| `root/lib/firmware/xilinx/10ee-7890-4351-000000006ad79000.xsabin` | Vivado-built binary containing AMD IP | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4.bit` | Vivado-built binary containing AMD IP and the ERT firmware | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_bope_primary.bin` | Vivado-built binary containing AMD IP and the ERT firmware | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_bope_primary.prm` | Ours, tool-generated | — |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_bope_secondary.bin` | Vivado-built binary containing AMD IP and the ERT firmware | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_bope_secondary.prm` | Ours, tool-generated | — |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_primary.mcs` | Vivado-built binary containing AMD IP and the ERT firmware | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_primary.prm` | Ours, tool-generated | — |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_secondary.mcs` | Vivado-built binary containing AMD IP and the ERT firmware | binary |
| `root/lib/firmware/xilinx/innova2_innova2_xdma_202320_4_secondary.prm` | Ours, tool-generated | — |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/doc/EVIDENCE.md` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/doc/RELEASE_inn2x_r10.md` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/COPYRIGHT` | Ours | Apache License, Version 2.0 (LICEN; Apache License, Version 2.0 (see L; Copyright (C) 2016 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/GPL-2.0-only.txt` | Licence text | Copyright (C) 1989, 1991 Free Software Foundation, Inc.,; GNU GENERAL PUBLIC LICENSE; copy |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/LICENSE` | Ours | Apache License; Apache License to your work, attac; Apache License to your work.; Copyrigh |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/LicenseRef-AMD-IP.txt` | Licence text | — |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/license/LicenseRef-ERT-BSP.txt` | Licence text | COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTI; |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/test/bandwidth.xclbin` | Vivado-built binary containing AMD IP | binary |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/test/platform.json` | Ours, tool-generated | — |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/test/verify.xclbin` | Vivado-built binary containing AMD IP | binary |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/innova2_ddr_mode.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/innova2_flash_user.sh` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/qspi_scan.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/tests/emu_test.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/tests/gate_dma_test.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/tests/p2p_bar_test8g.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/tests/p2p_dma_xcheck8g.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/tests/temp_modes.py` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xbflash.probe` | Binary built from Xilinx Apache-2.0 source | binary |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/README.md` | Ours | — |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/innova2_devices.patch` | Ours, a patch to XRT's GPL-2.0 xocl driver | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: GPL-2.0-only |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/innova2_ert_sleep_cu_xgq.patch` | Ours, a patch to XRT's GPL-2.0 xocl driver | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: GPL-2.0-only |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/innova2_host_retag.sh` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/innova2_p2p_mmap_xocl_drm.patch` | Ours, a patch to XRT's GPL-2.0 xocl driver | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: GPL-2.0-only |
| `root/opt/xilinx/dsa/innova2_innova2_xdma_202320_4/tools/xrt/xocl_dev_minor_6_18.patch` | Ours, a patch to XRT's GPL-2.0 xocl driver | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: GPL-2.0-only |
| `root/usr/bin/innova2_ddr_mode` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/usr/bin/innova2_flash_user` | Ours | CopyrightText: 2026 the innova2 contributors; SPDX-License-Identifier: Apache-2.0 |
| `root/usr/share/doc/innova2-xdma/copyright` | Ours | COPYRIGHT; Copyright (C) 2016-2019 Xilinx, Inc., Apache-2.0; ERT-BSP; Copyright (C) 2019-2 |

## Classes

* **Licence text** (8 files): Verbatim licence text (SPDX licence list, or our LicenseRef explanation). Not a work of ours to license.
* **Ours** (25 files): Written in this project. Apache-2.0, (c) 2026 the innova2 contributors (SPDX header or REUSE.toml).
* **Vivado-built binary containing AMD IP** (6 files): Bitstreams/images/platform archives synthesised by Vivado: contain AMD IP cores (XDMA, MIG, SmartConnect, HWICAP, ...) under AMD's IP licence terms. Normal for Vitis platforms, but those terms apply.
* **Vivado-built binary containing AMD IP and the ERT firmware** (5 files): As AMD_BIN, plus the ERT firmware in the MicroBlaze local memory: XRT's scheduler (Xilinx, Apache-2.0) linked with the ERT-BSP start-up code (MIT-style notices: LicenseRef-ERT-BSP).
* **Ours, tool-generated** (5 files): Produced by Vivado/our scripts from our own design or measurements; no third-party text. Apache-2.0 via REUSE.toml.
* **Binary built from Xilinx Apache-2.0 source** (1 files): xbflash.probe: XRT xbflash.qspi (Apache-2.0) + our probe hooks. Ship with the Apache licence and a modification notice.
* **Ours, a patch to XRT's GPL-2.0 xocl driver** (4 files): Our changes to XRT's xocl driver (GPL-2.0; devices.h is Apache-2.0 OR GPL-2.0); offered as GPL-2.0-only (SPDX header).
