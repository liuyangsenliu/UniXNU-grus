#!/usr/bin/env python3
"""Inject a per-device probe counter + device-name readout into U-Boot's
drivers/core/device.c.

grus has no UART; the ABL splash framebuffer at 0x9c000000 is the only output
channel. board_init_r freezes deterministically inside the DM scan/probe
initcall with probe counter frozen at 3 (device #4), so besides the 8-bit
cyan counter (y=2100) each device_probe() now also paints the first 5
characters of dev->name as 5 rows of 8-bit ASCII (orange lit blocks,
y=1830.., bit0 leftmost), redrawn on every probe. Whatever stays on screen
when the boot hangs names the driver that hung.

Usage: inject-device.py <path-to-drivers/core/device.c>
"""
import sys

HELPER = """
/* DIAG (grus): per-probe framebuffer counter + device-name readout.
 * Cyan 8-bit binary counter at y=2100, bit0 leftmost. Orange 5x8 ASCII
 * readout of dev->name[0..4] at y=1830 (row = char, bit0 leftmost).
 * Armed from board_init_r (post-relocation) via diag_probe_arm(); every
 * device_probe() entry redraws both, so the value left on screen when the
 * boot freezes is the probe index and the name of the device that hung.
 */
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

"""


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

    call = "\n\tif (diag_probe_ready)\n\t\tdiag_probe_tick(dev->name);\n"
    out = src.replace(anchor, HELPER + anchor + call, 1)

    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected per-probe counter + name readout into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
