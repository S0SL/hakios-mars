# Device: Xiaomi Mi 11 Pro (mars)

A HakiOS device repository: what is true of this phone and of no other. The kernel, the loader, the drivers and the tools are
the common repository's; the `sm8350` family's facts are in `soc/`, carried with this device.

**Nothing has been run on this phone yet.** Every part is `missing` in `device.conf`; `soc.args` does not exist until
`./pull-soc.sh` reads the phone's own device tree; `uefi/` has this phone's platform (made from Mu-Silicium's `venus`) and not
the vendor's drivers, so there is nothing to build an image from yet. That is what a port looks like on day one
(docs/porting/index.md).

## The phone

| | |
|---|---|
| Model | M2102K1AC / M2102K1G |
| Codename | `mars` |
| SoC | Qualcomm **SM8350**, Snapdragon 888 ("lahaina"): 1x Cortex-X1 (core 7), 3x A78, 4x A55 |
| GPU | **Adreno 660** |
| Panel | 6.81", **1440x3200 at 120 Hz**, AMOLED |
| Storage | UFS 3.1 |
| Wi-Fi / Bluetooth | **`qcom,cnss-qca6490`** on PCIe (CNSS; the WCN6855 generation) -- read from this phone's own device tree |
| Modem | the SM8350's own, SDX60-class |
| Battery | 5000 mAh, 67 W wired |

## What the phone itself says

Read on 8 November 2026 from the phone on this machine (`adb`, root through KernelSU) and from its own device tree, which
`devices/mars/soc.args` was made from. Nothing here is assumed: each line is a value the phone reported.

| | |
|---|---|
| `ro.product.device` / `ro.soc.model` / board | `mars` / `SM8350` / `mars` |
| Android | 16 (`d8abd3250b`) |
| Bootloader | `androidboot.verifiedbootstate=orange` -- **unlocked** |
| Panel | `1440x3200`, density 560, DSC **command** mode, panel id `K2_0A_MP`, `msm_drm.dsi_display0=…mdss_dsi_k2_38_08_0a_mp_dsc_cmd` |
| Touch | **FocalTech (`fts`) on `spi@a8c000`**, IRQ GPIO 23, reset GPIO 22, `x-max 1440 y-max 3200`, 7 MHz, firmware `st_fts_k2.ftb`, under-display fingerprint supported |
| Wi-Fi / BT | `qcom,cnss-qca6490` at `0xb0000000`, its own `cnss_wlan_region` |
| Modem's memory | `modem_region@8f000000` (256 MB), `pil_ipa_fw_region@8e700000`, `pil_ipa_gsi_region@8e710000` |
| Storage | `1d84000.ufshc` |
| PMICs | `pm8350`, `pm8350c`, `pmk8350` |
| `soc.args` | 11 of the 13 values `tools/soc-args.py` reads are the reference phone's; **`soc_ipa_stream` is `0x5c0` (reference `0x480`)** and `soc_ipa_fw` is `ipa_fws` (reference `yupik_ipa_fws`) |

Two values the tool did not emit, and why: SM8350 names its reserved-memory nodes `modem_region@…` and `pil_ipa_gsi_region@…`,
while `tools/soc-args.py` matches `mpss` and `ipa_gsi` exactly (`find_named`), so `soc_mpss_mem` and `modem_ipa_fw_at` were
added to `soc.args` by hand from those two nodes. `soc_cmd_db` has no node at all in this tree; the kernel's default
(`0x80860000`) stands.

The touch controller being FocalTech is good news: `drivers/input/hakios.goodix.c` already has a FocalTech path (FTS 5.x
SPI framing, `ft3680` conventions) beside the Goodix one, so its step may be a change of bus address, pins and firmware
rather than a new driver.

The reference phone is a POCO X5 Pro 5G (`redwood`, SM7325, Adreno 642L, 1080x2400 at 120 Hz). Same vendor, same generation
of Qualcomm software, a smaller chip.

## Where this differs from the reference phone

This is the whole difficulty of the port in one table. "Change" means the code exists and its addresses are the other phone's;
"new" means the code does not exist here.

| Part | Reference (SM7325) | This phone (SM8350) | What it costs |
|---|---|---|---|
| The kernel itself (XNU patch, GICv3, PSCI, platform expert, APFS, minicrypto) | -- | -- | **nothing**: these are SoC-generic |
| Loader, configuration system, user space, tools | -- | -- | **nothing** |
| Boot firmware (UEFI) | Mu-Silicium `redwood` platform | Mu-Silicium has `venus` (Mi 11) and `vili` (11T Pro), **no `mars`** | **new platform**, copied from `venus` (uefi/README.md) -- the hardest step |
| SoC layer | `sc7280` | `sm8350` | **new**: `soc.args` from the phone's tree, then each driver's addresses |
| CPU clocks, thermal sensors, PMIC | SM7325's | SM8350's GCC, TSENS table and PM8350/PM8350C/PMK8350 | **change**: one table per driver |
| Display | UEFI lights the panel, the kernel writes UEFI's framebuffer | the same, on a 1440x3200 panel | **small**: `fbwidth=1440 fbheight=3200 fbscale=2`, and `fb_intf=` for the scan-line trick |
| GPU | Adreno 642L, a660 | Adreno **660**, also a660: the firmware is `a660_*` on both | **change** the addresses; a 660 may need a different speed bin and SP count |
| Metal (`hakios-metal`) | tables for chip id `0x06030500` | refused by name until someone ports the tables | **off by default**; OpenGL ES through Mesa is the path (see below) |
| Touch | Goodix GT9916 / FocalTech FT3680 on SPI | **unknown -- find out first** | if it is not one of those two, **a new driver** |
| Storage | UFS 3.1, SM7325 host controller | UFS 3.1, SM8350 host controller | **change**: controller and PHY addresses |
| Audio, battery | ADSP + WCD9385-class codec | ADSP + a codec of this phone's | **change**: three addresses, then the DSP's firmware |
| Wi-Fi | **WCN6750**, `hakios.wifi.c` + Linux's ath11k | **WCN6855** | **the largest single risk**: another radio, another QMI/wlfw flow. Budget for a rewrite of the Wi-Fi path, or leave it missing |
| Modem | SDX53-class, `hakios.mpss.c` | SDX60-class | **change** the IPA layout is not the same; this is the last step of the port |
| Fingerprint, Face ID, Apple's services | -- | -- | **never**: no Secure Enclave, no activation, and not a goal |

## Before anything: six things to find out on the phone

None of these needs a build; all of them decide whether the rest is worth starting.

```sh
adb shell getprop ro.boot.flash.locked            # 1 = unlocked. Without an unlock, nothing here is possible
adb shell getprop ro.product.device               # mars
adb shell dmesg | grep -i -E 'goodix|focaltech|nt36|synaptics'   # the touch controller -- decides step 3
adb shell dmesg | grep -i -E 'wcn|qca|ath11k|cnss'               # the Wi-Fi chip
adb shell 'ls /vendor/firmware | head -50'        # a660_gmu.bin, a660_sqe.fw, aw8697_haptic.bin?
adb pull /sys/firmware/fdt device-tree.dtb        # with root; ./pull-soc.sh does this too
```

Then, once, the go/no-go test that costs nothing but a reboot:

```sh
adb reboot bootloader && fastboot devices
fastboot boot <any small known-good image>        # e.g. a TWRP for mars
```

Xiaomi's bootloader accepts `fastboot boot` on many of its phones and refuses it on others. If it is refused, the project's
other road is U-Boot in `boot_a` (docs/dual-boot.md in the common tree), which writes to the phone -- a different decision,
with a different risk.

## The port, step by step

The order is the project's (docs/porting/index.md); the commands are this phone's.

**1. The SoC's addresses.**

```sh
devices/mars/pull-soc.sh                          # -> devices/mars/soc.args, from the phone's own device tree
python3 tools/soc-args.py device-tree.dtb         # the same file by hand, to see what it read (writes nothing)
```

Done when `soc.args` exists, and every value that differs from the reference's is explained (the phone's tree is the source).

**2. The first boot, with nothing of the phone's.**

```sh
make mars_defconfig && make config          # only the common kernel: no driver of this phone is built in
make kernel && make loader
make phone SECS=120
```

Done when the log shows the loader's banner, `kernel.ver=...-sm8350-...`, `hakios-kernel: N drivers built in`, and launchd,
and the phone comes back to Android by itself. The screen is still UEFI's framebuffer.

**3. The drivers, in the order of docs/porting/index.md:** `SOCINFO`, `CPUFREQ`, `THERMAL` first (they read the chip and
touch nothing else), then `BUTTONS` and the touch screen, then `UFS`, then `ADRENO`, then audio and battery, then Wi-Fi, then
the modem. Each one: turn it on in `soc/configs/sm8350.config` (the SoC's drivers) or `configs/mars.config` (the phone's),
delete the matching `# CONFIG_HAKIOS_<NAME> is not set`, build, run, and write the result in `device.conf`.

**4. Write it down.** `python3 tools/docs-gen.py` makes this phone's page from `device.conf`; `tools/hakios-device.py check
mars` must pass.

**5. Publish it.** `tools/hakios-device.py split mars ../hakios-mars`, push it, and add its block to `devices/manifest.conf`
in the common tree. The common tree ignores `devices/*` on purpose: a device is a repository of its own.

## The two things that will decide how far this goes

- **The UEFI platform.** Everything after step 2 depends on it. `venus` is the nearest neighbour that exists; if its display
  path does not take to this panel, the port stops at a black screen, and the work is in Mu-Silicium, not here.
- **The Wi-Fi radio.** The reference phone's driver speaks to a WCN6750. A WCN6855 is another part with another firmware
  interface; Linux's ath11k supports both, but the kernel side here (QMI service, WLFW, the station) is 190 KB of code written
  against one of them. Leave `wifi` missing, and the port is still worth having.

## Files here

| File | What |
|---|---|
| `device.conf` | what this phone is, and how far each part works -- every line `missing` until seen on the phone |
| `configs/mars_defconfig` | `common_defconfig` + `sm8350.config` + `mars.config`: `make mars_defconfig` |
| `configs/mars.config` | this phone's own: every phone driver left out, `CONFIG_FIRMWARE="none"` until firmware is pulled |
| `soc/` | the SM8350 layer: `soc.conf`, `configs/sm8350.config` (8 cores, core 7 the big one, and which drivers are on) |
| `metal.args` | what `tools/metal-run.sh` gives this phone: `bootcpu=7 cpus=8 fb_hz=120 fb_threads=4` |
| `pull-soc.sh` | the phone's device tree -> `soc.args` |
| `pull-firmware.sh`, `pull-firmware-root.sh` | the phone's firmware -> `fw-*/`, never committed |
| `uefi/` | this phone's Mu-Silicium platform (`marsPkg`, made from `venus`'s), and what the vendor's drivers must fill (uefi/README.md) |

## Notes

- `pull-firmware.sh` files everything under `fw-*/` at the top of the common tree. That is where `make phone` and the image
  build look for it, and where `.gitignore` expects it.
- A wrong value in a driver of another phone can take the whole run down before the log says anything. That is why every
  driver here starts switched off, and why step 2 builds a kernel with none of them.
- This port is not affiliated with Xiaomi or Qualcomm, and nothing of their firmware belongs in a repository
  (LEGAL.md in the common tree).
