# HakiOS on Xiaomi 11 Pro (mars)

**Apple's open-source Darwin kernel (XNU) on the Xiaomi 11 Pro** (SM8350 /
`mars`, 12 GB) — a device port of [HakiOS](https://github.com/oosexgang/hakios-xnu-kernel).
A research bench, not a ROM: it boots from RAM via `fastboot boot`, and a
reboot gives the phone back to Android.

This tree is the upstream `hakios-xnu-kernel` common repository **plus** the
`devices/mars/` port, porting notes and bring-up tools. It runs a full Darwin
user space on the device: the home screen with GPU-accelerated rendering
(Mesa/freedreno on the Adreno 730), working touch, and a persistent run log.

## Status

| Part | State |
|---|---|
| Kernel + 6 GB high memory window | ✅ stable (`memory 6144 MB`, no jetsam) |
| Display / SpringBoard desktop | ✅ GPU-accelerated rendering (CA compositor) |
| Touch (FocalTech FTM5, `fts_dual`) | ✅ full protocol over GPIO bitbang |
| GPU (Adreno 730, Mesa 25.0.7) | ✅ firmware + GMU + 3D + zap, on-screen |
| Run log (8 GiB `darwin` partition) | ✅ full log every run, one `dd` to extract |
| USB fastboot command channel | 🔧 partial — enumeration flaky (Qcom `UsbfnDwc` quirks, see handover) |
| Buttons / Wi-Fi / audio | ⬜ not yet |

## Getting started

```sh
# phone in fastboot mode, platform-tools on the host:
fastboot boot xnu-mars-<variant>.img
# the loader brings the kernel up by itself after 30 s (or: `fastboot oem run`)
# extract the full run log from Android afterwards:
adb shell dd if=/dev/block/by-name/darwin of=/data/local/tmp/klog.bin bs=4096 skip=2097152 count=4096
```

Build instructions are upstream's: see [docs/getting-started/](docs/getting-started/index.md)
and `devices/mars/README.md`. The device needs its own extracted UEFI
firmware (`devices/mars/uefi/files/Binaries/`, never tracked — see
`devices/mars/uefi/README.md`).

## Porting notes

The mars port's hard-won details live in [`docs/porting/`](docs/porting/):

- [`mars-handover.md`](docs/porting/mars-handover.md) — the full handover
  document: memory window (`--physbase 100000000` + page-table patch), touch
  protocol, GPU bring-up ladder, USB/DWC3 state machine, logging pipeline,
  known pitfalls
- [`mars-port-log.md`](docs/porting/mars-port-log.md) — chronological port log
- [`mars-uefi-status.md`](docs/porting/mars-uefi-status.md) — UEFI side status

Bring-up tools (`tools/mars/`) include image inspection, log-dump probes and
build patches; `scripts/*.example` are host-side helpers (remote build,
WebDAV) with placeholders instead of credentials.

## Repositories

| Repository | Contents |
|---|---|
| [hakios-xnu-kernel](https://github.com/oosexgang/hakios-xnu-kernel) | upstream: kernel port, common drivers, loader, user space, tools, docs |
| this tree | upstream + `devices/mars/` and the mars porting notes |
| [dipper-xnu](https://github.com/youzjuzi/dipper-xnu) | sister project (Mi 8 / SDM845), useful references |

## License

XNU-derived files remain under the Apple Public Source License 2.0
([LICENSE.APSL](LICENSE.APSL)); the project's own files follow [LICENSE](LICENSE).
Third-party components are listed in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
No Apple-proprietary firmware, images or software is included — extract those
from your own device/IPSW.
