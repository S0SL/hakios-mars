#!/bin/bash
# The same pull by way of su, for ROMs that keep /vendor/firmware and /vendor/firmware_mnt readable by root only (seen on a
# Xiaomi ROM: firmware_mnt is a vfat mount with fmask=0337, and /vendor/firmware is not readable by the adb shell user either).
# Nothing on the phone is changed: the files are copied under su into a staging directory in /data/local/tmp, pulled from
# there, and the staging directory removed again.
#
#   devices/mars/pull-firmware-root.sh            the small images: GPU, Wi-Fi, audio, modem, haptics
#   IMAGE=1 devices/mars/pull-firmware-root.sh    ... and the modem's own files (fw-modem/image/, ~370 files)
set -e
cd "$(dirname "$0")/../.."
adb get-state >/dev/null
stage=/data/local/tmp/hakios-fw
cleanup() { adb shell "su -c 'rm -rf $stage'" >/dev/null 2>&1 || true; }
trap cleanup EXIT

copy_list="/vendor/firmware/a660_* /vendor/firmware/aw8697_haptic.bin /vendor/firmware_mnt/image/wpss.* /vendor/firmware_mnt/image/adsp.* /vendor/firmware_mnt/image/modem.*"
if [ "${IMAGE-}" = 1 ]; then
	copy_list="$copy_list /vendor/firmware_mnt/image"
fi

adb shell "su -c 'rm -rf $stage && mkdir -p $stage && cp -r $copy_list $stage/ && chmod -R 755 $stage'" >/dev/null 2>&1 ||
	echo "pull-firmware-root.sh: su was refused, or some of the files are not on this phone"

rm -rf fw-tmp && mkdir fw-tmp
adb pull "$stage" fw-tmp/ >/dev/null 2>&1 || { echo "pull-firmware-root.sh: nothing pulled from $stage"; exit 1; }
cleanup

filed=0
for f in fw-tmp/*/*; do
	[ -e "$f" ] || continue
	b=$(basename "$f")
	case "$b" in
		a660_*)           mkdir -p fw-gpu;    mv -f "$f" fw-gpu/ ;;
		wpss.*)           mkdir -p fw-wifi;   mv -f "$f" fw-wifi/ ;;
		adsp.*)           mkdir -p fw-audio;  mv -f "$f" fw-audio/ ;;
		modem.*)          mkdir -p fw-modem;  mv -f "$f" fw-modem/ ;;
		aw8697*)          mkdir -p fw-haptic; mv -f "$f" fw-haptic/ ;;
		image)            mkdir -p fw-modem;  mv -f "$f" fw-modem/image ;;
		*)                echo "pull-firmware-root.sh: $b: not filed (a file this phone has and the script does not know)"; continue ;;
	esac
	filed=$((filed + 1))
done
rm -rf fw-tmp
for d in fw-gpu fw-wifi fw-audio fw-modem fw-haptic; do
	[ -d "$d" ] && echo "pull-firmware-root.sh: $d: $(ls -1 "$d" | wc -l | tr -d ' ') files"
done
echo "pull-firmware-root.sh: done, $filed files filed"
