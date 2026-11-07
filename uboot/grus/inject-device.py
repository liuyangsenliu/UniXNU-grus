#!/usr/bin/env python3
"""Inject a per-device probe counter into U-Boot's drivers/core/device.c.

grus has no UART; the ABL splash framebuffer at 0x9c000000 is the only output
channel. board_init_r freezes nondeterministically inside the DM scan/probe
initcall, so paint one 8-bit binary readout (cyan lit blocks, y=2100) per
device_probe() entry, armed only after relocation. Whatever value stays on
screen is the number of probes that STARTED; the hang is inside probe #N
(0-based: the probe that started but never returned).

Usage: inject-device.py <path-to-drivers/core/device.c>
"""
import sys

HELPER = """
/* DIAG (grus): per-probe framebuffer counter. Cyan 8-bit binary readout at
 * y=2100, bit0 leftmost. Armed from board_init_r (post-relocation) via
 * diag_probe_arm(); every device_probe() entry redraws it, so the value left
 * on screen when the boot freezes is the index of the probe that hung.
 */
static int diag_probe_n;
static int diag_probe_ready;

void diag_probe_arm(void)
{
	diag_probe_n = 0;
	diag_probe_ready = 1;
}

static void diag_probe_tick(void)
{
	volatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
	int i, x, y;
	int n = diag_probe_n++;

	for (i = 0; i < 8; i++) {
		unsigned int c = ((n >> i) & 1) ? 0xff00ffff : 0xff101010;
		int bx = 140 + i * 100;

		for (y = 2100; y < 2180; y++)
			for (x = bx; x < bx + 70; x++)
				fb[y * 1080 + x] = c;
	}
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

    call = "\n\tif (diag_probe_ready)\n\t\tdiag_probe_tick();\n"
    out = src.replace(anchor, HELPER + anchor + call, 1)

    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected per-probe counter into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
