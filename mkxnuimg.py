#!/usr/bin/env python3
"""
Pack a device's UEFI (with the hook that starts the XNU loader) and an optional payload
into an Android boot image for `fastboot boot`.

  kernel = gzip(BootShim + UEFI FD + ["XNUP" container]) + DTB

The boot shim copies the FD to its base and the payload to PAYLOAD_BASE.

The UEFI pieces are taken from a Mu-Silicium tree built here (Mu-Silicium/, see uefi/README.md)
or, when there is none, from devices/<device>/prebuilt/.

usage: mkxnuimg.py [-d device] [-p payload.bin] [-o out.img]
"""
import argparse, gzip, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MU = os.path.join(HERE, 'Mu-Silicium')
PAYLOAD_BASE, PAYLOAD_MAX = 0xF0000000, 0x04000000

ap = argparse.ArgumentParser()
ap.add_argument('-d', '--device', default='redwood')
ap.add_argument('-p', '--payload')
ap.add_argument('-o', '--output')
ap.add_argument('--mode', default='RELEASE')
args = ap.parse_args()

device = args.device
if not re.fullmatch(r'[A-Za-z0-9_-]+', device):
    sys.exit(f'mkxnuimg.py: invalid device name: {device}')
prebuilt = os.path.join(HERE, 'devices', device, 'prebuilt')
config = os.path.join(MU, 'Resources', 'Configs', f'{device}.toml')
if not os.path.isfile(config):
    config = os.path.join(HERE, 'devices', device, 'uefi', 'files', 'Resources', 'Configs', f'{device}.toml')

def fd_config():
    if device == 'redwood' and not os.path.isfile(config):
        return 0x9FD00000, 0x200000
    section = ''
    values = {}
    try:
        with open(config, encoding='utf-8') as source:
            for line in source:
                match = re.match(r'\s*\[([^]]+)\]', line)
                if match:
                    section = match.group(1)
                    continue
                if section == 'uefi_fd':
                    match = re.match(r'\s*(base|size)\s*=\s*(0[xX][0-9a-fA-F]+|[0-9]+)', line)
                    if match:
                        values[match.group(1)] = int(match.group(2), 0)
    except OSError as error:
        sys.exit(f'mkxnuimg.py: cannot read {config}: {error}')
    if set(values) != {'base', 'size'}:
        sys.exit(f'mkxnuimg.py: {config} must define [uefi_fd] base and size')
    return values['base'], values['size']

FD_BASE, FD_SIZE = fd_config()
fd_path = os.path.join(MU, f'Build/{device}Pkg/{args.mode}_CLANGPDB/FV/SILICIUM_UEFI.fd')
if os.path.isfile(fd_path):
    shim_dir = os.path.join(MU, 'BootShim')
    for f in ('BootShim.elf', 'BootShim.bin'):
        try: os.unlink(os.path.join(shim_dir, f))
        except FileNotFoundError: pass
    subprocess.check_call(['make', 'REQUIRES_KERNEL_HEADER=1', f'FD_BASE={FD_BASE:#x}', f'FD_SIZE={FD_SIZE:#x}',
                           f'CFLAGS=--target=aarch64-linux-gnu -DPAYLOAD_BASE={PAYLOAD_BASE:#x}'],
                          cwd=shim_dir, stdout=subprocess.DEVNULL)
    parts = {'shim': os.path.join(shim_dir, 'BootShim.bin'), 'fd': fd_path,
             'dtb': os.path.join(MU, f'Resources/DTBs/{device}.dtb'), 'ramdisk': os.path.join(MU, 'Resources/ramdisk'),
             'mkbootimg': os.path.join(MU, 'Resources/Scripts/mkbootimg.py')}
else:
    parts = {'shim': os.path.join(prebuilt, 'BootShim.bin'), 'fd': os.path.join(prebuilt, 'SILICIUM_UEFI.fd'),
             'dtb': os.path.join(prebuilt, 'device-tree.dtb'), 'ramdisk': os.path.join(prebuilt, 'ramdisk'),
             'mkbootimg': os.path.join(prebuilt, 'mkbootimg.py')}
for name, path in parts.items():
    if not os.path.isfile(path):
        hint = ''
        if name == 'fd':
            hint = ("\n  The UEFI image is not in the repository: it carries the phone vendor's own drivers, which are not\n"
                    "  redistributed here. Build it from your own phone's firmware: uefi/README.md")
        sys.exit(f'mkxnuimg.py: {path} not found{hint}')
shim = open(parts['shim'], 'rb').read()
fd = open(parts['fd'], 'rb').read()
assert len(fd) == FD_SIZE, hex(len(fd))

blob = shim + fd
if args.payload:
    data = open(args.payload, 'rb').read()
    # the payload file is a complete "XNUP" container (see xnuloader/mkpayload.py)
    assert data[:4] == b'XNUP' and len(data) <= PAYLOAD_MAX - 0x1000, 'bad or oversized payload'
    blob += data
    blob += b'\0' * (-len(blob) % 16)
    print(f'payload: {len(data)} bytes, bytesum={sum(data) & 0xffffffff:08x}')

dtb = open(parts['dtb'], 'rb').read()
output = args.output or os.path.join(HERE, f'xnu-{device}.img')
kernel = output + '.kernel~'
open(kernel, 'wb').write(gzip.compress(blob, 6) + dtb)
try:
    subprocess.check_call([sys.executable, parts['mkbootimg'], '--kernel', kernel, '--ramdisk', parts['ramdisk'],
                           '--header_version', '1', '-o', output])
finally:
    os.unlink(kernel)
print(f'{output}: {os.path.getsize(output)} bytes (shim {len(shim)}, uncompressed {len(blob)})')
