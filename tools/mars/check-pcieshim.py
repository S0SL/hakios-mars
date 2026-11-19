#!/usr/bin/env python3
"""Exercise the Mars shim's actual C code with bounded, recorded MMIO.

No device access: checks SM8350 clock votes without clobbering other clients,
the reported branch addresses, stage boundaries and timeout access guards.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


PRELUDE = r'''
#include <assert.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>
typedef void VOID;
typedef char CHAR8;
typedef uint32_t UINT32;
typedef uintptr_t UINTN;
typedef UINTN EFI_STATUS;
typedef void *EFI_HANDLE;
typedef struct { int unused; } EFI_SYSTEM_TABLE;
typedef struct { uint32_t a; uint16_t b, c; uint8_t d[8]; } EFI_GUID;
#define CONST const
#define EFIAPI
#define EFI_SUCCESS 0
#define EFI_VARIABLE_BOOTSERVICE_ACCESS 2
#define DEBUG_ERROR 0
#define DEBUG(arguments) ((void)0)
#define VA_LIST va_list
#define VA_START va_start
#define VA_END va_end
#define CopyMem memcpy
static UINT32 MmioRead32(UINTN address);
static VOID MmioWrite32(UINTN address, UINT32 value);
static EFI_STATUS mock_stall(UINTN delay);
static EFI_STATUS mock_variable(const wchar_t *, EFI_GUID *, UINT32, UINTN, VOID *);
static struct { EFI_STATUS (*Stall)(UINTN); } boot = {mock_stall};
static struct {
  EFI_STATUS (*SetVariable)(const wchar_t *, EFI_GUID *, UINT32, UINTN, VOID *);
} runtime = {mock_variable};
#define gBS (&boot)
#define gRT (&runtime)
static UINTN AsciiVSPrint(CHAR8 *buffer, UINTN size,
                          const CHAR8 *format, VA_LIST arguments)
{
  char converted[256];
  assert(strlen(format) < sizeof(converted));
  strcpy(converted, format);
  /* EDK2's ASCII-string %a is libc's %s. No floating-point formats here. */
  for (char *p = converted; *p != 0; p++) {
    if (p[0] == '%' && p[1] == 'a') p[1] = 's';
  }
  return vsnprintf(buffer, size, converted, arguments);
}
'''

POSTLUDE = r'''
static int power_ready, phy_ready, link_ready;
static unsigned touched, perst, window_reads, clock_writes, all_writes;
static UINTN waited;
static uint32_t vote = 0xa5000040, clkref = 0x42;
static VOID access_address(UINTN address)
{
  if (address >= 0x100000 && address < 0x200000) {
    touched |= 1;
  } else if (address >= PARF_BASE && address < PHY_BASE) {
    assert(power_ready && PCIE_SHIM_STAGE >= 2);
    touched |= 2;
  } else if (address >= PHY_BASE && address < PARF_BASE + 0x8000) {
    assert(power_ready && PCIE_SHIM_STAGE >= 3);
    touched |= 4;
  } else if (address >= TLMM_BASE && address < TLMM_BASE + 0x100000) {
    assert(power_ready && PCIE_SHIM_STAGE >= 2);
    touched |= 8;
    if (address >= TLMM_BASE + 94 * 0x1000 &&
        address < TLMM_BASE + 95 * 0x1000) {
      assert(PCIE_SHIM_STAGE == 4 && phy_ready);
      perst++;
    }
  } else if ((address >= DBI_BASE && address < DBI_BASE + 0x2000) ||
             (address >= ECAM_BASE && address < ECAM_BASE + 0x100000)) {
    assert(PCIE_SHIM_STAGE == 4 && power_ready && phy_ready && link_ready);
    touched |= 16;
    window_reads++;
  } else {
    fprintf(stderr, "Unexpected MMIO: %lx\n", (unsigned long)address);
    abort();
  }
}
static UINT32 MmioRead32(UINTN address)
{
  access_address(address);
  if (address == GDSCR) return power_ready ? GDSC_STATUS | 1 : 1;
  if (address == PHY_BASE + PHY_PCS_STATUS1) return phy_ready ? 0 : 0x48;
  if (address == PARF_BASE + PARF_LTSSM) return link_ready ? LTSSM_L0 : 0;
  if (address == 0x152008) return vote;
  if (address == 0x18c004) return clkref;
  /* Distinct values catch mislabeled clock status addresses. */
  if (address == 0x16b028) return 0xa1;
  if (address == 0x16b024) return 0xa2;
  if (address == 0x16b01c) return 0xa3;
  if (address == 0x16b014) return 0xa4;
  if (address == 0x16b010) return 0xa5;
  if (address == 0x16b030) return 0xa6;
  return 0;
}
static VOID MmioWrite32(UINTN address, UINT32 value)
{
  access_address(address);
  all_writes++;
  if (address == 0x152008) {
    /* slv=0, mstr=1, cfg=2, aux=3, pipe=4, slv_q2a=5. */
    assert(value == (vote | 0x3f));
    vote = value;
    clock_writes++;
  }
  if (address == 0x18c004) {
    assert(value == (clkref | 1));
    clkref = value;
    clock_writes++;
  }
}
static EFI_STATUS mock_stall(UINTN delay)
{
  waited += delay;
  assert(waited <= 100000);
  return EFI_SUCCESS;
}
static EFI_STATUS mock_variable(const wchar_t *name, EFI_GUID *guid,
                                UINT32 attributes, UINTN size, VOID *data)
{
  (void)name; (void)guid; (void)data;
  assert(attributes == EFI_VARIABLE_BOOTSERVICE_ACCESS && size < 2048);
  return EFI_SUCCESS;
}
int main(int argc, char **argv)
{
  assert(argc == 2);
  power_ready = strcmp(argv[1], "power-timeout") != 0;
  phy_ready = strcmp(argv[1], "phy-timeout") != 0;
  link_ready = strcmp(argv[1], "link-timeout") != 0;
  assert(PcieShimEntry(NULL, NULL) == EFI_SUCCESS);
  if (!power_ready) {
    assert(touched == 1 && all_writes == 1 && clock_writes == 0);
    assert(strstr(mPcieShimLog, "GDSC did not turn on"));
  } else {
    assert(clock_writes == 2 && vote == 0xa500007f && clkref == 0x43);
    assert(strstr(mPcieShimLog, "aux=a1 cfg=a2 mstr=a3 slv=a4 q2a=a5 pipe=a6"));
    if (PCIE_SHIM_STAGE == 1) {
      assert(touched == 1);
      assert(strstr(mPcieShimLog, "stage1 power/clocks complete"));
    } else if (PCIE_SHIM_STAGE == 2) {
      assert(touched == (1 | 2 | 8) && perst == 0);
      assert(strstr(mPcieShimLog, "stage2 PARF/GPIO complete"));
    } else if (!phy_ready) {
      assert(touched == (1 | 2 | 4 | 8) && perst == 0);
      assert(strstr(mPcieShimLog, "PHY not ready; skipping"));
    } else if (PCIE_SHIM_STAGE == 3) {
      assert(touched == (1 | 2 | 4 | 8) && perst == 0);
      assert(strstr(mPcieShimLog, "stage3 PHY ready"));
    } else if (!link_ready) {
      assert(touched == (1 | 2 | 4 | 8) && perst > 0 && window_reads == 0);
      assert(strstr(mPcieShimLog, "link not L0; skipping"));
    } else {
      assert(touched == (1 | 2 | 4 | 8 | 16) && perst > 0 && window_reads == 5);
      assert(strstr(mPcieShimLog, "link L0; probing"));
    }
  }
  printf("stage=%u scenario=%s passed\n", PCIE_SHIM_STAGE, argv[1]);
  return 0;
}
'''


def check(source_path, output):
    source = ''.join(line for line in source_path.read_text().splitlines(True)
                     if not line.startswith('#include'))
    anchor = '#define PCIE_SHIM_STAGE    1'
    if source.count(anchor) != 1:
        raise ValueError('Expected default stage 1')
    results = []
    for stage in range(1, 5):
        path = output / f'stage{stage}.c'
        path.write_text(PRELUDE + source.replace(anchor,
                        f'#define PCIE_SHIM_STAGE    {stage}') + POSTLUDE)
        binary = path.with_suffix('')
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        str(path), '-o', str(binary)], check=True)
        for scenario in ('power-timeout', 'phy-timeout', 'link-timeout', 'ok'):
            result = subprocess.run([str(binary), scenario],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                print(result.stderr, end='', flush=True)
                result.check_returncode()
            print(result.stdout, end='', flush=True)
            results.append({'stage': stage, 'scenario': scenario, 'passed': True})
    for stage in (0, 5):
        path = output / f'invalid{stage}.c'
        path.write_text(PRELUDE + source.replace(anchor,
                        f'#define PCIE_SHIM_STAGE    {stage}') + POSTLUDE)
        result = subprocess.run(['cc', '-std=c11', '-fsyntax-only', str(path)],
                                capture_output=True, text=True)
        assert result.returncode != 0 and 'Invalid PCIe shim stage' in result.stderr
        results.append({'stage': stage, 'invalid_stage_rejected': True})
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: clock votes/status, 16 staged MMIO cases, 2 invalid stages')


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=root / 'devices/mars/uefi/files/'
                        'Silicon/Silicium/SiliciumPkg/Drivers/PcieShimDxe/PcieShimDxe.c')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=False)
        check(args.source, args.output)
    else:
        with tempfile.TemporaryDirectory(prefix='mars-pcieshim-check-') as directory:
            check(args.source, Path(directory))


if __name__ == '__main__':
    main()
