#!/usr/bin/env python3
"""Replace UFSDxe's TEE-backed listener initializers with success stubs.

The mars UEFI does not bring up the TEE protocols RPMB needs.  Normal GPT
partition discovery and Block I/O do not need those protected listeners, so
this experiment keeps the UFS driver and omits only the RPMB and GPT-RW
callbacks.  The original PE is preserved next to the patched file on first use.
"""

from pathlib import Path
import shutil
import sys


EXPECTED = bytes.fromhex("ff8300d1fd7b01a9")  # sub sp, sp, #32; stp x29, x30, [sp, #16]
STUB = bytes.fromhex("e0031faac0035fd6")      # mov x0, xzr; ret
PATCHES = (
    (0x10900, "RPMB listener"),
    (0xFD2C, "GPT listener"),
)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} UFSDxe.efi", file=sys.stderr)
        return 2

    image = Path(sys.argv[1])
    backup = image.with_name(image.name + ".rpmb-original")
    data = bytearray(image.read_bytes())
    if not backup.exists():
        shutil.copy2(image, backup)
        print(f"backup: {backup}")

    for offset, label in PATCHES:
        current = bytes(data[offset:offset + len(EXPECTED)])
        if current == STUB:
            print(f"{image}: {label} already patched")
            continue
        if current != EXPECTED:
            print(
                f"{image}: unexpected {label} bytes at {offset:#x}: "
                f"{current.hex()} (expected {EXPECTED.hex()})",
                file=sys.stderr,
            )
            return 1
        data[offset:offset + len(STUB)] = STUB
        print(f"patched: {label} at {offset:#x}")

    image.write_bytes(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
