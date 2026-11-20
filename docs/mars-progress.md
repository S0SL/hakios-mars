# Mars (Xiaomi 11 Pro) Port — Progress & Transfer Notes

Last updated: 2026-11-20. This file is the hand-off: what is done and what is
blocked. The former build server is no longer available.

## 2026-11-19: build server unavailable; local WSL prepared

The user confirmed the former build server is gone. Its SSH endpoint refuses
connections, so do not rely on `/home/shen/hakios` or attempt further remote
builds. The last server working tree may have contained changes not present in
GitHub; those changes cannot currently be recovered or independently compared.

The work resumed from `S0SL/hakios-mars` at `bed91a54c6a0695fb73251dc9f06e0139ca56c72`
(`Add verified Mars PCIe shim stage 1`). The local WSL clone is now synced
through `8264a28` before the on-device recovery described below, in
`/home/hakios/hakios-github-snapshot`. The recovered Mars map and driver
dispatch lists are now also preserved with their runtime evidence.
The clone runs in Ubuntu 22.04 WSL, whose virtual disk is on E:; keep builds
in this Linux filesystem rather than under `/mnt/c` or the Windows checkout.
This GitHub snapshot matches the local GitHub checkout, but must not be
described as identical to the lost server tree.

The local host setup is ready for Linux builds: apt uses the Aliyun Ubuntu
mirror, pip uses the Aliyun PyPI mirror, and the WSL `hakios` user has
clang/LLD, GCC/make, Python/venv, Git, Meson/Ninja, 7-Zip 25.01, lz4, and the
Theos Linux toolchain with the iPhoneOS 16.5 SDK. `tools/doctor.sh` reports 9
checks passing and no failures. The Mars XNU kernel and both Darwin APFS
images have now been built from this GitHub snapshot; see the build records
below. The minimal kernel has reached the desktop with a fresh matching log.
Remaining gaps include testing the new APFS images on-device and recovering
modem firmware for modem-enabled runs.
The IPSW is available in the Windows workspace at
`/mnt/c/Users/97770/Documents/mi11/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw`.
The Mars XBL drivers and phone device tree are available in the local WSL
build tree. The recovered RELEASE UEFI has now been tested on the phone with
the prior working kernel and user-space payload. The freshly compiled minimal
kernel has now also been desktop-tested with that existing user space; the
newly built APFS images remain untested on-device.

## 2026-11-19: first local Mars kernel build

Built `hakios-kernel` in `/home/hakios/hakios-github-snapshot` with the Mars
minimal configuration (`CONFIG_HAKIOS_UFS=y`; Wi-Fi, GPU, touch and other
device drivers remain disabled). The output is a 14,962,080-byte arm64 Mach-O
kernel with SHA-256
`fa36648db4422172ab63f0c89d6432fd4713290dacfd86afee7b03159f402078`.
`tools/make-kernel.sh --judge xnu-build.log` passes: the kernel linked, and
the only rejected targets are XNU's expected kext symbol-set checks for this
non-Apple machine configuration. This was initially a compile result; the
2026-11-20 minimal-kernel test below now supplies phone boot evidence. The
local `xnu-deps/setup.sh` also includes `dsymutil` in the Theos tool
mapping, which the Linux build setup requires.

## 2026-11-20: local Darwin user-space build

Built from `/home/hakios/hakios-github-snapshot/userland` in Ubuntu 22.04 WSL
with `REST=1 GL=1 CHECK=1`. The resulting `root.apfs` is 4,194,304 bytes
(SHA-256 `34399978675950109a3e6fd03419721aee75b2e4b8ce7fc2ae672a72fa0a5080`);
`system.apfs` is 2,481,246,208 bytes (SHA-256
`22377908edb50cde07542fc8ab5917d17642e5acaee94bfd030c4d46d7211a2c`). Both
passed `apfsck -cw` and the independent XNU APFS reader: 483 root-volume
entries and 62,266 system-volume entries matched their source directories.
The system image contains the 14,838,744-byte Mesa 25.0.7 OSMesa library.
`REST=1` generated the full on-demand launchd job set.
Installed Ubuntu's `libssl-dev` package so the APFS checker could build its
independent `apfs-tool` reader.

Linux Git checkouts preserve Python files without executable bits, while the
userland script previously ran four generators directly. `userland/build.sh`
now invokes them through `python3`. `tools/mk-mesa.sh` also maps Ubuntu's
versioned LLVM tools and configures Meson, libc++, pkg-config, and the iOS
SDK's zlib for the local cross-build. The full userland build passed with
`CHECK=1`; the exact log is
`/home/hakios/hakios-github-snapshot/userland-build-20261120-r3.log`.
Neither APFS image has been boot-tested in this build session. The successful
UEFI and minimal-kernel desktop tests use the existing user-space payload and
Darwin volume already on the phone.

## 2026-11-20: local Mars UEFI and temporary boot image

Restored the pinned Mu-Silicium source with `uefi/apply.sh mars`, the local
XBL driver archive (`xbl-drivers.tgz`), and the phone's device tree. The
archive has 313 regular files and no unsafe paths. Vendor binaries and the
device tree remain local and are not part of the Git commits. The UFS PE was
patched at the two previously verified listener offsets; its SHA-256 is
`c162bfd021e143fa438f38e4da1a1719e308a7bec1e707cbf264a673540a1969`, and the
unmodified backup remains beside it.

Corrected the Mars firmware map to match this phone's XBL: UEFI FD
`0x9FC00000`/3 MiB and display reservation `0xEA600000`/36 MiB. The local
RELEASE UEFI build passed, including post-build validation of 49 EFI images;
the stage-1 `PcieShimDxe` is registered in both driver-order lists. The FD is
3,145,728 bytes (SHA-256
`bf515de340c6e965b0ffc93850fd05721f05c3c3cc097bb1d1135b5b20f254e0`).

Built the XNU loader at `-O0` (the `-O1` build fails with an out-of-range
AArch64 fixup), then packed the 176-byte boot shim, Mars UEFI FD, Mars DTB,
and USB loader payload into `xnu-mars-local-20261120.img`. A Windows-readable
copy is at `diagnostics/mars-local-boot-20261120.img`. The 1,826,816-byte
Android v1 image has SHA-256
`cc344c6f1052965b3c0f5f9f2cc24a0474d9cea99337c699739bebcec8e49166` and boot
ID `d33688a2d9c13625d541c7bf00f29d16afbd6813000000000000000000000000`.
Independent checks passed for the boot header/ID, gzip stream, DTB hash, 3 MiB
FD extent, and XNUP loader payload. This initial image subsequently failed
the on-device test below; use the recovered r2 image for the desktop baseline.

At the initial preparation stage, the phone was visible on ADB in Android,
unlocked, at 45% battery. The initial plan was to enter Fastboot manually
with Power + Volume Down and confirm
`fastboot getvar is-userspace` reports `no` before a temporary `fastboot boot`.
The later explicit user request authorized direct ADB reboot, as recorded
below. No Fastboot flash operation is authorized by this boot-test workflow.

## 2026-11-20: local UEFI boot regression recovered on-device

The user explicitly authorized direct operation. ADB reboot to the bootloader
succeeded; normal Fastboot reported `product: mars` and `is-userspace: no`.
At 05:29:18 (Asia/Shanghai), the initial local USB-loader image was accepted
by `fastboot boot`, but the user saw no console and the phone returned to
Android. The 2 MiB persistent logs before and after were byte-identical:
`6ba00f96f01c11e8060a133945adda86ae205be3c751f317e8417feb05114f72`.
They contain an older stage-2 run and cannot be attributed to this attempt.

Comparing the saved `diagnostics/active-server-snapshot-20261119-v2/`
configuration exposed missing boot prerequisites in the GitHub baseline:
an 8 MiB decompressed FV region at `0x9F400000`, CPU vectors, the conventional
kernel/loading window, the XNUP reservation at `0xF0000000`, the Mars TZ/DBI
layout, and the trimmed vendor-driver lists. Restored this configuration while
retaining stage-1 PCIe gating and the verified UFS listener stubs. The missing
`Dwc3ShimDxe` source could not be recovered from that snapshot; it remains
unregistered, so USB command-channel recovery is separate work.

The local RELEASE rebuild passed. The r2 test changes its UEFI FD and the
version marker in the known-good stage-1 image, preserving BootShim, DTB,
Android ramdisk, kernel, loader, payload ramdisks, command line and physical
base byte-for-byte. This is a test of the rebuilt UEFI with the older working
kernel and user space; it does not validate the new minimal kernel or new
APFS images. Independent boot-ID, component-preservation, patched-UFS and
stage-1 checks passed before the temporary boot.

At 05:43:58 (Asia/Shanghai), normal Fastboot accepted
`diagnostics/local-boot-20261120-052807/mars-recovered-r2.img` (11,833,344 bytes).
Image SHA-256:
`4579c7a9b5d346c921ea946c91a82586f26cd00f438c3654b67160cf8d51c013`.
UEFI FD SHA-256:
`b01272dcc7fa12339a66e296e0fe49d3b6bafa50387955215de2748fe036e72a`.
The unique version suffix is `local-uefi-r2`. The user confirmed that the
phone reached the iOS desktop. After the user returned to Android, a fresh
2 MiB persistent log was captured as
`diagnostics/local-boot-20261120-052807/persist-r2.bin` and decoded in the
adjacent `.txt`. SHA-256:
`d611c89ef15062564f8ab3efbde81d5af011be9dc74d36a680ea2dc86f522d48`.
It differs from the failed attempt and contains the unique `local-uefi-r2`
version, `display 1440 x 3200 at ea600000`, stage-1 completion, a running
SpringBoard, Mesa 25.0.7/FD660, and rendered frames. `dwc3shim: no variable`
confirms the missing USB shim, while PCIe still reports PHY NOT ready
(`PCS_STATUS1 48`) and `pcie: done (pcie_step=12)`. The phone is back in
Android with a completed boot, active slot b and 96% battery. No partition
was flashed. This validates the recovered
configuration as a whole; it does not isolate one change as the only cause.

Build log: `/home/hakios/hakios-github-snapshot/uefi-build-mars-20261120-r2.log`.
The local repacker, manifests and failed/successful firmware images are
preserved under `diagnostics/`; keep them local because they contain vendor
firmware and, for the full test image, user-supplied system content.

## 2026-11-20: local minimal kernel desktop verified; data is volatile

Normal bootloader Fastboot accepted the temporary boot at 06:03:48
(Asia/Shanghai), after confirming `product: mars` and `is-userspace: no`.
The user confirmed an iOS desktop, then returned to Android. No partition
was flashed or slot changed. Android reports a completed boot and slot b.

Image: `diagnostics/local-kernel-20261120-060226/mars-local-kernel-min1.img`,
11,780,096 bytes, SHA-256
`b37da64e9ccc28e80dc98cbe5d0bdd3f930d584f1c3b99a3e037b9ee844e7174`.
Its kernel is the 14,962,080-byte local build recorded above (SHA-256
`fa36648db4422172ab63f0c89d6432fd4713290dacfd86afee7b03159f402078`).
Only the XNUP `kernel` and `kernel.ver` entries changed from the recovered r2
baseline. Independent boot-ID and component checks confirmed preservation
of the UEFI prefix, DTB, Android ramdisk, loader, payload ramdisks, command
line and physical base. The new APFS build outputs were not used.

After Android returned, read 2 MiB from `darwin` at offset 8 GiB into
`diagnostics/local-kernel-20261120-060226/persist-min1.bin` and decoded the
adjacent `.txt`. Binary SHA-256:
`d314d109d4e988f11d8fbe326d967e1fba52b76b96f2ee92b58806f31d459233`.
The pre-test log hash was
`d611c89ef15062564f8ab3efbde81d5af011be9dc74d36a680ea2dc86f522d48`.
The new log contains `local-min1` in both the version banner and command
line, the local kernel build timestamp, stage-1 shim completion, display
`1440 x 3200 at ea600000`, successful UFS/APFS root mounting, and
`=== 46 checks, 0 failed ===`. It reports 6,144 MB RAM and seven kernel CPUs;
`cpus=8` in the command line must not be described as eight CPUs online.
SpringBoard and window-server activity corroborate the user's desktop
report. No kernel-panic signature was found in the captured log.

This is a minimal-kernel baseline: UFS is built in, while the hardware GPU,
Mars touch and Wi-Fi drivers are not. The log explicitly says
`no GPU to draw with: CoreAnimation keeps its software renderer`, followed
by window-server software-renderer/context warnings. The preserved `gpu=1`
and `touchscreen=1` flags cannot enable drivers absent from this kernel.
This run does not reproduce the older kernel's GPU/touch milestones and
does not provide a new PCIe PHY result. `dwc3shim: no variable` remains.

The persistence question is resolved for this image: init logs
`mount the Darwin volume read only` and
`mount a memory filesystem on /private/var`. The save daemon logs
`var_store: not asked to keep the data volume (var_store=1): nothing to watch`.
The command line already has `ufs_write=1`, but lacks `var_store=1`; enabling
block writes alone does not save application data. Settings, home-screen
changes and application data under this memory filesystem are discarded
on reboot. Diagnostic logs are saved separately to storage.

Source contains optional `var_store=1` restore/save support, but it has not
been enabled or validated on Mars in this run. Before calling persistence
working, check its storage range against the existing Darwin layout, then
verify a saved marker and actual application data across two boots. Its
default watcher saves on a kernel shutdown notification; a forced power
reset must not be assumed to deliver that notification. The newly built
userland images, persistent data, stable loader USB and Mars hardware
drivers remain separate follow-up work. Keep images and raw logs local.

## 2026-11-20: correct PCIe clock votes; stage-3 PHY trial

The existing shim and saved XNU PCIe probe had incorrect SM8350 clock
definitions. Cross-checking Xiaomi `venus-r-oss`'s `gcc-lahaina.c` and
upstream Linux `gcc-sm8350.c` confirms that GCC `0x52008` bits 0 through 5
are slave AXI, master AXI, configuration AHB, AUX, PIPE and slave Q2A AXI.
The old `0x35` vote omitted master AXI (bit 1) and AUX (bit 3), and replaced
the whole shared vote word. It also labeled Q2A status `0x6b010` as slave
and PIPE status `0x6b030` as master. The actual slave/master status offsets
are `0x6b014`/`0x6b01c`. Earlier statements that all clocks worked were
therefore too strong; AUX was explicitly still halted in the old logs.

The corrected UEFI shim ORs `0x3f` into the existing vote, preserves other
CLKREF bits, and reports the vote before/after plus all six correctly
labeled branch registers under the `clocks-v7` marker. The source default
remains stage 1; a build-local stage-3 override returns after the PHY check,
before PERST release, link training or ELBI/ECAM reads. No saved XNU probe
was enabled in the minimal kernel, so it cannot overwrite these votes.

Read this phone's current PCIe device-tree properties through Android:
all 75 PHY writes (including delay values) match the shim; status offset is
`0x214`, status bit is 6, power-down offset is `0x240`. Android enumerates
the endpoint as `17cb:1103`. These reads validate the hardware description,
not an iOS Wi-Fi connection. The available `drivers/wifi/` is still the
reference WCN6750 DSP driver, rather than a working Mars PCIe transport.
Do not enable it unchanged merely because the PCIe PHY becomes ready.

`tools/mars/check-pcieshim.py` compiles the actual C source with recorded
MMIO. It reproduced a failure with the old clock code and passes with the
fix: preservation of other clients' bits, complete clock votes, branch
labels, all 16 stage/timeout combinations, bounded waits and two invalid
stage compile checks. The isolated local RELEASE UEFI build passed with
the verified UFS listener stubs. Default stage-1 source and DSC output
settings were restored after the trial build.

Trial artifacts: `diagnostics/wifi-clocks-v7-s3-20261120/`.
Image `mars-wifi-clocks-v7-s3.img`: 11,780,096 bytes, SHA-256
`5a3d42cb73b2529cfff656ad9038338bf1285498de03c2870b3a6c9e990aa35a`.
UEFI FD SHA-256:
`e89b89e3a1b40fc0c8f2df03d08a78b00a8f4cbe50632ae814fd7c31ad9da9b4`.
Version suffix: `local-min1-wifi-clocks-v7-s3`. This image changes only
the FD and version from the verified local-min1 baseline. An independent
reader verified the Android v1 boot ID and preservation of BootShim, DTB,
Android ramdisk and every other XNUP entry, including kernel and loader.
Normal Fastboot accepted the temporary boot at 06:26:36 (Asia/Shanghai).
The user confirmed the desktop and returned to Android. The pre-test 2 MiB log has SHA-256
`d314d109d4e988f11d8fbe326d967e1fba52b76b96f2ee92b58806f31d459233`.
The fresh `persist-v7.bin` has SHA-256
`6317c0c7456392bd43f4da5057211afe8706e19f46b77c516cef5e4b03224066`.
It contains the unique version, `clocks-v7`, stage 3 and:

```text
GCC halt pre  aux=80000220 cfg=0 mstr=80000220 slv=220 q2a=80000000 pipe=80000000
clocks-v7 vote pre=2000 clkref=80000000 mask=3F
clocks-v7 vote post=203F clkref=1
GCC halt post aux=220 cfg=0 mstr=220 slv=220 q2a=0 pipe=0
PCS_STATUS1=86 ready=1 after=1 ms
stage3 PHY ready; returning
```

Both AUX and master AXI lost their halt bit, and the vote retained the
pre-existing `0x2000`. PHY status bit 6 cleared: the previous PHY-not-ready
blocker is resolved for this UEFI stage-3 path. Init again reports 46 checks
with no failures, SpringBoard/window-server activity is present, and no
kernel-panic signature was found in this capture. The phone is back in
Android on slot b. No partition was flashed or slot changed.

Wi-Fi is not connected yet. Stage 3 deliberately does not release PERST,
train the link, configure outbound address translation, enumerate the
endpoint or run a Wi-Fi transport. The next checkpoint is a bounded
stage-4 link test with the correct status source and a guarded endpoint
configuration window. The older PARF-LTSSM-control polling must be reviewed
before treating it as a link-state report. The default source stage stays 1.

### Stage 4: guarded link and endpoint trial (desktop verified)

The live device tree confirms the six PCIe resources, including unrolled
iATU at `0x60001000` and the configuration aperture at `0x60100000`.
The stage-4 path now restores PARF's internal DBI base to zero, matching
Xiaomi `pci-msm.c`, rather than using the CPU physical address there.
It holds PERST low for 100 ms, releases it, enables training and polls
both ELBI's XMLH link-up bit and the root port's DLL-active bit for up to
100 ms. Only local controller registers are read during training.

Once both indicators report up and the root ID is valid, it sets bus
numbers and programs unrolled outbound iATU region 0 as CFG0: a 4 KiB
host window at `0x60100000` targets `01:00.0` (`0x01000000`). It checks
the region-enable bit with a bounded wait and rechecks the link before
reading the endpoint's ID, command/status and class. No BARs are assigned
and no DMA engine or radio firmware is started. Failure skips endpoint
access; the stage-1 default is retained.

The host harness passes 22 cases, adding root-config rejection, iATU
enable timeout, link loss, disagreement between link indicators and an
absent endpoint to the earlier stage/timeout checks. These are host
checks. The isolated local RELEASE build passed and restored its default
stage-1 source and DSC afterward. Image:
`diagnostics/wifi-link-v8-s4-20261120/mars-wifi-link-v8-s4.img`, 11,782,144 bytes.
SHA-256: `9f79936c8d5cfa424c01ef799573ac75370e00e88f53d788089b0748f2c5001f`.
FD SHA-256: `dc314c2928c00a6132c4642a38a356dc88f4a9a2e96bf3d9dfbf2f1d3715c18f`.
Unique version suffix: `local-min1-wifi-link-v8-s4`. Independent image
checks confirm only the FD/version changed from the verified stage-3
baseline; BootShim, DTB, Android ramdisk and every other XNUP entry are
preserved. Normal Fastboot accepted the temporary boot at 06:41:14
(Asia/Shanghai); the user confirmed the desktop and returned to Android.
The fresh log `persist-v8.bin` has SHA-256
`6ebbcdf34a54f02be5c78e943cae2eef75c8f78d708a4eef672e0c765344aa12`.
It contains the unique stage-4 version and `clocks-v7` marker. PHY still
reports `PCS_STATUS1=0x86`, ready after 1 ms. With DBI routed internally,
the bounded 100 ms link poll ends at `ELBI=0x1001`, LTSSM `0x1`
(`Detect.Active`), and `DLL=0x10110008` (DLL-active clear). The endpoint
did not respond, so the stage correctly skipped iATU and ECAM accesses.
SpringBoard started, init reports 46 checks with 0 failed, and no panic
signature appears in the capture. Android completed on slot b. No
partition was flashed or slot changed. The tested image does not connect
Wi-Fi; link training is the current blocker.

### Android hardware reference and stage-5 trial

After the stage-4 trial, Android again enumerated `17cb:1103`, bound its
CNSS PCI driver and exposed `wlan0`; the negotiated link was 5 GT/s x1.
The same live FDT maps the Wi-Fi `wlan-en-gpio` to GPIO64 and describes five
CNSS supply rails plus the antenna-switch rail. Android's regulator
sysfs showed all six enabled during this reference capture. The saved FDT
and the selected-property decoder are local at `mars-device-tree.dtb` and
`diagnostics/wifi-research-20261120/dump-relevant-fdt.py`. This confirms
that the endpoint works under Android's initialization; it does not prove
the rails remained enabled during the temporary Darwin boot.

Comparing the temporary path with Xiaomi's `venus-r-oss` `pci-msm.c`
revealed missing, device-tree-backed setup before link training. Linux
switches the PIPE mux to the externally supplied `PCIE_0_PIPE_CLK`, toggles
the named core and PHY resets (GCC `0x6b000` and `0x6c01c`, 1 ms each),
loads the PHY sequence, then enables the PIPE clock before polling PHY
readiness. The trial only enabled the vote early; it did not select the
parent or pulse those resets. On this board the live DT resolves the PIPE
mux to GCC clock ID `0x3a`, external parent ID `1`, and the named resets to
GCC reset IDs 4 and 7.

The build-local stage-5 trial now applies that bounded sequence: assert
PERST, select the external PIPE parent while preserving other mux bits,
vote the four controller clocks without PIPE, pulse core/PHY reset with
readback, program the PARF and PHY sequence, then add the PIPE vote before
the ready check. It retains the default stage-1 source and uses no direct
PMIC writes. Host MMIO tests pass for all five stages (32 scenarios),
including both reset pulses, mux selection, delayed PIPE enable, link
timeouts, lost-link checks and suppression of endpoint access.

The stage-5 local RELEASE build succeeded and the user confirmed a desktop.
Image: `diagnostics/wifi-pipe-v9-s5-20261120/mars-wifi-pipe-v9-s5.img`,
11,782,144 bytes, SHA-256
`5a7d6838a4320131dd9f094b1aa26f6150645cb9099bfc4ec8cef7ae769bf247`.
FD SHA-256:
`52524ac49f4fbaec3f9eb6c7674024502292d3aca542f05a5b907fdf514e9502`.
The fresh `persist-v9.bin` log SHA-256 is
`da5c93c7389bcc312583387f3f901aac95212790fb775d50217a4f1e29cc7033`.
It confirms PIPE mux `2 -> 0`, core/PHY reset pulses `0 -> 1 -> 0`, and
the PIPE vote enabled after PHY programming. PHY is ready at
`PCS_STATUS1=0x86`; the 100 ms link poll still ends at `ELBI=0x1`, LTSSM
`0`, and DLL-active clear, so endpoint access is skipped. SpringBoard
starts, 46 init checks pass, and no panic signature appears. Android
returned on slot b; no partition was flashed. Reset and PIPE-clock
selection alone did not resolve link training.

The just-before-test Android capture showed all five CNSS WLAN rails and
the antenna-switch rail enabled: PMR735A S2, PM8350 S11/S10, PM8350C S1,
PM8350 S12 and PMR735A L7. This is an Android reference, not a measurement
of their UEFI state. The shim drives WLAN_EN via GPIO64 but does not submit
CNSS supply votes to RPMh. Inspect the installed RPMh/NPA/VCS UEFI interfaces
and initialization ordering before another RF-power test; do not use raw
PMIC writes.

### Stage 5 control with the TCXO PIPE parent

Xiaomi's GCC table maps mux value `0` to the PCIe PHY PIPE output and `2` to
`bi_tcxo`. The stage-5 control retained the initial value `2` and ran
the same core and PHY resets, delayed PIPE vote and link probe as v9.
The compile-time `PCIE_PIPE_PARENT` selector makes this comparison
reproducible. The local RELEASE firmware comparison reports 94 FFS files
with only PcieShimDxe changed. The independent image check verified the
boot ID and preserved the loader, kernel, DTB, ramdisks and boot arguments.
The shim check now covers both stage-5 parents (42 cases total).

At 21:24 (Asia/Shanghai), normal Fastboot accepted the temporary boot of
`diagnostics/wifi-pipe-xo-v10-s5-20261120/mars-wifi-pipe-xo-v10-s5.img`.
Image SHA-256:
`6071a520f5dc180bfc38bf1025f88a1b6c5c536be553a6e2edec659f4c06c038`.
The user confirmed the desktop. The new `persist-after.bin` SHA-256 is
`31ea6dabf1791139b1a875dfd82d0b4cfcb5294c44bd6f8c8fdcfe58921b756f`.
It contains the `wifi-pipe-xo-v10-s5` version, mux readback `2 -> 2`,
both reset pulses, PIPE vote `0x203f` and PHY status `0x86`. LTSSM
reached `Detect.Active` again (`ELBI=0x1001` versus v9's `0x1`).
DLL-active stayed clear and the shim skipped endpoint config access.
All 46 init checks passed. Android completed on slot b after the test.
The test used temporary boot and no flash command.

The live DT also names separate PCIe root-controller supplies and a PHY
rate-change clock. Android's read-only regulator capture showed PM8350 L5
enabled at 0.88 V, PM8350 L6 enabled at 1.2 V, and the PM8350C S6 CX vote
at level 256. These are Android readings. UEFI must still verify those
supplies and the GCC PHY rate-change branch before attributing the missing
PIPE output to the endpoint's WLAN supply rails. Check the branch and its
source readback before adding a clock or regulator vote.

## Current status (one screen)

| Track | State |
|---|---|
| Local build environment | **Prepared** — Ubuntu 22.04 WSL on E:, Aliyun mirrors, Theos + iPhoneOS 16.5 SDK; `doctor.sh` has 0 failures |
| Mars kernel | **Local minimal build desktop verified** — fresh `local-min1` log, UFS/APFS root, 46 init checks with 0 failures, 6 GB RAM and 7 CPUs; software rendering |
| Darwin images | **Built and checked locally** — `REST=1 GL=1 CHECK=1`; APFS checker and independent reader pass; not yet boot-tested from these outputs |
| Local Mars UEFI | **Desktop verified on-device** — r2 restored the Mars map/dispatch prerequisites; old working payload retained; unique marker, SpringBoard and GPU rendering confirmed in a fresh log |
| Source availability | **Recovery preserved** — WSL builds use the GitHub baseline plus recovered Mars map/driver lists from the saved server snapshot; other former-server work may still be unavailable |
| Darwin user space | **Existing volume desktop verified** — older kernel also demonstrated touch (FTM5 fts_dual) and Mesa/freedreno rendering; the new minimal kernel uses software rendering without those hardware drivers |
| Data persistence | **Disabled in the tested image** — system root is read-only; `/private/var` is writable RAM; `var_store=1` is absent and the saver exits; changes are lost on reboot |
| Run logs | **Working** — full log at the 8 GiB offset in `darwin`; check image markers for freshness |
| GPU polish | **-31% stutter** (64.5→40 ms/frame): shader warm-up v2, sampled hash, TexSubImage reuse, EGLImage fail cache |
| USB fastboot channel | **Partial** — enumeration flaky behind Qcom `UsbfnDwc`; 30 s idle auto-run fallback in loader |
| UEFI PCIe shim | **Stage-5 PIPE parent comparison verified** — PHY ready with either parent, TCXO reaches Detect.Active, DLL remains inactive |
| Wi-Fi / PCIe (QCA6490) | **Android hardware works; temporary Darwin link down** — Android sees `17cb:1103` at 5 GT/s x1 with CNSS/`wlan0`; stages 4–5 stop before DLL-active; UEFI RPMh supply voting remains unimplemented |

## 2026-11-19 follow-up: bounded PCIe shim stages (v6)

The successful v5 run is preserved as the rebuilt-firmware baseline. The
active UEFI shim now has a compile-time `PCIE_SHIM_STAGE` (default 1):

1. GDSC power and GCC clocks only; return before PARF, GPIO or PHY access.
2. Add PARF configuration and GPIO95/GPIO64, then return before PHY writes.
3. Add PHY programming and bounded readiness polling, then return.
4. Attempt PERST/LTSSM and read ELBI/ECAM only after a reported L0 link.

Failure guards return on GDSC timeout, skip PERST/LTSSM and ELBI/ECAM
after PHY timeout, and skip ELBI/ECAM after link timeout. These guards
cover the shim; the existing XNU PCIe probe is unchanged. The staged
source remains in the active tree, backed up and patched under
`/home/shen/hakios/tmp/pcieshim-staged-v6-20261119/`.
`remote-src/build-pcieshim-nommio.py --stage 1..4` builds isolated trials
against the verified v5 payload, requires the restored UFS input, and
restores its temporary macro/DSC edits. Older isolation options remain
available and cannot be combined with `--stage`.

A host-side C harness compiled the actual shim with mocked MMIO and
UEFI services: all 16 combinations of four stages with power timeout,
PHY timeout, link timeout and ready status passed. It checks stage
boundaries, bounded waits and suppression of downstream accesses on
failure. Invalid stages 0 and 5 were also rejected by the compiler.
Evidence: `diagnostics/pcieshim-staged-v6-20261119/check-stages.py` and
`results.json`. These checks validate control flow, not hardware readiness.

The stage-1 DEBUG firmware build passed. Image:
`diagnostics/pcieshim-staged-v6-20261119/xnu-pcie-shim-staged-v6-s1.img`.
SHA-256:
`170087bd700c0908f96c87606affc66ef261aa2a16d8368ee0cfa29c615e4497`.
Size: 11,894,784 bytes. Remote artifacts:
`/home/shen/hakios/tmp/pcieshim-nommio-ac7g3nl2/`.
Expected log markers: `pcieshim: staged-v6 stage=1` and, if power becomes
ready, `pcieshim: stage1 power/clocks complete; returning`.

Independent local verification passed for the complete image hash,
Android v1 boot ID, unchanged BootShim, complete XNUP payload, DTB and
ramdisk, and stage-1 EFI markers. The EFI does not contain the later
PARF/GPIO, PHY-status, PERST or ELBI diagnostic strings. The build also
verified inclusion of the restored UFS PE. The first independent check
incorrectly omitted the empty recovery-DTBO component from the v1 boot
ID calculation; the checker was corrected to match the existing packer
and the verified v5 header. No image change was needed.

Android ADB identified `mars` and a completed Android boot before the
test. Normal bootloader Fastboot (`is-userspace: no`) accepted temporary
`fastboot boot` at 06:50:30 on 2026-11-19 (Asia/Shanghai), with no partition
flash. At 06:50:55 neither ADB nor Fastboot was enumerated. The user
subsequently confirmed a desktop boot and returned to Android. At
06:53:47 (Asia/Shanghai), the successful run's 2 MiB persistent log was
extracted before any further test:
`diagnostics/pcieshim-staged-v6-20261119/stage1-desktop-runtime-20261119-065347.bin`
and its decoded `.txt`. Binary SHA-256:
`b3265d50fcea430333510063688ee06f08d87ad3816c2d04af515782300eeefd`.
It contains both the stage-1 freshness and completion markers, the
corrected kernel tag, and `pcie: done (pcie_step=12)`. GDSCR changed from
`0x0022f001` (collapse set, on clear) to ready value `0xf822f000`;
the reported slave/master clock registers changed from `0x80000000`
to zero. AUX remained `0x80000220` and CFG remained zero; this is not
evidence that every PCIe clock is running. The XNU probe still reports
`PCS_STATUS1=0x48`, LTSSM 0, and vendor/device `ffff:ffff`.

The log was backed up and hash-verified under
`/home/shen/hakios/tmp/pcieshim-staged-v6-20261119/stage1-success-20261119-065347/`.
Stage 1 is the verified power/clock-stage desktop baseline. This confirms
its executed path coexists with desktop boot; PHY/link/Wi-Fi remain
unavailable. No stage-1 log may be attributed to a later stage.

### Stage 2: PARF and GPIO preparation

The unchanged staged driver was built with `--stage 2`. It adds PARF
configuration and GPIO95/GPIO64, returning before the PHY sequence,
GPIO94 PERST, LTSSM and ELBI/ECAM. Temporary macro/DSC changes were
restored to the saved default-stage-1 source after the DEBUG build.
Image: `diagnostics/pcieshim-staged-v6-20261119/xnu-pcie-shim-staged-v6-s2.img`.
SHA-256:
`e4d9f1cd88780e8f84f0697d557bf6176dca5bb2e2e88c8c54c9997dbff4858f`.
Size: 11,896,832 bytes. Remote artifacts:
`/home/shen/hakios/tmp/pcieshim-nommio-h2oav8cn/`.
Expected fresh marker: `pcieshim: staged-v6 stage=2`; completion marker:
`pcieshim: stage2 PARF/GPIO complete; returning`.
The DEBUG build and independent image checks passed: complete image hash,
Android v1 boot ID, preserved BootShim/XNUP payload/DTB/ramdisk, and the
compiled stage-2 EFI markers. PHY-status, PERST and ELBI diagnostic
strings are absent from this EFI. The stage-1 EFI remains preserved;
stage-2 EFI is saved separately as `PcieShimDxe.stage2.efi`.

After confirming Android `mars` and `sys.boot_completed=1`, normal
bootloader Fastboot (`is-userspace: no`) accepted temporary `fastboot boot`
at 06:56:58 on 2026-11-19 (Asia/Shanghai). No partition was flashed.
At 06:57:24 neither ADB nor Fastboot was enumerated; this is not proof
of a desktop boot. Screen feedback and a fresh persistent log with the
stage-2 marker remain pending. Transcript:
`diagnostics/pcieshim-staged-v6-20261119/temporary-boot-stage2-20261119-065644.txt`.
Do not attribute the saved stage-1 runtime log to this test. No additional
automatic reboot is queued.

## 2026-11-19: sync the verified PCIe shim baseline

Compared the GitHub Mars UEFI overlay with the active build-server snapshot.
The GitHub memory map has more complete PCIe AHB/AXI windows than the active
server's trimmed map, so it remains the base; only the missing GCC window
(`0x00100000`–`0x001fffff`) was added. Existing GitHub mappings already cover
PARF/PHY, TLMM, DBI and ECAM and were preserved.

The exact `PcieShimDxe.c` source used for the verified stage-1 image
(SHA-256 `ca52698efa02adcd7c4f830e999b3d8d72c311c2e6a08866a75bb936fc04d03b`)
and its INF were added to `devices/mars/uefi/files/`. The Mars DSC, APRIORI
and DXE lists register it for build, early dispatch and firmware inclusion.
The default stage remains 1. The stage-1 desktop log
(`diagnostics/pcieshim-staged-v6-20261119/stage1-desktop-runtime-20261119-065347.txt`,
binary SHA-256 `b3265d50fcea430333510063688ee06f08d87ad3816c2d04af515782300eeefd`)
confirms power/clock initialization returned and the desktop booted. This
does not establish PARF/GPIO stage-2 success, PHY lock, PCIe link, or Wi-Fi.
The 16 host MMIO-control cases are recorded as passing in
`diagnostics/pcieshim-staged-v6-20261119/results.json`; they are not hardware
readiness evidence. Stage-2 runtime confirmation remains pending.

Only these stage-1-backed changes were synchronized; no vendor UEFI binary,
untested server working-tree changes, or unverified later stages were merged.
They were committed and pushed to `S0SL/hakios-mars` as `bed91a5` after the
local GitHub checkout fast-forwarded through `9ee435e`. The older non-Git
snapshot at `hakios/hakios-xnu-kernel-main` received only the five Mars UEFI
file updates and the two shim source files; its unrelated upstream README and
other local-only files were left untouched.

## 2026-11-19 follow-up: rebuilt UEFI lost the UFS listener stubs

The quick resets reproduced with the no-MMIO driver (v2), and again with
the four added mappings removed (v3). Neither attempt wrote a new loader
log; the old successful control log remained byte-identical. These tests
do not establish a PCIe-register fault or a mapping fault. Android remains
recoverable and no partition was flashed.

### Verified rebuild regression and restoration

The known-good firmware contains a patched `UFSDxe` PE. The current UEFI
build input `Mu-Silicium/Binaries/mars/QcomPkg/Drivers/UFSDxe/UFSDxe.efi`
instead matched its unpatched `.rpmb-original` byte-for-byte:
`021a5ed5c168d58d5b023b11907e290c9523c700f13e4ece3bb21d05708611a9`.
At offsets `0x10900` (RPMB listener) and `0xFD2C` (GPT listener), it again
contained `ff8300d1fd7b01a9` instead of the success-return stubs.
This is the prerequisite documented in `PORT-LOG.md` on 2026-11-10:
the TEE-backed listeners previously asserted during UEFI startup.

Restored the two eight-byte stubs using the existing
`patch_ufsdxe_rpmb_stub.py`, after validating both original spans and
backing up the current PE. The restored binary is byte-identical to the
PE inside the known-good firmware's UFSDxe FFS, not merely a similar patch.
Restored SHA-256:
`c162bfd021e143fa438f38e4da1a1719e308a7bec1e707cbf264a673540a1969`.
Backup/evidence: `/home/shen/hakios/tmp/pcieshim-ufs-restore-asyypdtd/`.
The existing `.rpmb-original`, good firmware, and baseline images remain
untouched. The repaired v5 image reached the desktop, confirmed by the
user and a fresh persistent log. Restoring these prerequisites recovers
the no-MMIO rebuilt-firmware configuration; the full PCIe shim sequence
has not yet been retested with the repaired UFS input.

### Current repaired-firmware isolation image

Local: `diagnostics/pcieshim-ufs-restored-20261119-v5/xnu-pcie-shim-nommio-ufs-v5.img`.
SHA-256: `cc95946c3c30becd47e87e514c46700792ba1111d7c6280d1ee78e4be1ab9146`.
Remote: `/home/shen/hakios/tmp/pcieshim-nommio-czpukao4/`.

The DEBUG build passed. This image retains all four new PCIe mappings and
the registered shim, but the shim only logs and returns before PCIe MMIO.
Expected variable text: `pcieshim: isolation-v5 no MMIO; returning`.
Its loader marker remains `diag-20261119-v1 shim`, with the corrected
`cmddb-protofix-v1` kernel. Only the UEFI FD changes from the corrected
shim image; BootShim, complete payload, DTB and ramdisk are preserved.
The built UFS FFS was checked to contain the restored known-good PE.
All temporary C/DSC edits were restored after building; the UFS binary
repair intentionally remains in the build inputs.

`remote-src/build-pcieshim-nommio.py` now checks the known-good UFS hash
before changing source or building and verifies its inclusion afterward.
This prevents the diagnostic builder from silently packaging the reverted
UFS input again. Earlier rebuilt shim firmware and v2-v4 isolation builds
retain the bad UFS input and are for failure analysis only. The known-good
old-firmware control image remains valid. The v4 no-driver control was
built but deliberately not booted after this regression was discovered.

The repaired v5 image passed independent local boot-ID, SHA-256, firmware,
payload-preservation and UFS-stub checks. Normal Fastboot (`is-userspace:
no`) accepted temporary boot at 06:36:17 (Asia/Shanghai). The 25-second
endpoint check found neither ADB nor Fastboot. The user subsequently
confirmed that v5 reached the desktop, then returned to Android. ADB
reconnected and the successful run's 2 MiB persistent log was extracted
at 06:40:25 (Asia/Shanghai), before any further boot test:
`diagnostics/pcieshim-ufs-restored-20261119-v5/desktop-runtime-20261119-064025.bin`
and its decoded `.txt`. Binary SHA-256:
`60364d7986e9e4a991e9533c85ece0c60159356010596b581c8c4f772fe893c6`.
This differs from the stale control log and contains the `shim` loader
marker, `pcieshim: isolation-v5 no MMIO; returning`, the corrected
`cmddb-protofix-v1` kernel tag, and `pcie: done (pcie_step=12)`.
V5 is the verified rebuilt-firmware baseline: mapping, module dispatch,
and the no-MMIO shim path coexist with a successful desktop boot.

The XNU PCIe probe still reports PHY NOT ready (`PCS_STATUS1=0x48`),
LTSSM 0 (not L0), and vendor/device `ffff:ffff`; QCA6490 enumeration and
Wi-Fi are not working yet. The UEFI shim returns before its PCIe MMIO
sequence, so this success does not validate that sequence. Next restore
initialization in bounded stages and skip downstream ELBI/ECAM accesses
when PHY or link readiness fails. Android is currently available; no
further automatic reboot is queued.

## 2026-11-19 follow-up: cmd_db pointer truncation

The user authorized direct ADB reboot to the bootloader. It succeeded;
`fastboot getvar is-userspace` reported `no`, with no EDL enumeration.

The initial tagged control image reached XNU and panicked at PCIe step 12.
Fresh log: `diagnostics/pcieshim-20261119-v1-tagged/control-runtime-20261119-055821.txt`.
It contains the `control` marker and the expected missing `PcieShim`
variable for the old firmware, confirming the early log reader works.

### Confirmed software fault and correction

- Panic: PC `0xfffffff0074a0744`, ESR `0x96000005`, FAR `0x56004004`.
- `drivers/pci/hakios.pcie.c` called `ml_io_map_wcomb` without its declaration.
  The old machine code executed `sxtw x21, w19` on the return value, turning
  `0xfffffff256004000` into `0x56004000` before reading byte offset 4.
  This explains the observed translation fault. The prior attribution to
  cmd_db timing was unproven and is superseded by this finding.
- Added the matching `extern vm_offset_t ml_io_map_wcomb(vm_offset_t,
  vm_size_t)` declaration to the driver and its actual kernel-tree copy.
  This is one added line in each copy; existing source is retained.
- The rebuilt object stores the full `x0` return value and reads through a
  64-bit register; the truncating `sxtw` is absent from this call sequence.
- The kernel was relinked. The existing build judge accepted the known
  kext symbol-set failures; the PCIe source had no compile diagnostics.
  Kernel SHA-256: `1eb8c460c1516935fb303395a5b8e7e461d01bb5130fcb444395e5e4aed83669`.
  The original top-level `hakios-kernel` was restored after building; the
  corrected kernel is retained in the isolated trial directory below.

### Current test artifacts

Local: `C:/Users/97770/Documents/mi11/diagnostics/pcie-cmddb-fix-20261119/`

Remote: `/home/shen/hakios/tmp/pcie-cmddb-fix-20261119-kPzuur/`

- `xnu-pcie-control-cmddb-fix.img`, SHA-256
  `90a4e240f09435d7b292513b9b471f9fca94c59436efe76cc214f8025c0b6c53`.
- `xnu-pcie-shim-cmddb-fix.img`, SHA-256
  `ac0f896cb8964d1ecc6a7344c81132811e3491be035f60aff2f326530947e300`.

Both use kernel version tag
`2.3.4-hakios-darwin22.5-sm8350-g63fc2b46-dirty-cmddb-protofix-v1`.
Their loader markers remain `diag-20261119-v1 control` / `shim`.
Relative to the original tagged images, only `kernel` and `kernel.ver`
change. `pcie_step=12` is intentionally retained to test the corrected
probe. Firmware, loader, DTB, command line, and both ramdisks are preserved.
Boot IDs and local/remote component hashes were verified independently.
The packer now accepts paired `--kernel` / `--kernel-version` arguments
and records all changed entries. Patch: `remote-src/pcie-cmd-db-prototype.patch`.

The fixed control image was accepted by `fastboot boot` at 06:06:28
(Asia/Shanghai). The user subsequently confirmed that this run entered the
desktop. The fixed control kernel therefore passes the previously fatal
step-12 path in this configuration and is the new verified boot baseline.
The user returned to Android and ADB reconnected. At 06:11:10
(Asia/Shanghai), the successful run's 2 MiB persistent log was extracted
before any further test:
`diagnostics/pcie-cmddb-fix-20261119/control-desktop-runtime-20261119-061110.bin`
and its decoded `.txt`. Binary SHA-256:
`36f411a57ac516b7766b53ba4512cddf71efd176c2207080e732607330be993a`.
The log contains both the `control` loader marker and `cmddb-protofix-v1`
kernel tag, readable cmd_db entries including `vrm.wlan @46008`, and
`pcie: done (pcie_step=12)`, followed by desktop rendering and touch events.
It confirms recovery from the pointer-truncation crash. PHY remains NOT
ready (`PCS_STATUS1=0x48`), LTSSM is 0 (not L0), and ECAM is all ones;
QCA6490 enumeration and Wi-Fi remain unproven. The corrected-kernel shim
image was accepted by temporary `fastboot boot` at 06:12:18
(Asia/Shanghai). The user reported a reboot in under one second; Android
ADB reconnected. No partition has been flashed.

The post-failure 2 MiB read is saved as
`diagnostics/pcie-cmddb-fix-20261119/shim-reboot-runtime-20261119-061332.bin`
and decoded `.txt`. Its SHA-256 is identical to the successful control log
above: the old `control` marker remains, with no fresh shim evidence.
This attempt did not reach the loader's first persistent-log flush; the
exact reset instruction/stage is not established. Android pstore is empty,
and both boot-reason properties report `bootloader`. Do not attribute the
old control log to this shim attempt. Next isolate the rebuilt firmware
and driver dispatch from PCIe MMIO by returning before the first register
access, retaining the corrected kernel and identical payload.

### No-MMIO isolation test: still resets

An isolated DEBUG UEFI build returns from `PcieShimEntry` before its first
PCIe MMIO access, after writing the diagnostic variable. The four PCIe
mapping descriptors and module registration remain present. Build passed;
the original driver and platform DSC were restored byte-for-byte afterward.
Image: `diagnostics/pcieshim-nommio-20261119-v2/xnu-pcie-shim-nommio-v2.img`.
SHA-256: `ed835ed09e3cfd1213396272af1fca9dd99d9f4e13454da94f4a17489725c4d4`.
Only the UEFI FD differs from the corrected shim image; BootShim, complete
payload, corrected kernel, DTB, and ramdisk were independently verified.
Fastboot accepted this image at 06:20:19 (Asia/Shanghai). The user again
reported a reboot in under one second; Android ADB reconnected. Therefore
the full PCIe register sequence is not required to reproduce this reset.
This does not distinguish the new mappings, driver logging/dispatch, or
other rebuilt-firmware behavior. Next remove only the four new mappings
from the same no-MMIO test to narrow the failure, without changing payload.
The v2 post-reset read is
`diagnostics/pcieshim-nommio-20261119-v2/nommio-reboot-runtime-20261119-062239.bin`;
it is also identical to the successful control log. LLVM IR inspection of
the compiled driver confirms its entry only initializes the log, calls
`reportf` twice, and returns success; the PCIe MMIO sequence is absent.

### No-map isolation test: still resets

The next isolated build removes the four new mappings while retaining
the no-MMIO driver and its registration. Temporary image:
`diagnostics/pcieshim-nomaps-20261119-v3/xnu-pcie-shim-nomaps-v3.img`,
SHA-256 `6d05786cc9576fc1a71f6f60c83976e2450c8d702c30b6e91da3fff2c464daa2`.
Remote artifacts: `/home/shen/hakios/tmp/pcieshim-nommio-zbtvc1mw/`.
The DEBUG build passed; all temporary source changes were restored.
Only the firmware FD changes from the corrected shim image. Fastboot
accepted it at 06:24:48 (Asia/Shanghai). The user reported the same quick
reboot; Android ADB reconnected. A device-side 2 MiB log hash check again
returned `36f411a57ac516b7766b53ba4512cddf71efd176c2207080e732607330be993a`.
There is still no fresh shim log. Keep the phone in Android during analysis.

The known-good control FD was identified byte-for-byte as
`Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd` (2026-11-13),
SHA-256 `e77e41d8e64ba09db5b4215445362cb87f8500ce4dc532e714e438065322766d`.
Recursive FFS/LZMA inspection successfully parsed 141 old and 142 new
modules without parse errors. Besides the added shim and APRIORI change,
SEC and UFSDxe binaries differ; binary differences alone do not establish
a functional regression. The SEC TE `.text` differs in four bytes, while
most other changes are in read-only/debug data. The next build restores
the original map and omits the PCIe driver entirely, using the control
loader and unchanged corrected-kernel payload to test rebuild equivalence.

## 2026-11-19: UEFI shim integration and diagnostic images

### Verified work

- Active source: `/home/shen/hakios` on the build server; the local
  `hakios/hakios-xnu-kernel-main` tree is an older snapshot.
- `PcieShimDxe` is registered once after `Dwc3ShimDxe` in `APRIORI.inc`,
  `DXE.inc`, and `SiliciumPkg.dsc.inc`. Mars `MemoryMapLib.c` adds device
  mappings for GCC (`0x00100000`, 1 MiB), PARF/PHY (`0x01c00000`, 32 KiB),
  DBI/ELBI/iATU (`0x60000000`, 8 KiB), and ECAM (`0x60100000`, 1 MiB).
- DEBUG UEFI build passed; the driver and GUID were verified in the firmware
  volume. Trial: `Mu-Silicium/Build/marsPcieShimTrial-20261119-025026-81682/DEBUG_CLANGPDB/`.
  Existing DEBUG/RELEASE artifacts were preserved.
- `fastboot boot xnu-pcie-shim-uefi.img` was accepted, then the phone returned
  to Android. This does **not** identify the failure stage or prove the shim ran.
- Live `xnuloader/loader.c` lacked the `PcieShim` EFI-variable reader. It now
  reads up to 2047 bytes, terminates the buffer, reports errors, and includes
  the result in the first persistent-log flush: 22 added lines, none removed.
- Both loader variants compile with `-O0`, with only the existing unused
  `wdt_arm` warning. `PCIE_SHIM_DIAG_CONTROL` changes the image marker only.
  Original `xnuloader/loader.efi` and `loader.obj` were restored after building;
  use the isolated diagnostic binaries below with the updated source.

### Captured evidence

Read-only capture: `darwin-persist-20261119-053817.bin` and `.txt`, locally.
The partition reports 25,771,880,448 bytes; 16 MiB was read at offset 8 GiB.
The binary includes 16,777,216 disk bytes and 84 trailing ADB/dd status bytes.
SHA-256 of disk bytes: `afcdb6d6973264ccace667860e82b4ff23db6f0e6accfa4ec06435aa2792f28b`.
The log includes user space and `PCS_STATUS1=0x48`, but no new image marker;
it cannot be attributed to the shim test. Boot reason is `bootloader` and
pstore is empty; neither establishes the failure stage.

### Initial diagnostic images (superseded; retain for comparison)

Local: `C:/Users/97770/Documents/mi11/diagnostics/pcieshim-20261119-v1-tagged/`

Remote: `/home/shen/hakios/tmp/pcieshim-diag-20261119-Gp13yr/tagged/`

| Image | Bytes | Expected log marker |
|---|---:|---|
| `xnu-pcie-control-diag-v1.img` | 11,892,736 | `pcieshim-loader: diag-20261119-v1 control` |
| `xnu-pcie-shim-diag-v1.img` | 11,896,832 | `pcieshim-loader: diag-20261119-v1 shim` |

SHA-256:

- Control: `b08f347a5ed07c5d468a79654b13bd9c48fd80caac31eea91ff33931cf68f53a`
- Shim: `1ffe1291d869fcc31073827f634f825dd35e4573a26ca7e3683033b78a296d62`

Each replaces only its payload loader. BootShim, source firmware, DTB,
kernel, ramdisks, resident image, command line, physical base, and kernel
version are preserved. Boot-header changes are limited to kernel size/ID.
JSON manifests record component hashes; the packer verifies/rebuilds the
boot ID and rejects overwrites and unsupported layouts.

Local patches/tools: `remote-src/pcie-shim-mmio-register.patch`,
`remote-src/pcie-shim-loader-log.patch`, `remote-src/repack-pcieshim-loader.py`.
The old `remote-src/pcie-shim.patch` is stale/malformed. Preliminary images
outside `tagged` lack the final variant markers; use the directory above.

### Initial test plan (superseded by follow-up above)

1. User manually enters normal Fastboot with Power + Volume Down. Do not
   use `adb reboot bootloader`; device history records an EDL recovery hazard.
   Verify `fastboot getvar is-userspace` reports `no`. Never flash.
2. Temporarily boot the control image first and require its `control` marker.
   An absent `PcieShim` variable is expected with the prior firmware.
3. Extract persistent logs, manually re-enter Fastboot, then boot the shim
   image and require its `shim` marker before interpreting EFI-variable data.
4. Check GDSC, PCS_STATUS1, LTSSM, and ECAM. No PHY lock, PCIe link, QCA6490
   enumeration, or Wi-Fi success is established by this update.

Markers identify image variants, not run timestamps; unchanged logs may be
stale. The shim still reads ECAM after LTSSM timeout: an unproven fault
candidate to evaluate if the next test fails.

## PCIe blocker detail

The 2026-11-20 clock audit above supersedes the earlier clock interpretation:
the vote omitted AUX/master AXI, and two branch status labels were wrong.
The following describes the older attempts, before that correction.

Everything before the PHY PLL works (power, clocks, GPIO94/95/64, full parf
sequence, 75-step PHY sequence, all register read/writes). The PHY never
reports ready (`PCS_STATUS1` stuck at `0x48`, bit 6). Tried: CLKREQ# high,
WLAN_EN (GPIO64) high, ETH PERST# release, DT phy-sequence verbatim, bus
clocks (`mstr_axi`/`slv_axi`/`pipe_clk`). The earlier `cmd_db` exception at
0x80860000 was traced to a missing function declaration that truncated a
mapped pointer (see follow-up above). PMIC SPMI direct writes remain a dead
end because these regulators go through RPMh.

**Next directions** (in order of promise):
1. Validate the integrated UEFI-side shim with the tagged diagnostic images
   above; obtain runtime evidence before further PHY changes.
2. PHY sequence timing experiments (insert delays in the 75 writes).
3. Confirm the reference clock really reaches the PHY (CLKREQ high ≠ EP
   actually outputting 100 MHz).

## Former build server paths (historical; host unavailable)

The former host used `~/hakios/` as its project root. It is no longer
reachable; the paths below describe the last known layout only.

```
~/hakios/
├── xnuloader/loader.c              # loader: USB command loop, log pipeline,
│                                    #   6 GB window patch (map_window),
│                                    #   pcie_step boot-arg plumbing
├── xnuloader/mkpayload.py          # XNUP payload builder (--physbase, --usb)
├── xnuloader/build.sh              # loader.efi build (clang -O0)
├── drivers/pci/hakios.pcie.c       # THE PCIe RC driver (13 steps, pcie_step=N)
├── drivers/pci/phy_seq.inc         # 75-entry QMP PHY sequence from the DT
├── drivers/pci/conf                # driver PCIE (CONFIG_HAKIOS_PCIE)
├── drivers/gpu/hakios.adreno.c     # GPU bring-up (22 steps, adreno=N)
├── drivers/wifi/                   # Wi-Fi stack (redwood WCN6750 base:
│   │                                #   hakios.wifi.c 4.4k lines, wlfw, apple80211)
├── drivers/input/hakios.input.c    # calls hakios_pcie_init() (line ~292)
├── drivers/core/hakios.stubs.c     # stubs for unbuilt drivers
├── xnu/files/bsd/sys/hakios.input.h
├── xnu-src/xnu-8796.121.2/         # XNU tree (apply.sh overlay = xnu/files/)
├── hakios-kernel                   # built kernel (make kernel)
├── userland/                       # userland (REST=1 GL=1 ./build.sh)
│   └── src/eagl.c                  # CA/GL shim: shader warm-up, hash, IOSurface
├── Mu-Silicium/                    # UEFI tree
│   └── Silicon/Silicium/SiliciumPkg/Drivers/Dwc3ShimDxe/   # USB shim
├── mkxnuimg.py                     # image packer (gzip+DTB)
├── tmp/
│   ├── dipper/                     # Mi 8 (SDM845) reference patches
│   ├── gcc-sm8350.c                # Linux GCC clock controller (clock offsets)
│   ├── dwc3-core.h                 # Linux DWC3 headers
│   └── pinctrl-sm8350.c            # TLMM GPIO layout
├── xnu-*.img                       # packed test images
└── venv/                           # build venv (mkxnuimg, build_uefi)
```

Kernel config: `~/.config` (active) / `devices/mars/configs/mars.config`
(template). Enable: `CONFIG_HAKIOS_PCIE=y`.

## Local bundle contents

```
mi11-bundle/
├── docs/          HANDOVER.md, PORT-LOG.md, silicium-status.md,
│                  mars-handover.md (sanitized), mars-progress.md (this)
├── tools/         fdt_dump.py, peinfo.py, make_warmup.py, probe*.py/sh,
│                  patch_*.py, check_img*.py/sh, search_apfs.py, fv-ls.py
├── scripts/       remote.ps1.example, webdav_*.sh.example (credentials stripped)
├── generated/     warmup_shaders.h, warmup_pairs.inc, phy_seq.inc
├── server-patches/  server-*.c  (XNU file snapshots with our edits; APSL headers kept)
├── uefi/          APRIORI.inc, DXE.inc (marsPkg include files)
├── dt/            dt-live.txt, dt-pcie.txt, dt-dump.txt (device-tree dumps)
├── images/        representative test images (latest per track)
└── logs/          key run logs (one per milestone)
```

## Reproduce / continue

1. Use `/home/hakios/hakios-github-snapshot` in the Ubuntu 22.04 WSL distro
   for Linux builds; this is on E: and is the latest source currently
   available. Do not assume it includes unpushed work from the lost host.
2. The Theos Linux toolchain and iPhoneOS 16.5 SDK are installed; the minimal
   Mars kernel, checked Darwin images, and Mars RELEASE UEFI build locally.
   The XBL drivers and device tree are recovered locally; the modem firmware
   still needs to be pulled for modem-enabled builds. The iPhone10,3/10,6 16.5
   (20F66) IPSW is unpacked under `sysimage/`.
3. For a device test, enter normal Fastboot manually and run
   `fastboot boot <img>` (never flash), then extract logs with
   `adb shell dd if=/dev/block/by-name/darwin of=/data/local/tmp/k.bin bs=4096 skip=2097152 count=4096`.
4. PCIe next: rebuild from the available source only after confirming its
   source provenance; validate any image with a boot ID and SHA-256 check.

## Known pitfalls (do not rediscover)

- `build.sh` must run with **`REST=1 GL=1`** — without `REST=1` only 36 of
  418 launchd plists are generated and the **wallpaper goes black**.
- `xnu/files` and `drivers/` edits must be `cp`'d into `xnu-src/` manually
  (apply.sh runs only on first checkout); after editing a driver, `rm` its
  `.o` or make will not rebuild it.
- `loader.c` is ~5000 lines: `-O1` fails with `fixup value out of range`
  (AArch64 ADR ±1 MB). Build with `-O0` (`build.sh` already does).
- TLMM GPIO: base **0xf100000** (not 0xf000000), cfg bit 9 = output enable,
  io bit 1 = value (write 2 = high). Bare `out=1` writes are silently dropped.
- `ml_io_map_wcomb` must have its 64-bit return type declared. Its missing
  declaration truncated the PCIe cmd_db mapping and caused a translation
  fault. The declaration is corrected; validate with the fixed-kernel images.
- Older UEFI firmware does not map GCC (`0x100000`); raw access faulted
  (`esr 0x96000006 far 0x10f010`). The new shim firmware adds the device
  mappings; control images still use the older firmware.
