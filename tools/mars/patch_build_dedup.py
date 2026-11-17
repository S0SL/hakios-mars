from pathlib import Path

p = Path("/home/shen/hakios/userland/build.sh")
s = p.read_text()
old = """\tD2=sysroot/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld
\tmkdir -p $D2
\tfor f in $CACHE/dyld_shared_cache_arm64*; do
\t\tcase "$f" in *.symbols) continue ;; esac
\t\tln -f "$f" $D2/
\tdone
"""
if old in s:
    s = s.replace(old, "")
    p.write_text(s)
    print("removed duplicate Cryptexes copy")
else:
    print("D2 block not found or already removed")
# show relevant lines
for i, line in enumerate(s.splitlines(), 1):
    if "com.apple.dyld" in line or "Put real APFS" in line:
        print(f"{i}:{line}")
