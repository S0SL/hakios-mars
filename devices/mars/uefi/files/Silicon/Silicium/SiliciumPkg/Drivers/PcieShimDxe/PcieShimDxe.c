#include <Uefi.h>
#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DebugLib.h>
#include <Library/IoLib.h>
#include <Library/PrintLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiDriverEntryPoint.h>
#include <Library/UefiRuntimeServicesTableLib.h>

#define PCIE_SHIM_STAGE    1

#if PCIE_SHIM_STAGE < 1 || PCIE_SHIM_STAGE > 5
#error Invalid PCIe shim stage
#endif

#ifndef PCIE_PIPE_PARENT
#define PCIE_PIPE_PARENT  0u
#endif

#if PCIE_PIPE_PARENT != 0u && PCIE_PIPE_PARENT != 2u
#error Invalid PCIe PIPE parent
#endif

#define GCC_BASE          0x00100000u
#define PARF_BASE         0x01c00000u
#define PHY_BASE          0x01c06000u
#define DBI_BASE          0x60000000u
#define ECAM_BASE         0x60100000u
#define TLMM_BASE         0x0f100000u
#define GDSCR             0x0016b004u
#define GCC_PCIE_CLKREF   (GCC_BASE + 0x8c004u)
#define GCC_PCIE_VOTE     (GCC_BASE + 0x52008u)
#define GCC_PCIE_CORE_RESET (GCC_BASE + 0x6b000u)
#define GCC_PCIE_PIPE_MUX (GCC_BASE + 0x6b054u)
#define GCC_PCIE_PHY_RESET (GCC_BASE + 0x6c01cu)
#define PCIE_PIPE_MUX_MASK 3u
/* SM8350 gcc-lahaina.c: shared vote bits, not the CBCR register order. */
#define PCIE_SLV_AXI      (1u << 0)
#define PCIE_MSTR_AXI     (1u << 1)
#define PCIE_CFG_AHB      (1u << 2)
#define PCIE_AUX          (1u << 3)
#define PCIE_PIPE         (1u << 4)
#define PCIE_SLV_Q2A      (1u << 5)
#define PCIE_CLOCK_VOTES  (PCIE_SLV_AXI | PCIE_MSTR_AXI | PCIE_CFG_AHB | \
                           PCIE_AUX | PCIE_PIPE | PCIE_SLV_Q2A)
#define PARF_LTSSM        0x1b0u
#define PHY_PCS_STATUS1   0x214u
#define ELBI_SYS_CTRL     (DBI_BASE + 0xf24u)
#define ELBI_SYS_STATUS   (DBI_BASE + 0xf28u)
#define DBI_LINK_STATUS   (DBI_BASE + 0x80u)
#define IATU_BASE         (DBI_BASE + 0x1000u)
#define XMLH_LINK_UP      (1u << 10)
#define DLL_LINK_ACTIVE   (1u << 29)
#define GDSC_SW_COLLAPSE  (1u << 0)
#define GDSC_STATUS       (1u << 31)
#define LTSSM_L0          0x11u

static EFI_GUID mPcieShimGuid =
  { 0xd7186a2c, 0x6b54, 0x47c0, { 0x91, 0xf4, 0x0a, 0x1d, 0x80, 0x52, 0x22, 0x49 } };
static CHAR8 mPcieShimLog[2048];
static UINTN mPcieShimLogLength;

static const struct { UINT32 Offset; UINT32 Value; } mPhySequence[] = {
  { 0x240, 0x3 }, { 0x94, 0x8 }, { 0x154, 0x34 }, { 0x16c, 0x8 },
  { 0x58, 0xf }, { 0xa4, 0x42 }, { 0x110, 0x24 }, { 0x11c, 0x3 },
  { 0x118, 0xb4 }, { 0x10c, 0x2 }, { 0x1bc, 0x11 }, { 0xbc, 0x82 },
  { 0xd4, 0x3 }, { 0xd0, 0x55 }, { 0xcc, 0x55 }, { 0xb0, 0x1a },
  { 0xac, 0xa }, { 0xc4, 0x68 }, { 0xe0, 0x2 }, { 0xdc, 0xaa },
  { 0xd8, 0xab }, { 0xb8, 0x34 }, { 0xb4, 0x14 }, { 0x158, 0x1 },
  { 0x74, 0x6 }, { 0x7c, 0x16 }, { 0x84, 0x36 }, { 0x78, 0x6 },
  { 0x80, 0x16 }, { 0x88, 0x36 }, { 0x1b0, 0x1e }, { 0x1ac, 0xca },
  { 0x1b8, 0x18 }, { 0x1b4, 0xa2 }, { 0x50, 0x7 }, { 0x10, 0x1 },
  { 0x1c, 0x31 }, { 0x20, 0x1 }, { 0x24, 0xde }, { 0x28, 0x7 },
  { 0x30, 0x4c }, { 0x34, 0x6 }, { 0xee4, 0x20 }, { 0xe84, 0x75 },
  { 0xe90, 0x3f }, { 0x115c, 0x7f }, { 0x1160, 0xff }, { 0x1164, 0xbf },
  { 0x1168, 0x3f }, { 0x116c, 0xd8 }, { 0x1170, 0xdc }, { 0x1174, 0xdc },
  { 0x1178, 0x5c }, { 0x117c, 0x34 }, { 0x1180, 0xa6 }, { 0x1190, 0x34 },
  { 0x10d8, 0x7 }, { 0xe3c, 0x1d }, { 0xe40, 0xc }, { 0x10dc, 0x0 },
  { 0x104c, 0x8 }, { 0x1050, 0x8 }, { 0x1044, 0xf0 }, { 0x11a4, 0x38 },
  { 0x10cc, 0xf0 }, { 0x694, 0x0 }, { 0x654, 0x0 }, { 0x6a8, 0xf },
  { 0x48, 0x90 }, { 0x620, 0xc1 }, { 0x388, 0x77 }, { 0x398, 0xb },
  { 0x2dc, 0x5 }, { 0x200, 0x0 }, { 0x244, 0x3 }
};

static VOID
reportf (CONST CHAR8 *Format, ...)
{
  CHAR8 Line[256];
  UINTN Length;
  VA_LIST Args;

  VA_START (Args, Format);
  Length = AsciiVSPrint (Line, sizeof (Line), Format, Args);
  VA_END (Args);
  if (Length >= sizeof (Line)) {
    Length = sizeof (Line) - 1;
  }
  DEBUG ((DEBUG_ERROR, "%a", Line));
  if (Length > sizeof (mPcieShimLog) - mPcieShimLogLength - 1) {
    Length = sizeof (mPcieShimLog) - mPcieShimLogLength - 1;
  }
  CopyMem (mPcieShimLog + mPcieShimLogLength, Line, Length);
  mPcieShimLogLength += Length;
  mPcieShimLog[mPcieShimLogLength] = '\0';
  gRT->SetVariable (L"PcieShim", &mPcieShimGuid,
      EFI_VARIABLE_BOOTSERVICE_ACCESS, mPcieShimLogLength, mPcieShimLog);
}

static UINT32
rd (UINTN Address)
{
  return MmioRead32 (Address);
}

static VOID
wr (UINTN Address, UINT32 Value)
{
  MmioWrite32 (Address, Value);
}

static VOID
report_clocks (CONST CHAR8 *Phase)
{
  /* gcc-lahaina.c / gcc-sm8350.c branch status registers, relative to GCC. */
  reportf ("pcieshim: GCC halt %a aux=%x cfg=%x mstr=%x slv=%x q2a=%x pipe=%x\n",
      Phase, rd (GCC_BASE + 0x6b028), rd (GCC_BASE + 0x6b024),
      rd (GCC_BASE + 0x6b01c), rd (GCC_BASE + 0x6b014),
      rd (GCC_BASE + 0x6b010), rd (GCC_BASE + 0x6b030));
}

static VOID
report_phy_clocks (CONST CHAR8 *Phase)
{
  /* SM8350 GCC maps the PHY rate-change branch to this CBCR and RCG. */
  reportf ("pcieshim: clk-v11 %a vote=%x refgen=%x cmd=%x cfg=%x pipe=%x\n",
      Phase, rd (GCC_BASE + 0x52000), rd (GCC_BASE + 0x6b038),
      rd (GCC_BASE + 0x6b03c), rd (GCC_BASE + 0x6b040),
      rd (GCC_BASE + 0x6b030));
}

static VOID
select_pipe_parent (VOID)
{
  UINT32 Before = rd (GCC_PCIE_PIPE_MUX);
  UINT32 After = (Before & ~PCIE_PIPE_MUX_MASK) | PCIE_PIPE_PARENT;

  /* GCC Lahaina maps PCIe PIPE to 0 and bi_tcxo to 2. */
  wr (GCC_PCIE_PIPE_MUX, After);
  gBS->Stall (10);
  reportf ("pcieshim: pipe-v9 mux before=%x after=%x readback=%x\n",
      Before, After, rd (GCC_PCIE_PIPE_MUX));
}

static VOID
pulse_reset (CONST CHAR8 *Name, UINTN Address)
{
  UINT32 Before = rd (Address);
  UINT32 Asserted = Before | 1u;

  wr (Address, Asserted);
  gBS->Stall (1000);
  wr (Address, rd (Address) & ~1u);
  gBS->Stall (1000);
  reportf ("pcieshim: pipe-v9 %a reset before=%x asserted=%x final=%x\n",
      Name, Before, Asserted, rd (Address));
}

static VOID
set_gpio (UINT32 Gpio)
{
  UINTN Base = TLMM_BASE + (Gpio * 0x1000u);

  wr (Base, rd (Base) | (1u << 9));
  wr (Base + 4, 2u);
}

static VOID
set_perst (UINT32 Level)
{
  UINTN Base = TLMM_BASE + (94u * 0x1000u);

  /* GPIO mode, output: set the latch before enabling the output. */
  wr (Base + 4, Level ? 2u : 0u);
  wr (Base, (rd (Base) & ~(0xfu << 2)) | (1u << 9));
}

static VOID
probe_link (VOID)
{
  UINT32 Elbi = 0;
  UINT32 Dll = 0;
  UINT32 Id;
  UINTN Tries;

  /* pci-msm.c uses zero here: this is the internal DBI base, not its CPU PA. */
  wr (PARF_BASE + 0x350, 0);
  reportf ("pcieshim: link-v8 DBI route=%x; asserting PERST\n", rd (PARF_BASE + 0x350));
  set_perst (0);
  /* Allow endpoint power to settle before releasing reset. */
  gBS->Stall (100000);
  set_perst (1);
  gBS->Stall (1000);
  wr (PARF_BASE + PARF_LTSSM, rd (PARF_BASE + PARF_LTSSM) | (1u << 8));
  for (Tries = 0; Tries < 100; Tries++) {
    Elbi = rd (ELBI_SYS_STATUS);
    Dll = rd (DBI_LINK_STATUS);
    if ((Elbi & XMLH_LINK_UP) != 0 && (Dll & DLL_LINK_ACTIVE) != 0) {
      break;
    }
    gBS->Stall (1000);
  }
  if (PCIE_SHIM_STAGE >= 5) {
    reportf ("pcieshim: clk-v11 LTSSM ctrl=%x PERST io=%x\n",
        rd (PARF_BASE + PARF_LTSSM), rd (TLMM_BASE + 94u * 0x1000u + 4));
  }
  reportf ("pcieshim: link-v8 ELBI=%x LTSSM=%x DLL=%x after=%u ms\n",
      Elbi, (Elbi >> 12) & 0x3fu, Dll, (UINT32)Tries);
  if ((Elbi & XMLH_LINK_UP) == 0 || (Dll & DLL_LINK_ACTIVE) == 0) {
    reportf ("pcieshim: link not ready; skipping iATU/ECAM\n");
    return;
  }
  Id = rd (DBI_BASE);
  reportf ("pcieshim: link ready; root id=%x\n", Id);
  if (Id == 0 || Id == 0xffffffffu || (Id & 0xffffu) == 0xffffu) {
    reportf ("pcieshim: root config invalid; skipping iATU/ECAM\n");
    return;
  }

  /* Bus 0 -> bus 1. Only region 0, a 4 KiB CFG0 window for 01:00.0. */
  wr (DBI_BASE + 0x18, (rd (DBI_BASE + 0x18) & 0xff000000u) | 0x00010100u);
  wr (IATU_BASE + 0x04, 0);
  wr (IATU_BASE + 0x00, 4);
  wr (IATU_BASE + 0x08, ECAM_BASE);
  wr (IATU_BASE + 0x0c, 0);
  wr (IATU_BASE + 0x10, ECAM_BASE + 0xfffu);
  wr (IATU_BASE + 0x14, 1u << 24);
  wr (IATU_BASE + 0x18, 0);
  wr (IATU_BASE + 0x04, 1u << 31);
  for (Tries = 0; Tries < 100; Tries++) {
    if ((rd (IATU_BASE + 0x04) & (1u << 31)) != 0) {
      break;
    }
    gBS->Stall (10);
  }
  if (Tries == 100) {
    reportf ("pcieshim: iATU did not enable; skipping ECAM\n");
    return;
  }
  if ((rd (ELBI_SYS_STATUS) & XMLH_LINK_UP) == 0 ||
      (rd (DBI_LINK_STATUS) & DLL_LINK_ACTIVE) == 0) {
    reportf ("pcieshim: link lost; skipping ECAM\n");
    return;
  }
  Id = rd (ECAM_BASE);
  if (Id == 0 || Id == 0xffffffffu || (Id & 0xffffu) == 0xffffu) {
    reportf ("pcieshim: endpoint absent id=%x; returning\n", Id);
    return;
  }
  reportf ("pcieshim: endpoint vendor=%x device=%x cmdsts=%x class=%x\n",
      Id & 0xffffu, Id >> 16, rd (ECAM_BASE + 4), rd (ECAM_BASE + 8));
}

EFI_STATUS EFIAPI
PcieShimEntry (EFI_HANDLE Image, EFI_SYSTEM_TABLE *System)
{
  UINT32 Value;
  UINT32 ClockMask = PCIE_CLOCK_VOTES;
  UINT32 PhyStatus = 0;
  UINTN Index;
  UINTN Tries;

  (VOID)Image;
  (VOID)System;
  mPcieShimLogLength = 0;
  mPcieShimLog[0] = '\0';
  reportf ("pcieshim: begin; phy-sequence=%u\n", (UINT32)(sizeof (mPhySequence) / sizeof (mPhySequence[0])));
  reportf ("pcieshim: staged-v6 stage=%u\n", (UINT32)PCIE_SHIM_STAGE);

  Value = rd (GDSCR);
  reportf ("pcieshim: GDSCR %x (collapse=%u on=%u)\n", Value,
      (Value & GDSC_SW_COLLAPSE) != 0, (Value & GDSC_STATUS) != 0);
  if ((Value & GDSC_SW_COLLAPSE) != 0) {
    wr (GDSCR, Value & ~GDSC_SW_COLLAPSE);
  }
  for (Tries = 0; Tries < 1000; Tries++) {
    Value = rd (GDSCR);
    if ((Value & GDSC_STATUS) != 0) {
      break;
    }
    gBS->Stall (10);
  }
  if ((Value & GDSC_STATUS) == 0) {
    reportf ("pcieshim: GDSC did not turn on; aborting PCIe access\n");
    return EFI_SUCCESS;
  }
  reportf ("pcieshim: GDSCR ready value=%x\n", Value);

  if (PCIE_SHIM_STAGE >= 5) {
    /* Match pci-msm.c: hold the endpoint in reset across RC/PHY reset. */
    set_perst (0);
    report_phy_clocks ("pre");
    select_pipe_parent ();
    /* Linux enables the PIPE branch only after loading the PHY sequence. */
    ClockMask &= ~PCIE_PIPE;
  }

  report_clocks ("pre");
  reportf ("pcieshim: clocks-v7 vote pre=%x clkref=%x mask=%x\n",
      rd (GCC_PCIE_VOTE), rd (GCC_PCIE_CLKREF), ClockMask);
  /* These registers also hold other clients' votes. Never replace the word. */
  wr (GCC_PCIE_CLKREF, rd (GCC_PCIE_CLKREF) | 1u);
  wr (GCC_PCIE_VOTE, rd (GCC_PCIE_VOTE) | ClockMask);
  gBS->Stall (1000);
  reportf ("pcieshim: clocks-v7 vote post=%x clkref=%x\n",
      rd (GCC_PCIE_VOTE), rd (GCC_PCIE_CLKREF));
  report_clocks ("post");
  if (PCIE_SHIM_STAGE >= 5) {
    pulse_reset ("core", GCC_PCIE_CORE_RESET);
    pulse_reset ("phy", GCC_PCIE_PHY_RESET);
  }
  if (PCIE_SHIM_STAGE == 1) {
    reportf ("pcieshim: stage1 power/clocks complete; returning\n");
    return EFI_SUCCESS;
  }

  reportf ("pcieshim: PARF pre sys=%x pm=%x phy=%x ltssm=%x type=%x dbi=%x\n",
      rd (PARF_BASE), rd (PARF_BASE + 0x20), rd (PARF_BASE + 0x40),
      rd (PARF_BASE + PARF_LTSSM), rd (PARF_BASE + 0x1000), rd (PARF_BASE + 0x350));
  wr (PARF_BASE + 0x1000, 0x4);
  wr (PARF_BASE + 0x20, rd (PARF_BASE + 0x20) & ~(1u << 5));
  wr (PARF_BASE + 0x40, rd (PARF_BASE + 0x40) & ~(1u << 0));
  wr (PARF_BASE + 0x350, DBI_BASE);
  wr (PARF_BASE, 0x365e);
  wr (PARF_BASE + 0x358, 0x04000000);

  set_gpio (95);
  set_gpio (64);
  gBS->Stall (1000);
  reportf ("pcieshim: GPIO95 CLKREQ cfg=%x io=%x; GPIO64 WLAN_EN cfg=%x io=%x\n",
      rd (TLMM_BASE + 95 * 0x1000), rd (TLMM_BASE + 95 * 0x1000 + 4),
      rd (TLMM_BASE + 64 * 0x1000), rd (TLMM_BASE + 64 * 0x1000 + 4));
  if (PCIE_SHIM_STAGE == 2) {
    reportf ("pcieshim: stage2 PARF/GPIO complete; returning\n");
    return EFI_SUCCESS;
  }

  for (Index = 0; Index < sizeof (mPhySequence) / sizeof (mPhySequence[0]); Index++) {
    wr (PHY_BASE + mPhySequence[Index].Offset, mPhySequence[Index].Value);
  }
  gBS->Stall (1000);
  if (PCIE_SHIM_STAGE >= 5) {
    wr (GCC_PCIE_VOTE, rd (GCC_PCIE_VOTE) | PCIE_PIPE);
    gBS->Stall (1000);
    reportf ("pcieshim: pipe-v9 PIPE vote=%x mux=%x\n",
        rd (GCC_PCIE_VOTE), rd (GCC_PCIE_PIPE_MUX));
    report_phy_clocks ("post");
  }
  for (Tries = 0; Tries < 10; Tries++) {
    PhyStatus = rd (PHY_BASE + PHY_PCS_STATUS1);
    if ((PhyStatus & (1u << 6)) == 0) {
      break;
    }
    gBS->Stall (1000);
  }
  reportf ("pcieshim: PCS_STATUS1=%x ready=%u after=%u ms\n", PhyStatus,
      (PhyStatus & (1u << 6)) == 0, (UINT32)Tries);
  if ((PhyStatus & (1u << 6)) != 0) {
    reportf ("pcieshim: PHY not ready; skipping PERST, LTSSM and ELBI/ECAM\n");
    return EFI_SUCCESS;
  }
  if (PCIE_SHIM_STAGE == 3) {
    reportf ("pcieshim: stage3 PHY ready; returning\n");
    return EFI_SUCCESS;
  }

  probe_link ();
  return EFI_SUCCESS;
}
