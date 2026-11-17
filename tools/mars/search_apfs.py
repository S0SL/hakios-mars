from pathlib import Path

p = Path(r'C:\Users\97770\Desktop\system.apfs')
needles = [
    b'SBStatusBarStateAggregator',
    b'BWFigCaptureDeviceVendor',
    b'CA::WindowServer',
    b'MetalContext',
    b'_OBJC_CLASS_$',
    b'dyld_shared_cache',
    b'Simulating crash',
]
with p.open('rb') as f:
    prev = b''
    off = 0
    found = {n: [] for n in needles}
    while True:
        chunk = f.read(64 * 1024 * 1024)
        if not chunk:
            break
        data = prev + chunk
        for n in needles:
            i = data.find(n)
            c = 0
            while i >= 0 and c < 3:
                found[n].append(off + i - len(prev))
                c += 1
                i = data.find(n, i + 1)
        prev = chunk[-64:]
        off += len(chunk)
for n, l in found.items():
    print(n[:40], '->', l)
