#!/system/bin/sh
P=/dev/block/by-name/logdump
echo "=== where our text is ==="
grep -abo -m 5 -E 'XNULOADER|platform |payload|kernel' $P
echo "=== the first 60 lines of whatever is at the start ==="
dd if=$P bs=64k count=1 2>/dev/null | tr -d '\000' | head -c 4000
echo
echo "=== end ==="