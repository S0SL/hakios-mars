#!/usr/bin/env python3
import struct, gzip, hashlib
from pathlib import Path

img = Path("/tmp/xnu-oldfd-capsz.img").read_bytes()
ks = struct.unpack_from("<I", img, 8)[0]
raw = gzip.decompress(img[2048:2048+ks])
idx = raw.find(b"XNUP")
print("XNUP", idx, "raw", len(raw))
p = idx + 8
while p + 24 <= len(raw):
    name = raw[p:p+16].split(b"\x00", 1)[0].decode("ascii", "replace")
    if not name:
        break
    size = struct.unpack_from("<I", raw, p+16)[0]
    data = raw[p+24:p+24+size]
    print(name, size)
    if name in ("hakios-kernel", "kernel", "loader.efi"):
        i = data.find(b"Darwin Kernel Version")
        if i >= 0:
            print("  ver:", data[i:i+90].split(b"\x00")[0].decode(errors="replace"))
        print("  sha256", hashlib.sha256(data).hexdigest())
    p = p + 24 + size
    p = (p + 15) & ~15

k = Path("/home/shen/hakios/hakios-kernel").read_bytes()
i = k.find(b"Darwin Kernel Version")
print("server hakios-kernel ver:", k[i:i+90].split(b"\x00")[0].decode(errors="replace") if i>=0 else "not found")
print("server hakios-kernel sha256", hashlib.sha256(k).hexdigest())
