#!/usr/bin/env python3
"""Inject per-bind diagnostics into U-Boot's drivers/core/device.c (grus v30).

v29 proved the stall is not dm_init(): `dm_init(false)` alone reaches
main_loop (v26), while adding `dm_scan_plat()` + `dm_scan_fdt()` -- which
only call device_bind_common() -- never gets there. So some driver's
bind() (or a post_bind hook) never returns.

This paints, on every call to device_bind_common(), the first five
characters of the DRIVER name plus the bind counter, and a 4-stage bar
showing how far that one bind got:

  stage 0 white  : entered device_bind_common(), about to uclass_bind_device
  stage 1 cyan   : uclass_bind_device() returned, about to drv->bind()
  stage 2 yellow : drv->bind() returned, about to child_post_bind/post_bind
  stage 3 gold   : bind fully completed (device marked DM_FLAG_BOUND)

The last name on screen when it hangs is the offending driver, and the lit
stage says whether it died inside bind() or in a post_bind hook.

Layout (framebuffer 0x9c000000, 1080 px/row):
  y 1150..1400  orange 5x8 ASCII readout, 5 chars, byte bits left->right
  y 1450..1530  cyan 8-bit bind counter
  y 1150+i*60   stage bar at x 980..1050 (right of the name block)

Usage: inject-bind.py <path-to-drivers/core/device.c>
"""
import sys

HELPER = """
/* DIAG (grus): per-bind framebuffer diagnostics. See file header comment. */
static int diag_bind_n;

static void diag_bind_paint(const char *nm, int n)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	int r, i, x, y;

	/* driver name: 5 rows of 8-bit ASCII, orange lit */
	for (r = 0; r < 5; r++) {
		unsigned char ch = (nm && nm[r]) ? (unsigned char)nm[r] : 0;

		for (i = 0; i < 8; i++) {
			unsigned int c = ((ch >> i) & 1) ? 0xffff8000 : 0xff101010;
			int bx = 140 + i * 100;
			int by = 1150 + r * 50;

			for (y = by; y < by + 40; y++)
				for (x = bx; x < bx + 70; x++)
					fb[y * 1080 + x] = c;
		}
	}

	/* bind counter: cyan 8-bit binary at y=1450 */
	for (i = 0; i < 8; i++) {
		unsigned int c = ((n >> i) & 1) ? 0xff00ffff : 0xff101010;
		int bx = 140 + i * 100;

		for (y = 1450; y < 1530; y++)
			for (x = bx; x < bx + 70; x++)
				fb[y * 1080 + x] = c;
	}
}

static void diag_bind_stage(int stage)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	static const unsigned int sc[4] = {
		0xffffffff, 0xff00ffff, 0xffffff00, 0xffffc000
	};
	int i, x, y;

	for (i = 0; i < 4; i++) {
		unsigned int c = (i == stage) ? sc[i] : 0xff101010;
		int by = 1150 + i * 60;

		for (y = by; y < by + 45; y++)
			for (x = 980; x < 1050; x++)
				fb[y * 1080 + x] = c;
	}
}

"""

A_ENTER = "\tret = uclass_bind_device(dev);\n"
A_BIND = "\tif (drv->bind) {\n"
A_POST = "\tif (parent && parent->driver->child_post_bind) {\n"
A_BOUND = "\tdev_or_flags(dev, DM_FLAG_BOUND);\n"
MARK = "DIAG (grus): per-bind framebuffer diagnostics"


def insert_before(src, anchor, text, label):
    if src.count(anchor) != 1:
        print("FATAL: %s anchor count=%d" % (label, src.count(anchor)),
              file=sys.stderr)
        raise SystemExit(1)
    return src.replace(anchor, text + anchor, 1)


def main(path):
    src = open(path, encoding="utf-8").read()  # universal newlines
    if MARK in src:
        print("already injected, skip")
        return 0

    anchor = "static int device_bind_common(struct udevice *parent, const struct driver *drv,"
    if src.count(anchor) != 1:
        print("FATAL: function anchor count=%d" % src.count(anchor),
              file=sys.stderr)
        return 1
    out = src.replace(anchor, HELPER.lstrip("\n") + anchor, 1)

    out = insert_before(out, A_ENTER,
                        "\tdiag_bind_paint(drv->name, diag_bind_n++);\n"
                        "\tdiag_bind_stage(0);\n", "uclass_bind_device")
    out = insert_before(out, A_BIND, "\tdiag_bind_stage(1);\n", "drv->bind")
    out = insert_before(out, A_POST, "\tdiag_bind_stage(2);\n", "child_post_bind")
    out = insert_before(out, A_BOUND, "\tdiag_bind_stage(3);\n", "DM_FLAG_BOUND")

    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected per-bind driver-name + stage probe into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
