#!/system/bin/sh
P=/dev/block/by-name/logdump
echo "=== grep for our text in the whole partition ==="
grep -abo -m 5 -E 'HakiOS|hakios|xnuloader|kernel.ver|XNU' $P
echo "=== first 300 non-zero bytes of the first MB ==="
dd if=$P bs=1M count=1 2>/dev/null | tr -d '\000' | head -c 300
echo
echo "=== done ==="