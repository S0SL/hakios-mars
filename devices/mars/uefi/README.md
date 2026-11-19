# devices/mars/uefi: the firmware that starts the loader

HakiOS's UEFI is Project Silicium's Mu-Silicium with HakiOS's changes: `uefi/` at the top of the common tree, built from
[hakios-uefi](https://github.com/oosexgang/hakios-uefi). This directory is this phone's part of it.

**State: the UEFI shim's stage 1 has been built and temporarily booted to the desktop on a Mi 11 Pro.** Its fresh runtime log
confirms the PCIe power domain and GCC clocks reached the stage-1 completion point. Stage 2 (PARF/GPIO), PHY readiness, PCIe
link training, and Wi-Fi remain unverified or not working. The firmware was started with temporary Fastboot boot; no partition
was flashed. The files below began from Mu-Silicium's `venusPkg` (Xiaomi Mi 11, the same SM8350) and were adapted for this phone.

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
(`Mi 11` -> `Mi 11 Pro`, `M2011K2G` -> `M2102K1AC`, board `mars`) and the platform GUID; everything else is `venus`'s,
because it is the same SoC.

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
