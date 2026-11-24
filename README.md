# HakiOS on Xiaomi 11 Pro (mars)

> ⚠️ **实验性研究项目：存在硬件损坏与数据丢失风险，动手前请阅读 [免责声明](DISCLAIMER.md)。**

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
| USB fastboot 通道 | ❌ **始终未打通** — `fastboot devices` 从未见到过设备，也从未能收发任何命令；根因是闭源 Qcom `UsbFnDwc` 的 `SetEPConfigCmd 0x80000009`（端点配置失败）——`GEVNTADR` 寄存器写不进（疑似 TrustZone 锁定 / Qcom wrapper 旁路），EP0 从未配置成功。loader 有 30 秒空闲自动起内核兜底（`fastboot boot` 后无需主机命令即可进桌面） |
| UEFI PCIe shim | 🧪 **stage 1 已进桌面** — 新鲜运行日志确认电源域/GCC 时钟阶段完成；stage 2 PARF/GPIO 尚待实机日志，PHY/link/Wi-Fi 仍未打通 |
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
1. **分阶段验证 UEFI PCIe shim**——当前仅 stage 1（电源域/GCC 时钟）有实机桌面证据；
   先确认 stage 2（PARF/GPIO），再验证 PHY 与 link。不可把 stage 1 结果当作 PCIe 已连通。
2. PHY 序列时序（75 次写入中插入延时）。
3. 确认 100MHz 参考时钟真的到达 PHY。

---

## 从零复现（完整操作流程）

### 0. 你需要什么

| 项 | 说明 |
|---|---|
| 手机 | **小米 11 Pro（mars，SM8350，12GB）**——12GB 是硬要求（6GB 内存窗需要） |
| 解锁 | Bootloader 解锁（`fastboot boot` 需要；不需要刷任何分区） |
| 构建服务器 | Ubuntu（或 WSL），约 20GB 磁盘；本项目全在远程构建 |
| 主机 PC | 有 `adb` / `fastboot`（platform-tools） |
| 固件来源 | **你自己的**手机与 IPSW——本仓库不含任何 Apple 专有文件 |

### 1. 手机分区：创建 24 GiB 的 `darwin` 分区

项目用一个 **24 GiB 的 `darwin` 分区**承载系统与日志：

| 区域 | 偏移 | 内容 |
|---|---|---|
| 前 2.47 GB | 0 | `system.apfs`（从 IPSW 提取） |
| 8.37 GiB 起 | `UFS_WRITE_FIRST` | 内核可写区（`ufs_write=1`） |
| 8 GiB 偏移 | `0x1F3000000` | **日志区**（`dd` 提取点，6291964 块） |

分区表是 GPT（UFS LUN0，4 KiB 扇区）。操作需要 root 的 adb（或 fastboot）：

```sh
# 1) 先备份分区表（必须！破坏性操作）
adb shell "dd if=/dev/block/sda of=/data/local/tmp/gpt-head.bin bs=512 count=34"
adb shell "dd if=/dev/block/sda of=/data/local/tmp/gpt-tail.bin bs=512 skip=<last-33> count=33"
adb pull /data/local/tmp/gpt-head.bin .
adb pull /data/local/tmp/gpt-tail.bin .

# 2) 用 sgdisk/sgdisk 在 UFS LUN0 上创建 24 GiB 的 darwin 分区
#    （从 userdata 尾部划出；具体扇区号看你的分区表——sgdisk -p /dev/block/sda）
adb shell
sgdisk -e /dev/block/sda                    # 转换 MBR→GPT（已是 GPT 则跳过）
sgdisk --new=0:0:+24G --change-name=0:darwin /dev/block/sda
sgdisk --typecode=0:0FC63DAF-8483-4772-8E79-3D69D8477DE4 /dev/block/sda  # Linux filesystem GUID
# 3) 确认并重读分区表
sgdisk -p /dev/block/sda
# 重启回安卓让内核识别，然后验证：
adb shell "ls -la /dev/block/by-name/darwin"
```

**注意**：
- `darwin` 分区名必须是 `darwin`（loader 和内核按名字找它）。
- `logdump` 分区是安卓自己的，别动。
- 任何写分区表的操作前**先备份 GPT**（上面第 1 步），出错可恢复。

### 2. 提取固件（都从你自己的设备/IPSW）

```sh
# a) system.apfs（2.47 GB）：从 iPhone X 的 IPSW 解出
#    （仓库不含它——sysimage/unpack.sh 会指引你下载并解包 IPSW）
sysimage/unpack.sh ~/Downloads/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw
# 产物在 sysimage/rootfs/、system.apfs 等（见 unpack.sh 头注释）

# b) UEFI 闭源驱动（Binaries）：从手机的 UEFI 分区/厂商镜像提取
#    放到 devices/mars/uefi/files/Binaries/（.gitignore 已排除，永不入库）

# c) GPU / 触摸固件：手机 /vendor/firmware/ 的 a660_*.fw、st_fts_*.ftb 等
#    放到 fw-gpu/、fw-touch/

# d) Wi-Fi 固件（未打通，但需要准备）：wpss.mdt、wpss.b02-b07、amss.bin、
#    m3.bin、bd_k1.elf、regdb_xiaomi.bin（手机 /vendor/firmware_mnt/image/）
#    放到 fw-wifi/
```

### 3. 构建服务器搭建

```sh
# 1) 拉源码（本仓库）
git clone https://github.com/S0SL/hakios-mars.git ~/hakios
cd ~/hakios

# 2) 依赖（XNU 构建链 + Mesa）
xnu-deps/setup.sh          # XNU 构建工具链（clang/lld、Python 依赖）
tools/mk-mesa.sh            # Mesa 25（freedreno，OSMesa）——需要 meson/ninja

# 3) 内核配置
cp devices/mars/configs/mars.config .config
# 或 make defconfig 后手动改（CONFIG_HAKIOS_ADRENO=y、CONFIG_HAKIOS_PCIE=y）

# 4) 解包 IPSW（见上一步）后，userland 依赖 sysimage/ 的产物
```

### 4. 构建

```sh
# 用户态（必须 REST=1 GL=1——见踩坑）
cd ~/hakios/userland && REST=1 GL=1 ./build.sh

# 内核
cd ~/hakios && LC_ALL=C make kernel -j24

# 打包（--physbase 是 6GB 内存窗的关键，12GB 机型专用）
python3 xnuloader/mkpayload.py -o p.bin loader.efi=xnuloader/loader.efi \
  kernel=hakios-kernel ramdisk=userland/root.apfs resident=userland/flashboot.apfs \
  --physbase 100000000 \
  --cmdline "-v cpus=8 bootcpu=7 ufs=2 ufs_write=1 root_apfs=ufs_darwin \
    amfi_get_out_of_my_way=1 thermal_stop=95 battery_stop=20 \
    touchscreen=1 touch_poll_us=2000 gpu=1"
venv/bin/python mkxnuimg.py -d mars --mode DEBUG -p p.bin -o out.img
```

### 5. 启动测试

```sh
# 手机进 fastboot（关机后按 音量下+电源，或 adb reboot bootloader）
adb reboot bootloader

# 从内存启动（不写 boot 分区，重启即回安卓）
fastboot boot out.img
```

**预期**：约 30 秒后 loader 自动起内核（或 `fastboot oem run`——USB 通道未打通，
所以依赖 30 秒兜底），2-3 分钟到桌面。

**首次启动慢**：Photos/Spotlight 在重建索引（根文件系统首次挂载）；之后的
启动快得多。

### 6. 提取运行日志（调试的生命线）

```sh
# 回到安卓后（长按电源重启）：
adb shell dd if=/dev/block/by-name/darwin of=/data/local/tmp/k.bin \
  bs=4096 skip=2097152 count=4096
adb pull /data/local/tmp/k.bin .
# k.bin 就是完整运行日志（loader + 内核 + 用户态）
```

**清日志区**（下次运行前，可选）——**写侧必须用 `seek=`**（`skip=` 只管输入；
用错会清掉 system.apfs 头，已踩坑）：

```sh
adb shell "dd if=/dev/zero of=/dev/block/by-name/darwin bs=4096 seek=2097152 count=2048"
# 清完验证 NXSB 未破坏：dd if=... bs=4096 count=1 | od -A d -t x1 -j 32 -N 4 → 4e 58 53 42
```

---

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
├── Mu-Silicium/                    # UEFI（Dwc3ShimDxe、PcieShimDxe）
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
│   ├── uefi/files/               UEFI 平台文件（APRIORI.inc、DXE.inc、Mars PCIe shim、marsPkg）
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
