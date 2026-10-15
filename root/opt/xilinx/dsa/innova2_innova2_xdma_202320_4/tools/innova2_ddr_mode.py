#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 the innova2 contributors
#
# SPDX-License-Identifier: Apache-2.0

"""DDR mode of an Innova2 card (calibration gate v1.2: on/off/emu; v1.3, E3 dev shells: also hybrid).   As root.

  innova2_ddr_mode.py [--bdf <mgmt BDF>] status
  innova2_ddr_mode.py [--bdf <mgmt BDF>] on | off | emu | hybrid
  innova2_ddr_mode.py [--bdf <mgmt BDF>] clear        (fp8c+ shells: zero the observability counters)
  innova2_ddr_mode.py [--bdf <mgmt BDF>] throttle      (fp8c E7+: show the thermal throttle)
  innova2_ddr_mode.py [--bdf <mgmt BDF>] throttle force on|off | level 2|4 | enable on|off | gate data|kernel|both
                                                       | thresholds <on C> <off C>
                       (E7a3 two-tier shells, OBS_ID 0x0B5E0006/7/9/A/C, also:)
                                                       | thresholds2 <on C> <off C>   (tier 2; 'thresholds' = tier 1)
                                                       | tierlevel 1|2 2|4             (divide tier 1 / tier 2 by 2 or 4)
                                                       | failsafe on|off               (stale temperature -> tier 2)
                       E7a3: 'level' is the FORCE level only; the automatic tiers use 'tierlevel'.
  innova2_ddr_mode.py [--bdf <mgmt BDF>] recorder [N]  (fp8c E7+: decode the last N flight-recorder records; all)

Modes (register resets to ON at power-up; set it again after every cold boot, before loading an xclbin):
  on   real DDR. On a card whose DDR does not calibrate, XRT refuses DDR *and* PLRAM xclbins (default).
  off  DDR fenced and the MIG held in reset (saves power); XRT is told "calibrated", so PLRAM-only
       xclbins load on any card. DDR reads return 0xBADCA1B0, DDR writes fail (xocl "DMA failed").
  emu  the bottom 1 MB of DDR bank0 is served from on-chip UltraRAM ("emulated DDR"); the rest of
       the bank is fenced as in off; the MIG is held in reset. Small DDR examples run unchanged.
  hybrid (gate v1.3 only) real DDR AND the on-chip window: the bottom 1 MB of bank0 is served from UltraRAM,
       everything above from the DDR; the MIG runs and XRT sees the real calibration. For descriptor rings /
       doorbell records / completion queues shared by the ConnectX and RP kernels. On a v1.2 shell the value
       means OFF: the tool detects that (off in force), says so and restores the previous mode.

Registers (mgmt PF BAR0): 0x32000 bit0 = the calibration bit XRT reads; 0x32008 bits1:0 = requested
mode; 0x36000 = mgmt_status: bit27 fenced-access seen (sticky), bit28 gate open (DDR live),
bits30:29 mode in force, bit31 MIG held in reset.
Changing mode with an xclbin loaded is allowed but its DDR buffers change underneath it -- reload.

status also prints the board identity: part number, revision (EC) and serial from the VPD of the ConnectX on the same
card. The DDR4 is soldered down -- no SPD EEPROM, and DDR4 has no manufacturer-ID register -- so the board part number
and revision are the only readable proxy for the memory part. The shell's DDR controller targets Micron
MT40A1G16KNR-075; it is validated only on the boards in VALIDATED_BOARDS, and status warns about any other.
"""
import ctypes, mmap, os, sys, time

MODES = {"on": 0, "off": 1, "emu": 2, "hybrid": 3}
NAMES = {0: "on", 1: "off", 2: "emu", 3: "hybrid"}   # requested 3 on a v1.2 gate shows "off" in force
MEMCALIB, MODE_REG, STATUS = 0x32000, 0x32008, 0x36000
# fp8c+ shells: ddr_health observability block in the same window (0x36030..0x360B8); absent (reads 0) on older shells
# The layout id at 0x36030 names the layout: 0x0B5E0001 = full (with the AXI error monitors at 0x40/0x60/0x80),
# 0x0B5E0002 = fp8c E4 gold master (no AXI monitors: 0x40-0x9F read 0). Older shells read 0.
# 0x0B5E0003 = fp8c E7a (E4 + thermal throttle, PCIe status, PR loads, timestamps, flight recorder at 0xC0-0x198),
# 0x0B5E0004 = fp8c E7b (E7a + the AXI error monitors).
# 0x0B5E0005 = fp8c E7a2 (E7a register map; the throttle switches the kernel clock to /2 or /4 instead of gating edges,
#              and THR_STATUS [2]/[3] are the measured delivered rate).
OBS_FULL, OBS_E4, OBS_E7A, OBS_E7B, OBS_CLEAR = 0x0B5E0001, 0x0B5E0002, 0x0B5E0003, 0x0B5E0004, 0xC1EAC1EA
# 0x0B5E0006 = fp8c E7a3 (E7a2 + the LIVE temperature: the wizard's frozen temperature bus is gone, the throttle reads
#              the polled SYSMON TEMP register; two-tier throttle (THR_THRESH 0xC4 = tier 1, THR_THRESH2 0xD8 = tier 2,
#              THR_TIER 0xDC = per-tier levels + stale fail-safe); temperature health block 0x140-0x154).
OBS_E7A2 = 0x0B5E0005
OBS_E7A3 = 0x0B5E0006
# 0x0B5E0007 = fp8c E7a3-2666ca48: the E7a3 register map unchanged (same RTL); the shell runs DDR4-2666 (MIG e6b750)
#              with the DDR4 CA pins at OUTPUT_IMPEDANCE RDRV_48_48. Treated as E7a3 everywhere below.
OBS_E7A3CA = 0x0B5E0007
# 0x0B5E0009 = fp8c E7a3-2400ca48: same E7a3 register map; DDR4-2400 (MIG dw8_833) + CA OUTPUT_IMPEDANCE RDRV_48_48.
# 0x0B5E000A = fp8c E7a3-2666ca60: same E7a3 register map; DDR4-2666 (MIG e6b750) + CA OUTPUT_IMPEDANCE RDRV_60_60.
OBS_E7A3CA48_2400 = 0x0B5E0009
OBS_E7A3CA60 = 0x0B5E000A
# 0x0B5E000C = fp8c rc1: E7a3-2666ca60 + the route-V r2 fence-window counters (0x218 FENCE_LDWIN, 0x21C FENCE_OUTWIN,
#              0x220 FENCE_WIN); every other offset is the E7a3 map.
OBS_RC1 = 0x0B5E000C
OBS_FENCEWIN = (OBS_RC1,)                 # layouts with the fence-window counters
OBS_E7A3_LAYOUT = (OBS_E7A3, OBS_E7A3CA, OBS_E7A3CA48_2400, OBS_E7A3CA60, OBS_RC1)   # shells with the E7a3 register map
OBS_IDS = (OBS_FULL, OBS_E4, OBS_E7A, OBS_E7B, OBS_E7A2) + OBS_E7A3_LAYOUT
OBS_MON = (OBS_FULL, OBS_E7B)            # layouts with the AXI error monitors
OBS_E7 = (OBS_E7A, OBS_E7B, OBS_E7A2) + OBS_E7A3_LAYOUT            # layouts with throttle / PCIe / PR / timestamps / recorder
TS_S = 65536 / 250e6                     # timestamp unit (uptime[47:16]): 262.144 us
REC_S = 256 / 250e6                      # recorder timestamp unit (uptime[47:8]): 1.024 us
import math
def c2code(c): return max(0, min(1023, int(math.ceil((c + 280.2308787) * 1024 / 509.3140064))))   # first code >= c
def code2c(k): return k * 509.3140064 / 1024 - 280.2308787
REC_TYPES = {1: "START", 2: "LINK_DOWN", 3: "RECAL_DONE", 4: "LOCK_LOSS", 5: "ECC_CE", 6: "ECC_UE", 7: "FENCE",
             8: "PR_ISOLATE", 9: "PR_RELEASE", 10: "THR_START", 11: "THR_STOP", 12: "PCIE_COR", 13: "PCIE_NONFATAL",
             14: "PCIE_FATAL", 15: "PCIE_LINK", 16: "OBS_CLEAR", 17: "THR_TIER", 18: "TEMP_STALE", 19: "TEMP_FRESH"}
TIER_NAMES = {0: "FULL", 1: "tier 1", 2: "tier 2", 3: "?"}
SYSMON_TEMP, SYSMON_TMAX, SYSMON_TMIN = 0xA0400, 0xA0480, 0xA0490   # the wizard's own AXI view (DRP 0x00/0x20/0x24)
CMC_FPGA_TEMP = 0x120100                                             # cmc_emul: what xbutil shows as "FPGA" (whole C)
LOCK_NAMES = ["kernel (DATA_CLK)", "kernel2 (KERNEL_CLK)", "icap", "spi", "freerun (clk_wiz_0)"]
MONITORS = [(0x40, "P2P  (host -> P2P BAR)"), (0x60, "HOST (kernels -> host memory)"), (0x80, "PEER (kernels -> PEER window)")]
RESP = {2: "SLVERR", 3: "DECERR"}
# (part number, EC revision) of boards this shell's DDR controller (Micron MT40A1G16KNR-075) is validated on
VALIDATED_BOARDS = {("MNV303212A-ADLT", "A7")}
DDR_PART = "Micron MT40A1G16KNR-075 (16 Gb x16, DDR4-2666 grade)"

def find_mgmt():
    for d in sorted(os.listdir("/sys/bus/pci/devices")):
        p = "/sys/bus/pci/devices/" + d
        try:
            v, dev = open(p + "/vendor").read().strip(), open(p + "/device").read().strip()
        except OSError:
            continue
        if v == "0x10ee" and d.endswith(".0") and dev in ("0x788f",):
            return d
    return None

def parse_vpd(raw):
    """PCI VPD -> {"name": identifier string, keyword: value} for the read-only section (PN, EC, SN, ...)."""
    out, i = {}, 0
    while i < len(raw):
        tag = raw[i]
        if tag == 0x78 or tag == 0x0F:                  # small-resource End tag
            break
        if not tag & 0x80:                              # other small resource: skip it
            i += 1 + (tag & 7); continue
        if i + 3 > len(raw):
            break
        n = raw[i + 1] | raw[i + 2] << 8; body = raw[i + 3:i + 3 + n]; i += 3 + n
        if tag == 0x82:
            out["name"] = body.decode("ascii", "replace").strip()
        elif tag == 0x90:                               # VPD-R: keyword(2) length(1) data
            j = 0
            while j + 3 <= len(body):
                k, ln = body[j:j + 2].decode("ascii", "replace"), body[j + 2]
                if k != "RV":
                    out[k] = body[j + 3:j + 3 + ln].decode("ascii", "replace").strip()
                j += 3 + ln
        elif tag == 0x91:                               # VPD-W: nothing we need
            continue
    return out

def board_nic(mgmt_bdf):
    """The ConnectX (15b3, function .0) on the same card: under the card's PCIe switch, i.e. the FPGA's grandparent."""
    path = os.path.realpath("/sys/bus/pci/devices/" + mgmt_bdf)
    up = os.path.dirname(os.path.dirname(path))       # FPGA -> switch downstream port -> switch upstream port
    if not os.path.basename(up).count(":") == 2:       # reached a host bridge (pci0000:xx): no on-card switch
        return None
    for root, dirs, files in os.walk(up):
        if root.count("/") - up.count("/") > 3:
            dirs[:] = []; continue
        b = os.path.basename(root)
        if b.endswith(".0") and "vendor" in files:
            try:
                if open(root + "/vendor").read().strip() == "0x15b3" and open(root + "/class").read().startswith("0x02"):
                    return b
            except OSError:
                pass
    return None

def board_id(mgmt_bdf):
    nic = board_nic(mgmt_bdf)
    if not nic:
        return {"error": "no ConnectX found behind this card's PCIe switch"}
    try:
        v = parse_vpd(open("/sys/bus/pci/devices/%s/vpd" % nic, "rb").read())
    except OSError as e:
        return {"error": "cannot read the VPD of %s: %s" % (nic, e), "nic": nic}
    v["nic"] = nic
    return v

def show_board(bi):
    if "error" in bi:
        print("board              : unknown (%s)" % bi["error"]); return
    pn, ec = bi.get("PN", "?"), bi.get("EC", "?")
    print("board              : %s rev %s, serial %s (VPD of ConnectX %s)" % (pn, ec, bi.get("SN", "?"), bi["nic"]))
    if (pn, ec) in VALIDATED_BOARDS:
        print("board check        : validated board (DDR controller targets %s)" % DDR_PART)
    else:
        print("board check        : *** WARNING: %s rev %s is not a validated board -- its DDR4 part may differ from %s;" % (pn, ec, DDR_PART))
        print("                     DDR4 cannot report its own part number: read the chip marking (Micron FBGA code) and"
              " report it with this output")

DDR_BANK0_BASE = 0x200000000   # XRT device address of bank0 (AXI address 0)

def decode_ffa(v):
    """The MIG's first-failing-address register (ECC_FFAS) as ddr_health captures it: bit 63 is not kept, so v holds
    bits 62:0. [62:56] = per-beat error flags for beats 6..0 (beat 7 lost); [51:0] = ecc_err_addr from
    ddr4_v2_2_mc_ecc_dec_fix: [51:48] logical rank, [44] RMW, [43:24] row, [23:8] column, [7:4] rank, [3:2] bank group,
    [1:0] bank. MEM_ADDR_ORDER ROW_COLUMN_BANK: app_addr = {row, col[9:3], bank, group, col[2:0]}, 8 bytes per app
    address, so the AXI byte address of the failing burst is app_addr * 8 (+ bank0 base for the XRT device address)."""
    beats = v >> 56 & 0x7F
    row, col, rank, grp, bnk = v >> 24 & 0xFFFF, v >> 8 & 0x3FF, v >> 4 & 0xF, v >> 2 & 3, v & 3
    app = row << 14 | (col >> 3) << 7 | bnk << 5 | grp << 3 | (col & 7)
    return "0x%016x = beats 0x%02x (6..0; 7 not kept)%s, row 0x%x col 0x%x bg %d bank %d%s -> AXI 0x%x (device 0x%x)" % (
        v, beats, ", RMW" if v >> 44 & 1 else "", row, col, grp, bnk, ", rank %d" % rank if rank else "",
        app * 8, app * 8 + DDR_BANK0_BASE)

ICAP_BENIGN_MAX = 4        # as innova2-smi's clk.icap_benign: up to 4 losses in the first ~0.7 ms after configuration
ICAP_CONFIG_S = 1.0        # a loss later than this (FPGA uptime) is not a configuration-time one

def icap_verdict(b, oid, n):
    """clk_wiz_icap is never reset, but every card shows up to 4 lock losses in the first ~0.7 ms after configuration
    (benign, as innova2-smi classes them). Benign = at most ICAP_BENIGN_MAX losses, all at configuration time, none
    since. E7 shells: the flight recorder's LOCK_LOSS records give each loss's time; elsewhere (or a wrapped ring)
    only the count can be judged, and the line says so."""
    times = None
    if oid in OBS_E7:
        wp, wraps = b.rd(STATUS + 0x184), b.rd(STATUS + 0x188)
        if not wraps and wp <= 4096:
            times = []
            for i in range(wp):
                t, p, ts = read_record(b, i)
                if t == 4 and p >> 2 & 1:
                    times.append(ts * REC_S)
    if times is not None:
        late = [t for t in times if t > ICAP_CONFIG_S]
        if not late and n <= ICAP_BENIGN_MAX:
            return ("clk_wiz_icap: %d lock losses, all at configuration (by %.3f ms), none since -- known benign" %
                    (n, 1e3 * max(times)) if times else
                    "clk_wiz_icap: %d lock losses, none recorded after configuration -- known benign" % n)
        return ("*** clk_wiz_icap lost lock %d x, %d after configuration (the last at FPGA uptime %.3f s): it is never "
                "reset -- report this" % (n, len(late), max(late)) if late else
                "*** clk_wiz_icap lost lock %d x (benign: <= %d at configuration): it is never reset -- report this" %
                (n, ICAP_BENIGN_MAX))
    if n <= ICAP_BENIGN_MAX:
        return ("clk_wiz_icap: %d lock losses (<= %d, the configuration-time count) -- known benign by count; loss times "
                "not available (%s)" % (n, ICAP_BENIGN_MAX, "recorder wrapped" if oid in OBS_E7 else "no flight recorder"))
    return "*** clk_wiz_icap lost lock %d x (benign: <= %d at configuration): it is never reset -- report this" % (
        n, ICAP_BENIGN_MAX)

def show_health(b):
    """link-down / ECC (0x10-0x2C, every fp8c ddr_health) and the observability block (0x30+), when present."""
    r = lambda o: b.rd(STATUS + o)
    oid = r(0x30)
    if oid not in OBS_IDS:
        return
    ld = r(0x10)
    print("link-down events   : %d%s%s" % (ld & 0xFFFF, ", recalibrated after the last" if ld >> 16 & 1 else "",
                                            ", MIG reset active NOW" if ld >> 17 & 1 else ""))
    ue = r(0x18)
    print("ECC                : %d corrected, %d uncorrectable polls%s, ECC %s, poller %s" % (
        r(0x14), ue & 0xFFFF, " (UE SEEN)" if ue >> 31 & 1 else "", "on" if ue >> 30 & 1 else "OFF",
        "alive" if ue >> 29 & 1 else "never polled"))
    for name, lo_o, hi_o in (("CE", 0x1C, 0x20), ("UE", 0x24, 0x28)):
        hi = r(hi_o)
        if hi >> 31 & 1:
            print("  first %s          : %s" % (name, decode_ffa(((hi & 0x7FFFFFFF) << 32) | r(lo_o))))
    lk, c1, c2 = r(0x34), r(0x38), r(0x3C)
    cnts = [c1 & 0xFF, c1 >> 8 & 0xFF, c1 >> 16 & 0xFF, c1 >> 24 & 0xFF, c2 & 0xFF]
    print("clock wizards      : " + ", ".join("%s %s%s" % (n, "locked" if lk >> i & 1 else "NOT LOCKED",
                                                          " (lost %d x)" % cnts[i] if lk >> (8 + i) & 1 else "")
                                             for i, n in enumerate(LOCK_NAMES)))
    if lk >> 10 & 1:
        print("                     " + icap_verdict(b, oid, cnts[2]))
    for base, name in (MONITORS if oid in OBS_MON else []):
        w, rr, info = r(base), r(base + 4), r(base + 8)
        line = "AXI errors %-30s: writes %d SLVERR / %d DECERR, reads %d SLVERR / %d DECERR" % (
            name, w & 0xFFFF, w >> 16, rr & 0xFFFF, rr >> 16)
        unk = r(base + 0x14) & 0xFFFF
        if unk:
            line += ", %d with untracked address" % unk
        print(line)
        if info >> 31 & 1:
            addr = (r(base + 0x10) << 32) | r(base + 0xC)
            print("  first            : %s %s, ID %d, address %s" % (
                "read" if info >> 30 & 1 else "write", RESP.get(info >> 28 & 3, "?"), info >> 16 & 0xFF,
                "0x%x" % addr if info >> 27 & 1 else "not tracked"))
    fi = r(0xA4)
    print("fenced DDR accesses: %d%s" % (r(0xA0), (", first: %s at 0x%x" % ("read" if fi >> 30 & 1 else "write",
                                                                           (r(0xAC) << 32) | r(0xA8))) if fi >> 31 & 1 else ""))
    if oid in OBS_FENCEWIN:
        w = r(0x220)
        print("  fence windows    : %d inside link-down windows, %d outside; window %s%s%s%s%s" % (
            r(0x218), r(0x21C), "OPEN" if w & 1 else "closed", ", link down" if w >> 1 & 1 else "",
            ", MIG reset active" if w >> 2 & 1 else "", ", waiting for recalibration" if w >> 3 & 1 else "",
            "" if w >> 4 & 1 else ", within the 2 s limit"))
    lo = r(0xB0); up = (r(0xB4) << 32) | lo; hz = r(0xB8) or 250000000
    print("uptime             : %.1f s since configuration (%d cycles at %d Hz)" % (up / hz, up, hz))
    if oid in OBS_E7:
        show_e7(b, up / hz)

def ts_str(t, now_s):
    return "never" if t == 0 else "%.3f s (%.1f s ago)" % (t * TS_S, now_s - t * TS_S)

def show_throttle(b):
    r = lambda o: b.rd(STATUS + o)
    c, th, st = r(0xC0), r(0xC4), r(0xC8)
    on, off = th & 0x3FF, th >> 16 & 0x3FF
    gates = [n for i, n in ((4, "DATA_CLK"), (5, "KERNEL_CLK")) if c >> i & 1]
    if r(0x30) in OBS_E7A3_LAYOUT:
        show_throttle_e7a3(b); return
    print("thermal throttle   : %s%s, level 1/%d, may gate %s; on at %.1f C (code %d), off below %.1f C (code %d)" % (
        "enabled" if c & 1 else "DISABLED", ", FORCE ON" if c >> 1 & 1 else "", 4 if (c >> 2 & 3) else 2,
        "+".join(gates) or "nothing", code2c(on), on, code2c(off), off))
    print("  now              : %.1f C (code %d), alarm %s, throttle %s, DATA_CLK %s, KERNEL_CLK %s" % (
        code2c(st >> 16 & 0x3FF), st >> 16 & 0x3FF, "ON" if st & 1 else "off", "REQUESTED" if st >> 1 & 1 else "off",
        "throttled" if st >> 2 & 1 else "full", "throttled" if st >> 3 & 1 else "full"))
    if r(0x30) == OBS_E7A2:
        print("  *** E7a2: this temperature is the wizard's temperature bus, which FREEZES after one value per reset --"
              " the throttle cannot see a rise (fixed in E7a3)")
    print("  history          : %d throttle starts, %.3f s throttled in total" % (r(0xCC), r(0xD0) * TS_S))

def show_throttle_e7a3(b):
    """E7a3: two tiers on the live temperature, staleness, and a three-way temperature cross-check."""
    r = lambda o: b.rd(STATUS + o)
    c, t1, t2, tl, st = r(0xC0), r(0xC4), r(0xD8), r(0xDC), r(0xC8)
    gates = [n for i, n in ((4, "DATA_CLK"), (5, "KERNEL_CLK")) if c >> i & 1]
    lv = lambda v: 4 if v & 3 else 2
    print("thermal throttle   : %s%s (FORCE level 1/%d), may gate %s; stale fail-safe %s" % (
        "enabled" if c & 1 else "DISABLED", ", FORCE ON" if c >> 1 & 1 else "", lv(c >> 2), "+".join(gates) or "nothing",
        "on (stale temperature -> tier 2)" if tl >> 16 & 1 else "OFF"))
    print("  tier 1 (1/%d)     : on at %.2f C (code %d), off below %.2f C (code %d)" % (
        lv(tl), code2c(t1 & 0x3FF), t1 & 0x3FF, code2c(t1 >> 16 & 0x3FF), t1 >> 16 & 0x3FF))
    print("  tier 2 (1/%d)     : on at %.2f C (code %d), off below %.2f C (code %d) -> back to tier 1, never straight to full" % (
        lv(tl >> 8), code2c(t2 & 0x3FF), t2 & 0x3FF, code2c(t2 >> 16 & 0x3FF), t2 >> 16 & 0x3FF))
    code = st >> 16 & 0x3FF
    print("  now              : %.2f C (code %d), temperature tier %s, in effect %s%s%s; request %s at 1/%d; DATA_CLK %s, KERNEL_CLK %s" % (
        code2c(code), code, TIER_NAMES[st >> 12 & 3], TIER_NAMES[st >> 4 & 3],
        ", TEMPERATURE STALE" if st >> 6 & 1 else "", " (FAIL-SAFE ENGAGED)" if st >> 7 & 1 else "",
        "ON" if st >> 1 & 1 else "off", lv(st >> 8), "throttled" if st >> 2 & 1 else "full",
        "throttled" if st >> 3 & 1 else "full"))
    print("  history          : %d throttle starts, %.3f s throttled in total, %d tier changes" % (
        r(0xCC), r(0xD0) * TS_S, r(0x154) & 0xFFFF))
    # staleness: the sample counter must move (the poller samples every ~100 ms); the 16-bit word should change too
    s0, ch0, raw0 = r(0x140), r(0x144), r(0x148)
    time.sleep(0.35)
    s1, ch1, raw1, sd, mm = r(0x140), r(0x144), r(0x148), r(0x14C), r(0x150)
    ds, dc = (s1 - s0) & 0xFFFFFFFF, (ch1 - ch0) & 0xFFFFFFFF
    print("  temperature feed : %s -- %d samples in 0.35 s (%d since configuration), %d word changes; last word 0x%04x, %.1f ms old" % (
        "LIVE" if ds > 0 else "*** NOT UPDATING", ds, s1, dc, raw1 & 0xFFFF, (raw1 >> 16) * TS_S * 1e3))
    print("  staleness        : %s, %d stale episodes%s; range since configuration/clear %.2f .. %.2f C" % (
        "STALE NOW" if sd >> 16 & 1 else "fresh", sd & 0xFFFF, " (stale seen)" if sd >> 18 & 1 else "",
        code2c(mm & 0x3FF) if (mm & 0x3FF) != 0x3FF else float("nan"), code2c(mm >> 16 & 0x3FF)))
    if ds > 0 and dc == 0 and s1 > 50 and ch1 * 20 < s1:
        print("  *** the ADC word has barely changed over %d samples: check the SYSMON max/min below" % s1)
    # cross-check: the SYSMON register itself, its max/min (a never-converting ADC has max 0 / min 0xFFFF), XRT's view
    if b.size > CMC_FPGA_TEMP + 4:
        t, mx, mn, xrt = b.rd(SYSMON_TEMP) & 0xFFFF, b.rd(SYSMON_TMAX) & 0xFFFF, b.rd(SYSMON_TMIN) & 0xFFFF, b.rd(CMC_FPGA_TEMP)
        print("  cross-check      : SYSMON 0xA0400 %.2f C (max %.2f, min %.2f%s); XRT FPGA temperature %d C; throttle %.2f C" % (
            code2c(t >> 6), code2c(mx >> 6), code2c(mn >> 6),
            ", ADC NEVER CONVERTED" if mx == 0 and mn == 0xFFFF else "", xrt, code2c(code)))
        if abs(code2c(t >> 6) - code2c(code)) > 3:
            print("  *** the throttle's temperature differs from the SYSMON register by more than 3 C")

def show_e7(b, now_s):
    r = lambda o: b.rd(STATUS + o)
    show_throttle(b)
    print("  last start       : %s" % ts_str(r(0xD4), now_s))
    lk = r(0x10C)
    print("PCIe               : %d correctable, %d non-fatal, %d fatal errors; LTSSM 0x%02x, speed code %d, width code %d; %d speed/width changes" % (
        r(0x100), r(0x104), r(0x108), lk & 0x3F, lk >> 8 & 7, lk >> 16 & 0xF, r(0x110)))
    print("PR loads           : %d RP isolations, the last lasted %.3f ms, RP %s" % (
        r(0x120), r(0x124) / 250e3, "released" if r(0x128) & 1 else "ISOLATED now"))
    for o, n in ((0xE0, "link-down"), (0xE4, "lock loss"), (0xE8, "ECC CE"), (0xEC, "ECC UE"), (0xF0, "fenced access"),
                 (0xF4, "PR load"), (0xF8, "PCIe error")):
        print("  last %-13s: %s" % (n, ts_str(r(o), now_s)))
    info = r(0x180)
    print("flight recorder    : %d records, %d written so far (ring wrapped %d x); 'recorder' dumps it" % (
        1 << (info & 0x1F), r(0x184) + (r(0x188) << (info & 0x1F)), r(0x188)))

def read_record(b, idx):
    b.wr(STATUS + 0x18C, idx)
    t0 = time.time()
    while not b.rd(STATUS + 0x198) & 1:
        if time.time() - t0 > 0.1:
            raise RuntimeError("recorder read of %d never became ready" % idx)
    lo, hi = b.rd(STATUS + 0x190), b.rd(STATUS + 0x194)
    v = hi << 32 | lo
    return v >> 58 & 0x3F, v >> 40 & 0x3FFFF, v & 0xFFFFFFFFFF

def decode_payload(t, p):
    if t == 4: return "wizard(s) " + ",".join(LOCK_NAMES[i] for i in range(5) if p >> i & 1)
    if t == 9: return "isolated %.3f ms" % ((p << 14) / 250e3)
    if t == 10: return "%.1f C%s" % (code2c(p & 0x3FF), ", FORCED" if p >> 10 & 1 else "")
    if t == 11: return "%.1f C" % code2c(p & 0x3FF)
    if t == 15: return "LTSSM 0x%02x speed %d width %d" % (p & 0x3F, p >> 6 & 7, p >> 9 & 0xF)
    if t == 17: return "%s -> %s at %.2f C (code %d)" % (TIER_NAMES[p >> 12 & 3], TIER_NAMES[p >> 10 & 3], code2c(p & 0x3FF), p & 0x3FF)
    if t in (18, 19): return "last %.2f C (code %d)" % (code2c(p & 0x3FF), p & 0x3FF)
    if t in (1, 3, 16): return ""
    return "count %d" % p

def dump_recorder(b, last=None):
    info = b.rd(STATUS + 0x180); aw = info & 0x1F; n = 1 << aw
    wp, wraps = b.rd(STATUS + 0x184), b.rd(STATUS + 0x188)
    idxs = list(range(wp, n)) + list(range(wp)) if wraps else list(range(wp))
    if last is not None:
        idxs = idxs[-last:]
    print("%-8s %-16s %-14s %s" % ("index", "time (s)", "event", "detail"))
    for i in idxs:
        t, p, ts = read_record(b, i)
        print("%-8d %-16.6f %-14s %s" % (i, ts * REC_S, REC_TYPES.get(t, "type%d" % t), decode_payload(t, p)))

class Bar:
    def __init__(self, bdf):
        self.fd = os.open("/sys/bus/pci/devices/%s/resource0" % bdf, os.O_RDWR | os.O_SYNC)
        # map up to 2 MB (covers the SYSMON at 0xA0000 and the CMC map at 0x120000 for the E7a3 cross-check); every
        # offset read here is decoded by the shell -- an undecoded management read hard-locks the host
        self.size = min(os.fstat(self.fd).st_size or 0x40000, 0x200000)
        self.m = mmap.mmap(self.fd, self.size, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        self.base = ctypes.addressof(ctypes.c_char.from_buffer(self.m))
    def rd(self, off):
        return ctypes.c_uint32.from_address(self.base + off).value
    def wr(self, off, val):   # one 32-bit store (python mmap slice writes can land twice)
        ctypes.c_uint32.from_address(self.base + off).value = val

def decode(b):
    s, c, r = b.rd(STATUS), b.rd(MEMCALIB), b.rd(MODE_REG)
    if s == 0xFFFFFFFF:
        sys.exit("*** mgmt BAR reads all-ones: card not responding / wrong BDF")
    eff, hold = (s >> 29) & 3, (s >> 31) & 1
    return {"requested": NAMES[r & 3], "in_force": NAMES[eff], "mig_held": hold, "gate_open": (s >> 28) & 1,
            "fenced_seen": (s >> 27) & 1, "xrt_calibration": c & 1, "raw_status": s}

def show(st):
    print("DDR mode requested : %s" % st["requested"])
    print("DDR mode in force  : %s%s" % (st["in_force"], "" if st["in_force"] == st["requested"] else "   (change pending: waits for DDR traffic to drain)"))
    print("MIG                : %s" % ("held in reset (DDR powered down)" if st["mig_held"] else "running"))
    if st["in_force"] in ("on", "hybrid"):
        print("DDR                : %s" % ("calibrated, gate open" if st["gate_open"] else "NOT calibrated -- DDR fenced; XRT will refuse DDR/PLRAM xclbins"))
        if st["in_force"] == "hybrid":
            print("on-chip window     : bottom 1 MB of bank0 served from UltraRAM (%s)" % ("the rest from DDR" if st["gate_open"] else "the rest fenced until DDR calibrates"))
    else:
        print("DDR                : not in use (real DDR state unknown while the MIG is held)")
    print("XRT calibration bit: %d" % st["xrt_calibration"])
    print("fenced access seen : %s" % ("yes (sticky)" if st["fenced_seen"] else "no"))
    print("mgmt_status raw    : 0x%08x" % st["raw_status"])

def main():
    a = sys.argv[1:]
    bdf = None
    if len(a) >= 2 and a[0] == "--bdf":
        bdf, a = a[1], a[2:]
    if not a or a[0] not in ("status", "on", "off", "emu", "hybrid", "clear", "throttle", "recorder") or \
       (a[0] not in ("throttle", "recorder") and len(a) != 1):
        sys.exit(__doc__)
    bdf = bdf or find_mgmt()
    if not bdf:
        sys.exit("*** no Innova2 management function (10ee:788f) found; pass --bdf")
    b = Bar(bdf)
    if a[0] == "status":
        show(decode(b)); show_health(b); show_board(board_id(bdf)); return
    if a[0] in ("throttle", "recorder"):
        if b.rd(STATUS + 0x30) not in OBS_E7:
            sys.exit("*** this shell has no throttle / flight recorder (fp8c E7+ only)")
        if a[0] == "recorder":
            dump_recorder(b, int(a[1]) if len(a) > 1 else None); return
        c = b.rd(STATUS + 0xC0)
        if len(a) == 3 and a[1] == "force" and a[2] in ("on", "off"):
            c = (c & ~2) | (2 if a[2] == "on" else 0)
        elif len(a) == 3 and a[1] == "level" and a[2] in ("2", "4"):
            c = (c & ~0xC) | (4 if a[2] == "4" else 0)
        elif len(a) == 3 and a[1] == "enable" and a[2] in ("on", "off"):
            c = (c & ~1) | (1 if a[2] == "on" else 0)
        elif len(a) == 3 and a[1] == "gate" and a[2] in ("data", "kernel", "both"):
            c = (c & ~0x30) | {"data": 0x10, "kernel": 0x20, "both": 0x30}[a[2]]
        elif len(a) == 4 and a[1] in ("thresholds", "thresholds2"):
            on, off = float(a[2]), float(a[3])
            if off >= on:
                sys.exit("*** the off temperature must be below the on temperature")
            if a[1] == "thresholds2" and b.rd(STATUS + 0x30) not in OBS_E7A3_LAYOUT:
                sys.exit("*** tier 2 exists on E7a3 shells only (OBS_ID 0x0B5E0006/7/9/A/C)")
            b.wr(STATUS + (0xD8 if a[1] == "thresholds2" else 0xC4), c2code(off) << 16 | c2code(on))
            if b.rd(STATUS + 0x30) in OBS_E7A3_LAYOUT:
                t1, t2 = b.rd(STATUS + 0xC4), b.rd(STATUS + 0xD8)
                if (t2 & 0x3FF) < (t1 & 0x3FF) or (t2 >> 16 & 0x3FF) < (t1 >> 16 & 0x3FF):
                    print("*** warning: tier 2 is set below tier 1 (tier 2 on %.1f C / off %.1f C, tier 1 on %.1f C / off %.1f C)" % (
                        code2c(t2 & 0x3FF), code2c(t2 >> 16 & 0x3FF), code2c(t1 & 0x3FF), code2c(t1 >> 16 & 0x3FF)))
        elif len(a) == 4 and a[1] == "tierlevel" and a[2] in ("1", "2") and a[3] in ("2", "4"):
            if b.rd(STATUS + 0x30) not in OBS_E7A3_LAYOUT:
                sys.exit("*** per-tier levels exist on E7a3 shells only")
            tl, sh = b.rd(STATUS + 0xDC), (0 if a[2] == "1" else 8)
            b.wr(STATUS + 0xDC, (tl & ~(3 << sh)) | ((1 if a[3] == "4" else 0) << sh))
        elif len(a) == 3 and a[1] == "failsafe" and a[2] in ("on", "off"):
            if b.rd(STATUS + 0x30) not in OBS_E7A3_LAYOUT:
                sys.exit("*** the stale-temperature fail-safe exists on E7a3 shells only")
            tl = b.rd(STATUS + 0xDC)
            b.wr(STATUS + 0xDC, (tl & ~(1 << 16)) | ((1 if a[2] == "on" else 0) << 16))
        elif len(a) != 1:
            sys.exit(__doc__)
        if len(a) == 3 and a[1] in ("force", "level", "enable", "gate"):
            b.wr(STATUS + 0xC0, c)
        time.sleep(0.01); show_throttle(b); return
    if a[0] == "clear":
        if b.rd(STATUS + 0x30) not in OBS_IDS:
            sys.exit("*** this shell has no observability block (fp8c+ only)")
        b.wr(STATUS + 0x30, OBS_CLEAR)
        oid = b.rd(STATUS + 0x30)
        print("observability counters cleared (lock losses, fenced accesses%s%s; uptime and ECC/link-down kept%s)" % (
            ", AXI errors" if oid in OBS_MON else "", ", throttle/PCIe/PR counters and timestamps" if oid in OBS_E7 else "",
            "; throttle settings and the flight recorder are never cleared" if oid in OBS_E7 else ""))
        show_health(b); return
    want = MODES[a[0]]
    prev = b.rd(MODE_REG) & 3
    b.wr(MODE_REG, want)
    if (b.rd(MODE_REG) & 3) != want:
        sys.exit("*** mode register did not take the write (read back %d) -- not an rbdm shell?" % (b.rd(MODE_REG) & 3))
    t0 = time.time()
    while time.time() - t0 < 5:
        st = decode(b)
        if st["in_force"] == NAMES[want]:
            break
        time.sleep(0.05)
    else:
        if want == 3 and st["in_force"] == "off":
            # a v1.2 gate maps 3 to OFF: undo, so a production shell is not left with its DDR switched off
            b.wr(MODE_REG, prev)
            sys.exit("*** this shell's calibration gate has no hybrid mode (v1.2: 3 = off); restored mode '%s'" % NAMES[prev])
        show(st); sys.exit("*** mode not applied within 5 s (DDR traffic still in flight?)")
    if want in (0, 3):
        t0 = time.time()
        while time.time() - t0 < 10 and not decode(b)["gate_open"]:
            time.sleep(0.1)
    show(decode(b))

if __name__ == "__main__":
    main()
