#!/system/bin/sh
P=/dev/block/by-name/logdump
echo "=== grep for our words in the whole partition ==="
grep -abo -m 8 -E 'HakiOS|hakios|xnuloader|kernel.ver|XNU|BootShim' $P
echo "=== first 400 non-zero bytes ==="
dd if=$P bs=1M count=2 2>/dev/null | tr -d '\000' | head -c 400
echo
echo "=== done ==="