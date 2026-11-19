#!/usr/bin/env python3
"""Patch panel-novatek-nt35596s.c: move DCS init sequence from .prepare() to a new
.enable() callback so DCS commands are sent AFTER the DSI host is enabled.
Fixes: panel-jdi-nt35596s "failed to send DCS Init 1st Code: -22" and the
panel auto-sleep (~30s watchdog) that caused black screen after boot text.
"""
import sys

PATH = "panel-novatek-nt35596s.c"

OLD_PREPARE = """static int nt35596s_panel_prepare(struct drm_panel *panel)
{
\tstruct nt35596s_panel *pinfo = to_nt35596s_panel(panel);
\tint err;

\tif (pinfo->prepared)
\t\treturn 0;

\terr = nt35596s_panel_power_on(pinfo);
\tif (err < 0)
\t\tgoto poweroff;

\t/* send first part of init cmds */
\terr = nt35596s_send_cmds(panel, pinfo->desc->on_cmds,
\t\t\t\t pinfo->desc->num_on_cmds);

\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to send DCS Init 1st Code: %d\\n", err);
\t\tgoto poweroff;
\t}

\terr = mipi_dsi_dcs_exit_sleep_mode(pinfo->link);
\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to exit sleep mode: %d\\n", err);
\t\tgoto poweroff;
\t}

\t/* 0x46 = 70 ms delay */
\tmsleep(70);

\terr = mipi_dsi_dcs_set_display_on(pinfo->link);
\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to Set Display ON: %d\\n", err);
\t\tgoto poweroff;
\t}

\tmsleep(120);

\tpinfo->prepared = true;

\treturn 0;

poweroff:
\tgpiod_set_value(pinfo->reset_gpio, 0);
\treturn err;
}
"""

NEW_PREPARE_ENABLE = """static int nt35596s_panel_prepare(struct drm_panel *panel)
{
\tstruct nt35596s_panel *pinfo = to_nt35596s_panel(panel);
\tint err;

\tif (pinfo->prepared)
\t\treturn 0;

\terr = nt35596s_panel_power_on(pinfo);
\tif (err < 0)
\t\tgoto poweroff;

\tpinfo->prepared = true;

\treturn 0;

poweroff:
\tgpiod_set_value(pinfo->reset_gpio, 0);
\treturn err;
}

/*
 * DCS init/display-on must happen in .enable(), not .prepare(): the DSI host
 * is not yet enabled during the pre_enable phase, so every DCS transfer
 * returns -EINVAL and the panel never receives Display On. The panel
 * controller then auto-sleeps after its ~30s watchdog and the screen goes
 * black with no kernel log. Enable runs after the DSI host bridge enable,
 * so the transfers succeed here.
 */
static int nt35596s_panel_enable(struct drm_panel *panel)
{
\tstruct nt35596s_panel *pinfo = to_nt35596s_panel(panel);
\tint err;

\tif (!pinfo->prepared)
\t\treturn 0;

\t/* send first part of init cmds */
\terr = nt35596s_send_cmds(panel, pinfo->desc->on_cmds,
\t\t\t\t pinfo->desc->num_on_cmds);

\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to send DCS Init 1st Code: %d\\n", err);
\t\treturn err;
\t}

\terr = mipi_dsi_dcs_exit_sleep_mode(pinfo->link);
\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to exit sleep mode: %d\\n", err);
\t\treturn err;
\t}

\t/* 0x46 = 70 ms delay */
\tmsleep(70);

\terr = mipi_dsi_dcs_set_display_on(pinfo->link);
\tif (err < 0) {
\t\tdev_err(panel->dev, "failed to Set Display ON: %d\\n", err);
\t\treturn err;
\t}

\tmsleep(120);

\treturn 0;
}
"""

OLD_FUNCS = """static const struct drm_panel_funcs panel_funcs = {
\t.disable = nt35596s_panel_disable,
\t.unprepare = nt35596s_panel_unprepare,
\t.prepare = nt35596s_panel_prepare,
\t.get_modes = nt35596s_panel_get_modes,
};"""

NEW_FUNCS = """static const struct drm_panel_funcs panel_funcs = {
\t.disable = nt35596s_panel_disable,
\t.unprepare = nt35596s_panel_unprepare,
\t.prepare = nt35596s_panel_prepare,
\t.enable = nt35596s_panel_enable,
\t.get_modes = nt35596s_panel_get_modes,
};"""


def main():
    src = open(PATH, encoding="utf-8").read()

    for name, old in (("prepare-body", OLD_PREPARE), ("panel-funcs", OLD_FUNCS)):
        n = src.count(old)
        if n != 1:
            print("ERROR: %s matched %d times (expected 1)" % (name, n))
            sys.exit(1)

    src = src.replace(OLD_PREPARE, NEW_PREPARE_ENABLE)
    src = src.replace(OLD_FUNCS, NEW_FUNCS)

    open(PATH, "w", encoding="utf-8").write(src)
    print("panel patch applied OK")


if __name__ == "__main__":
    main()
