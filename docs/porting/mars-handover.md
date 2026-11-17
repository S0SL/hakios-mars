# HakiOS 移植到小米 11 Pro（mars / SM8350）— 交接文档

> 整理于 2026-11-11，**当日续更**。换电脑后按本文档即可接着干。
> 完整实验日志：服务器 `~/hakios/devices/mars/PORT-LOG.md`（按时间顺序，含每次失败的判断依据）。
> 本地工作副本：`C:\Users\97770\XiaomiMiMoProjects\mi11`（源 `C:\Users\97770\Documents\mi11` 已只读保留，勿改）。

---

## 0. 一分钟速览（2026-11-11 深夜更新）

**里程碑：已进 SpringBoard 桌面，可稳定运行数分钟。**

```text
BootShim → Mu-Silicium UEFI（旧 FD）→ XnuLoader（6GB 高位窗 + UEFI 页表补映射）
→ XNU（exit 追踪进 loader_log）→ APFS 双盘 → init → switch_root
→ launchd.darwin → backboardd/SpringBoard 常驻 → 桌面
```

**已解决（按时间）：**

1. **CS 签名**：page shift 14 放行 + 页 hash 跳过（`ubc_subr.c`）→ error 98 / NOT_CODESIGNED / NSException 归零。
2. **日志导出**：UEFI `WriteBlocks` 第 4 参是字节数；livelog 每 2s 持久化到 darwin 8GiB 区；**进程退出追踪**（`kern_exit.c` 的 `hakios-exit:` 行，经 `loader_log_line` 直写 loader_log——内核 `printf` 只进 msgbuf，live 日志看不到！）。
3. **jetsam 风暴（苹果标循环真因）**：固件只给 192MB 窗口（`a2000000+192MB`），VMPAGESHORTAGE/FCTHRASHING 疯杀进程（154 次退出/轮）。**修法 = `--physbase 100000000`**：窗口改到 4GB 以上（设备 12GB，`0x100000000+6GB` 全是真 RAM，不在固件内存图里）：
   - loader：claim 失败（EFI_NOT_FOUND）改为警告后照常用；
   - loader：**`map_window_for_uefi()`** 直接补页表——TCR T0SZ=24（40 位 VA、4KB 粒度），TTBR 是 **L0 表**，下钻 L0[0]→真 L1（`0x9f3fe000`），给 L1 项 4..9 填 1GB 大块（属性抄 2–4GB DRAM 描述符），`tlbi vmalle1`。不做这步第一次写 resident 镜像就 `UEFI EXCEPTION far=107800000`。
   - 结果：`memory 6144 MB`，退出 154→29（几乎全是正常退出），backboardd/SpringBoard **0 次死亡**。
4. **每轮内存图**：loader 现在每次启动打印完整 UEFI 内存图（`memory map (type 7...)`）。

**当前镜像与构建**（产物一律放服务器 `~/hakios/`，勿放 `/tmp`）：

```bash
cd ~/hakios && LC_ALL=C make kernel -j24          # exit 2 = kext 符号集，可忽略
cd ~/hakios && PATH=$HOME/bin-xnuloader:$PATH xnuloader/build.sh
fd=Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd
cp -p "$fd" ~/hakios/current-SILICIUM_UEFI.fd; cp ~/hakios/old-SILICIUM_UEFI.fd "$fd"
python3 xnuloader/mkpayload.py -o ~/hakios/p.bin loader.efi=xnuloader/loader.efi \
  kernel=hakios-kernel ramdisk=userland/root.apfs resident=userland/flashboot.apfs \
  --physbase 100000000 \
  --cmdline "-v cpus=8 bootcpu=7 ufs=2 ufs_write=1 root_apfs=ufs_darwin amfi_get_out_of_my_way=1 thermal_stop=95 battery_stop=20"
venv/bin/python mkxnuimg.py -d mars --mode DEBUG -p ~/hakios/p.bin -o ~/hakios/<name>.img
cp -p ~/hakios/current-SILICIUM_UEFI.fd "$fd"
```

最新实机镜像：`xnu-oldfd-himem4.img`（SHA256 `6be4904d…`，本机有）。

**日志提取（每轮必做）**：
```powershell
# 回安卓后：读取用 skip=（作用于输入）
adb shell "dd if=/dev/block/by-name/darwin of=/data/local/tmp/k.bin bs=4096 skip=2097152 count=2048"
adb pull /data/local/tmp/k.bin .
# 启动前清区必须用 seek=（!! 写侧偏移）：少了它 = 把 system.apfs 头 8MB 清零（已踩坑并修复）
adb shell "dd if=/dev/zero of=/dev/block/by-name/darwin bs=4096 seek=2097152 count=2048"
# 清完验证 NXSB：dd if=... bs=4096 count=1 | od -A d -t x1 -j 32 -N 4 → 4e 58 53 42
```

**当前状态 / 下一步**（2026-11-12 凌晨更新）：
- **触摸已通**（`xnu-oldfd-touch6.img`）：FocalTech FTM5（secondary fts_dual）在 SE11 bitbang 下正常。要点全在 `hakios.goodix.c`：
  - 协议 = vendor `fts_dual/secondary`：HW_REG 读 `{0xFB, addr32BE}` + dummy；chip id `36 39`（secondary，非 primary 的 `36 50`）@`0x20000000`；FIFO `{0x87}` + dummy + 8 字节事件；复位后 8ms 内出 `CONTROLLER_READY(0x03)`；开扫 `{0xA0,0x00,0x00}`→`{0xA0,0x00,0x01}`（ACTIVE+MULTI_TOUCH）。
  - 坐标 = **secondary 的 12 位打包**：`x=((evt[3]&0xF)<<8)|evt[2]`，`y=(evt[4]<<4)|(evt[3]>>4)`（primary 是 16 位，不能混用）。
  - 引脚：SE11 @0xa8c000，GPIO48=MISO/49=MOSI/50=CLK/51=CS（qup11=func1），IRQ23 RST22 AVDD132，VDD=PM8350C LDO2 cmd_db `ldoc2`。
  - GENI 时钟 S_AHB 起不来（vote 写进去了但 0x18008 bit31 不清）→ 目前 bitbang（读 47µs，够用）；`touch_poll_us=2000`。
  - vendor 源已解压：`vendorkernel/android_kernel_xiaomi_sm8350-lineage-23.2/drivers/input/touchscreen/fts_dual/`；FW 已拉取 `st_fts_k2.ftb`（118KB，暂未用到——芯片 flash 自带 FW）。
- 桌面稳定；`NOT_CODESIGNED/NSException/jetsam` 归零；CA 偶发 `Simulating crash!` 不致死。
- **GPU 全阶梯完成（2026-11-12）：adreno=1..22 全绿，三色图画上屏**（用户亲眼确认；日志 `klog26.txt`）。金句：`THE GPU BLOCK IS ALIVE`(6) → `TRUSTZONE ACCEPTS THE ZAP SHADER`(12) → `THE GMU'S FIRMWARE RUNS`/`MESSAGE QUEUES ARE UP`(15/16) → `THE 3D CORE HAS POWER AND ANSWERS`(17) → `THE 3D CORE TAKES COMMANDS`(20) → `THE 3D CORE WRITES OUR MEMORY ON COMMAND`(21, 0x600dc0de) → **`A PICTURE DRAWN BY THE GPU IS ON THE PANEL: orange, white, blue from the top`**(22)，收尾逆序干净（slumber/zap 放弃/CM3 回复位）。要点：
  - mars 与 redwood **共享 GPU 全套地址**（kgsl@0x3d00000 / gmu@0x3d6a000 / gpucc@0x3d90000 / smmu@0x3da0000 / rscc / pdc@0xb290000），仅 **QFPROM 熔丝偏移 0x1e9→0x17b**（已改）；
  - GCC GPU 时钟偏移 sm8350=sc7280 全同；**GCC 频率计数器在 sm8350 读 0Hz** → `measure_clocks`/`cx_ready` 已加 CBCR 兜底；
  - SMMU 全局寄存器（cbar/s2cr/smr）写入经 hypervisor 应答正常；SMC/TZ 全通过；
  - 固件 7 文件在 `~/hakios/fw-gpu/`（进 root.apfs 的 fw/）；门控 `CONFIG_HAKIOS_ADRENO=y`；`adreno_stream1` 默认1安全；
  - **下一步**：`gpu=1 adreno_keep=1` 常驻 → 窗口服务器走 HakiosGPU/Mesa 绘制，替代软件渲染（配合官方 `metal`/`gpu` 文档）。
- **待做**：① GPU 阶梯继续；② USB 通道（FD 管线已解禁）；③ GENI S_AHB（可选）；④ 按键；⑤ xpcproxy exit 78。
- 官方文档 https://hackios-web.vercel.app/zh/guide（boot-args 目录 350 个；QEMU 全用户态要 ≥7GB 佐证了扩容方向）。

### 关键约束（换机必读）

| 项 | 值 |
|---|---|
| 必须用的 UEFI FD | 旧版 `old-SILICIUM_UEFI.fd`（`5fdbe919…`）。**新构建 FD 会随机重启** |
| 服务器文件 | 一律 `~/hakios/`（`/tmp` 重启即丢） |
| 系统镜像 | `system.apfs` 2,477,412,352 字节，SHA1 `1ff1545da4e571202aab62aab1cddf332c121f1a`，已写入 `darwin`；含主路径 dyld cache |
| 内核补丁 | `ubc_subr.c` CS；`kern_exit.c` hakios-exit 退出追踪（printf + loader_log_line） |
| 内存窗 | `--physbase 100000000` = `0x100000000+6GB`（12GB 机型；必须配 loader 页表补映射） |
| 启动方式 | `fastboot boot` 纯内存，不写 boot 分区 |
| 日志持久区 | `darwin` 8 GiB（skip/seek=2097152 bs=4096） |
| 大文件传输 | WebDAV `https://WEBDAV_HOST/dav`（shen），本机 `L:\115open\mi11` |

### 本机关键文件

| 文件 | 说明 |
|---|---|
| `xnu-oldfd-himem4.img` | **最新实机镜像（进桌面）** |
| `klog11.txt` / `.bin` | 进桌面那轮日志（9641 行） |
| `klog*.txt` | 当晚各轮日志（exittrace/memmap/himem 系列） |
| `old-SILICIUM_UEFI.fd` | 已验证 UEFI FD |
| `HANDOVER.md` | 本文件 |

---

## 1. 机器、账号、路径

### 服务器（编译、源码、工具链、IPSW、QEMU）

```bash
ssh -p SSH_PORT USER@BUILD_SERVER
```

- 调用：`C:\Users\97770\XiaomiMiMoProjects\mi11\remote.ps1`（`.\remote.ps1 -Command '...'`）
- askpass：`%TEMP%\askpass.bat`

### 手机

| 项 | 值 |
|---|---|
| 序列号 | `DEVICE_SERIAL` |
| 机型 | mars / M2102K1AC / SM8350 |
| 系统 | LineageOS 23.2，BakaSU root（清过 userdata） |
| 引导 | 解锁，slot a |

### 本地 Windows

```text
C:\platform-tools\adb.exe
C:\platform-tools\fastboot.exe
C:\Users\97770\XiaomiMiMoProjects\mi11\    ← 工作目录
C:\Users\97770\Documents\mi11\            ← 旧源目录（只读）
L:\115open\mi11\                          ← WebDAV 挂载
```

### 分区（LUN0，4 KiB）

| 分区 | 说明 |
|---|---|
| `darwin` | 24 GiB；前 2.47 GB = `system.apfs`；日志区 8 GiB / `0x1F3000000` |
| `logdump` | Android 启动会清零，只能 halt 窗口内读 |
| 块数 | darwin = 25771880448/4096 = **6291964** 块（尾部 skip=6291452） |

---

## 2. 服务器目录

| 路径 | 是什么 |
|---|---|
| `~/hakios/devices/mars/PORT-LOG.md` | **完整实验日志** |
| `~/hakios/xnuloader/loader.c` | loader 源（日志导出已改） |
| `~/hakios/userland/build.sh` | 含 dyld 主路径硬链补丁 |
| `~/hakios/xnu-src/.../bsd/kern/ubc_subr.c` | page shift 14 + 非对齐跳过 |
| `~/hakios/xnu-src/.../bsd/vm/vm_unix.c` | bindfs 后端卷校验 |
| `~/hakios/old-SILICIUM_UEFI.fd` | 已验证 FD。**重要文件一律放项目目录 `~/hakios/`（持久），不要放 `/tmp`（重启即丢）** |
| `~/hakios/xnu-oldfd-exittrace.img` / `p.bin` | 打包产物示例（同在项目目录） |

打包命令（必须旧 FD；产物也写 `~/hakios/`）：
```bash
fd=Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd
cp -p "$fd" ~/hakios/current.fd; cp ~/hakios/old-SILICIUM_UEFI.fd "$fd"
# mkpayload + mkxnuimg 后 cp 回 current.fd
```

---

## 3. 日志导出（2026-11-11 修复说明）

| 通道 | 状态 |
|---|---|
| `logdump` EFI 写 | **一直成功**；Android 重启清零 |
| `darwin` EFI 写 | 根因 = 把块数当字节数传给 WriteBlocks → `0x8000000000000004`；**logfix4 已改 `blocks*bs`，未实测** |
| `HAKIOS-DYLD-PATHS` 持久区 | `darwin` skip=2043904 块，整块 4096 写，**已验证可读** |
| 屏幕 `HOST EXTRACT` | logfix4 成功时会打印 dd 参数 |

提取示例：
```powershell
adb root
adb shell 'dd if=/dev/block/by-name/darwin of=/data/local/tmp/x.bin bs=4096 skip=2097152 count=512'
adb pull /data/local/tmp/x.bin .
# 按 4KiB 块去零拼 ASCII
```

---

## 4. 已验证结论（勿重复踩坑）

1. `SCTLR_EL1` M/C/I 必须分阶段写 + ISB  
2. 禁止猜测范围的 UEFI 栈缓存清理  
3. MMU 开后 framebuffer 映射前不写屏  
4. 必须旧 UEFI FD；新 FD 随机重启  
5. UFSDxe RPMB/GPT listener 需存根；`CONFIG_HAKIOS_UFS=y`  
6. 不修 USB DWC3  
7. dyld 主路径必须有**真实 APFS 文件**，bindfs 会被 shared_region 卷校验拒绝（已加 bindfs 后端解析，但主路径仍用真文件更稳）  
8. CS：`pageSize` 允许 14；4K fault 对 16K 签名未对齐时 **跳过校验不 panic**  
9. `has_word` 必须完整词边界  
10. Android shell `$((big/4096))` 会 32 位溢出，用固定 skip  

---

## 5. 换机/下次执行顺序

1. 读 `PORT-LOG.md` 尾部  
2. 取 `logfix4` → `fastboot boot` → 看 CS/launchd  
3. 需要日志：halt 后长按回 Android，按上面 skip 提取  
4. 改源 → 旧 FD 打包 → 测试 → 写回 PORT-LOG  

---

## 6. 大文件传输分工

- **我**：服务器 → WebDAV 上传  
- **你**：WebDAV → 本机（`L:\115open\mi11`）  
- 小文件（&lt;10MB 镜像）可直接 scp  

---

## 7. 安全

- 破坏性操作（`-w`、写 GPT、写 darwin）需用户明确授权；此前已授权 userdata/darwin  
- `fastboot boot` 不写 boot 分区，可反复回 Android  


---

## 1. 机器、账号、路径

### 服务器（编译、源码、工具链、IPSW、QEMU）

```bash
ssh -p SSH_PORT USER@BUILD_SERVER
```

- 用户 `shen`，密码为你自己设的那个
- 本地调用方式：工作目录里的 `remote.ps1`（`.\remote.ps1 -Command '...'`）
- 若连不上：先确认安全组放行当前 IP；`kex_exchange_identification: Connection closed` = SSH 被拦

### 手机

| 项 | 值 |
|---|---|
| 序列号 | `DEVICE_SERIAL` |
| 机型 | `mars` / M2102K1AC / SM8350 |
| 系统 | LineageOS 23.2（Android 16），BakaSU/KernelSU root（userdata 已清过，管理器需重装） |
| 引导 | 已解锁（`verifiedbootstate=orange`），slot `a` |
| 注意 | `ro.build.fingerprint` 不可信，勿用它判断固件版本 |

### 本地 Windows

```text
C:\platform-tools\adb.exe
C:\platform-tools\fastboot.exe
C:\Users\97770\XiaomiMiMoProjects\mi11\    ← 本工作目录
C:\Users\97770\Documents\mi11\            ← 旧源目录（只读备份，勿改）
```

### 分区（GPT LUN0，4 KiB 扇区）

| 分区 | 说明 |
|---|---|
| `userdata` | 约 201 GiB（`fastboot -w` 后重建） |
| `darwin` | 24 GiB，内含 `system.apfs`（前约 2.47 GB）+ 尾部日志区 |
| 日志区偏移 | `dd ... bs=4096 skip=2043904`（约 8.37 GiB，`UFS_WRITE_FIRST` 之后） |
| 诊断区（旧） | `skip=2097152`（8 GiB）——早期探针用，部分路径曾写不进去 |

`darwin` 内布局经验：

- `0 ~ 2.5 GB`：`system.apfs`（APFS 容器 + 内嵌 OS/App cryptex）
- `8 GiB` 附近：曾尝试的 loader 持久日志（不稳定）
- `8.37 GiB` 起：**当前有效**的 launchd/init 持久日志区

---

## 2. 服务器目录结构（重点）

所有路径在 `/home/shen/` 下：

| 路径 | 是什么 |
|---|---|
| `~/hakios/` | **主仓库**。脚本、设备配置、驱动都在这里 |
| `~/hakios/devices/mars/` | 本机型全部移植资料 |
| `~/hakios/devices/mars/PORT-LOG.md` | **完整实验日志**（换机后第一件事读这个） |
| `~/hakios/devices/mars/prebuilt/images/` | 所有已打包的 `xnu-mars-*.img` |
| `~/hakios/devices/mars/configs/mars.config` | 内核配置（含 `CONFIG_HAKIOS_UFS=y`） |
| `~/hakios/devices/mars/uefi/files/Platforms/Xiaomi/marsPkg/Include/` | `APRIORI.inc` / `DXE.inc`（UFSDxe、USB 顺序） |
| `~/hakios/Mu-Silicium/` | Mu-Silicium UEFI 构建树 |
| `~/hakios/Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd` | **当前构建产物（有问题，勿直接用于测试）** |
| `~/hakios/xnu-src/xnu-8796.121.2/` | XNU 源码（已打 HakiOS 补丁） |
| `~/hakios/xnuloader/` | loader 源码（`loader.c` / `build.sh` / `loader.efi` / `identity.h`） |
| `~/hakios/hakios-kernel` | 编译出的内核（Mach-O arm64） |
| `~/hakios/userland/` | 用户态：`src/`、`boot.apfs`、`root.apfs`、`flashboot.apfs`、**`system.apfs`** |
| `~/hakios/userland/build.sh` | 用户态/镜像构建（`FLASHBOOT=1 CRYPTEXES=flash REST=1`） |
| `~/hakios/sysimage/` | IPSW 解包：`rootfs/`、`cryptex/`、`cryptex-app/`、`20F66__iPhone10,3_6/` |
| `~/hakios/sysimage/downloads/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw` | 16.5 IPSW（已校验） |
| `~/hakios/qemu/run-darwin.sh` | QEMU 验证脚本（`QEMU_CPU=max`） |
| `~/hakios/logs/qemu-mars-final.log` | QEMU 成功启动 SpringBoard 的日志 |
| `~/hakios/tools/userdata-carve.py` | userdata 尾部分区工具 |
| `~/hakios/tools/darwin-write.py` | 向 `darwin` 写系统镜像 |
| `~/hakios/tools/apfs/` | `mkapfs.py` / `apfs.py` / `apfs-tool` |
| `~/hakios/venv/` | Python 虚拟环境（跑 `mkxnuimg.py`、`build_uefi.py`） |
| `~/theos/`、`~/bin-xnuloader/` | loader 交叉工具链 |
| `~/hakios/old-SILICIUM_UEFI.fd` | **已验证可用的旧 UEFI FD**（持久目录；丢失则用本机 `old-SILICIUM_UEFI.fd` scp 补传） |

构建常用命令：

```bash
# 内核
cd ~/hakios && LC_ALL=C make kernel -j24

# loader（正式身份，Darwin 必须用这个，不要用 loader-open 占位身份）
cd ~/hakios && xnuloader/mkidentity.sh sysimage/downloads/iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw
PATH=$HOME/bin-xnuloader:$PATH xnuloader/build.sh

# 用户态小盘（跳过 system.apfs 重压缩）
cd ~/hakios/userland
system_hash_before=$(sha256sum system.apfs | cut -d" " -f1)
system_time=$(stat -c %y system.apfs)
trap "touch -d \"$system_time\" system.apfs" EXIT
touch -d "2030-01-01 00:00:00" system.apfs
LC_ALL=C FLASHBOOT=1 CRYPTEXES=flash REST=1 ./build.sh
test "$system_hash_before" = "$(sha256sum system.apfs | cut -d" " -f1)"

# 打包 flash-root 镜像（必须用旧 FD）
cd ~/hakios
fd=Mu-Silicium/Build/marsPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd
cp -p "$fd" ~/hakios/current-SILICIUM_UEFI.fd
trap "cp -p ~/hakios/current-SILICIUM_UEFI.fd \"$fd\"" EXIT
cp ~/hakios/old-SILICIUM_UEFI.fd "$fd"
python3 xnuloader/mkpayload.py -o ~/hakios/p.bin \
  loader.efi=xnuloader/loader.efi \
  kernel=hakios-kernel \
  ramdisk=userland/root.apfs \
  resident=userland/flashboot.apfs \
  --cmdline "-v cpus=8 bootcpu=7 ufs=2 ufs_write=1 root_apfs=ufs_darwin amfi_get_out_of_my_way=1"
venv/bin/python mkxnuimg.py -d mars --mode DEBUG -p ~/hakios/p.bin -o ~/hakios/xnu-oldfd-flashroot.img
```

QEMU 验证（不碰手机）：

```bash
cd ~/hakios
QEMU_CPU=max QEMU_SMP=4 CMDLINE='cpus=4' qemu/run-darwin.sh 180 -display none > logs/qemu-mars-final.log 2>&1
```

---

## 3. 本机关键文件

| 文件 | 说明 |
|---|---|
| `remote.ps1` | SSH 到服务器执行命令 |
| `system.apfs`（服务器 / 桌面） | SHA-256 `7d8cf31b7b7404c637832b75d1fd8c6a008539e42888fb18e0999808e80a08f6`，大小 `2477412352` |
| `iPhone10,3,iPhone10,6_16.5_20F66_Restore.ipsw` | SHA-256 `c1091c401f67e3aa7cdfeb2cc19e6c79be3c957aae4e097a019e9ccea07d52f2` |
| `old-SILICIUM_UEFI.fd` | 从 `xnu-mars-apfs-hold.img` 抽出的可用 FD |
| `xnu-oldfd-flashroot-boot7.img` | **最近一次真机测试镜像**（含 cryptex bind + 日志） |
| `PORT-LOG.md` / `remote-src/` | 本地同步的日志与源码补丁副本 |
| `EDL-backup-audit.md` | EDL 备份审计（缺 `userdata`/`rawdump`，用户已确认可接受） |
| `E:\下载\GeekFlashTool_Readback_20261110210404583` | EDL 全分区回读（114/118 分区） |
| `E:\下载\BakaSU_v4.2.0-rc3_35215-manager.apk` | root 管理器（清 userdata 后需重装） |

---

## 4. 已验证结论（勿重复踩坑）

### 内核 / 交接

1. **`SCTLR_EL1` 的 M/C/I 不能一次全关或全开**，必须分阶段写 + 每次 `ISB`（stub13 已证）。
2. **禁止按猜测范围清理 UEFI 栈**（`SP±N KiB` 会越界，stub17）。
3. **MMU 开启后、framebuffer 被 XNU 映射前，内核探针不能直接写屏**。
4. 内核 checkpoint 不得在 M/C/I 已关时重复写全关状态。
5. 测试 cmdline 必须**完整词匹配**（`entry_stub=1` 曾被当成 `stub=1`）。
6. 真实内核入口 `__start` @ `fffffff00741e4a8`，探针在 `start_first_cpu`；入口页交接已证明正确。

### UFS / UFSDxe

1. 内核需 `CONFIG_HAKIOS_UFS=y`（mars.config 已开）。
2. 闭源 `UFSDxe` 的 RPMB/GPT listener 依赖缺失的 TEE 会断言；已用成功存根绕过（`patch_ufsdxe_rpmb_stub.py`）。
3. `ufs=1` 做完整哈希审计（慢）；`ufs=2` 直接建分区块服务。
4. `/dev/ufs_boot_a` 读出 `ANDROID!`（`41 4e 44 52 4f 49 44 21`）已验证。

### UEFI FD（最重要）

- **谜底已解（2026-11-12）：坏 FD = 11-10 20:53 的 USB 实验改动**，只在两份文件：`APRIORI.inc` / `DXE.inc`（加了 ClockDxe、TZ(ScmDxeLA/TzDxeLA)、DisplayDxe、CPRDxe、EnvDxe、SPSSDxe、Sdcc 并挪 UFSDxe）。实验版本备份在 `~/hakios/uefi-experiment-2053/`。
- **恢复 00:52 好版本后重建 → SHA256 `5fdbe919…` 与旧 FD 逐字节一致**（构建确定性）→ **重建 FD 管线可信，可放心改 UEFI**（USB 修复解禁）。源两处都要改：`devices/mars/uefi/files/.../Include/` 和 `Mu-Silicium/Platforms/Xiaomi/marsPkg/Include/`（`mars.fdf` 行 82-84 include 的就是这对；`Binaries/mars/*.inc` 是另一套，未动）。
- 打包任何测试镜像前仍用 `~/hakios/old-SILICIUM_UEFI.fd`（或与其同哈希的新构建）。

### USB

- `UsbDwcCoreInitImpl` / `0x80000009`：`fastboot boot` 交接后 DWC3 状态残留（唯一拦路虎）。
- 已试失败（当时）：UsbInit 进 APRIORI、强制 USB 顺序、USB2-only、`USB->stop()`（会直接复位）。
- **2026-11-12 重启此课题**：坏 FD 已归因并恢复（见上节），UEFI 可以放心改了。下一步：定位 `UsbDwcCoreInitImpl`（可能在闭源 Binaries 里——若闭源，就在我们控制的开放 DXE 里做先行 DWC3 核复位），单变量改一次 → 重建 FD（应哈希可比对）→ 实测。loader 侧 `usb_poll_command`/`oem log`/`oem fetch` 协议代码齐全（redwood 官方 xl 流验证过）。
- **2026-11-13 通道打通（usbmode3 实测）**：DWC3 shim（`Dwc3ShimDxe`，PRTCAP=device + DCTL.CSFTRST 核复位）后 `usb: started` 成功、PC `fastboot devices` 枚举到设备。SetEPConfigCmd `0x80000009` 仍打印但非致命。**usbmode3 全程日志证明 darwin 完整跑通**：6144MB、launchd/SpringBoard/Photos、触摸事件（`backboardd [TouchEvents] touching`）、GPU GL 调用 1 万+ 次。
- **"屏幕卡住"不是死机**：`usb_command_loop`（fastboot 协议服务器）在等 PC 命令，`screen_quiet=1` 停止画屏后屏幕停在最后一帧文本。系统其实在等 `oem run` / 或随后继续跑内核。
- **usbmode4（`xnu-usbmode4.img`，SHA `7bc240f5…`）新增**：① `fb_command` 打 `usb: cmd: ...` 命令日志（搞清是谁触发的 run_kernel）；② 30 秒空闲自动 `run_kernel`（`== XNULOADER run (usb idle) ==`），之后等显式 `oem run`，不再自动重跑。PC 开发流：`fastboot boot` → 30 秒窗口内 `fastboot oem log / oem run / oem stop`。
- **编译坑**：loader.c（5000 行单文件）`-O1` 报 `error: fixup value out of range`（无行号，AArch64 ADR ±1MB 超范围）；`-mcmodel=large` 与 COFF 目标不兼容。**build.sh 已改 `-O0`**（启动代码，性能不敏感）。`-O0` 编译通过。
- **usbmode5（`xnu-usbmode5.img`，SHA `34ecd03b…`）实测成功**：30 秒兜底自动起内核 → darwin 桌面正常显示。对照实验（`xnu-shim-nousb.img`，同 shim FD 无 usb 入口，SHA `ec8c21fa…`）证明 **shim FD 无显示问题**；usbmode3/4 的"屏幕卡住"= 卡在 `usb_command_loop` 等命令/等连接（`usb_wait(0xff)` 无超时，枚举失败就永等），桌面其实会出来。
- **SetEPConfigCmd `0x80000009` 根因定位**：主流程 dwc3 dump 显示 `GCTL=0x101001`（**PRTCAP=host**）且 `GEVNTADR=0`——**UsbInitDxe 在 shim 复位后又把核切回 host 模式**，UsbfnDwc 在 host 模式下 SetEPConfigCmd 必败。usbmode6 修复：`usb_start()` 在 `start_ex` **之前**做干净复位（PRTCAP=device + GEVNTADR=4KB 事件缓冲 + CSFTRST），日志行 `usb: pre-start reset ...`。
- **修正（usbmode8/9 实测）**：`GCTL=101001` 的 PRTCAP 位其实是 **device(1)**（此前解析错，一直正常）。真问题 = **GEVNTADR 寄存器写不进**（SIZ 能写、ADR 读回恒 0；对齐 4KB、SIZ→HI→LO 写序均无效）——疑似 TZ 安全寄存器锁定或 Qcom wrapper 旁路（UsbfnDwc 可能自管事件）。**CSFTRST 会把 PRTCAP/GEVNTADR 清回默认——配置必须在复位之后写**（shim 和 pre-start 都曾顺序写反）。SetEPConfigCmd 失败非致命（start_ex 仍成功）。usbmode10 在 `usb: started` 后再 dump 一次寄存器（看 Qcom 驱动是否自设 GEVNTADR）。
- **GCC 时钟坑（usbmode7b 崩溃）**：UEFI 页表**未映射 GCC（0x100000）**，shim 裸读 CBCR = 翻译错误挂死（`esr 0x96000006 far 0x10f010`）。要开 USB 时钟必须在 loader 侧先补页表（loader 有 `map_window_for_uefi` 经验）。
- **log_len=0 坑**：auto-run/oem run 的 `log_len=0` 会清掉 shim/pre-start 诊断行（日志只剩 run 之后）。已全部禁用——**全量日志是主要调试通道**（`adb shell dd ... skip=2097152` 提取）。

### 用户态 / Darwin

1. APFS bootstrap（`boot.apfs`+`root.apfs`，22 checks）真机稳定。
2. 完整 `system.apfs` 在 QEMU 能到 SpringBoard。
3. 真机 flash-root：根卷、`switch_root`、cryptex、173 应用均 `[ ok ]`。
4. **不要把 `launchd.darwin` 重写回 `/sbin/launchd`（那是 stage0）。**
5. dyld 需要 cryptex 出现在标准路径（`/private/preboot/Cryptexes`、`/System/Library/Caches/com.apple.dyld` 等）；bind 已加，**仍未完全解决**——这是当前主攻点。
6. `hello` / 测试 PID 1 的 `signal 6` 是测试程序主动 `exit`，不是内核问题。

### 持久日志

- 内核只允许写 `darwin` 的 `UFS_WRITE_FIRST` 之后（约 8.37 GiB）。
- 启动参数需 `ufs_write=1`，否则 `/dev/rufs_darwin` 只读。
- 读取：

```powershell
adb root
adb shell 'dd if=/dev/block/by-name/darwin of=/data/local/tmp/hakios-launchd-persist.bin bs=4096 skip=2043904 count=512'
adb pull /data/local/tmp/hakios-launchd-persist.bin .
# 按 4KiB 块去零拼 ASCII 文本
```

---

## 5. 换机后建议执行顺序

1. **读服务器 `PORT-LOG.md` 尾部**，确认没有比本文档更新的结论。
2. 确认 SSH：`.\remote.ps1 -Command 'tail -n 50 /home/shen/hakios/devices/mars/PORT-LOG.md'`
3. 确认旧 FD 还在：`ls -l ~/hakios/old-SILICIUM_UEFI.fd`  
   - 若不在：从本机 `old-SILICIUM_UEFI.fd` scp 上去，或从 `xnu-mars-apfs-hold.img` 重抽（见下）。
4. 确认手机 ADB / Fastboot、`darwin` 分区与 `system.apfs` 哈希。
5. **主攻 dyld/cryptex 路径**（对照 `logs/qemu-mars-final.log` 成功路径 vs 真机 boot7 日志）。
6. 每次改动：改源 → 旧 FD 打包 → `fastboot boot` → 回 Android 读日志区 → 写回 PORT-LOG。

从本地镜像重抽旧 FD：

```powershell
# 解析 xnu-mars-apfs-hold.img 的 boot 镜像头，kernel gzip 内 XNUP 段
# 已有抽取结果：old-SILICIUM_UEFI.fd（3,145,728 字节）
scp -P 47301 .\old-SILICIUM_UEFI.fd USER@BUILD_SERVER:~/hakios/old-SILICIUM_UEFI.fd
```

---

## 6. 已知可忽略 / 已关闭项

| 项 | 状态 |
|---|---|
| EDL 备份缺 `userdata`/`rawdump` | 用户确认无重要数据，可接受 |
| `7 processors running` | 正确：CPU0 留 loader，内核用 1–7 |
| 控制台滚动慢 | framebuffer 软件滚动，已知；verbose 可用 4x 字体拍照裁切 |
| `v_scale` 放大字体 | 无效（只影响进度图），已回退 |
| 新 UEFI USB 通道 | 关闭，不再投入 |
| 内核 kext symbol-set 构建尾部报错 | 已知可忽略 |

---

## 7. 联系与安全

- 所有破坏性操作（`fastboot -w`、写 GPT、写 `darwin`）此前均已获用户明确授权；**换机后若再动分区，需再次确认**。
- 当前测试路径 `fastboot boot` 不写 boot 分区，可反复回 Android。
- 勿把服务器密码写进仓库；`remote.ps1` 使用 `SSH_ASKPASS`。

- **usbmode10 判别结果（2026-11-13 凌晨）**：after start_ex 后 GEVNTADR 仍=0、DEPCMD(EP0)=0——**Qcom UsbfnDwc 不走标准 Synopsys 事件缓冲**（wrapper 旁路），SetEPConfigCmd 失败 = EP0 从未配置成功。下一步：逆向 UsbfnDwc（闭源 EFI）找真实初始化序列与事件机制，或参考 Qcom XBL USB 源码。**实用现状：8GiB 日志分区通道完全可用（主调试手段）**；fastboot 命令通道（oem log/oem run）待闭源驱动吃透后再攻。
