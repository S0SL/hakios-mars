# HakiOS on Xiaomi 11 Pro (mars)

**在小米 11 Pro（mars，SM8350，12GB）上运行苹果开源的 Darwin 内核（XNU）**——
[HakiOS](https://github.com/oosexgang/hakios-xnu-kernel) 的设备移植。
研究台架而非 ROM：通过 `fastboot boot` 从内存启动，重启即可回到安卓。

本仓库是上游 `hakios-xnu-kernel` 公共仓库 **加上** `devices/mars/` 移植、
配套工具与下文笔记。设备上已运行完整 Darwin 用户态：GPU 加速渲染的主屏幕
（Adreno 730 上的 Mesa/freedreno）、可用的触摸、持久化运行日志。

---

## 项目现状（先读这里）

| 方向 | 状态 |
|---|---|
| Darwin 用户态 | ✅ **可用** — SpringBoard 桌面、触摸（FocalTech FTM5 `fts_dual`）、GPU 渲染（Mesa 25.0.7 / freedreno）、稳定 6GB 内存窗（`--physbase 100000000`） |
| 运行日志 | ✅ **可用** — 每次运行全量日志，8GiB `darwin` 分区，一条 `dd` 提取 |
| GPU 打磨 | ✅ **卡顿 −31%**（64.5→40ms/帧）：shader 预热 v2（编译尖峰 322ms→3ms）、大纹理采样 hash、`glTexSubImage2D` 复用、EGLImage 失败缓存 |
| USB fastboot 通道 | ❌ **始终未打通** — 枚举偶尔闪现（`fastboot devices` 短暂出现过 `???????????? fastboot`）但从未能收发命令；根因是闭源 Qcom `UsbFnDwc` 的 `SetEPConfigCmd 0x80000009`（端点配置失败）——`GEVNTADR` 寄存器写不进（疑似 TrustZone 锁定 / Qcom wrapper 旁路），EP0 从未配置成功。loader 有 30 秒空闲自动起内核兜底（`fastboot boot` 后无需主机命令即可进桌面） |
| Wi-Fi / PCIe（QCA6490） | 🔧 **进行中** — `drivers/pci/hakios.pcie.c` 13 步 bring-up（`pcie_step=N`）；电源/时钟/GPIO/parf/PHY 序列全部通过；**卡在 PHY PLL 锁定** |

### 唯一卡点：PCIe PHY PLL

`PCS_STATUS1`（PHY +0x214）停在 `0x48`——QMP PHY 永不报 ready，
LTSSM 无法启动，QCA6490 无法枚举。它之前的全部环节都已打通：
GDSC 电源、全部总线时钟、GPIO94/95/64（PERST/CLKREQ/WLAN_EN，
TLMM 基址 `0xf100000`）、完整的 `msm_pcie_enable` parf 序列
（`DEVICE_TYPE=4`、`SYS_CTRL=0x365E`、DBI 窗口）、设备树的 75 项 PHY 序列。

已排除的死路：
- **0x80860000 的 cmd_db**：在 pcie_init 时机读取即 trap 崩溃
  （只有 GPU 驱动时机可读——`gfx.lvl` 等在那里工作）。
- **PMIC SPMI 直写**：所有稳压器走 RPMh（TCS）。
- **WLAN_EN / CLKREQ / PERST**：都能正确翻转（`io 3`），PHY 仍卡住。

**下一步（按可行性排序）：**
1. **UEFI 侧 PCIe shim**（仿照 USB 的 `Dwc3ShimDxe`）——在内核运行前完成
   PCIe 完整初始化，绕开时机问题。
2. PHY 序列时序（75 次写入中插入延时）。
3. 确认 100MHz 参考时钟真的到达 PHY。

---

## 构建与测试（在构建服务器上）

全部工作在远程构建服务器上进行，基础目录是 `~/hakios/`：

```
~/hakios/
├── xnuloader/loader.c              # loader：USB 命令循环、日志管线、
│                                    #   6GB 内存窗补丁、pcie_step 启动参数
├── drivers/pci/hakios.pcie.c       # ★ PCIe RC 驱动（13 步，pcie_step=N）
├── drivers/pci/phy_seq.inc         # 设备树的 75 项 QMP PHY 序列
├── drivers/gpu/hakios.adreno.c     # GPU bring-up（22 步，adreno=N）
├── drivers/wifi/                   # Wi-Fi 协议栈（redwood WCN6750 基础）
├── drivers/input/hakios.input.c    # 调用 hakios_pcie_init()
├── xnu/files/…                     # XNU 覆盖层（编辑后需手动 cp 到 xnu-src/！）
├── xnu-src/xnu-8796.121.2/         # XNU 源码树
├── hakios-kernel                   # 已构建的内核（make kernel）
├── userland/                       # 用户态（REST=1 GL=1 ./build.sh）
│   └── src/eagl.c                  # ★ CA/GL 垫片：shader 预热、hash、IOSurface
├── Mu-Silicium/                    # UEFI（Dwc3ShimDxe USB shim 在这里）
├── tmp/                            # 参考：gcc-sm8350.c、dwc3-core.h、dipper 补丁
└── venv/                           # 构建虚拟环境
```

内核配置：`~/.config`（生效）/ `devices/mars/configs/mars.config`（模板）。
启用 `CONFIG_HAKIOS_PCIE=y`。

```sh
# 用户态（必须带 REST=1——见踩坑）
cd ~/hakios/userland && REST=1 GL=1 ./build.sh

# 内核（编辑 drivers/ 后：rm 掉旧 .o，否则 make 不会重编）
cd ~/hakios && LC_ALL=C make kernel -j24

# 打包镜像
python3 xnuloader/mkpayload.py -o p.bin loader.efi=xnuloader/loader.efi \
  kernel=hakios-kernel ramdisk=userland/root.apfs resident=userland/flashboot.apfs \
  --physbase 100000000 \
  --cmdline "-v cpus=8 bootcpu=7 ufs=2 ufs_write=1 root_apfs=ufs_darwin \
    amfi_get_out_of_my_way=1 thermal_stop=95 battery_stop=20 \
    touchscreen=1 touch_poll_us=2000 gpu=1 pcie_step=5"
venv/bin/python mkxnuimg.py -d mars --mode DEBUG -p p.bin -o out.img
```

设备上（永远不要刷分区——只用 `fastboot boot`）：

```sh
fastboot boot out.img
# 之后从安卓提取完整运行日志：
adb shell dd if=/dev/block/by-name/darwin of=/data/local/tmp/k.bin \
  bs=4096 skip=2097152 count=4096
```

---

## 踩坑清单（不要重踩）

- **`build.sh` 必须带 `REST=1 GL=1`。** 不带 `REST=1` 只生成 418 个
  launchd plist 中的 36 个，**壁纸会变黑**。
  正常 `root.apfs` ≈ 1525 块 / 418 plist；1462 块 / 36 plist = 坏构建。
- **`xnu/files` 和 `drivers/` 的编辑必须手动 `cp` 进 `xnu-src/`**
  （`apply.sh` 只在首次检出时运行）。改完驱动要 `rm` 掉它的 `.o`，
  否则 make 不会重编。
- **`loader.c` 约 5000 行：`-O1` 编译失败**（`fixup value out of range`，
  AArch64 ADR ±1MB）。用 `-O0` 构建（`build.sh` 已经是）。
- **TLMM GPIO**：基址 **`0xf100000`**（不是 `0xf000000`），cfg 的 bit 9 =
  输出使能，io 的 bit 1 = 值（写 **2** = 高电平）。裸写 `out=1` 会被
  hypervisor 的 TLMM 模拟层静默丢弃。
- **0x80860000 的 cmd_db**：在 pcie_init 时机读取即 trap 崩溃；
  只有 GPU 驱动时机可读（`gfx.lvl` 等）。
- **GCC（`0x100000`）在 UEFI 页表里没有映射**——裸读会挂
  （`esr 0x96000006 far 0x10f010`）；时钟使能必须走 loader
  （它能建页表项）。
- **`log_len = 0` 会清掉诊断**——自动起内核路径曾清掉 shim/pre-start
  的寄存器读数。已禁用：保留全量日志。

---

## 仓库结构

本树是上游 `hakios-xnu-kernel`（内核移植、公共驱动、loader、用户态、
工具、文档）加上 mars 移植。各处是什么：

```
hakios-mars/
├── README.md                     ← 本文档（唯一的移植文档）
├── Makefile                      ← 上游构建入口（make kernel / make defconfig）
├── VERSION, LICENSE*, NOTICE…    ← 上游元数据与许可
│
├── devices/mars/                 ← 小米 11 Pro 设备移植本体
│   ├── configs/                  mars.config（内核配置模板）
│   ├── uefi/files/               UEFI 平台文件（APRIORI.inc、DXE.inc、marsPkg）
│   ├── uefi/dwc3shim/            DWC3 USB shim 说明（源码在 Mu-Silicium）
│   └── device.conf, soc.args…    构建系统的设备描述
│
├── drivers/                      ← 内核驱动（公共 + mars 专用）
│   ├── pci/hakios.pcie.c         ★ PCIe RC 驱动（QCA6490 bring-up，pcie_step=N）
│   ├── pci/phy_seq.inc           QMP PHY 75 项序列（来自设备树）
│   ├── pci/conf                  CONFIG_HAKIOS_PCIE 注册
│   ├── gpu/hakios.adreno.c       Adreno bring-up（adreno=N，22 步）
│   ├── wifi/                     Wi-Fi 协议栈（redwood 基础：wlfw、apple80211、sta）
│   ├── input/hakios.input.c      输入 + 调用 hakios_pcie_init() / hakios_adreno_init()
│   ├── core/hakios.stubs.c       未构建驱动的空实现
│   └── …                         电池、UFS、马达、闪光灯、相机、麦克风…
│
├── xnu/                          ← XNU 覆盖层（构建时拷入 xnu-src/）
│   ├── files/bsd/…               APFS、sysctl、kern_exit（hakios-exit 追踪）
│   └── files/osfmk/…             loader_return、gic、tunables
│
├── xnuloader/                    ← 启动 loader（XNUP payload）
│   ├── loader.c                  ★ USB 命令循环、日志管线、6GB 内存窗
│   ├── mkpayload.py              构建 XNUP 容器
│   └── build.sh                  loader.efi（clang -O0）
│
├── userland/                     ← Darwin 用户态构建
│   ├── src/eagl.c                ★ CA/GL 垫片（shader 预热、IOSurface、hash）
│   ├── src/hakios.*.c            注入的钩子（SpringBoard、WiFi、GPU…）
│   └── build.sh                  REST=1 GL=1 构建（见踩坑）
│
├── tools/                        ← 主机工具（mkapfs、hakios-config、frames…）
├── sysimage/                     ← unpack.sh：从你自己的 IPSW 构建 root.apfs
├── fw-gpu/, fw-touch/            ← 固件目录（从你自己的手机提取）
├── qemu/                         ← QEMU 测试环境
├── hakios-metal/                 ← Adreno 上的 Metal（姊妹组件）
├── socs/, configs/, ci/          ← SoC 片段、CI、配置机制
└── scripts/                      ← 主机辅助脚本（remote.ps1.example、webdav_*.example）
```

---

## 许可

XNU 衍生文件仍受 Apple 公开源代码许可 2.0 约束
（[LICENSE.APSL](LICENSE.APSL)）；项目自身文件遵循 [LICENSE](LICENSE)。
第三方组件列在 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。
不包含任何 Apple 专有固件、镜像或软件——请从你自己的设备/IPSW 提取。
