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
static int root_valid, atu_ready, drop_link, dbi_routed;
static int xmlh_only, dll_only, endpoint_absent;
static unsigned touched, perst, window_reads, clock_writes, all_writes;
static unsigned phy_writes, core_asserts, core_deasserts, phy_asserts, phy_deasserts;
static UINTN waited;
static uint32_t vote = 0xa5000040, clkref = 0x42;
static uint32_t pipe_mux = 0xa5000002;
static uint32_t core_reset = 0xa5000010, phy_reset = 0xa5000020;
static uint32_t atu[7];
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
      assert(PCIE_SHIM_STAGE >= 5 || phy_ready);
      perst++;
    }
  } else if (address >= DBI_BASE && address < DBI_BASE + 0x2000) {
    assert(PCIE_SHIM_STAGE >= 4 && power_ready && phy_ready && dbi_routed);
    touched |= 16;
  } else if (address >= ECAM_BASE && address < ECAM_BASE + 0x100000) {
    assert(PCIE_SHIM_STAGE >= 4 && power_ready && phy_ready && link_ready);
    assert(root_valid && atu_ready && !drop_link && atu[1] == 0x80000000);
    assert(atu[0] == 4 && atu[2] == 0x60100000 && atu[3] == 0);
    assert(atu[4] == 0x60100fff && atu[5] == 0x01000000 && atu[6] == 0);
    touched |= 32;
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
  if (address == PHY_BASE + PHY_PCS_STATUS1) {
    if (PCIE_SHIM_STAGE >= 5) assert(phy_writes == 75 && (vote & 0x10));
    return phy_ready ? 0 : 0x48;
  }
  if (address == PARF_BASE + PARF_LTSSM) return link_ready ? LTSSM_L0 : 0;
  if (address == DBI_BASE + 0xf28)
    return (link_ready || xmlh_only) && !(drop_link && atu[1]) ? (0x11 << 12) | 0x400 : 0;
  if (address == DBI_BASE + 0x80)
    return (link_ready || dll_only) && !(drop_link && atu[1]) ? 0x20010000 : 0;
  if (address == DBI_BASE) return root_valid ? 0x010c17cb : 0xffffffff;
  if (address == DBI_BASE + 0x1004) return atu_ready ? atu[1] : 0;
  if (address == ECAM_BASE) return endpoint_absent ? 0xffffffff : 0x110317cb;
  if (address == ECAM_BASE + 8) return 0x02800000;
  if (address == 0x152008) return vote;
  if (address == 0x18c004) return clkref;
  if (address == 0x16b054) return pipe_mux;
  if (address == 0x16b000) return core_reset;
  if (address == 0x16c01c) return phy_reset;
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
  if (address == PARF_BASE + 0x350 && value == 0) dbi_routed = 1;
  if (address >= DBI_BASE + 0x1000 && address <= DBI_BASE + 0x1018) {
    assert(link_ready && root_valid);
    if (address != DBI_BASE + 0x1004) assert(atu[1] == 0);
    atu[(address - DBI_BASE - 0x1000) / 4] = value;
  }
  if (address == 0x152008) {
    /* slv=0, mstr=1, cfg=2, aux=3, pipe=4, slv_q2a=5. */
    if (PCIE_SHIM_STAGE >= 5 && phy_writes == 0)
      assert(value == (vote | 0x2f));
    else if (PCIE_SHIM_STAGE >= 5)
      assert(phy_writes == 75 && value == (vote | 0x10));
    else
      assert(value == (vote | 0x3f));
    vote = value;
    clock_writes++;
  }
  if (address == 0x18c004) {
    assert(value == (clkref | 1));
    clkref = value;
    clock_writes++;
  }
  if (address == 0x16b054) {
    assert(PCIE_SHIM_STAGE >= 5 && (value & ~3u) == (pipe_mux & ~3u));
    assert((value & 3u) == PCIE_PIPE_PARENT);
    pipe_mux = value;
  }
  if (address == 0x16b000) {
    assert(PCIE_SHIM_STAGE >= 5 && (value & ~1u) == (core_reset & ~1u));
    if (value & 1u) core_asserts++; else core_deasserts++;
    core_reset = value;
  }
  if (address == 0x16c01c) {
    assert(PCIE_SHIM_STAGE >= 5 && (value & ~1u) == (phy_reset & ~1u));
    if (value & 1u) phy_asserts++; else phy_deasserts++;
    phy_reset = value;
  }
  if (address >= PHY_BASE && address < PARF_BASE + 0x8000) {
    if (PCIE_SHIM_STAGE >= 5) {
      assert(pipe_mux == (0xa5000000u | PCIE_PIPE_PARENT));
      assert(core_reset == 0xa5000010 && phy_reset == 0xa5000020);
    }
    phy_writes++;
  }
}
static EFI_STATUS mock_stall(UINTN delay)
{
  waited += delay;
  assert(waited <= 250000);
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
  xmlh_only = strcmp(argv[1], "xmlh-only") == 0;
  dll_only = strcmp(argv[1], "dll-only") == 0;
  if (xmlh_only || dll_only) link_ready = 0;
  endpoint_absent = strcmp(argv[1], "endpoint-absent") == 0;
  root_valid = strcmp(argv[1], "root-invalid") != 0;
  atu_ready = strcmp(argv[1], "atu-timeout") != 0;
  drop_link = strcmp(argv[1], "link-lost") == 0;
  assert(PcieShimEntry(NULL, NULL) == EFI_SUCCESS);
  if (!power_ready) {
    assert(touched == 1 && all_writes == 1 && clock_writes == 0);
    assert(strstr(mPcieShimLog, "GDSC did not turn on"));
  } else {
    assert(clock_writes == (PCIE_SHIM_STAGE >= 5 ? 3 : 2));
    assert(vote == 0xa500007f && clkref == 0x43);
    assert(strstr(mPcieShimLog, "aux=a1 cfg=a2 mstr=a3 slv=a4 q2a=a5 pipe=a6"));
    if (PCIE_SHIM_STAGE >= 5) {
      assert(pipe_mux == (0xa5000000u | PCIE_PIPE_PARENT));
      assert(core_asserts == 1 && core_deasserts == 1 && core_reset == 0xa5000010);
      assert(phy_asserts == 1 && phy_deasserts == 1 && phy_reset == 0xa5000020);
      assert(phy_writes == 75);
      assert(strstr(mPcieShimLog, "pipe-v9 mux"));
      assert(strstr(mPcieShimLog, "pipe-v9 core reset"));
      assert(strstr(mPcieShimLog, "pipe-v9 phy reset"));
      assert(strstr(mPcieShimLog, "pipe-v9 PIPE vote"));
    } else {
      assert(pipe_mux == 0xa5000002 && core_asserts == 0 && phy_asserts == 0);
    }
    if (PCIE_SHIM_STAGE == 1) {
      assert(touched == 1);
      assert(strstr(mPcieShimLog, "stage1 power/clocks complete"));
    } else if (PCIE_SHIM_STAGE == 2) {
      assert(touched == (1 | 2 | 8) && perst == 0);
      assert(strstr(mPcieShimLog, "stage2 PARF/GPIO complete"));
    } else if (!phy_ready) {
      assert(touched == (1 | 2 | 4 | 8) && perst == (PCIE_SHIM_STAGE >= 5 ? 3 : 0));
      assert(strstr(mPcieShimLog, "PHY not ready; skipping"));
    } else if (PCIE_SHIM_STAGE == 3) {
      assert(touched == (1 | 2 | 4 | 8) && perst == 0);
      assert(strstr(mPcieShimLog, "stage3 PHY ready"));
    } else if (!link_ready) {
      assert(touched == (1 | 2 | 4 | 8 | 16) && perst > 0 && window_reads == 0);
      /* Local status reads are allowed during training, never endpoint reads. */
      assert(strstr(mPcieShimLog, "link not ready; skipping iATU/ECAM"));
    } else if (!root_valid) {
      assert(window_reads == 0 && atu[1] == 0);
      assert(strstr(mPcieShimLog, "root config invalid; skipping iATU/ECAM"));
    } else if (!atu_ready) {
      assert(window_reads == 0);
      assert(strstr(mPcieShimLog, "iATU did not enable; skipping ECAM"));
    } else if (drop_link) {
      assert(window_reads == 0);
      assert(strstr(mPcieShimLog, "link lost; skipping ECAM"));
    } else if (endpoint_absent) {
      assert(window_reads == 1);
      assert(strstr(mPcieShimLog, "endpoint absent"));
    } else {
      assert(touched == (1 | 2 | 4 | 8 | 16 | 32) && perst > 0 && window_reads == 3);
      assert(strstr(mPcieShimLog, "endpoint vendor=17cb device=1103"));
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
    variants = [(stage, 0) for stage in range(1, 6)] + [(5, 2)]
    for stage, parent in variants:
        path = output / f'stage{stage}-parent{parent}.c'
        path.write_text(PRELUDE + source.replace(anchor,
                        f'#define PCIE_SHIM_STAGE    {stage}') + POSTLUDE)
        binary = path.with_suffix('')
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        f'-DPCIE_PIPE_PARENT={parent}u',
                        str(path), '-o', str(binary)], check=True)
        scenarios = ['power-timeout', 'phy-timeout', 'link-timeout', 'ok']
        if stage >= 4:
            scenarios += ['root-invalid', 'atu-timeout', 'link-lost',
                          'xmlh-only', 'dll-only', 'endpoint-absent']
        for scenario in scenarios:
            result = subprocess.run([str(binary), scenario],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode:
                print(result.stderr, end='', flush=True)
                result.check_returncode()
            print(result.stdout, end='', flush=True)
            results.append({'stage': stage, 'pipe_parent': parent, 'scenario': scenario, 'passed': True})
    for stage in (0, 6):
        path = output / f'invalid{stage}.c'
        path.write_text(PRELUDE + source.replace(anchor,
                        f'#define PCIE_SHIM_STAGE    {stage}') + POSTLUDE)
        result = subprocess.run(['cc', '-std=c11', '-fsyntax-only', str(path)],
                                capture_output=True, text=True)
        assert result.returncode != 0 and 'Invalid PCIe shim stage' in result.stderr
        results.append({'stage': stage, 'invalid_stage_rejected': True})
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('PASS: clock/reset sequencing, 42 staged MMIO cases including both PIPE parents, 2 invalid stages')


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
