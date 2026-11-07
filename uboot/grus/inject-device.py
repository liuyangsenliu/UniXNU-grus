#!/usr/bin/env python3
"""Inject per-probe diagnostics into U-Boot's drivers/core/device.c.

grus has no UART; the ABL splash framebuffer at 0x9c000000 is the only output
channel. board_init_r freezes inside DM init with probe counter frozen at 3
and the last probed device named "root_...", so besides the cyan 8-bit probe
counter (y=2100) and the orange 5x8 ASCII name readout (y=1830, x=140..850)
this injects 7 colour milestone bars on the right of the name block
(x=880..950, y=1830+i*50) that show how far the CURRENT device_probe() got:

  stage 0 (white)   : entered device_probe()
  stage 1 (yellow)  : device_of_to_plat() done
  stage 2 (magenta) : parent chain probed
  stage 3 (orange)  : pinctrl default state done
  stage 4 (green)   : clk_set_defaults() done
  stage 5 (blue)    : drv->probe() returned
  stage 6 (red)     : post-probe / POST_PROBE notify done, about to return

Only the bar of the current stage is lit; entering a probe repaints all 7.
The bar left on screen when the boot hangs is the stage that hung.

Usage: inject-device.py <path-to-drivers/core/device.c>
"""
import sys

HELPER = """
/* DIAG (grus): per-probe framebuffer diagnostics. See file header comment. */
static int diag_probe_n;
static int diag_probe_ready;

void diag_probe_arm(void)
{
	diag_probe_n = 0;
	diag_probe_ready = 1;
}

static void diag_probe_paint(const char *nm, int n)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	int r, i, x, y;

	/* device name: 5 rows of 8-bit ASCII, orange lit */
	for (r = 0; r < 5; r++) {
		unsigned char ch = (nm && nm[r]) ? (unsigned char)nm[r] : 0;

		for (i = 0; i < 8; i++) {
			unsigned int c = ((ch >> i) & 1) ? 0xff2080ff : 0xff101010;
			int bx = 140 + i * 100;
			int by = 1830 + r * 50;

			for (y = by; y < by + 40; y++)
				for (x = bx; x < bx + 70; x++)
					fb[y * 1080 + x] = c;
		}
	}

	/* probe counter: cyan 8-bit binary at y=2100 */
	for (i = 0; i < 8; i++) {
		unsigned int c = ((n >> i) & 1) ? 0xff00ffff : 0xff101010;
		int bx = 140 + i * 100;

		for (y = 2100; y < 2180; y++)
			for (x = bx; x < bx + 70; x++)
				fb[y * 1080 + x] = c;
	}
}

static void diag_probe_tick(const char *nm)
{
	if (!diag_probe_ready)
		return;
	diag_probe_paint(nm, diag_probe_n++);
}

/* fail-path error code: cyan 8-bit binary of ret at y=2240 (bit0 leftmost) */
static void diag_probe_fail(int ret)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	int i, x, y;

	for (i = 0; i < 8; i++) {
		unsigned int c = ((ret >> i) & 1) ? 0xff00ffff : 0xff101010;
		int bx = 140 + i * 100;

		for (y = 2240; y < 2320; y++)
			for (x = bx; x < bx + 70; x++)
				fb[y * 1080 + x] = c;
	}
}

/* milestone bars: 8 vertical bars right of the name block; 7=gold means
 * device_notify(EVT_DM_POST_PROBE) returned 0 and probe is about to return */
static void diag_probe_stage(int stage)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	static const unsigned int sc[8] = {
		0xffffffff, 0xffffff00, 0xffff00ff, 0xffff8000,
		0xff00ff00, 0xff0000ff, 0xffff0000, 0xffffc000
	};
	int i, x, y;

	for (i = 0; i < 8; i++) {
		unsigned int c = (i == stage) ? sc[i] : 0xff101010;
		int by = 1830 + i * 50;

		for (y = by; y < by + 40; y++)
			for (x = 880; x < 950; x++)
				fb[y * 1080 + x] = c;
	}
}

"""

STAGES = [
    # (name, unique anchor in device_probe(); stage call inserted BEFORE anchor)
    ("S1", "\tret = device_of_to_plat(dev);\n\tif (ret)\n\t\tgoto fail;"),
    ("S2", "\tdev_or_flags(dev, DM_FLAG_ACTIVATED);"),
    ("S3", "\tif (CONFIG_IS_ENABLED(IOMMU) && dev->parent &&"),
    ("S4", "\tif (drv->probe) {"),
    ("S5", "\tret = uclass_post_probe_device(dev);"),
    ("S6", "\tret = device_notify(dev, EVT_DM_POST_PROBE);"),
    # gold bar: notify returned 0, success path, about to return 0
    ("S7", "\treturn 0;\nfail_event:"),
]


def stage_call(n):
    return "\tif (diag_probe_ready)\n\t\tdiag_probe_stage(%d);\n" % n


def main():
    if len(sys.argv) < 2:
        print("usage: inject-device.py <drivers/core/device.c>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    src = open(path, encoding="utf-8").read()

    anchor = "int device_probe(struct udevice *dev)\n{"
    if src.count(anchor) != 1:
        print(f"FATAL: anchor not unique/found: {anchor!r} (count={src.count(anchor)})",
              file=sys.stderr)
        return 1

    call = ("\n\tif (diag_probe_ready) {\n\t\tdiag_probe_tick(dev->name);\n"
            "\t\tdiag_probe_stage(0);\n\t}\n")
    out = src.replace(anchor, HELPER + anchor + call, 1)

    for name, a in STAGES:
        n = int(name[1])
        if out.count(a) != 1:
            print(f"FATAL: stage {name} anchor not unique: count={out.count(a)}",
                  file=sys.stderr)
            return 1
        out = out.replace(a, stage_call(n) + a, 1)

    # fail-path: paint the error code so a failing probe shows ret on screen
    fail_anchor = "\nfail:\n\tdev_bic_flags(dev, DM_FLAG_ACTIVATED);"
    fail_call = "\n\tif (diag_probe_ready)\n\t\tdiag_probe_fail(ret);"
    if out.count(fail_anchor) != 1:
        print(f"FATAL: fail anchor count={out.count(fail_anchor)}", file=sys.stderr)
        return 1
    out = out.replace(fail_anchor, fail_call + fail_anchor, 1)

    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected probe counter + name readout + 8 milestone bars + fail readout into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
