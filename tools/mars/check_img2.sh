#!/bin/bash
set -eu
python3 - <<'PY'
from pathlib import Path
import struct
for name in ("/tmp/xnu-oldfd-capsz.img", "/tmp/xnu-oldfd-logfix4.img"):
    img = Path(name).read_bytes()
    print(name, "len", len(img), "magic", img[:8],
          "ks", struct.unpack_from("<I", img, 8)[0],
          "rs", struct.unpack_from("<I", img, 12)[0],
          "hdr", struct.unpack_from("<I", img, 40)[0] if len(img) > 44 else "?")
    print("  @2048", img[2048:2056].hex())
    print("  XNUP", img.find(b"XNUP"))
PY
echo "==== kernel version strings ===="
strings /tmp/xnu-oldfd-capsz.img | grep -F "Darwin Kernel Version" | head -n 3 || true
strings /home/shen/hakios/hakios-kernel | grep -F "Darwin Kernel Version" | head -n 3
echo "==== image vs kernel sha ===="
sha256sum /home/shen/hakios/hakios-kernel
# extract kernel from payload via mkpayload format - check mkxnuimg
grep -n "gzip\|compress\|payload" /home/shen/hakios/mkxnuimg.py | head -n 25
