#!/usr/bin/env python3
import struct, zlib, hashlib
from pathlib import Path

def decompress_one(data):
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = d.decompress(data)
    out += d.flush()
    return out, len(data) - len(d.unused_data)

def payload_kernel_info(img_path):
    img = Path(img_path).read_bytes()
    ks = struct.unpack_from("<I", img, 8)[0]
    print(img_path, "file_ks", ks)
    blob, used = decompress_one(img[2048:])
    print("  decompressed", len(blob), "gzip_used", used)
    idx = blob.find(b"XNUP")
    print("  XNUP", idx)
    p = idx + 8
    while p + 24 <= len(blob):
        name = blob[p:p+16].split(b"\x00", 1)[0].decode("ascii", "replace")
        if not name:
            break
        size = struct.unpack_from("<I", blob, p+16)[0]
        data = blob[p+24:p+24+size]
        sha = hashlib.sha256(data).hexdigest()
        print(" ", name, size, sha[:16])
        if name == "kernel":
            i = data.find(b"Darwin Kernel Version")
            print("   ver:", data[i:i+96].split(b"\x00")[0].decode(errors="replace") if i >= 0 else "NO VER")
            print("   fullsha", sha)
        p = p + 24 + size
        p = (p + 15) & ~15

payload_kernel_info("/tmp/xnu-oldfd-capsz.img")
payload_kernel_info("/tmp/xnu-oldfd-logfix4.img")
k = Path("/home/shen/hakios/hakios-kernel").read_bytes()
i = k.find(b"Darwin Kernel Version")
print("hakios-kernel ver:", k[i:i+96].split(b"\x00")[0].decode(errors="replace"))
print("hakios-kernel sha", hashlib.sha256(k).hexdigest())
