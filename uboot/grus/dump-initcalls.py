#!/usr/bin/env python3
"""Dump the runtime initcall call order out of a built U-Boot aarch64 ELF.

The grus diag patch draws one 70x70 framebuffer block per INITCALL() the moment
board_init_r starts running. To map block N back to a function name we disassemble
the function that owns the ordered INITCALL list (initcall_run_r, or board_init_r
when it is inlined) and print every `bl` target in order.

Usage: dump-initcalls.py <u-boot-elf> [objdump-cmd]
"""
import re
import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        print("usage: dump-initcalls.py <elf> [objdump]", file=sys.stderr)
        return 2
    elf = sys.argv[1]
    od = sys.argv[2] if len(sys.argv) > 2 else "aarch64-linux-gnu-objdump"

    try:
        out = subprocess.run([od, "-d", "--no-show-raw-insn", elf],
                             capture_output=True, text=True, check=False).stdout
    except FileNotFoundError:
        print(f"objdump not found: {od}", file=sys.stderr)
        return 2
    if not out:
        print("objdump produced no output", file=sys.stderr)
        return 2

    lines = out.splitlines()
    targets = ["initcall_run_r", "board_init_r"]
    func = None
    start = None
    for i, line in enumerate(lines):
        m = re.match(r"^[0-9a-f]+ <([^>]+)>:$", line.strip())
        if m and m.group(1) in targets:
            func, start = m.group(1), i
            break
    if start is None:
        print("neither initcall_run_r nor board_init_r found", file=sys.stderr)
        return 1

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^[0-9a-f]+ <[^>]+>:$", lines[j].strip()):
            end = j
            break

    print(f"# function: {func}  (lines {start + 1}..{end})")
    print(f"# elf: {elf}")
    print("# idx  call-target")
    idx = 0
    for line in lines[start:end]:
        m = re.search(r"\bbl\s+[0-9a-f]+\s+<([^>]+)>", line)
        if not m:
            continue
        print(f"{idx:5d}  {m.group(1)}")
        idx += 1
    print(f"# total bl targets: {idx}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
