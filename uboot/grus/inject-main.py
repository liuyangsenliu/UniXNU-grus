#!/usr/bin/env python3
"""Inject framebuffer progress markers into U-Boot's common/main.c.

The grus splash framebuffer at 0x9c000000 is the only output channel this port
has. Rather than guessing why main_loop() stalls, paint one full-width colour
band per stage, in the exact order main_loop() executes them. Whatever band is
missing on the panel marks the stage that hung.

The anchors are unique bare substrings of common/main.c, so this does not
depend on line numbers or whitespace.

Usage: inject-main.py <path-to-common/main.c>
"""
import sys

MARKS = {
    "after_bootstage":  (1560, 0xffffffff),  # white : main_loop entered
    "after_cli_init":   (1620, 0xff00ffff),  # cyan  : cli_init() returned
    "before_buttons":   (1800, 0xffff8020),  # orange: about to probe buttons
    "after_buttons":    (1860, 0xff4080ff),  # pink  : process_button_cmds() returned
    "after_bootdelay":  (1920, 0xff8000ff),  # purple: bootdelay_process() returned
    "before_autoboot":  (1980, 0xffffff00),  # yellow: about to run bootcmd
    "after_autoboot":   (2040, 0xff00ff00),  # green : autoboot_command() returned
    "before_cliloop":   (2100, 0xffff0000),  # red   : about to enter the shell
}

HELPER = """
/* DIAG (grus): direct splash-framebuffer progress markers. No console
 * framework involved: the ABL splash buffer at 0x9c000000 is 1080 px wide
 * and the display controller scans it statically, so any write is visible.
 */
static void diag_band_ml(int y0, int y1, unsigned int c)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	int x, y;

	for (y = y0; y < y1; y++)
		for (x = 0; x < 1080; x++)
			fb[y * 1080 + x] = c;
}

static void diag_mark_ml(const char *which, int y0, int y1, unsigned int c)
{
	diag_band_ml(y0, y1, c);
	(void)which;
}

"""


def band(name):
    y0, color = MARKS[name]
    return f"\tdiag_mark_ml(\"{name}\", {y0}, {y0 + 36}, 0x{color:08x});\n"


def main():
    if len(sys.argv) < 2:
        print("usage: inject-main.py <common/main.c>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    src = open(path, encoding="utf-8").read()

    # Anchor -> (text to insert before it, text to insert after it)
    edits = [
        ("bootstage_mark_name(BOOTSTAGE_ID_MAIN_LOOP, \"main_loop\");",
         "", band("after_bootstage")),
        ("cli_init();",
         "", band("after_cli_init")),
        ("process_button_cmds();",
         band("before_buttons"), band("after_buttons")),
        ("bootdelay_process();",
         "", band("after_bootdelay")),
        ("autoboot_command(s);",
         band("before_autoboot"), band("after_autoboot")),
        ("cli_loop();",
         band("before_cliloop"), ""),
    ]

    # Add the helper right after the last #include line.
    lines = src.splitlines(keepends=True)
    last_inc = max(i for i, l in enumerate(lines) if l.startswith("#include"))
    lines.insert(last_inc + 1, HELPER)
    out = "".join(lines)

    for anchor, before, after in edits:
        if anchor not in out:
            print(f"FATAL: anchor not found: {anchor!r}", file=sys.stderr)
            return 1
        if out.count(anchor) != 1:
            print(f"FATAL: anchor not unique: {anchor!r}", file=sys.stderr)
            return 1
        out = out.replace(anchor, before + anchor + after, 1)

    open(path, "w", encoding="utf-8", newline="").write(out)
    print(f"injected {len(edits)} markers into {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
