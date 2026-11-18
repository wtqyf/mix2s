#!/usr/bin/env python3
"""
Patch the Qualcomm DSI 10nm PHY driver so that the PLL can lock when
it is started by the clock framework during probe.

Background
----------
dsi_pll_enable_pll_bias() only asserts BIT(5) of REG_DSI_10nm_PHY_CMN_CTRL_0
(= PLL bias). The PHY digital top stays powered down (BIT(6) not set) until
dsi_10nm_phy_enable() runs.

Since the clock framework applies DT "assigned-clock-parents" at probe time
(of_clk_set_defaults -> clk_set_parent -> clk_prepare_enable on the PLL),
dsi_pll_10nm_vco_prepare() runs before the PHY is enabled. The PLL cannot
lock in that state:

    msm_dsi_phy ae94400.phy: dsi_pll_10nm_vco_prepare: DSI PLL(0) lock failed, status=0x00000000

Upstream (Luca Weiss / Dmitry Baryshkov, dri-devel 2026-09) fixes this for
the 7nm PHY by powering up the digital top together with the PLL bias, and
notes the same fix applies to the 10nm PHY.

This script asserts BIT(6) alongside BIT(5). The normal enable path is
unaffected because dsi_10nm_phy_enable() writes 0x7f to CMN_CTRL_0 anyway.
"""
import sys

PATH = "dsi_phy_10nm.c"

OLD = "writel(data | BIT(5), pll->phy->base + REG_DSI_10nm_PHY_CMN_CTRL_0);"
NEW = "writel(data | BIT(6) | BIT(5), pll->phy->base + REG_DSI_10nm_PHY_CMN_CTRL_0);"


def main():
    try:
        src = open(PATH, "r", encoding="utf-8").read()
    except OSError as exc:
        print("ERROR: cannot read %s: %s" % (PATH, exc))
        return 1

    count = src.count(OLD)
    print("target occurrences: %d" % count)

    if count != 1:
        print("ERROR: expected exactly 1 occurrence, got %d" % count)
        print("--- lines mentioning CMN_CTRL_0 ---")
        for lineno, line in enumerate(src.splitlines(), 1):
            if "CMN_CTRL_0" in line or "CMN_CTRL" in line:
                print("%5d: %s" % (lineno, line.strip()))
        return 1

    patched = src.replace(OLD, NEW)
    open(PATH, "w", encoding="utf-8", newline="").write(patched)

    print("patched OK: digital top now powered up together with PLL bias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
