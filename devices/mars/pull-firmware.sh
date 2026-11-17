#!/bin/bash
# Pull the phone's own firmware out of its Android into the fw-*/ directories at the top of the repository. Never committed:
# it is the vendor's (tools/provenance.allow, LEGAL.md). The phone is on adb, in Android.
#
# The names below are the ones a Qualcomm phone of this generation has; the SEGMENTS of each image are read from the phone
# itself, so a phone that has more or fewer of them still comes out whole. A file that is not there is told, not fatal: what a
# first boot needs is fw-gpu/ only (docs/porting/index.md step 3).
set -e
cd "$(dirname "$0")/../.."
adb get-state >/dev/null

pull() { # DIR FILE...
	local dir=$1; shift
	mkdir -p "$dir"
	local f
	for f in "$@"; do
		[ -n "$f" ] || continue
		adb pull "$f" "$dir/" >/dev/null 2>&1 || echo "pull-firmware.sh: $f: not on the phone"
	done
	echo "pull-firmware.sh: $dir: $(ls -1 "$dir" | wc -l | tr -d ' ') files"
}

# what the phone has, as it lists it (nothing when the pattern matches nothing)
segments() { adb shell "ls $1 2>/dev/null" | tr -d '\r' | grep -v -e 'No such file' -e 'Permission denied' || true; }

# The GPU. The reference phone's 642L and this phone's Adreno 660 are both a6xx "a660": the firmware is the GPU family's, not
# the SKU's, so these names are the same on both. Whether the kernel's driver can wake a 660 is another question (README.md).
pull fw-gpu /vendor/firmware/a660_gmu.bin /vendor/firmware/a660_sqe.fw $(segments '/vendor/firmware/a660_zap.*')

# The wireless processor (Wi-Fi) and the modem: every segment the phone has. This phone's radio is a WCN6855, the reference
# phone's a WCN6750; the image is called wpss.* on both, the protocol the kernel speaks to it is not the same (README.md).
pull fw-wifi $(segments '/vendor/firmware_mnt/image/wpss.*')
pull fw-audio $(segments '/vendor/firmware_mnt/image/adsp.*')
pull fw-modem $(segments '/vendor/firmware_mnt/image/modem.*')
mkdir -p fw-modem/image && adb pull /vendor/firmware_mnt/image fw-modem/ >/dev/null 2>&1 &&
	echo "pull-firmware.sh: fw-modem/image: the modem's own files (TFTP)"

# The vibration motor. The reference phone's chip is an Awinic AW86927; check which one this phone has before trusting the
# line (README.md, "Before anything"): a wrong firmware is a motor that does nothing, not a brick.
pull fw-haptic /vendor/firmware/aw8697_haptic.bin

echo "pull-firmware.sh: done. If most of these said 'not on the phone', this ROM keeps them readable by root only:"
echo "    devices/mars/pull-firmware-root.sh"
echo "pull-firmware.sh: next: tools/hakios-config.py needs   (and CONFIG_FIRMWARE=\"device\" in configs/mars.config)"
