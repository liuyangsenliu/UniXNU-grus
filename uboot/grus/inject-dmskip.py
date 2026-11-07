#!/usr/bin/env python3
"""Skip dm_scan()/dm_autoprobe() in initr_dm().

On grus the driver-model scan hangs (no UFS/clock/regulator bring-up in this
port), which kills board_init_r before main_loop ever runs. Keep dm_init() so
uclass/root structures stay valid, but skip the scan and autoprobe stages.

Idempotent.
"""
import sys

ANCHOR = "\tret = dm_init_and_scan(false);\n"
REPL = (
    "\t/* grus bring-up: dm_scan()/dm_autoprobe() never return on this port\n"
    "\t * (UFS/clock/regulator probes), killing board_init_r before\n"
    "\t * main_loop. Keep dm_init() for uclass/root, skip the scan.\n"
    "\t */\n"
    "\tret = dm_init();\n"
)
MARK = "ret = dm_init();"


def main(path):
    src = open(path, encoding="utf-8").read()  # universal newlines
    if "dm_scan()/dm_autoprobe() never return" in src:
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

    # initr_dm_devices() probes the early timer, which also hangs on this port.
    old_timer = "\tif (IS_ENABLED(CONFIG_TIMER_EARLY)) {\n\t\tret = dm_timer_init();\n"
    new_timer = "\tif (0) {\n\t\tret = dm_timer_init();\n"
    if out.count(old_timer) == 1:
        out = out.replace(old_timer, new_timer, 1)
    else:
        print("note: timer anchor count=%d, skipped" % out.count(old_timer),
              file=sys.stderr)
    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected dm scan skip into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
