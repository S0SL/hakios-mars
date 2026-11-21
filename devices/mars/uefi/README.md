# devices/mars/uefi: the firmware that starts the loader

HakiOS's UEFI is Project Silicium's Mu-Silicium with HakiOS's changes: `uefi/` at the top of the common tree, built from
[hakios-uefi](https://github.com/oosexgang/hakios-uefi). This directory is this phone's part of it.

**State: the corrected UEFI shim's stage 4 reached the desktop with the PHY ready on a Mi 11 Pro.** Its fresh runtime log
confirms AUX/master clock halt bits clear and `PCS_STATUS1=0x86`, ready after 1 ms. Link training stopped at LTSSM
`Detect.Active`; the endpoint did not respond and config-space access was skipped. Wi-Fi remains unavailable. The firmware was started with temporary Fastboot boot; no partition
was flashed. The files below began from Mu-Silicium's `venusPkg` (Xiaomi Mi 11, the same SM8350) and were adapted for this phone.

On 20 November 2026, a local Ubuntu 22.04 WSL RELEASE rebuild also reached the iOS desktop, as confirmed on the phone.
The test preserved the previously working kernel, loader and user-space payload and replaced the UEFI FD. It validates the
local UEFI rebuild with the older payload. The separate minimal-kernel test is described below.
The fresh persistent log contains `local-uefi-r2`, the stage-1 completion marker, SpringBoard and Mesa/FD660 rendering.
Its 2 MiB binary has SHA-256 `d611c89ef15062564f8ab3efbde81d5af011be9dc74d36a680ea2dc86f522d48`.

The local minimal kernel subsequently reached the desktop with the existing user space (`local-min1`); the new APFS
images remain untested. That kernel has UFS enabled and uses software rendering; GPU, Mars touch and Wi-Fi are not built in.

## PCIe clock correction

The earlier shim voted `0x35` at GCC `0x52008`, missing AUX and master AXI, and replaced other clients' votes.
The SM8350 definitions agree in Xiaomi's
[gcc-lahaina.c](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/venus-r-oss/drivers/clk/qcom/gcc-lahaina.c)
and upstream Linux's [gcc-sm8350.c](https://github.com/torvalds/linux/blob/master/drivers/clk/qcom/gcc-sm8350.c):

| Clock | Vote bit at GCC `0x52008` | Branch status offset from GCC |
|---|---|---|
| slave AXI | 0 | `0x6b014` |
| master AXI | 1 | `0x6b01c` |
| configuration AHB | 2 | `0x6b024` |
| AUX | 3 | `0x6b028` |
| PIPE | 4 | `0x6b030` |
| slave Q2A AXI | 5 | `0x6b010` |

The corrected shim ORs `0x3f` into the existing vote and preserves the other bits of CLKREF (`0x8c004`) too.
Its `clocks-v7` marker reports both vote words and all six correctly labeled branch registers. Earlier logs labeled
Q2A as slave and PIPE as master; they did not establish that the actual master clock ran. A vote is a request,
so interpret the branch status and PHY result separately from the vote readback.

Run `python3 tools/mars/check-pcieshim.py` from the repository root on Linux. It compiles the actual driver against
recorded MMIO and checks shared-bit preservation, the branch labels, all 16 stage/timeout combinations, bounded waits,
and rejection of invalid stages. The stage-4 follow-up adds six failure/access cases (22 total), including checking
both link indicators and suppressing endpoint reads when the root, translation window or link is unavailable.
These checks pass with the correction and fail against the earlier clock/link code.
The default stage remains 1. The isolated stage-3 device trial is recorded in `docs/mars-progress.md`: the user confirmed
the desktop, and the fresh log shows vote `0x2000` becoming `0x203f`, AUX/master halt bits clearing, and PHY ready after 1 ms.
The log's SHA-256 is `6317c0c7456392bd43f4da5057211afe8706e19f46b77c516cef5e4b03224066`.
This stage-3 trial stops before link training; it establishes PHY readiness, not a Wi-Fi connection.

The subsequent stage-4 trial uses the local ELBI/DLL link indicators, restores the internal DBI base to zero,
and sets up a bounded 4 KiB CFG0 iATU window before endpoint reads. The user confirmed a desktop; the fresh
`persist-v8.bin` log has SHA-256 `6ebbcdf34a54f02be5c78e943cae2eef75c8f78d708a4eef672e0c765344aa12`.
It records LTSSM `Detect.Active`, an inactive DLL and no ECAM access. The link is still down.

After returning to Android, the same phone enumerated `17cb:1103` at 5 GT/s x1 under `cnss_pci` and exposed `wlan0`.
The saved live FDT maps WLAN_EN to GPIO64 and lists five WLAN rails plus the antenna-switch rail; all six regulators
reported enabled in the Android reference capture. The UEFI stage-4 log only proves GPIO64 was driven high and does not
confirm that RPMh rail votes survived the transition.

The stage-5 trial follows Xiaomi's controller sequence more closely: select the external PIPE-clock parent (`PCIE_0_PIPE_CLK`),
pulse the FDT-named core and PHY resets, and enable the PIPE vote after the PHY register sequence. This addresses concrete
gaps in the prior shim. The RELEASE build and temporary desktop boot succeeded. Its `persist-v9.bin` log has SHA-256
`da5c93c7389bcc312583387f3f901aac95212790fb775d50217a4f1e29cc7033`. It records mux `2 -> 0`, both reset pulses
`0 -> 1 -> 0`, and the PIPE vote turning on after PHY programming. PHY reports ready, but link training ends at LTSSM 0
with DLL-active clear; endpoint access is skipped. Android reported all five CNSS rails and the antenna-switch rail enabled
in its reference boot. UEFI has not yet requested them through RPMh. Default remains stage 1.

The stage-5 TCXO comparison selects `PCIE_PIPE_PARENT=2` and keeps the reset and PIPE vote sequence. It
reached the iOS desktop and read back mux `2 -> 2`. The link reached `Detect.Active` (`ELBI=0x1001`),
with DLL inactive and endpoint access skipped. The host checks now cover both parents for stage 5
(42 cases total). See `docs/mars-progress.md` for the image and log hashes.

The subsequent clock-readback image confirms that the PHY rate-change branch vote is on and its branch halt bit is clear.
The source RCG remains on `bi_tcxo` (19.2 MHz). Qualcomm's 100 MHz rate is used for bandwidth scaling after link-up;
the Mars tree does not define `qcom,bw-scale` or `qcom,target-link-speed`. Link training still stops at `Detect.Active`,
so the next blocker is the controller/endpoint power and link sequence rather than an unverified clock vote.

## Required Mars boot configuration

The original Venus memory map and vendor driver lists cause an early reset on Mars. Keep these recovered settings:

- The decompressed firmware volume has an 8 MiB region at `0x9F400000`; a 4 MiB region is too small for this build.
- The UEFI FD is 3 MiB at `0x9FC00000`, with the CPU vectors at `0x9FF8C000` and the display at `0xEA600000`.
- `0xA0000000` through `0xAFFFFFFF` is conventional memory for loading the EFI application. The 64 MiB XNUP payload
  reservation at `0xF0000000` must be mapped before BDS accesses it.
- `APRIORI.inc` and `DXE.inc` keep `EnvDxe`, `SdccDxe`, `CPRDxe`, `ScmDxeLA`, `TzDxeLA`,
  `ShmBridgeDxeLA`, and `SPSSDxe` out of the boot path. Restoring them requires separate bring-up work.
- The v19 trial added the pinned Mu-Silicium Venus `ClockDxe` before the Mars PCIe shim. The original
  Venus and Mars binaries and dependency expressions match byte for byte. The Venus INF selects
  the upstream patched binary. The trial reached the desktop and found the clock protocol.
- Keep `UFSDxe` in the firmware and its two verified listener stubs in the local vendor input. For the extracted Mars
  version, offsets `0x10900` and `0xFD2C` contain `e0031faac0035fd6`; the patched PE has SHA-256
  `c162bfd021e143fa438f38e4da1a1719e308a7bec1e707cbf264a673540a1969`. Other versions need independent verification.

These settings were recovered together from the saved working Mars configuration. The successful test does not identify
one individual missing setting as the sole cause. The former build's `Dwc3ShimDxe` source remains unavailable, so it is
not registered here. A stable loader USB command channel is still pending.

## What is here

| File | Where it goes in Mu-Silicium | What it is |
|---|---|---|
| `files/Platforms/Xiaomi/marsPkg/mars.dsc` | `Platforms/Xiaomi/marsPkg/` | the platform: SM8350 (`LahainaPkg`), the DDR base, the UEFI stack, the SMBIOS strings, the panel 1440x3200 |
| `.../mars.fdf` | the same | what the image is made of |
| `.../mars.dec` | the same | the package's declarations (empty, as `venus.dec` and `redwood.dec` are) |
| `.../DeviceBuild.py` | the same | `stuart`/`build_uefi.py` entry point for `-d mars` |
| `.../Include/APRIORI.inc`, `DXE.inc`, `RAW.inc` | the same | the driver lists, including the Mars PCIe shim and device-specific vendor modules |
| `.../Library/MemoryMapLib/` | the same | the SM8350 ("lahaina") memory map, including the PCIe GCC, PARF/PHY, TLMM and DBI/ECAM windows |
| `files/Silicon/Silicium/SiliciumPkg/Drivers/PcieShimDxe/` | Mu-Silicium | the stage-gated PCIe initialization driver; stage 1 is the verified default |
| `.../Library/ConfigurationMapLib/` | the same | where the boot devices are (UFS) |
| `files/Resources/Configs/mars.toml` | `Resources/Configs/` | the boot shim's layout: the FD at `0x9FC00000`, 3 MB, as listed in this phone's `uefiplat.cfg`; gzip |
| `make-mars-pkg.py` | -- | the record of how the files above were made |

## How they were made, and how to make them again

```sh
python3 devices/mars/uefi/make-mars-pkg.py      # fetches venusPkg, renames, changes the SMBIOS strings
```

Kept as the record and not as a build step. **Running it again overwrites every file it wrote**, so do not run it after
editing the platform by hand. The three things it changes are the name (`venus` -> `mars`), the SMBIOS strings
(`Mi 11` -> `Mi 11 Pro`, `M2011K2G` -> `M2102K1AC`, board `mars`) and the platform GUID. The memory map and driver lists
were subsequently corrected for Mars; regenerating from Venus would discard those boot prerequisites.

## What this phone's platform still needs

1. **The vendor's drivers.** Reproducing the firmware build requires the display, storage and USB drivers Qualcomm and
   Xiaomi wrote for this phone. They are not distributed here. Extract them from **your own** `xbl` with [UEFIReader](https://github.com/WOA-Project/UEFIReader)
   into `devices/mars/uefi/files/Binaries/mars/` (`QcomPkg`, `MiPkg`, `RawFiles`, the EDK2 modules as the vendor built them).
   `.gitignore` ignores `files/Binaries/*/*`, and `tools/provenance-check.py` fails if they come back: they are the vendor's.
2. **The device tree** (optional to build, needed to boot what XNU is given): `files/Resources/DTBs/mars.dtb`, from your own
   phone (`adb pull /sys/firmware/fdt`). The `.fdf`'s device-tree block is commented out, as `venus`'s is; HakiOS's loader
   builds XNU's tree itself, so this is for the firmware's own use.
3. **`SOC_TYPE`**: `0` = SM8350, `1` = SM8350-AB, `2` = SM8350-AC. A Mi 11 Pro is an SM8350, so `0`; if the image boots and
   the chip is misread, this is the first number to try.

Two things are deliberately not this phone's yet:

- **The ACPI tables** are `venus`'s (`Silicium-ACPI/Platforms/Xiaomi/venus/AcpiTables.inf`). Nothing in HakiOS's boot path
  reads ACPI -- the loader builds XNU's device tree -- so this costs nothing today; make `mars`'s own when it does.
- **`PcdStorageIsUfs3`** is not set, as `venus` has it. This phone's storage is UFS 3.1, so if UFS bring-up misbehaves this is
  the PCD to turn on (`gQcomPkgTokenSpaceGuid.PcdStorageIsUfs3|TRUE`).

## Build

From the top of the common tree (the full recipe is `uefi/README.md` there):

```sh
uefi/apply.sh mars                       # Mu-Silicium + HakiOS's changes + this phone's platform
python3 -m venv venv && venv/bin/pip install -r Mu-Silicium/pip-requirements.txt
(cd Mu-Silicium && source ../venv/bin/activate && python3 build_uefi.py -d mars -r RELEASE)
# -> Mu-Silicium/Build/marsPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd
```

`mkxnuimg.py` (what `./xl enter` calls) takes the image from `Mu-Silicium/`.

## Done when

The phone shows the HakiOS mark, then the loader's banner, then the kernel's first lines -- and a reboot gives Android back.
That is step 2 of `docs/porting/index.md`; everything before it is preparation, and everything after it is drivers.
