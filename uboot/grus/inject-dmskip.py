#!/usr/bin/env python3
"""Lazy driver-model bring-up: bind everything, probe nothing (grus v27).

v26 proved main_loop is reachable when the DM scan is skipped entirely --
but that also skips binding, so there is no UFS device to boot from.
The full dm_autoprobe() (probe every bound device at initcall time) is
what stalls this port. v27 keeps the binding stages (the exact body of
root.c's static dm_scan(), via its public pieces) but drops the
autoprobe: devices are probed lazily, on demand, when a command actually
touches them (scsi scan -> UFS chain only). Unrelated devices that hung
the autoprobe are never probed at all.

Idempotent.
"""
import sys

ANCHOR = "\tret = dm_init_and_scan(false);\n"
REPL = (
    "\t/* grus v27: bind all devices (dm_scan_plat + dm_extended_scan +\n"
    "\t * dm_scan_other) but skip the autoprobe stage. Probing every device\n"
    "\t * at initcall time stalls the port; lazy probing on demand\n"
    "\t * (scsi scan -> UFS chain) avoids it.\n"
    "\t */\n"
    "\tret = dm_init(CONFIG_IS_ENABLED(OF_LIVE));\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_plat(false);\n"
    "\tif (!ret)\n"
    "\t\tret = dm_extended_scan(false);\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_other(false);\n"
)
MARK = "grus v27: bind all devices"


def main(path):
    src = open(path, encoding="utf-8").read()  # universal newlines
    if MARK in src:
        print("already injected, skip")
        return 0
    if src.count(ANCHOR) != 1:
        print("FATAL: anchor count=%d" % src.count(ANCHOR), file=sys.stderr)
        return 1
    out = src.replace(ANCHOR, REPL, 1)
    # the "if (ret) return ret;" then "return dm_autoprobe();" must not call
    # autoprobe either -> neutralise that too.
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
    print("injected lazy dm scan into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
