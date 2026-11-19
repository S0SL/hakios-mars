# devices/mars/uefi: the firmware that starts the loader

HakiOS's UEFI is Project Silicium's Mu-Silicium with HakiOS's changes: `uefi/` at the top of the common tree, built from
[hakios-uefi](https://github.com/oosexgang/hakios-uefi). This directory is this phone's part of it.

**State: the UEFI shim's stage 1 has been built and temporarily booted to the desktop on a Mi 11 Pro.** Its fresh runtime log
confirms the PCIe power domain and GCC clocks reached the stage-1 completion point. Stage 2 (PARF/GPIO), PHY readiness, PCIe
link training, and Wi-Fi remain unverified or not working. The firmware was started with temporary Fastboot boot; no partition
was flashed. The files below began from Mu-Silicium's `venusPkg` (Xiaomi Mi 11, the same SM8350) and were adapted for this phone.

On 20 November 2026, a local Ubuntu 22.04 WSL RELEASE rebuild also reached the iOS desktop, as confirmed on the phone.
The test preserved the previously working kernel, loader and user-space payload and replaced the UEFI FD. It validates the
local UEFI rebuild; the newly compiled minimal kernel and Darwin APFS images still need their own device tests.
The fresh persistent log contains `local-uefi-r2`, the stage-1 completion marker, SpringBoard and Mesa/FD660 rendering.
Its 2 MiB binary has SHA-256 `d611c89ef15062564f8ab3efbde81d5af011be9dc74d36a680ea2dc86f522d48`.

## Required Mars boot configuration

The original Venus memory map and vendor driver lists cause an early reset on Mars. Keep these recovered settings:

- The decompressed firmware volume has an 8 MiB region at `0x9F400000`; a 4 MiB region is too small for this build.
- The UEFI FD is 3 MiB at `0x9FC00000`, with the CPU vectors at `0x9FF8C000` and the display at `0xEA600000`.
- `0xA0000000` through `0xAFFFFFFF` is conventional memory for loading the EFI application. The 64 MiB XNUP payload
  reservation at `0xF0000000` must be mapped before BDS accesses it.
- `APRIORI.inc` and `DXE.inc` keep `EnvDxe`, `ClockDxe`, `SdccDxe`, `CPRDxe`, `ScmDxeLA`, `TzDxeLA`,
  `ShmBridgeDxeLA`, and `SPSSDxe` out of the boot path. Restoring them requires separate bring-up work.
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
