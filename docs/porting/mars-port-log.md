# Port log: Xiaomi Mi 11 Pro (mars)

What was done, in the order it was done, and what it showed. The device's own state is in `device.conf`; this file is the
work's diary, including the things that did not work.

## 2026-11-08 -- from an empty repository to a boot image the phone accepts

### The phone, read over adb (LineageOS 23.2, KernelSU root, bootloader unlocked)

| | |
|---|---|
| `ro.product.device` | `mars`, model M2102K1AC, `ro.soc.model` SM8350 |
| Bootloader | `androidboot.verifiedbootstate=orange` (unlocked) |
| Panel | 1440x3200, 560 dpi, DSC command mode, panel id `K2_0A_MP` |
| Touch | FocalTech `fts` on `spi@a8c000`, IRQ GPIO 23, reset 22, 7 MHz, firmware `st_fts_k2.ftb` |
| Wi-Fi | `qcom,cnss-qca6490` (CNSS, the WCN6855 generation) -- **no `wpss.*` image**, only `bdwlan.*` |
| GPU | `Adreno660v2`; firmware `a660_gmu.bin`, `a660_sqe.fw`, `a660_zap.*` (same names as redwood) |
| PMICs | pm8350, pm8350c, pmk8350 |

The ROM is LineageOS, so `ro.build.fingerprint` is a spoofed Xiaomi one: **do not read the firmware version from it**. The
device tree in `/sys/firmware/fdt` is LineageOS's, not the stock one -- the addresses are still the hardware's, but node
names may differ (see `soc.args` below).

### `soc.args` (from the phone's own tree)

11 of the 13 values `tools/soc-args.py` reads are the reference phone's. Different: `soc_ipa_stream=0x5c0` (redwood `0x480`),
`soc_ipa_stream_uc=0x5c2` (redwood `0x482`), `soc_ipa_fw=ipa_fws` (redwood `yupik_ipa_fws`).

Two values the tool did not emit, added by hand from the tree's reserved memory: `soc_mpss_mem=0x8f000000`
(`modem_region@8f000000`) and `modem_ipa_fw_at=0x8e700000` (`pil_ipa_fw_region@8e700000`). SM8350 names those nodes
`modem_region` / `pil_ipa_gsi_region`, which `soc-args.py`'s `find_named` (exact leaf name) does not match -- a small gap
worth fixing upstream. `soc_cmd_db` has no node at all here; the kernel's `0x80860000` default stands.

### The kernel

`make mars_defconfig && make kernel -j24` on the build machine: `hakios-kernel`, 15 MB, Mach-O 64-bit arm64,
`kernel.ver=2.3.4-hakios-darwin22.5-sm8350-g63fc2b46`, 4 drivers built in (the virtio ones), every phone driver left out.

Four things had to be fixed before it would build on Ubuntu 22.04 (each is a real portability hole in the project):

1. `xnu-deps/hostinc/hostcompat.h` did not provide BSD's `strlcpy`/`strlcat`, which glibc lacks and which XNU's
   `SETUP/replacecontents` uses. Added two `static inline` implementations.
2. `xnu-deps/host/bin/xnu-clang` dropped `-enable-trivial-auto-var-init-zero-...` unconditionally; clang 14 and 15 refuse
   `-ftrivial-auto-var-init=zero` without it. The wrapper now keeps it for clang < 16.
3. XNU's `makesyscalls.sh` is an awk script whose `printf "\(sy_call_t *\)"` relies on BSD awk dropping the backslash; mawk
   keeps it, and the generated `init_sysent.c` does not compile. Installed `original-awk` and made it the system awk.
4. `tools/make-kernel.sh` judges a build by matching `Error 2` in make's output; under a non-English locale make prints
   `错误 2`, so a good kernel was reported as a failed build. Run the build with `LC_ALL=C` (the script should set it itself).

Also needed on a Debian/Ubuntu host: `python-is-python3` (XNU's lldbmacros step calls `/usr/bin/env python`) and
`python3-venv` for the UEFI build's venv.

### The UEFI firmware

`xbl_a` (8 MB, ELF) was dumped read-only off the phone and unpacked with MSMTools/UEFIReader (built on the server with the
.NET 8 SDK): **313 files, 7.5 MB**, XBL build `BOOT.MXF.1.0-00852-LAHAINA-2.12801.13`, including 67 `QcomPkg/Drivers`,
`MiPkg`, 49 `RawFiles` -- and `RawFiles/Panel_K2_38_08_0a_mp_amoled_dsc_cmd.xml`, this phone's own panel.

The XBL also carries its own driver manifests (`APRIORI.inc`, `DXE.inc`, `DXE.dsc.inc`). Those were used, but the platform
that builds is a hybrid and it is worth knowing why: the phone's list names modules from Xiaomi's older EDK2
(`RscRtDxe.inf`, `SCHandlerRtDxe.inf`) that Mu-Silicium's EDK2 does not have, so the *source* module list is Mu-Silicium's
`venusPkg` (whose 51 vendor binaries all exist in this phone's set), while the *raw files* are the phone's own
(`uefiplat.cfg`, `BDS_Menu.cfg`, `logo1.bmp`). `Binaries/venus/` -> `Binaries/mars/` is the only rewrite.

`build_uefi.py` needed `tomli` (Python 3.10 has no `tomllib`) and a `Resources/DTBs/mars.dtb` (the phone's own FDT).

Result: `SILICIUM_UEFI.fd`, 2.0 MB, 164 modules built, `PROGRESS - Success`.

### The boot image and three boots

`make loader-open` (placeholder identity), `mkpayload.py` (kernel + `hello` ramdisk), `mkxnuimg.py -d mars` (a `--device`
option was added; it was redwood-only). Result: a 7 MB `ANDROID!` boot image, `fastboot boot` accepted it (`Sending OKAY`,
`Booting OKAY`).

| # | Image | Screen | After |
|---|---|---|---|
| 1 | mars, `USE_CUSTOM_DISPLAY_DRIVER=0` | black (not watched) | back in Android |
| 2 | same | black | back in Android |
| 3 | mars, `USE_CUSTOM_DISPLAY_DRIVER=1` | black | back in Android |
| 4 | **venus** (control) | black | **hung, USB gone** |

Not one boot wrote a byte to `logdump` (checked the whole 64 MB partition on the phone): **the XNU loader never started**, so
the firmware dies before BDS. The venus control hanging the same way says this is not mars's platform but the layer under it.

### What the phone's own `uefiplat.cfg` says (the lead for next time)

```
0x9FC00000, 0x00300000, "UEFI FD"            <- the phone's own UEFI region: base 0x9FC00000, 3 MB
0xEA600000, 0x02400000, "Display Reserved"   <- venus's map (which mars.toml copies) has 0xE2A00000
0x9FF90000, 0x00040000, "UEFI Stack"
0xA0000000, 0x10000000, "Kernel"
```

`Resources/Configs/mars.toml` (copied from venus) says `base = 0x9FD00000, size = 0x200000`. Next: try
`0x9FC00000` / `0x300000`, and rebuild `MemoryMapLib` from this phone's `uefiplat.cfg` (at least `Display Reserved`).

### To pick this up

```sh
# on the build machine, in ~/hakios
devices/mars/pull-soc.sh                 # already made: soc.args is committed in this repository
make mars_defconfig && LC_ALL=C make kernel -j
cd Mu-Silicium && MAX_CONCURRENCY=24 ~/hakios/venv/bin/python build_uefi.py -d mars -r RELEASE
python3 mkxnuimg.py -d mars -p /tmp/mars-payload.bin -o /tmp/xnu-mars.img
# on the phone (fastboot driver installed, bootloader unlocked)
adb reboot bootloader && fastboot boot xnu-mars.img
```

### Later that night: the stub that proved the bottom of the stack works

Four more boots, each black, each ending in a power-cycle. Then a control that did not need the UEFI at all: a 32-byte
AArch64 stub, packed where the FD goes, whose only work is to fill `0xEA600000` (this phone's `Display Reserved`) with
`0xFFFFFFFF` and spin.

**The screen went white.** That one result rules out most of what had been suspected:

| Question | Answer |
|---|---|
| Does the bootloader decompress the gzip kernel? | yes -- a **raw** (uncompressed) image is refused and the phone stays in fastboot |
| Does the BootShim run and copy to `FD_BASE`? | yes |
| Is `0xEA600000` the panel's framebuffer? | yes, and XBL leaves the panel on |
| Does code execute at `FD_BASE` with the MMU off? | yes |

So the failure is **inside the firmware**, after its entry point: the FD's first word is `0x14000400` (a `b #0x1000` to the
SEC core), and the SEC core starts and dies without printing anything -- and its console *is* that same framebuffer
(`FrameBufferSerialPortLib` finds it by the memory-map name `"Display Reserved"`).

### What to do next: paint the screen from inside SEC, then move the paint later

The phone has no accessible UART, so the framebuffer is the only output, and SEC is where it goes quiet. The method that
works without a console is to make SEC itself the indicator:

1. In `Silicon/Silicium/SiliciumPkg/Sec/Sec.c` (or its `AArch64/ModuleEntryPoint.S`), write a distinctive colour to
   `0xEA600000` as the very first thing, then hang.
2. Boot it. White means the C entry of SEC runs at all.
3. Move the marker one step later at a time -- after `SerialPortInitialize`, after the FV is decompressed, after the
   page tables, into PEI -- and boot after each, until a step stops painting. That step is the bug.

Each cycle is about three minutes (rebuild, `mkxnuimg.py`, `fastboot boot`) plus one power-cycle of the phone.

Alongside that, two things worth checking in the same pass:
- `PcdFdBaseAddress` / `PcdFvBaseAddress` in the built FD against `0x9FC00000` / `0x300000` (they come from `mars.toml`).
- Whether SEC's stack (`0x9FF90000`) and page tables (`0x9FF8D000`) are the phone's own: `uefiplat.cfg` says "UEFI Stack
  0x9FF90000, 0x00040000" and "MMU PageTables 0x9FF8D000, 0x00003000" -- they match, so this is likely fine.

### The marker ladder (same night, after the stub)

Painting the framebuffer from inside the firmware turned the black box into a progress bar. Each stage fills the screen with a
colour, so the last colour seen is the last stage reached:

| Stage (in `SiliciumPkg/Sec`) | Colour | Reached? |
|---|---|---|
| `_ModuleEntryPoint` | white | yes |
| after `PlatformAssemblyInitialize` | blue | yes |
| after the SPAN disable | yellow | yes |
| after `ArmEnableVFP` | magenta | yes |
| `SetupExceptionLevel1` entered (the EL1 path) | cyan | yes |
| `MainEntryPoint` (EL1 path returns here) | green | **no** |

So the firmware runs, gets through its platform assembly init, VFP and exception-level selection, and dies on the way back out
of `SetupExceptionLevel1` -- about six instructions, all of which look ordinary (`msr cpacr_el1; ret`, then `b MainEntryPoint`).

Tried, and did not change it: skipping the redundant `CPACR_EL1` write in `SetupExceptionLevel1` (since `ArmEnableVFP` already
wrote it). Same cyan, same reset.

Two things the ladder also showed:
- The phone's XBL hands the firmware to **EL1, not EL2** (the cyan marker is on the EL1 path).
- The markers themselves are suspect: each fill was 36 MB, six of them is seconds of uncached writes. Shrinking the fill to a
  256 KB band (a line at the top of the screen) made the run *faster* but the colour could no longer be told apart by eye, so
  that experiment was inconclusive.

### The next experiment: position, not colour

The colour is a bad channel -- it flashes by, and a thin band is unreadable. The position is a good one: make stage *N* paint a
band at row *N* (or `N` separate bands), so a single look at the top of the screen says exactly how far the firmware got,
whatever the colours are, and however fast it runs. Then move the bands one instruction at a time through
`SetupExceptionLevel1`, `ArmEnableVFP` and `MainEntryPoint`.

If the firmware turns out to reset because the *markers* are slow (an XBL watchdog), the bands make that visible too: the run
will get further the less each stage paints.

### The bisect that worked: fill the screen and stop

The colour ladder was misleading because each stage painted 36 MB. The reliable primitive turned out to be: **fill the
display reservation, then stop** -- the screen holds the answer, nothing has to be caught mid-flash. On a clean baseline
(`git checkout` of the files that had been edited), one freeze point per boot:

| Frozen at | Screen | Conclusion |
|---|---|---|
| `_ModuleEntryPoint` (the first instruction) | white, stays | baseline, shim and framebuffer are all good |
| `MainEntryPoint` (after platform asm init, VFP, EL setup) | white, stays | the whole SEC assembly path is fine |
| `SecEntry` (the C entry) | white, stays | the asm hands over to C correctly |
| after `InitializeMemory ()` | blue, stays | HOB built, **MMU on**, and the framebuffer is still writable |
| after `DecompressFirstFv ()` | green, stays | the DXE firmware volume decompresses |

An earlier "cyan then reset" was my own doing: a trial that replaced `SetupExceptionLevel1`'s `b ArmWriteCpacr` with a bare
`ret` broke it. Restored, it works. The lesson for the log: change one thing at a time, and treat a reset as the *absence* of
the marker, not as a stage.

### And then the console came up

A DEBUG build (`build_uefi.py -d mars -r DEBUG`) keeps `SerialPortInitialize ()` and `PrintFirmwareVersion ()`, and Silicium's
serial port is `FrameBufferSerialPortLib` -- it draws the log on the phone's own screen. Booted: **text appears**, the firmware
is alive past SEC and into DXE, and the phone reboots 1-2 seconds later.

That is the state to pick up from: the firmware runs and has a working console; something 1-2 s into DXE takes it down. Next:

1. Print a line and then stop, to read it calmly and to prove the console end to end (`PrintFirmwareVersion`, then freeze).
2. Then markers *inside* DXE (or raise `PcdDebugPrintErrorLevel`), one driver at a time, the same way SEC was bisected.
3. Consider the watchdog: 1-2 s is suspiciously timer-like, and `uefiplat.cfg` has `EnableUefiSecAppDebugLogDump` and a
   ULog file size; the XBL may be resetting a firmware that does not pet it. Feeding it, or disabling it early, may be the
   difference between "resets" and "boots".

### TrustZone drivers ruled out, and an EDL scare

The four TrustZone drivers (`ScmDxeLA`, `TzDxeLA`, `ShmBridgeDxeLA`, `SPSSDxe`) were dropped from `APRIORI.inc` and
`DXE.inc` and the DEBUG firmware rebuilt: same behaviour, text then a reset 1-2 s in. So the reset is not those drivers
calling into TEE.

Worth recording: one DEBUG boot left the phone in **EDL (Qualcomm 9008, `QUSB_BULK_CID:041D`)**. Holding power for 20-30 s
brought it back, and `fastboot getvar product` still answered `mars` with slot `a`; nothing was written. But it means a bad
enough DXE crash can drop the device into the emergency-download path, so each further test carries that risk. Prefer
experiments that **freeze** over ones that let the firmware crash.

The lists in `devices/mars/uefi/files/Platforms/Xiaomi/marsPkg/Include/` are now the venus-based ones **minus** those four
drivers; put them back if a later stage needs TEE (PIL, the modem and the GPU all do).

### The blocker now: reading 1-2 s of text

The console works, the firmware prints, and the phone resets before anyone can read it. Options, cheapest first:

1. **Film the screen** with a second device (240 fps is plenty); the debug lines are large and high-contrast, so a single
   frame will show the last lines printed before the reset. This answers "where did DXE die" without a single extra boot.
2. **Bisect inside DXE** with the freeze primitive: `MdeModulePkg/Core/Dxe/DxeMain/DxeMain.c` calls its `CoreInitializeXxx`
   steps in order; freeze after each, one boot per step. Reliable, but ~10 boots.
3. Make the DXE exception handler print ESR/ELR/FAR to the console and then spin (instead of the reset): then the faulting
   address is on the screen, held there by the spin.

### From black screen to 22 DXE drivers

With the FV given a safe 8 MB home below the FD (`0x9F400000`-`0x9FC00000`, the old Sched Heap + FV Region + ABOOT FV
merged), the firmware stopped overwriting itself and the DEBUG console became readable. Photographs of the screen did the
rest:

| Change | Result |
|---|---|
| FV region merged into one 8 MB block below the FD | `FV Hob 0x9F5C0000-0x9FBFEFFF` -- no more self-overwrite |
| `uefiplatLA.cfg` added to the FV (a copy of the phone's own `uefiplat.cfg`) | did not help on its own |
| `EnvDxe` removed | **DXE runs: 22 drivers load** |

`EnvDxe` failed with `ASSERT_EFI_ERROR (Status = Not Found)` in `AutoGen.c:611` -- a *library* constructor, i.e. Qcom's
`UefiCfgLib` looking for the platform config the XBL hands to a native UEFI. A replacement firmware has no such thing, and
HakiOS's loader does not need it, so it is out of the lists.

What loads now, in order: PcdDxe, ReportStatusCodeRouter, StatusCodeHandler, RuntimeDxe, ArmGicDxe, MetronomeDxe, TimerDxe,
SmemDxe, DALSYSDxe, HWIODxe, ChipInfoDxe, PlatformInfoDxe, ProjectInfoDxe, HALIOMMUDxe, ULogDxe, CmdDbDxe, PwrUtilsDxe,
NpaDxe, RpmhDxe, VcsDxe, **ClockDxe** -- and there the phone reboots.

One warning on the way, worth following up:

    Rpmh Sleep callback registration failed, Status = 0x8000000000000003

ClockDxe drives the whole chip's clocks through RPMh, so if RPMh is only half up, ClockDxe is where it would break. Next:
boot with ClockDxe removed and see whether the next driver loads (TLMM, I2C, SPI, UFS, the USB stack, BDS), and separately
look at what the RPMh callback registration needs.

### The debug technique that produced all of this

DEBUG firmware (`build_uefi.py -d mars -r DEBUG`) + `PcdDebugPropertyMask` + `FrameBufferSerialPortLib` = the phone's own
screen as a console. Photographing it needs no extra hardware and answers in one boot what the fill-and-freeze bisect answered
in ten.

### Past ClockDxe, past UFS, into the display and USB: ~40 drivers

ClockDxe was the next wall, so it came out first. Then, in order:

| Removed | What happened |
|---|---|
| `ClockDxe` | DXE ran on: DALTLM, I2C, SPI, PmicDxe (PMIO 47, PMI1 40, PMI2 49, PMI3 50, PMI4 51 -- the phone's own PMICs answer), DiskIo, Partition, English, SdccDxe, **UFSDxe** |
| `UFSDxe`, `SdccDxe` | `UFS INQUIRY ID: KIOXIA THGJFAT1T84BAIRB1Z01`, then `ASSERT RpmbListener.c` (RPMB wants the TEE, which is not up) -- and HakiOS's boot does not need UEFI storage, so both went |

With those out, the firmware loads **40+ drivers**: Fat, VariableRuntime, DDRInfo, ResetSystemRuntime, FeatureEnabler, **DisplayDxe**,
PILProxy, IPCC, GLink, UsbConfig, SecurityStub, EmbeddedMonotonicCounter, RealTimeClock, Print, DevicePath -- and then dies on a
**Data Abort**:

    Data abort: Translation fault, second level
    ESR 0x96000050   ELR 0x000000009DE5FF74   FAR 0x000000006BEE0000

`0x6BEE0000` is not a plausible pointer, so some driver took a number for one. The faulting instruction is at `0x9DE5FF74`, inside
one of the drivers loaded into the DXE heap; the boot log in the recording names the load address of each, so matching
`0x9DE5F000` against those lines identifies the driver.

Two things this run also showed, both consequences of the removals and both worth fixing rather than living with:

- `MDIPlib: Failed to setup MDP core clocks!` then `DisplayDxe: SW renderer mode enabled!` and `Resolution 640x480`: the display
  works, but through the software renderer, because there is no ClockDxe to set the MDP clocks. Putting ClockDxe back (once
  RPMh is happy) should give the real panel.
- `FeatureEnablerDxe: Cannot locate gQcomQseecomProtocolGuid` and `smem_alloc_ex failed err=-31`: the TEE path (removed with
  `ScmDxeLA`/`TzDxeLA`) and one SMEM allocation. Neither stopped the boot.

### Where it stopped at the end of the night

Frame-by-frame from the recording, the last drivers to load were ChargerEx, UsbPwrCtrl, XhciPciEmulation, UsbBus, UsbKb,
UsbMassStorage, UsbMsd, UsbDevice, UsbConfig, Buttons -- and then **CPRDxe**, immediately followed by

    Synchronous Exception at 0x000000009DE5F74
    (X0=0, X1=1, X5=0x4BD730, X24..X28 holding 0x9D.. pointers, FP=0x9FFCEAF0)

`CPRDxe` (Core Power Reduction, the CPU's voltage/clock relationship) is the prime suspect and was removed next; that build is
made and waiting to be booted.

### The workarounds are piling up, and they need a pass of their own

Everything below got the firmware further but is not a fix. When the port is finished these all need to come back and be made
to work, roughly in this order of importance:

| Removed / skipped | Why | What it costs |
|---|---|---|
| `ClockDxe` | the wall after 22 drivers | the whole chip's clocks; the display falls back to a software renderer at 640x480 |
| `UFSDxe`, `SdccDxe` | `ASSERT RpmbListener.c`, because RPMB needs the TEE | storage in UEFI (HakiOS's loader does not need it) |
| `ScmDxeLA`, `TzDxeLA`, `ShmBridgeDxeLA`, `SPSSDxe` | suspected of the earliest resets; not proven guilty | TEE: RPMB, feature enabling, Qseecom |
| `EnvDxe` | `UefiCfgLib` cannot find the XBL's platform config | no Qcom environment/configuration plumbing |
| `CPRDxe` | the synchronous exception above | CPU voltage/clock |

The likely root of the ClockDxe wall is the warning printed two drivers earlier:

    Rpmh Sleep callback registration failed, Status = 0x8000000000000003

RPMh is what every clock vote travels over, so "RPMh half up" explains both ClockDxe failing and the MDP clocks failing in
DisplayDxe.

### BDS reached

With the DXE list trimmed down to what runs, the firmware went past the driver wall and into the **Boot Manager**:

    Loading driver ... ConPlatformDxe, ConSplitterDxe, GraphicsConsoleDxe, TerminalDxe, SmbiosDxe,
                       SetupBrowser, AcpiPlatform ...
    PlatformBootManagerAfterConsole: Failed to display boot logo! Status = Not Found
    Locate GOP Protocol! Status = Not Found
    USB boot desired, but no USB devices found on first attempt.

Two findings from that run:

1. **`DisplayDxe` is this phone's GOP provider.** Removing it to keep the big console also removed the Graphics Output Protocol, and
   BDS then cannot draw anything. It has to stay.
2. Before that, with `DisplayDxe` in and the payload region absent from the memory map, the crash was
   `FAR = 0x0F0000000` with the string `"Display Reserved"` on the stack -- **`0xF0000000` is `PAYLOAD_BASE`**, where the shim puts
   the XNUP container. The map had no region there, so once the MMU was on, anything touching it took a translation fault. The map
   now declares `{"HakiOS Payload", 0xF0000000, 0x04000000, ...}`.

So the configuration to continue from is: DisplayDxe **in**, payload region **in the map**, and these still out: EnvDxe, ClockDxe,
UFSDxe, SdccDxe, CPRDxe, ScmDxeLA, TzDxeLA, ShmBridgeDxeLA, SPSSDxe.

### What is left

BDS is the last stage before HakiOS's own work: `SiliciumPkg/Library/BootManagerLib` (which HakiOS's patch points at `XnuLoader.c`)
is what starts the XNU loader from the payload. The next run should show either the loader's banner (`kernel.ver=...`) or the
reason it does not start. Everything below BDS -- the display, the console, the drivers -- is now in place.

### The loader's door: `PlatformBootManagerUnableToBoot`

HakiOS's patch starts the XNU loader from exactly one place:

    VOID EFIAPI PlatformBootManagerUnableToBoot (VOID)
    {
      XnuLoaderMain ();                       // does not return
      DeviceBootManagerUnableToBoot ();
      ...
      gRT->ResetSystem (EfiResetShutdown, ...);
    }

So the loader runs only when BDS concludes there is nothing to boot -- which is what our runs do (no boot options, no USB
devices, no GOP for the logo). The last run showed BDS's closing lines and then a black screen: `XnuLoaderMain ()` clears the
display when it takes over, so the black screen is the loader being entered, not a failure before it. One or two seconds later
the phone rebooted.

That reboot is the open question, and it has two possible owners:

- `XnuLoaderMain ()` returned (it found no XNUP container, or a check failed), and the code after it -- `ResetSystem (EfiResetShutdown)`
  -- is what rebooted the phone; or
- the loader did start the kernel, and the kernel (built with `CONFIG_FIRMWARE="none"` and no drivers) panicked at once.

`logdump` is still empty of HakiOS text: the loader writes its log at the end of a run that hands control back, and a
`fastboot boot` that reboots does not get there.

### To pick this up

1. Make the loader's own progress visible: `XnuLoader.c` already logs to the console; stop clearing the screen (or print again
   right after the clear) and photograph the first lines it prints. That says "payload found" or "payload not found" in one run.
2. Or write the log to `logdump` before starting the kernel rather than after the run, so the evidence survives a reboot.
3. Then: the kernel's first panic. `tools/modem-cycle.sh`-style logging already exists for reading it back.

### The missing piece: the payload has to carry `loader.efi`

The loader's own probe settled it in one run:

    [Bds] Unable to boot!
    PROBE: XnuLoaderMain entered
    PROBE: payload base=f0000000 magic=50554e58 size=E4A3E0
    PROBE: StartPayloadLoader returned

`magic=50554e58` is "XNUP", so the shim really does place the payload at `0xF0000000`, and it is whole. And
`StartPayloadLoader` is the whole story:

    if (AsciiStrnCmp (Entry->Name, "loader.efi", sizeof (Entry->Name)) == 0) {
      gBS->LoadImage (FALSE, gImageHandle, NULL, Entry + 1, Entry->Size, &Handle);
      gBS->StartImage (Handle, NULL, NULL);
    }

It looks for one entry, **`loader.efi`**, and starts it as an EFI image. Our payload held `kernel=` and `ramdisk=` only -- that is
why it walked the whole container and returned. The payload now also carries `loader.efi=xnuloader/loader.efi`:

    python3 xnuloader/mkpayload.py -o payload.bin loader.efi=xnuloader/loader.efi \
        kernel=hakios-kernel ramdisk=userland/hello --cmdline "cpus=8 bootcpu=7 ufs=2"

### The two console rules that cost the most time

- `DEBUG ((EFI_D_ERROR, ...))` goes through `SerialPortLib`, which on this platform is `FrameBufferSerialPortLib`: it lands on
  the phone's screen and always works.
- `AsciiPrint ()` goes through `gST->ConOut`, which reports `Unable to set console mode - Unsupported` here: whatever it prints
  is invisible. A probe written with `AsciiPrint` looks exactly like a probe that never ran.

### Where it stands

The firmware: SEC -> DXE -> BDS -> `XnuLoaderMain` -> `StartPayloadLoader` -> `LoadImage (loader.efi)` -> `StartImage`. Every one
of those steps is now known to be reached. What is left is what the loader itself does with `kernel=`: the Mach-O load, the
device tree it builds for XNU, and the jump. The loader writes its log to the `logdump` partition at the end of a run that hands
control back, so a run that hangs or resets leaves nothing there -- read it only after a run that returns to Android.

### `loader.efi` starts, and crashes

With `loader.efi` in the payload, `StartPayloadLoader` found it, `LoadImage` took it, `StartImage` ran it -- and the screen showed a
stack dump: the loader faulted inside itself. The exception header (ESR/ELR/FAR) had already scrolled off the 640x480 console by the
time the dump was photographed, so the faulting address is not known yet.

Next, in order:

1. Make the loader's own exception report survive: print the header **after** the stack dump as well, or keep the dump short. A
   photograph then gives ESR/ELR/FAR, and ELR names the faulting instruction in `loader.efi` (compare with its map).
2. `xnuloader/loader.efi` here was built with `make loader-open`, i.e. `mkidentity.sh --placeholder` -- an identity with no Apple
   data. It is meant to be enough for the open kernel, but if the dump points at the identity table, a real `identity.h` (from an
   IPSW of the user's own) is what the loader needs.
3. Everything the loader does after that -- the Mach-O load, the device tree it builds, the jump -- is the same code that runs on
   the reference phone, so the fault is most likely in what this phone's firmware hands it: the framebuffer, the memory map, the
   payload layout.

### The loader's crash: a QEMU probe on real hardware

The exception header, made to print again after the stack dump, gave:

    ESR 0x96000010   ELR 0x000000009CF027C4   FAR 0x0000000009020008

`ESR 0x96000010` is EC 0x25 (data abort, same EL) with DFSC 0x10, a **synchronous external abort** -- the address is mapped, the
bus refused it. Disassembling `loader.efi` at the ELR's offset (the image was relocated to 0x9CF00000, so offset 0x27C4) shows

    a10027a0:  mov  w22, #8
    a10027a4:  movk w22, #2306, lsl #16     ; x22 = 0x09020008
    a10027c4:  strh w8, [x22]

and `loader.c` has `#define FW_CFG_BASE 0x09020000ULL` for QEMU's fw_cfg: the loader was probing **QEMU's** framebuffer
interface on a phone.

Why: the loader decides where it is by the framebuffer address the firmware hands it --

    PLAT = &platform_qemu_virt;
    if (SCREEN.base == 0xE1000000ULL) { PLAT = &platform_redwood; } else { ramfb_phone_screen(); }

`0xE1000000` is the reference phone's display reservation; **this phone's is `0xEA600000`** (its own `uefiplat.cfg` says so, and the
SEC clears that region). So the loader took the QEMU path. The check now accepts both:

    if (SCREEN.base == 0xE1000000ULL || SCREEN.base == 0xEA600000ULL) { PLAT = &platform_redwood; }

The platform struct fits this phone as it is: GIC 0x17A00000 / 0x17A60000 (SM8350's), 8 cores numbered in affinity field 1, the
first four small.

A cleaner fix for upstream: the loader should say which platform it assumes as a boot argument, or identify the phone by something
better than one framebuffer address -- the address is a per-device accident.

### Where the night ended

The last run ended with a reboot, and the frame extraction could not read the loader's `platform ...` line: it comes after BDS's
lines and the phone resets within a few seconds, so the text is either overwritten or too small to photograph at that angle.

The next run should make that line unmissable: a `stall (10 s)` (or a small spin) right after

    print("platform %s\n", PLAT->name);

so the screen holds long enough to be photographed. That single line says whether the widened framebuffer check took effect, and
the lines after it (`payload: ...`, the kernel load, `kernel.ver=`) say how far the loader got before the reboot.

If the platform line says `redwood`, the reboot is almost certainly the kernel itself starting and failing at once -- which is a
different, much more ordinary problem than everything above it, and the kernel has its own ways of reporting (the panic log in
`logdump`, `tools/frames.py`, the serial console).

### The loader runs, and is silent -- how to hear it

Photographs of the last runs show the same ending:

    PROBE: payload base=f0000000 magic=50554e58 size=E48730
    ConvertPages: Incompatible memory types, the pages to allocate have been allocated
    Loading driver at 0x0009CF0000 EntryPoint=0x0009CF02148

DXE loads and starts `loader.efi` at 0x9CF00000. The loader then produces **nothing** on screen, and it is not because it is not
running: its `put_char` writes to two places only --

    if (log_len < sizeof(log_buf) - 1) { log_buf[log_len++] = c; }
    if (ST->con_out != NULL && !screen_quiet) { ST->con_out->output_string(...); }

-- the in-memory log, and `ConOut`. On this phone `ConOut` reports `Unable to set console mode - Unsupported`, so every line the
loader prints is invisible. `flush_log ()` would put the log buffer on the `logdump` partition, but it finds the partition through
the **UEFI's** Block I/O, and `UFSDxe` is one of the drivers removed to get past the RPMB assert. Hence: no console, and no log.

Three ways out, in the order worth trying:

1. **Draw to `SCREEN` directly.** The loader already has the framebuffer (`SCREEN.base`, width, height, stride) and only lacks a
   font; an 8x8 table is a few hundred bytes and turns `put_char` into something that cannot be silenced. Best of the three: it
   makes every future run readable.
2. **Put `UFSDxe` back** -- which means making RPMB work, which means the TEE path (`ScmDxeLA`/`TzDxeLA`), which is a real piece of
   porting, not a workaround.
3. **Fix `ConOut`** so `output_string` lands on the panel. Unknown why it is broken; the GOP does exist (DisplayDxe, 640x480).

Also worth a look, from the same photograph: `ConvertPages: Incompatible memory types, the pages to allocate have been allocated`
-- DXE complaining about a memory type while loading the image. Harmless so far, but it is the kind of thing that turns into a
fault later, and the memory map is ours to fix.

## Day two: the kernel is started

### The loader speaks

`put_char` writes to the in-memory log and to `ConOut`, and `ConOut` is dead on this phone, so the loader was inaudible.
It now also draws on the panel: an 8x8 font (public domain, `font8x8_basic.h` from dhepper/font8x8), 2x scale, straight into
`0xEA600000` at 1440x3200 -- the region the SEC's own console writes to and the screen really scans out. Every line the loader
prints is now visible, which turned the rest of the day into ordinary work:

    == XNULOADER v3 ==
    hello, hakios-kernel!
    kernel.ver=2.3.4-hakios-darwin22.5-sm8350-g63fc2b46-dirty
    CurrentEL=1 MIDR=412fd050 MMFR0=101122 CNTFRQ=19200000 image=9d084000
    platform redwood

### Four things that had to be fixed to get from there to the jump

1. **`platform qemu-virt` -> `redwood`.** The loader picks its board by comparing the framebuffer address with the reference
   phone's `0xE1000000`; this phone's is `0xEA600000`, so it fell into the QEMU branch and wrote to QEMU's fw_cfg at
   `0x09020008` -- a synchronous external abort. It is now `platform_redwood` unconditionally.
2. **The panel console must not depend on the GOP.** With `DisplayDxe` out there is no GOP, and the console is set from the fixed
   panel address instead.
3. **A watchdog that fires looks exactly like a crash.** `wdt_arm ()` is disarmed while porting.
4. **Never reset inside a `fastboot boot` session.** `reboot ()` used to call `ResetSystem (EfiResetCold)`, and on this phone that
   is one of the ways into EDL; it now prints `== halted; power-cycle the phone ==` and spins. Step markers with 6 s pauses
   between them say exactly how far a run got.

### The last two errors, in the loader

    largest free block 0 size 0
    phys window 0 size 0, claim status 800000000000000e

`choose_window ()` only accepts `EfiConventionalMemory`, and the memory map had exactly one such region -- the 60 MB `DXE Heap`,
which DXE has consumed long before the loader runs. The 256 MB region at `0xA0000000` is what the phone's own `uefiplat.cfg`
calls `Kernel`; it was declared `Reserv`. Declaring it `Conv` gave the loader its window, and the run went on to

    [payload] loader.efi size e400
    [payload] kernel ... / kernel.ver ...
    payload entry 0xf0000000, cmdline size 217
    kernel entry ffffff8007f1e4a8
    kernel va ... entry ...
    device tree ... len ..., boot_args ..., top ...
    cmdline: cpus=8 bootcpu=7 ufs=2
    jumping to ffffff8007f1e4a8

and the phone reset a moment later: **the loader hands the machine to XNU.** Everything the loader does is now done.

### What is next

The kernel runs and says nothing, because on this platform its early console is a serial port that this build has no driver
for. The porting work from here is kernel-side and ordinary: a console (`uart` or the framebuffer), then the platform drivers in
the order HakiOS already has them -- CPU/memory first, then interrupts and timers, then UFS and the rest.

### After the jump: the kernel does not say anything, and does not paint either

The loader finishes: `jumping to a541e4a8`, with the kernel at `a5417000`, boot args built, device tree built, cmdline
`debug=0x0 rd=md0 hakios_kver=... -v cpus=8 bootcpu=7 ufs=2`. Then nothing. `-v` in the cmdline makes the loader set
`ba->video.v_display = 0` (verbose), which should let the kernel print on the framebuffer, but no line appears.

To tell "the kernel never ran" from "the kernel ran and died", the kernel's own `LOADER_CHECKPOINT` macro
(`osfmk/arm64/start.s`) was made to paint the phone's panel: turn the data cache off (`SCTLR_EL1.C`), fill 1 MiB at
`0xEA600000` with a green that no pixel-format mistake can hide, restore `SCTLR_EL1`. Two runs, both with the entry
disassembled and confirmed in the binary:

| Run | Result |
|---|---|
| `bootcpu=7` (the loader starts core 7 through PSCI and waits) | no green |
| no `bootcpu` (the loader jumps on the core it is on, no PSCI) | no green |

So either the branch to the kernel never executes, or a write to `0xEA600000` with the MMU off does not reach the panel.

### The experiment that separates those two

A stub in the loader: allocate a page, write the same "paint green and spin" in ARM64, and reach it through the same
`jump_to_kernel ()` path. Green means the jump mechanism is sound and the kernel entry is what fails; no green means the
jump itself (MMU-off transition, cache, exception vectors) has to be fixed first. It needs nothing from the kernel, which
is what makes it worth doing before anything else.

### The jump itself: narrowed to `jump_to_kernel ()`

Two runs settled it, both using a stub in the loader -- a naked function that fills 1 MiB at `0xEA600000` with
`0x070000FF` and spins:

| Run | What it does | Screen |
|---|---|---|
| `stub=2` | calls the stub **with the MMU still on** | **the top turns blue** (0x07 alpha, 0xFF blue: the panel is ARGB8888) |
| `stub=1` | reaches the same stub through `jump_to_kernel ()` | nothing |

So the stub's code is right, the framebuffer write reaches the panel, and the panel's pixel format is ARGB. What does not
work is the handoff: `jump_to_kernel ()` turns the MMU and the caches off (`SCTLR_EL1` M/C/I), invalidates the I-cache and
`br`s to the entry. That is the only difference between the two runs, so the fault is in those dozen instructions on this
phone -- not in the kernel, and not in the display.

Next, in the order that separates the remaining candidates:

1. **Same jump, MMU left on** (a plain `br`, nothing else). If that paints, the `br` and the address are fine and the MMU-off
   transition is what fails.
2. **Whether UEFI's virtual addresses are physical on this platform.** EDK2 here may map `0xA1000000` (where the loader runs)
   to some other physical page; with the MMU off, a stub at its linked address would then execute whatever is really at that
   physical address. Allocating a page, copying the stub there and jumping to the *physical* address answers this. The kernel
   is jumped to at `a541e4a8`, which the loader computes from the claimed window, so it is a physical address already.
3. If the MMU-off transition is the problem, look at what the firmware leaves in `SCTLR_EL1` and at the boot-args handoff. The
   reference phone works with the same code, so the difference is in what this phone's firmware (or the hypervisor below it)
   requires.


### stub3 result: the MMU-on branch reaches the stub

2026-11-09, physical mars DEVICE_SERIAL, `fastboot boot xnu-mars-stub3.img`:

- The payload command line was verified as `stub=3`.
- The UEFI, kernel and ramdisk bytes matched stub2; the loader rebuild was not byte-identical.
- The top of the panel turned blue, so the direct `br` and framebuffer address work while the MMU remains enabled.
- This narrows the next test to the MMU-off handoff, but does not prove that MMU shutdown alone is the only cause.
- The original stub1 did not flush the stub code page before caches were disabled. `stub=4` now repeats stub1 with that one cache-coherency step added.


### stub4: refreshing the stub page did not fix the MMU-off jump

2026-11-09, physical mars DEVICE_SERIAL:

- `stub=4` is stub1 plus an explicit clean+invalidate of the stub code page.
- The path stayed non-blue, then the phone reset.
- Therefore a dirty stub code line is not sufficient to explain the failure.
- Next change is the documented DarwinBoot handoff order: `IC IALLU` before MMU/cache shutdown, followed by `TLBI VMALLE1`, barriers, then the branch.


### handoff1/handoff4: ordering alone did not fix

2026-11-09, physical mars DEVICE_SERIAL:

- `handoff1` changed the handoff to DarwinBoot order (`IC IALLU` before shutdown, then `TLBI VMALLE1`) but still stayed non-blue and reset.
- `handoff4` used the identical loader and additionally flushed the stub code page before the jump; it also stayed non-blue and reset.
- The next unresolved variable is address translation: jump to a newly allocated executable page, first with the MMU on (`stub=5`) and then with the MMU/caches off (`stub=6`).


### stub5: a copied executable page works with the MMU on

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-phys5.img`:

- Loader log: `STUB TEST 5: br to a freshly allocated physical page, MMU on`.
- `STUB PAGE: copied 24 bytes to pa 9d94b000 (mmu now maps it 1:1 or not)`.
- The top of the panel turned blue and remained blue.
- Therefore the 24-byte stub was copied correctly, the allocated page is executable, and the returned page address is directly usable while the current UEFI mapping is enabled.
- `stub=6` now uses the same page installation and changes only the handoff to MMU/caches off.


### stub6: the same physical page fails after MMU shutdown

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-phys6.img`:

- The loader printed `STUB TEST 6: jump to a fresh physical page with MMU/caches off`.
- It also printed `STUB PAGE: copied 24 bytes to pa 9ab94000`.
- No blue appeared; the previous panel text remained until reset.
- Combined with stub5, this rules out page allocation, code copying and a wrong physical target. The failure occurs while changing `SCTLR_EL1` or immediately after it.
- Next: isolate C, I and M individually (`stub=7..10`).


### stub7: data-cache shutdown alone works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr7.img`:

- MMU remained enabled; only `SCTLR_EL1.C` was cleared.
- `STUB PAGE: copied 24 bytes to pa 9ab94000`.
- The top of the panel turned blue and remained blue.
- Therefore `C=0` itself does not break execution or framebuffer writes. The remaining candidates are instruction-cache shutdown and, most importantly, MMU shutdown.


### stub8: instruction-cache shutdown alone works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr8.img`:

- MMU remained enabled; only `SCTLR_EL1.I` was cleared.
- The same 24-byte page copy was used.
- The top of the panel turned blue and remained blue.
- Therefore neither C=0 nor I=0 by itself breaks the branch. The next test clears only M.


### stub9: MMU shutdown alone works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr9.img`:

- Boot CPU context: `CurrentEL=1 MIDR=412fd050 MMFR0=101122 CNTFRQ=19200000`.
- The same 24-byte stub was copied to physical page `0x9ab94000`.
- Only `SCTLR_EL1.M` was cleared; C and I remained enabled.
- The top of the panel turned blue.
- Therefore disabling translation is permitted by this EL1/hypervisor environment, and the physical page is reachable with M=0 alone.
- The remaining high-confidence candidate is the combined M+C transition used by the normal handoff.


### stub10: M+C together also works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr10.img`:

- The same physical page and branch path were used.
- Both `SCTLR_EL1.M` and `C` were cleared; I was left enabled.
- The top of the panel turned blue.
- So the normal failure requires interaction between instruction-cache shutdown and one or both of M/C.
- `stub=11` tests M+I and `stub=12` tests C+I.


### stub11: M+I works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr11.img`:

- Same physical-page copy and branch path.
- `SCTLR_EL1.M=0`, `I=0`, C left enabled.
- The top of the panel turned blue.
- Therefore MMU shutdown together with instruction-cache shutdown is valid.


### stub12: C+I works; only the triple fails

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr12.img`:

- `SCTLR_EL1.C=0`, `I=0`, M left enabled.
- The same physical page turned the top blue.
- Together with stub7-stub11, every single bit and every pair works. Only clearing M+C+I in one `MSR SCTLR_EL1` fails.
- Next: stage the same three changes over three SCTLR writes with ISBs, in several orders.


### stub13: staging M, C and I fixes the handoff

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr13.img`:

- The same physical page was used.
- Instead of one MSR clearing M+C+I, three MSR operations cleared M, then C, then I, each followed by ISB.
- The top of the panel turned blue.
- Root cause: this SM8350/QHEE environment does not tolerate the atomic M+C+I transition, although every individual bit and every pair works.
- The real `jump_to_kernel()` is being changed to the staged transition.


### fixed1: staged SCTLR but full helper still failed

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-fixed1.img`:

- The real jump helper used staged M/C/I transitions but still reset without blue.
- `stub13` differs from it by also omitting the stack flush, `IC IALLU`, and `TLBI VMALLE1`.
- `stub=16` keeps the staged transition and adds only `TLBI VMALLE1`, testing a likely Qualcomm-specific restriction.


### stub16: TLBI after the staged shutdown works

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr16.img`:

- Staged M, C and I writes were followed by `TLBI VMALLE1`, DSB and ISB.
- The same physical page turned the top blue and stayed blue.
- TLBI is valid in this state. The remaining difference from the failing real helper is its stack cache-clean loop and surrounding function context.


### stub17: the guessed stack-clean window is unsafe

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-sctlr17.img`:

- The otherwise-working staged M/C/I + TLBI path was preceded by the real helper's stack clean loop.
- No blue appeared; the phone reset immediately.
- The loop walks from roughly `SP-1 KiB` to `SP+16 KiB`, which can cross an unmapped UEFI stack boundary.
- `run_kernel()` already performs memory-map-based cache cleaning before handoff. The guessed stack window is removed from `jump_to_kernel()` and a new stub1 control is built.


### fixed2: the real jump helper now reaches the stub

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-fixed2.img`:

- The real `jump_to_kernel()` used staged M/C/I transitions and the unsafe guessed stack-clean loop was removed.
- The original `stub=1` path turned the top blue and remained blue.
- This closes the handoff investigation: the combined atomic M+C+I write was invalid here, and the stack-clean range also crossed an unmapped boundary.
- Next: boot the real XNU kernel on the current core with no `bootcpu` and no UFS initialization.


### real-kernel first run: entry bytes are correct, but the probe stays dark

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-fixed-kernel.img`:

- The repaired loader completed and printed `jumping to a541e4a8`.
- Mach-O inspection confirms that this is `__start`; its first instruction is `b start_first_cpu`.
- The loaded kernel contains the panel probe at `start_first_cpu`.
- No blue/green appeared and the loader text stayed until reboot.
- Next diagnostic: after the real kernel is fully loaded, replace only the in-memory entry page with the known 24-byte stub and jump there through the real kernel PA.


### entry_stub test invalidated by substring matching

2026-11-09:

- The first `entry_stub=1` image displayed `STUB TEST: jumping to a page of our own`, not `KERNEL PA STUB`.
- `has_word()` used substring matching, so the suffix `stub=1` in `entry_stub=1` triggered the early stub branch.
- Fixed `has_word()` to require non-alphanumeric/non-underscore boundaries.
- Stub2 through stub17 still hit their own earlier exact branches; the substring collision only affected the new diagnostic marker.


### entry physical page works with the real kernel PA

2026-11-09, physical mars DEVICE_SERIAL, corrected `entry_stub=1`:

- The loader printed `kernel entry words 14000aed d503201f d503201f d503201f at pa a541e4a8`.
- The first word is the exact `__start` branch to `start_first_cpu`.
- It then printed `KERNEL PA STUB: replaced 24 entry bytes at a541e4a8`.
- The panel top turned blue and stayed blue.
- Therefore the real kernel physical entry address, page, cache flush and handoff all work.
- Next: patch `__start`'s branch target (`a542105c`) instead, so the kernel's own first branch reaches the stub.


### kernel probe was rewriting the forbidden all-off SCTLR state

2026-11-09:

- `entry_stub=1` and `entry_stub=2` both turned blue, including a stub placed at `a541e4a8` and at the branch target `a542105c`.
- Therefore the physical kernel pages, `__start` branch and MMU-off handoff work.
- The real kernel dies in `LOADER_CHECKPOINT`: the loader already leaves M/C/I off, and the probe writes the same all-off SCTLR state again before painting.
- Fix: skip the SCTLR write when C is already off; when C is on, switch only C and restore only if changed. Also use a clearly green pixel and DSB before restoring.


### holdpre stopped before its post-flush marker

2026-11-09, physical mars DEVICE_SERIAL:

- The real kernel path printed its pre-flush entry/follow words and `jumping to a541e4a8`.
- Neither `POSTFLUSH entry` nor `POSTFLUSH follow` appeared.
- The real path still contained a second guessed stack-clean window in `run_kernel`: `SP-8 KiB .. SP+8 KiB`.
- Removed it; the memory-map pass already cleans loader ranges, followed by the claimed window flush.


### kernel entry probe finally reached and held green

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-holdpre2.img`:

- After removing the second unsafe stack-clean window, the kernel turned the top green and kept it in a WFE loop.
- Post-flush diagnostics showed:
  - entry `a541e4a8`: `14000aed d503201f d503201f d503201f`
  - branch target `a542105c`: real `start_first_cpu` probe instructions
- This proves XNU reached `start_first_cpu`.
- The diagnostic WFE hold is now removed for the next real boot.


### MMU-on XNU console reached BSD initialization

2026-11-09, physical mars DEVICE_SERIAL:

- After fixing the handoff and removing post-MMU checkpoint writes to the
  not-yet-mapped framebuffer, XNU enabled the MMU and initialized its native
  video console.
- Photographs show KernelCopyright, all eight `GenericARMcpu` registrations,
  BSD bootstrap, `bsd_init`, `kern_subsalloc`, buffer headers and the start of
  `pshm_cache_init`.
- This is the first confirmed execution after MMU enable on mars, not merely
  loader or stub execution.
- The native console text is too small to photograph at 1x, so verbose
  `boot_args.Video.v_depth` now requests 2x scale for the next diagnostic image.


### Mars reaches BSD root and execs launchd

2026-11-09, physical mars DEVICE_SERIAL, `xnu-mars-readable4.img`:

- The 4x native framebuffer console made the complete log readable.
- XNU completed CPU registration, MAC/kauth, BSD buffer and pshm initialization,
  machine and socket initialization, and all required kernel-thread scheduling
  checks.
- The kernel published `MiniIOFramebuffer` for the 1440x1600 verbose viewport,
  mounted `/dev/md0` as the BSD root, and completed `bsd_init`.
- `load_init_program` executed `/sbin/launchd` from the payload ramdisk.
- The test launchd (`userland/hello`) then exited with signal 6 before printing.
  The loader recovered the kernel log and printed `END OF LOG` / halted.
- This confirms the complete mars chain from BootShim through MMU-on XNU to
  process 1. Remaining work is userland execution/debugging, not kernel entry.

Key implementation fixes accumulated today:

- stage SCTLR M/C/I transitions in separate writes rather than an all-off/all-on
  atomic transition;
- do not flush a guessed window beyond the UEFI stack;
- avoid post-MMU writes to the framebuffer until XNU has mapped it;
- use conditional SCTLR writes in the kernel checkpoint probe;
- use exact token matching rather than substring matching for test boot args;
- use 4x scale and a 1440x1600 verbose viewport for readable, faster diagnostics.


### PID 1 exit was the test program ending by design

2026-11-09:

- A minimal PID 1 that opens `/dev/console`, writes two markers and spins
  printed both:
  - `RAW PID1: entered`
  - `RAW PID1: console open OK`
- The kernel remained alive, brought all eight CPUs online, initialized the
  60 Hz MiniIOFramebuffer path and continued periodic memory reporting.
- Re-reading `userland/src/hello.c` showed its `hello_wait=N` behavior: with
  no `hello_wait` argument the test intentionally reaches `exit(0)`. XNU kills
  PID 1 with signal 6 when process 1 exits, producing the previous END OF LOG.
- This is expected test behavior, not a launchd crash.
- Next image uses `hello_wait=60`, which keeps PID 1 alive and reports the
  device/thermal sysctls every five seconds.


### Minimal PID 1 confirms the complete mars boot chain

2026-11-10, physical mars DEVICE_SERIAL, `xnu-mars-rawsysctl.img`:

- With one CPU, the native XNU framebuffer console booted to PID 1.
- The minimal PID 1 opened `/dev/console`, printed `RAW SYSCTL: entered`, and
  called `sysctlbyname("kern.bootargs")` successfully.
- It printed `RAW SYSCTL: kern.bootargs OK` followed by the full command line,
  including `cpus=1 hello_wait=20`.
- The process then spun forever; XNU continued periodic memory reporting and
  did not panic.
- Therefore the complete chain works through user mode on mars:
  BootShim, Mu UEFI, Xnuloader, MMU-on XNU, BSD bootstrap, framebuffer device,
  RAM-disk root, PID 1, open/write/sysctl system calls.
- The previous `hello` panic is confined to that test program's own wait/exit
  logic, not to PID 1 execution or the kernel.


### Hello PID 1 stays alive and exposes the full userland diagnostics

2026-11-10, physical mars DEVICE_SERIAL, `xnu-mars-hold.img` built with
`-v cpus=1 hello_wait=20`:

- `hello.c` no longer calls `SYS_exit`. After its validation sequence it
  prints `PID 1: validation complete; holding forever.` and executes `WFE`
  in an infinite loop.
- The panel showed `Hello from user space on Darwin!`, `I am process 1`,
  the complete `kernel.ver` value, and the SoC/thermal diagnostics.
- The console then reported one processor running and continued printing
  periodic kernel memory accounting. No `pid 1 exited` message and no panic
  appeared.
- The host saw neither Android ADB nor Fastboot for more than 60 seconds after
  `fastboot boot`, independently confirming that PID 1 did not terminate and
  reset the device.
- This qualifies the complete mars path through a persistent userspace
  process: BootShim, Mu UEFI, Xnuloader, XNU MMU, framebuffer console, md0
  ramdisk root, process creation, open/write/sysctl calls, and a non-exiting
  PID 1.
- The next experiment is `xnu-mars-8cpu-ufs2.img`. Its loader has staged
  M/C/I writes in `other_cpu_entry`; disassembly confirms three separate
  `SCTLR_EL1` writes with `ISB` between them, followed by `TLBI VMALLE1`.


### SMP works from CPU 7; seven processors is the intended kernel count

2026-11-10, physical mars DEVICE_SERIAL, `xnu-mars-8cpu-ufs2.img` with
`-v cpus=8 bootcpu=7 ufs=2 hello_wait=20`:

- The staged `other_cpu_entry` path reached the kernel on CPU 7 and started
  the other cores through PSCI.
- The panel showed CPU registration, the slower-core scheduler pairing, the
  delayed small-core startup, and `7 processors running`.
- Seven is correct for this boot arrangement, not a missing physical core:
  CPU 0 remains in the loader monitoring the session, while the XNU kernel
  owns CPUs 1 through 7.
- PID 1 still reached `validation complete; holding forever.` across multiple
  scheduling reports. The host saw no ADB or Fastboot return for more than
  60 seconds.
- The large white area in the photograph is an earlier diagnostic colour
  band, not framebuffer corruption.
- The next image adds read-only PID 1 probes for `/dev/ufs_boot_a` and
  `/dev/ufs_super`. A successful boot_a read should begin with the eight
  bytes `41 4e 44 52 4f 49 44 21` (`ANDROID!`).


### Diagnostic colour bands removed; UFS driver enabled

2026-11-10, physical mars DEVICE_SERIAL:

- The bring-up colour probes have served their purpose. `LOADER_CHECKPOINT`
  no longer paints the top of the panel green when it handles a checkpoint,
  and the `PANEL_MARK` macro plus every red/blue/yellow/magenta/cyan/orange/
  purple/white invocation were removed from `start.s`.
- `xnu-mars-nocolors-ufsprobe.img` booted with a clean black console and no
  diagnostic bands, while retaining SMP and a persistent PID 1.
- The first UFS probe returned `ENOENT` for both `/dev/ufs_boot_a` and
  `/dev/ufs_super`. This was a kernel configuration issue, not a storage
  read failure: `devices/mars/configs/mars.config` explicitly disabled
  `CONFIG_HAKIOS_UFS`, while `CONFIG_UFS=2` was already set.
- Enabling `CONFIG_HAKIOS_UFS=y` changes the build from 4 to 5 built-in
  drivers and removes `ufs` from the "left out" list. The next image is
  `xnu-mars-nocolors-ufs.img`; it uses the loader-backed `ufs=2` path and
  does not request the SM8350 native host-controller path (`ufs_native`).


### UFSDxe listener stubs unlock GPT and real partition I/O

2026-11-10, physical mars DEVICE_SERIAL:

- With the UFS driver built into XNU, `/dev/ufs_boot_a` still returned
  `ENOENT`. The added `kern.bootargs` probe showed no `ufs_shared_pa=`, so
  the failure was in the loader's UEFI block-service construction.
- The server UEFI lists omitted `UFSDxe` even though DiskIo and PartitionDxe
  were present; with no UFS block handles, `block_start()` had no GPT table.
- The prebuilt UFSDxe's `RPMBListenerInit` and `GPTListenerInit` both assert
  when their TEE-backed protocols are absent. For ordinary read-only Block
  I/O neither listener is required. `patch_ufsdxe_rpmb_stub.py` backs up the
  original PE and replaces both initializers with `mov x0, xzr; ret`.
- UFSDxe was added back to `APRIORI.inc` and `DXE.inc`. The rebuilt DEBUG FD
  passed validation and booted without the former reset.
- The panel then enumerated the real GPT: `xbl_a`, `xbl_b`, `xbl_config`,
  `boot`, `dtbo`, `super`, `userdata`, and others, and began hashing the
  reference partitions through UFS.
- A performance bug surfaced: `ufs=2` also ran the full `ufs=1` diagnostic
  audit, hashing `modem`, `dsp`, boot images and more. The character-by-
  character framebuffer scroll made this extremely slow and left heavy
  display trails. The normal `ufs=2` path now skips `ufs_survey()` and goes
  directly to `block_start()`; `ufs=1` retains the full survey.
- The next image is `xnu-mars-ufs-fast.img`, which should show
  `ufs_shared_pa=` in the kernel arguments, create `/dev/ufs_*`, and read
  `ANDROID!` from `/dev/ufs_boot_a`.


### UFS block service verified end to end

2026-11-10, physical mars DEVICE_SERIAL, `xnu-mars-ufs-fast.img` with
`-v cpus=8 bootcpu=7 ufs=2 hello_wait=20`:

- UFSDxe enumerated the GPT and the loader published the phone's partitions
  through the `ufs=2` block-service page.
- PID 1 successfully opened the block nodes:

  ```text
  /dev/ufs_boot_a: open=1 read=8 bytes=41 4e 44 52 4f 49 44 21
  /dev/ufs_super:  open=1 read=8 bytes=00 00 00 00 00 00 00 00
  ```

  The first eight bytes are `ANDROID!`, proving that the kernel's open/read
  path reaches the loader's UFS page and the real SSD correctly.
- The loader reported the partition devices as `/dev/ufs_NAME` and
  `/dev/rufs_NAME`, read only, backed by its 4096 KB shared buffer.
- The same run retained seven kernel processors, the slower-core scheduler
  pairing, and a persistent PID 1. It did not reset or revert to Android.
- The loader's own `logdump` probe also reported eight KB written and read
  back identically.
- Skipping `ufs_survey()` for `ufs=2` removed the multi-minute partition hash
  wall; `ufs=1` still provides the complete diagnostic survey.
- This closes the storage milestone needed to boot a real root/userland from
  the phone's flash instead of the `hello` ramdisk.


### Apple-free APFS bootstrap and the real memory-window limit

2026-11-10, physical mars DEVICE_SERIAL:

- The server has no unpacked Darwin root or IPSW. `userland/build-bootstrap.sh`
  was added to build a two-volume bootstrap from the repository's own
  prebuilt programs: `boot.apfs` contains `stage0` as `/sbin/launchd`;
  `root.apfs` contains `init`, `child`, a 300 KB pattern file and `hello`
  renamed to `hold`, which becomes a persistent PID 1 after init's checks.
- Both images are valid APFS containers (4 MiB each), built without any
  Apple file.
- The first two-disk payload stopped by design in the loader:

  ```text
  largest free block a2000000 size c000000
  resident 400000 does not fit in the memory window
  == halted; power-cycle the phone ==
  ```

- The historic resident constants assumed a much larger window
  (`0x08000000` offset plus a `0x30000000` reserve). Mars exposes only
  192 MiB. The port now uses a `0x07800000` offset and `0x01000000` reserve,
  leaving room below the resident image for the XNU Mach-O and payload
  ramdisk and more than 64 MiB after it for XNU's static mapping and
  userland.
- `xnu-mars-apfs-bootstrap2.img` is the rebuilt test. It remains a pure
  memory boot and writes no partition.


### Apple-free APFS root and persistent PID 1 work end to end

2026-11-10, physical mars DEVICE_SERIAL, `xnu-mars-apfs-hold.img`:

- The two-disk payload now loads correctly with the 192 MB memory-window
  constants. `boot.apfs` is md0 and contains `stage0`; `root.apfs` is md1
  and is mounted on `/redwood`.
- `stage0` executed `/redwood/sbin/init`. The init suite reached:

  ```text
  [ ok ] devfs is mounted on /dev
  [ ok ] /dev/zero
  [ ok ] /dev/null
  [ ok ] /dev/random
  slept 200 ms, the clock advanced 206 ms
  [ ok ] sleep and wall clock agree
  === 22 checks, 3 failed ===
  ```

- Reusing `hello` as `hold` caused a user-space signal and PID 1 exit after
  exec. A dedicated `userland/src/hold.c` now uses only console setup and a
  non-exiting loop. The cleaned build reports:

  ```text
  === /redwood/etc/rc ===
  $ exec /redwood/bin/hold
  HOLD: PID 1 is alive and staying here.
  ... the slower cores started too: 7 processors running
  ```

- The panel also listed the phone's `/dev/ufs_*` and `/dev/rufs_*` nodes,
  confirming that the APFS userspace sees the UFS block and character devices
  created earlier.
- The process remained alive with no ADB/Fastboot return. Kernel memory
  accounting continued normally, with seven XNU processors (CPU 0 remains in
  the loader).
- This establishes an Apple-free platform baseline: real APFS roots, stage0,
  init, execve, devfs, ramfs, file/memory/process checks, persistent PID 1,
  SMP and UFS all in one boot.


### Full Darwin 16.5 userland boots in QEMU

2026-11-10, server QEMU 6.2, CPU model `max`, four virtual CPUs:

- The official iPhone10,3/10,6 16.5 20F66 IPSW was downloaded from Apple,
  SHA-256 verified, unpacked with 7-Zip 23.01, and used to build the complete
  `root.apfs` and `system.apfs`.
- The initial QEMU boot stopped in mockfs because the APFS root was not in the
  root-filesystem candidate list. `apfs_vfsops` was linked, but the mars build
  left the `APFS` option out of `vfs_conf.c`. The port now registers APFS as a
  root candidate explicitly.
- A second root fault was the resident image address: Mars' 192 MB memory
  layout moved the image from `FC000000` to `FB800000`, while QEMU still
  preloaded the old address. QEMU now preloads the image at the loader's
  actual resident address.
- `launchd` initially rejected every job plist with error 122 because the
  source checkout's `0775/0664` modes were preserved. The root-image build now
  seals `/LaunchDaemons` as `0755` and its plists as `0644`.
- Final QEMU run reached the real Darwin launchd. The session spawned 78
  distinct services, including:

  ```text
  com.apple.backboardd [13] job state = running
  com.apple.SpringBoard [8] job state = running
  ```

- A framebuffer screenshot shows the Apple boot mark; processing continued
  normally through launchd/XPC, containing many expected hardware-specific
  lookup failures but no kernel panic and no launchd permission rejection.
- The QEMU screenshot is saved as `mars-springboard-qemu.png` locally and on
  the server test artifacts.


### Rebuilt UEFI FD regression isolated; 01:48 FD restores the physical boot

2026-11-10, physical mars DEVICE_SERIAL:

- The untested flash-root image (`root_apfs=ufs_darwin`) reached the console
  briefly, then reset to Android before a stable userland checkpoint.
- Persistent write probes in `stage0`/`init` were not usable: the UFS character
  device requires whole 4096-byte writes and a live `kern.hakios.var_busy`
  claim, and the probe attempt perturbed the boot it was meant to observe.
  The original `stage0` was restored; only an in-memory `flash_stop=1` hold was
  retained for A/B testing.
- The last known-good physical image,
  `devices/mars/prebuilt/images/xnu-mars-apfs-hold.img`, still held and showed
  UFS nodes, `22 checks, 3 failed`, PID 1 alive and seven processors.
- Payload comparison showed the old and current kernels differ in only 26
  bytes: the Mach-O UUID and version strings. Their executable code and symbol
  table are identical. Cross tests therefore ruled out the kernel.
- The real difference is
  `Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`.
  The verified 01:48 image contains FD SHA-256
  `5fdbe919b866b1f64059ded4842edf1891502d893c0b51b0771f1a1dac6791e3`;
  the rebuilt FD was
  `d76c5555f69022cb2e0a322d8b8d6419ab4516b6445f3ba8728a8aefd85701eb`.
  BootShim and DTB are byte-identical.
- Rebuilding the baseline with the 01:48 FD, the current loader (built from
  the real 16.5 device-tree identity) and the current kernel held beyond 30
  seconds and showed the normal console log. The next physical test is the
  same FD and loader with `root_apfs=ufs_darwin`.
- The current FD is restored after every temporary test. Do not overwrite it
  until the flash-root result identifies which post-01:48 UEFI change must be
  reapplied on top of the known-good FD.


### `root_apfs` reaches Darwin root and ends at three userland assumptions

2026-11-10, physical mars DEVICE_SERIAL, known-good UEFI FD:

- The flash-root image with `root_apfs=ufs_darwin flash_stop=1` held for 60
  seconds. The panel showed the complete UFS table, the Darwin root mounted
  read only as `System` (45,043 files, 16,547 directories, 602,112 blocks of
  4096 used), and `kern.hakios_switch_root` succeeding:

  ```text
  [ ok ] mount the Darwin volume read only
  [ ok ] the Darwin volume is the root, the RAM part of the boot on /private/preboot
  [ ok ] this image back on /redwood
  ```

- Three checks were stale assumptions from the separate-cryptex design:

  ```text
  synthetic directory /flash/redwood: File exists
  [FAIL] a synthetic /redwood on it, for this image
  0 applications waiting to be installed, 0 of them in /Applications
  the OS cryptex from /dev/ufs_darwin,c=1: Invalid argument
  the App cryptex from /dev/ufs_darwin,c=2: Invalid argument
  ```

- `apfs-tool ls` confirmed that this `system.apfs` already contains a real
  `/redwood` directory, `/Applications`, `/System/Cryptexes/OS` with the dyld
  shared-cache segments, and `/System/Cryptexes/App`. The mountable
  `c=1`/`c=2` containers are not present because this image embeds the data.
- `init` now accepts the existing `/redwood`, scans `/Applications` when the
  obsolete staged-app directory is absent, and treats the embedded cryptex
  directories as the OS and App cryptexes. The diagnostic stop remains in
  place for one confirmation run; the next image can remove `flash_stop=1`
  and try Darwin's own launchd.
- Confirmation on the physical phone passed every root-related check:

  ```text
  [ ok ] mount the Darwin volume read only
  [ ok ] /redwood is ready for this image
  [ ok ] our launchd jobs, not Darwin's
  [ ok ] applications are present in /Applications
  [ ok ] the Darwin volume is the root, the RAM part of the boot on /private/preboot
  [ ok ] the OS cryptex in the Darwin volume (/System/Cryptexes/OS)
  [ ok ] the App cryptex in the Darwin volume (/System/Cryptexes/App)
  [ ok ] this image back on /redwood
  ```

  The panel reported 173 applications already in `/Applications` and seven
  kernel processors running. `xnu-oldfd-flashroot-boot1.img` removes only the
  diagnostic stop and is the next test of Darwin's own `launchd`.


### Darwin launchd stops at the missing shared-cache graft

2026-11-10, physical mars DEVICE_SERIAL, `xnu-oldfd-flashroot-boot1.img`:

- The real Darwin `launchd` became PID 1 and reached its library load, then
  stopped because the dyld shared cache was not available:

  ```text
  shared_region: ... shared_region_start_address() failed
  Library not loaded: /usr/lib/libSystem.B.dylib
  Referenced from: /sbin/launchd.darwin
  Reason: tried ... (no such file, no dyld cache)
  ```

- The initial embedded-cryptex check was not sufficient. Darwin's boot path
  expects the OS and App cryptex directories under
  `/private/preboot/Cryptexes`, not merely under the system root.
- `init` now bind-mounts the real system directories read-only:
  `/System/Cryptexes/OS` to `/private/preboot/Cryptexes/OS` and the same for
  `App`, with `bindfs`. This preserves the boot volume's path layout without
  duplicating data.
- The loader now successfully persists its own log to `darwin` at 8 GiB
  (`log: 143360 bytes copied to darwin at 200000000`), so subsequent boot
  evidence can be read over ADB after the fallback Android boot instead of
  photographed.
- `xnu-oldfd-flashroot-boot2.img` is the next launchd test.
