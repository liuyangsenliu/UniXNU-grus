#!/usr/bin/env python3
"""Inject an unconditional bootcmd run at the top of main_loop().

grus has no reachable console (no UART, vidconsole disabled), so stdin is a
dead serial device. main_loop() -> autoboot/process_button_cmds() blocks on
that dead stdin and bootcmd never runs. Patch main_loop to execute bootcmd
before anything else, so the boot continues without any console input.

Idempotent: skips if already injected.
"""
import sys

ANCHOR = "void main_loop(void)\n{\n\tconst char *s;\n"
INJECT = """void main_loop(void)
{
\tconst char *s;

\t/* grus: no usable console, so autoboot would block on a dead stdin
\t * before bootcmd ever runs. Run bootcmd unconditionally right here.
\t */
\tif (env_get("bootcmd"))
\t\trun_command_list(env_get("bootcmd"), -1, 0);
"""


def main(path):
    src = open(path, encoding="utf-8", newline="").read()
    if "run_command_list(env_get(\"bootcmd\"), -1, 0);" in src:
        print("already injected, skip")
        return 0
    if src.count(ANCHOR) != 1:
        print("FATAL: anchor count=%d" % src.count(ANCHOR), file=sys.stderr)
        return 1
    out = src.replace(ANCHOR, INJECT, 1)
    open(path, "w", encoding="utf-8", newline="").write(out)
    print("injected early bootcmd into", path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
