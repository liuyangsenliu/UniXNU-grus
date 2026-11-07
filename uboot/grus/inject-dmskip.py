#!/usr/bin/env python3
"""Driver-model bring-up: bind from the flat DT, probe lazily (grus v29).

History of this hook:
  v26  dm_init(false) and nothing else -> main_loop reached, but no devices
       were bound at all, so there was no UFS to boot from.
  v27  dm_init(CONFIG_IS_ENABLED(OF_LIVE)) + dm_scan_plat + dm_extended_scan
       + dm_scan_other -> never reached main_loop. This .config has
       CONFIG_OF_LIVE=y, so that expression evaluated to dm_init(true): the
       flat device tree was converted to a live tree, which is the one
       difference against the v26 call that demonstrably worked.
  v29  dm_init(false) (flat tree, exactly like v26) + dm_scan_plat(false) +
       dm_scan_fdt(false). The extra "/chosen", "/clocks", "/firmware",
       "/reserved-memory" sweeps of dm_extended_scan are dropped, and
       dm_autoprobe() stays disabled: a command that needs a device
       (`scsi scan`) probes just that device's chain on demand.

Idempotent.
"""
import sys

ANCHOR = "\tret = dm_init_and_scan(false);\n"
REPL = (
    "\t/* grus v29: flat-tree dm_init (v26 semantics) + bind only.\n"
    "\t * dm_extended_scan's extra /chosen, /clocks, /firmware and\n"
    "\t * /reserved-memory sweeps are dropped, and dm_autoprobe() is not\n"
    "\t * called: `scsi scan` probes the UFS chain on demand instead of\n"
    "\t * every bound device being probed here at initcall time.\n"
    "\t */\n"
    "\tret = dm_init(false);\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_plat(false);\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_fdt(false);\n"
)
MARK = "grus v29: flat-tree dm_init"


def main(path):
    src = open(path, encoding="utf-8").read()  # universal newlines
    if MARK in src:
        print("already injected, skip")
        return 0
    if src.count(ANCHOR) != 1:
        print("FATAL: anchor count=%d" % src.count(ANCHOR), file=sys.stderr)
        return 1
    out = src.replace(ANCHOR, REPL, 1)
    # the "if (ret) return ret;" then "return dm_autoprobe();" tail must not
    # call autoprobe either -> neutralise that too.
    old_tail = "\tif (ret)\n\t\treturn ret;\n\n\treturn dm_autoprobe();\n"
    new_tail = "\tif (ret)\n\t\treturn ret;\n\n\treturn 0;\n"
    if out.count(old_tail) != 1:
        print("FATAL: tail anchor count=%d" % out.count(old_tail), file=sys.stderr)
        return 1
    out = out.replace(old_tail, new_tail, 1)

    # initr_dm_devices() probes the early timer, which also hangs on this
    # port. Neutralise it: lib/time.c probes the timer lazily on first use.
    old_timer = "\tif (IS_ENABLED(CONFIG_TIMER_EARLY)) {\n\t\tret = dm_timer_init();\n"
    new_timer = "\tif (0) {\n\t\tret = dm_timer_init();\n"
    if out.count(old_timer) == 1:
        out = out.replace(old_timer, new_timer, 1)
    else:
        print("note: timer anchor count=%d, skipped" % out.count(old_timer),
              file=sys.stderr)
    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected flat-tree dm init into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
