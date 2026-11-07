#!/usr/bin/env python3
"""Inject a C-level framebuffer paint (plus an early bootcmd run) at the top
of main_loop().

grus has no usable console and the env/bootcmd path proved unreliable, so we
paint the splash framebuffer (0x9c000000) straight from C:

  rows   0..149  -> white   (main_loop entered)
  rows 150..199  -> green   (paint helper ran to completion)

No command parsing, no console, no env involved: plain volatile stores. After
that we still try bootcmd so a working env can continue the boot.

Idempotent.
"""
import sys

ANCHOR = "void main_loop(void)\n{\n\tconst char *s;\n"

INJECT = """void main_loop(void)
{
\tconst char *s;

\t/* grus: C-level proof-of-life, independent of console/env/commands */
\t{
\t\tvolatile unsigned int *fb = (volatile unsigned int *)0x9c000000;
\t\tint y, x;

\t\tfor (y = 0; y < 150; y++)
\t\t\tfor (x = 0; x < 1080; x++)
\t\t\t\tfb[y * 1080 + x] = 0xffffffff;
\t\tfor (y = 150; y < 200; y++)
\t\t\tfor (x = 0; x < 1080; x++)
\t\t\t\tfb[y * 1080 + x] = 0xff00ff00;
\t}

\tif (env_get("bootcmd"))
\t\trun_command_list(env_get("bootcmd"), -1, 0);
"""

MARK = "fb[y * 1080 + x] = 0xff00ff00;"


def main(path):
    src = open(path, encoding="utf-8", newline="").read()
    if MARK in src:
        print("already injected, skip")
        return 0
    if src.count(ANCHOR) != 1:
        print("FATAL: anchor count=%d" % src.count(ANCHOR), file=sys.stderr)
        return 1
    out = src.replace(ANCHOR, INJECT, 1)
    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected C-level paint + early bootcmd into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
