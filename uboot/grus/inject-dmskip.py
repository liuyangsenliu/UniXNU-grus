#!/usr/bin/env python3
"""Driver-model bring-up for grus: bind from the flat DT, probe lazily (v30).

  v26  dm_init(false) and nothing else -> main_loop reached, but nothing was
       bound, so there was no UFS to boot from.
  v27  dm_init(CONFIG_IS_ENABLED(OF_LIVE)) + dm_scan_plat + dm_extended_scan
       + dm_scan_other -> never reached main_loop. This .config has
       CONFIG_OF_LIVE=y, so that expression evaluated to dm_init(true).
  v29  dm_init(false) + dm_scan_plat + dm_scan_fdt -> still never reached
       main_loop (the phone fell back to the stock aboot fastboot). Binding
       happens inside device_bind_common(), so a driver's bind() or a
       post_bind hook is what never returns -- see inject-bind.py, which
       paints the offending driver's name on screen.

v30 keeps the same shape as v29 and adds three status bands so the screen
says exactly which stage ran:

  y 1000..1039  green  : dm_init(false) returned 0
  y 1060..1074  cyan   : dm_scan_plat(false) returned
  y 1080..1094  yellow : dm_scan_fdt(false) returned (bind stage done)

Idempotent.
"""
import sys

ANCHOR = "\tret = dm_init_and_scan(false);\n"
REPL = (
    "\t/* grus v30: flat-tree dm_init (v26 semantics) + bind only, with\n"
    "\t * status bands. dm_autoprobe() stays off: a command that needs a\n"
    "\t * device probes just that chain on demand (scsi scan -> UFS).\n"
    "\t */\n"
    "\tret = dm_init(false);\n"
    "\t{\n"
    "\t\tvolatile unsigned int *fb = (volatile unsigned int *)0x9c000000;\n"
    "\t\tint py, px;\n"
    "\n"
    "\t\t/* green: dm_init() came back */\n"
    "\t\tfor (py = 1000; py < 1040; py++)\n"
    "\t\t\tfor (px = 0; px < 1080; px++)\n"
    "\t\t\t\tfb[py * 1080 + px] = 0xff00ff00;\n"
    "\t}\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_plat(false);\n"
    "\t{\n"
    "\t\tvolatile unsigned int *fb = (volatile unsigned int *)0x9c000000;\n"
    "\t\tint py, px;\n"
    "\n"
    "\t\t/* cyan: dm_scan_plat() came back */\n"
    "\t\tfor (py = 1060; py < 1074; py++)\n"
    "\t\t\tfor (px = 0; px < 1080; px++)\n"
    "\t\t\t\tfb[py * 1080 + px] = 0xff00ffff;\n"
    "\t}\n"
    "\tif (!ret)\n"
    "\t\tret = dm_scan_fdt(false);\n"
    "\t{\n"
    "\t\tvolatile unsigned int *fb = (volatile unsigned int *)0x9c000000;\n"
    "\t\tint py, px;\n"
    "\n"
    "\t\t/* yellow: dm_scan_fdt() came back (all binds returned) */\n"
    "\t\tfor (py = 1080; py < 1094; py++)\n"
    "\t\t\tfor (px = 0; px < 1080; px++)\n"
    "\t\t\t\tfb[py * 1080 + px] = 0xffffff00;\n"
    "\t}\n"
)
MARK = "grus v30: flat-tree dm_init"


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
    print("injected flat-tree dm init + stage bands into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
