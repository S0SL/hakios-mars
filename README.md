# HakiOS on Xiaomi 11 Pro (mars)

**Apple's open-source Darwin kernel (XNU) on the Xiaomi 11 Pro** (SM8350 /
`mars`, 12 GB) — a device port of [HakiOS](https://github.com/oosexgang/hakios-xnu-kernel).
A research bench, not a ROM: it boots from RAM via `fastboot boot`, and a
reboot gives the phone back to Android.

This tree is the upstream `hakios-xnu-kernel` common repository **plus** the
`devices/mars/` port, the bring-up tools, and the notes below. It runs a full
Darwin user space on the device: the home screen with GPU-accelerated rendering
(Mesa/freedreno on the Adreno 730), working touch, and a persistent run log.

---

## Where the project stands (read this first)

| Track | State |
|---|---|
| Darwin user space | ✅ **Working** — SpringBoard desktop, touch (FocalTech FTM5 `fts_dual`), GPU rendering (Mesa 25.0.7 / freedreno), stable 6 GB memory window (`--physbase 100000000`) |
| Run logs | ✅ **Working** — full log every run, 8 GiB `darwin` partition, one `dd` to extract |
| GPU polish | ✅ **−31% stutter** (64.5→40 ms/frame): shader warm-up v2 (compile spikes 322ms→3ms), sampled hash for large textures, `glTexSubImage2D` reuse, EGLImage-fail cache |
| USB fastboot channel | 🔧 **Partial** — enumeration flaky behind the closed-source Qcom `UsbfnDwc`; loader has a 30 s idle auto-run fallback (`fastboot boot` → desktop without host commands) |
| Wi-Fi / PCIe (QCA6490) | 🔧 **In progress** — `drivers/pci/hakios.pcie.c` 13-step bring-up (`pcie_step=N`); power/clocks/GPIO/parf/PHY-sequence all pass; **PHY PLL lock is the blocker** |

### The one blocker: PCIe PHY PLL

`PCS_STATUS1` (PHY +0x214) stuck at `0x48` — the QMP PHY never reports
ready, so LTSSM never starts and the QCA6490 never enumerates. Everything
before it works: GDSC power, all bus clocks, GPIO94/95/64 (PERST/CLKREQ/
WLAN_EN, TLMM at `0xf100000`), the full `msm_pcie_enable` parf sequence
(`DEVICE_TYPE=4`, `SYS_CTRL=0x365E`, DBI window), and the device tree's
75-entry PHY sequence.

Dead ends already ruled out:
- **cmd_db at 0x80860000** traps when read at pcie_init timing (readable only
  from the GPU driver's timing — `gfx.lvl` etc. work there).
- **PMIC SPMI direct writes** — all regulators go through RPMh (TCS).
- **WLAN_EN / CLKREQ / PERST** — all toggle correctly (`io 3`), PHY still stuck.

**Next steps, in order of promise:**
1. **UEFI-side PCIe shim** (like `Dwc3ShimDxe` for USB) — full PCIe init
   before the kernel runs, bypassing the timing problem entirely.
2. PHY sequence timing (insert delays in the 75 writes).
3. Confirm the 100 MHz reference clock really reaches the PHY.

---

## Build & test (on the build server)

All work happens on a remote build server; the base directory is `~/hakios/`:

```
~/hakios/
├── xnuloader/loader.c              # loader: USB command loop, log pipeline,
│                                    #   6 GB window patch, pcie_step boot-arg
├── drivers/pci/hakios.pcie.c       # THE PCIe RC driver (13 steps, pcie_step=N)
├── drivers/pci/phy_seq.inc         # 75-entry QMP PHY sequence from the DT
├── drivers/gpu/hakios.adreno.c     # GPU bring-up (22 steps, adreno=N)
├── drivers/wifi/                   # Wi-Fi stack (redwood WCN6750 base)
├── drivers/input/hakios.input.c    # calls hakios_pcie_init()
├── xnu/files/…                     # XNU overlay (cp to xnu-src/ after edits!)
├── xnu-src/xnu-8796.121.2/         # XNU tree
├── hakios-kernel                   # built kernel (make kernel)
├── userland/                       # userland (REST=1 GL=1 ./build.sh)
│   └── src/eagl.c                  # CA/GL shim: shader warm-up, hash, IOSurface
├── Mu-Silicium/                    # UEFI (Dwc3ShimDxe USB shim lives here)
├── tmp/                            # references: gcc-sm8350.c, dwc3-core.h, dipper patches
└── venv/                           # build venv
```

Kernel config: `~/.config` (active) / `devices/mars/configs/mars.config`
(template). Enable `CONFIG_HAKIOS_PCIE=y`.

```sh
# userland (must use REST=1 — see pitfalls)
cd ~/hakios/userland && REST=1 GL=1 ./build.sh

# kernel (after editing drivers/: rm the stale .o or make won't rebuild)
cd ~/hakios && LC_ALL=C make kernel -j24

# pack an image
python3 xnuloader/mkpayload.py -o p.bin loader.efi=xnuloader/loader.efi \
  kernel=hakios-kernel ramdisk=userland/root.apfs resident=userland/flashboot.apfs \
  --physbase 100000000 \
  --cmdline "-v cpus=8 bootcpu=7 ufs=2 ufs_write=1 root_apfs=ufs_darwin \
    amfi_get_out_of_my_way=1 thermal_stop=95 battery_stop=20 \
    touchscreen=1 touch_poll_us=2000 gpu=1 pcie_step=5"
venv/bin/python mkxnuimg.py -d mars --mode DEBUG -p p.bin -o out.img
```

On the device (never flash a partition — `fastboot boot` only):

```sh
fastboot boot out.img
# extract the full run log from Android afterwards:
adb shell dd if=/dev/block/by-name/darwin of=/data/local/tmp/k.bin \
  bs=4096 skip=2097152 count=4096
```

---

## Pitfalls (do not rediscover)

- **`build.sh` must run with `REST=1 GL=1`.** Without `REST=1` only 36 of
  418 launchd plists are generated and the **wallpaper goes black**.
  Normal `root.apfs` ≈ 1525 blocks / 418 plists; 1462 blocks / 36 plists = broken.
- **`xnu/files` and `drivers/` edits must be `cp`'d into `xnu-src/`** manually
  (`apply.sh` runs only on first checkout). After editing a driver, `rm` its
  `.o` or make will not rebuild it.
- **`loader.c` is ~5000 lines: `-O1` fails** with `fixup value out of range`
  (AArch64 ADR ±1 MB). Build with `-O0` (`build.sh` already does).
- **TLMM GPIO**: base **`0xf100000`** (not `0xf000000`), cfg bit 9 = output
  enable, io bit 1 = value (write **2** = high). Bare `out=1` writes are
  silently dropped by the hypervisor's TLMM emulation.
- **`cmd_db` at `0x80860000`** traps when read at pcie_init timing; readable
  only from the GPU driver's timing (`gfx.lvl` etc. work there).
- **GCC (`0x100000`) is not mapped in UEFI page tables** — a raw access faults
  (`esr 0x96000006 far 0x10f010`); clock enable must go through the loader
  (which can build page-table entries).
- **`log_len = 0` clears diagnostics** — the auto-run path used to wipe the
  shim/pre-start register reads from the log. Disabled: keep the full log.

---

## Repository layout

This tree is the upstream `hakios-xnu-kernel` (kernel port, common drivers,
loader, user space, tools, docs) plus the mars port. What is where:

```
hakios-mars/
├── README.md                     ← this file (the only porting document)
├── Makefile                      ← upstream build entry (make kernel / make defconfig)
├── VERSION, LICENSE*, NOTICE…    ← upstream metadata and licensing
│
├── devices/mars/                 ← THE Xiaomi 11 Pro device port
│   ├── configs/                  mars.config (kernel config template)
│   ├── uefi/files/               UEFI platform files (APRIORI.inc, DXE.inc, marsPkg)
│   ├── uefi/dwc3shim/            notes for the DWC3 USB shim (source is in Mu-Silicium)
│   └── device.conf, soc.args…    device description for the build system
│
├── drivers/                      ← kernel drivers (common + mars-specific)
│   ├── pci/hakios.pcie.c         ★ PCIe RC driver (QCA6490 bring-up, pcie_step=N)
│   ├── pci/phy_seq.inc           QMP PHY 75-entry sequence (from the device tree)
│   ├── pci/conf                  CONFIG_HAKIOS_PCIE registration
│   ├── gpu/hakios.adreno.c       Adreno bring-up (adreno=N, 22 steps)
│   ├── wifi/                     Wi-Fi stack (redwood base: wlfw, apple80211, sta)
│   ├── input/hakios.input.c      input + calls hakios_pcie_init() / hakios_adreno_init()
│   ├── core/hakios.stubs.c       stubs for drivers not built
│   └── …                         battery, ufs, haptic, torch, camera, mic…
│
├── xnu/                          ← XNU overlay (files copied into xnu-src/ at build)
│   ├── files/bsd/…               APFS, sysctl, kern_exit (hakios-exit tracing)
│   └── files/osfmk/…             loader_return, gic, tunables
│
├── xnuloader/                    ← the boot loader (XNUP payload)
│   ├── loader.c                  ★ USB command loop, log pipeline, 6 GB window
│   ├── mkpayload.py              builds the XNUP container
│   └── build.sh                  loader.efi (clang -O0)
│
├── userland/                     ← Darwin user space build
│   ├── src/eagl.c                ★ CA/GL shim (shader warm-up, IOSurface, hash)
│   ├── src/hakios.*.c            injected hooks (SpringBoard, WiFi, GPU…)
│   └── build.sh                  REST=1 GL=1 to build (see pitfalls)
│
├── tools/                        ← host-side tools (mkapfs, hakios-config, frames…)
├── sysimage/                     ← unpack.sh: build root.apfs from your own IPSW
├── fw-gpu/, fw-touch/            ← firmware dirs (extract from your own phone)
├── qemu/                         ← QEMU test harness
├── hakios-metal/                 ← Metal-on-Adreno (sister component)
├── socs/, configs/, ci/          ← SoC fragments, CI, config machinery
└── scripts/                      ← host helpers (remote.ps1.example, webdav_*.example)
```

Upstream documentation: [docs/](docs/index.md), the site
[hackios-web.vercel.app](https://hackios-web.vercel.app), and the sister
project [dipper-xnu](https://github.com/youzjuzi/dipper-xnu) (Mi 8 / SDM845).

## License

XNU-derived files remain under the Apple Public Source License 2.0
([LICENSE.APSL](LICENSE.APSL)); the project's own files follow [LICENSE](LICENSE).
Third-party components are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
No Apple-proprietary firmware, images or software is included — extract those
from your own device/IPSW.
