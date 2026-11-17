# Dwc3ShimDxe (mars USB bring-up shim)

A DXE driver that runs before the Qualcomm UsbfnDwc drivers and resets the DWC3
core (`ssusb@a600000`) left mid-sentence by `fastboot boot`: forces
`GCTL.PRTCAP = device` and does the core soft reset (`DCTL.CSFTRST`), so the
Qcom drivers meet a core as at power-on. It reports what it saw in the EFI
variable `Dwc3Shim`, which the loader prints at startup (its own DEBUG output
has nowhere to go that early).

Source: `SiliciumPkg/Drivers/Dwc3ShimDxe/{Dwc3ShimDxe.c,Dwc3ShimDxe.inf}` in
the Mu-Silicium UEFI tree (built into `SILICIUM_UEFI.fd` for mars).

Known pitfalls (see `docs/porting/mars-handover.md`):

- **A core reset restores GCTL/GEVNTADR to their defaults** — program
  PRTCAP/event buffer *after* the reset, never before.
- **GCC (`0x100000`) is not mapped in UEFI's page tables** — a raw access
  faults (`esr 0x96000006 far 0x10f010`). Clock enable must go through the
  loader, which can build page-table entries.
- `GCTL = 0x101001` means PRTCAP=device (bit 12 set), not host.

> TODO: copy `Dwc3ShimDxe.c` / `.inf` here verbatim from the Mu-Silicium tree
> once the build server is reachable again.
