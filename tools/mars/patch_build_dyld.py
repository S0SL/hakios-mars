from pathlib import Path

p = Path("/home/shen/hakios/userland/build.sh")
s = p.read_text()
old = """\tD=sysroot/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld
\tmkdir -p $D
\tfor f in $CACHE/dyld_shared_cache_arm64*; do
\t\tcase "$f" in *.symbols) continue ;; esac     # symbolication data, never mapped
\t\t# -f: a cryptex fetched with the cache already in it would otherwise stop the build
\t\tln -f "$f" $D/
\tdone
"""
new = """\t# dyld searches /System/Library/Caches/com.apple.dyld first. Put real APFS
\t# files there so shared_region maps root-volume vnodes, not a bindfs view.
\tD=sysroot/System/Library/Caches/com.apple.dyld
\tmkdir -p $D
\tfor f in $CACHE/dyld_shared_cache_arm64*; do
\t\tcase "$f" in *.symbols) continue ;; esac
\t\tln -f "$f" $D/
\tdone
\tD2=sysroot/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld
\tmkdir -p $D2
\tfor f in $CACHE/dyld_shared_cache_arm64*; do
\t\tcase "$f" in *.symbols) continue ;; esac
\t\tln -f "$f" $D2/
\tdone
"""
if s.count(old) != 1:
    raise SystemExit("pattern count %d" % s.count(old))
if "System/Library/Caches/com.apple.dyld" in s and "Put real APFS" in s:
    print("already patched")
else:
    s = s.replace(old, new)
    p.write_text(s)
    print("build.sh patched: dyld cache at primary path")
