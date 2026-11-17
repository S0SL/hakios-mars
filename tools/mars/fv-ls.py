#!/usr/bin/env python3
"""List the UEFI firmware volume inside an XBL image: the FFS files, their types, and the PE32 images in them.

An XBL image is an ELF whose payload ends in a firmware volume (EFI_FIRMWARE_VOLUME_HEADER, "_FVH"). Inside it are FFS
files; a driver is an FFS file of type DRIVER holding one PE32 section. This walks that structure and prints what is there,
and with --out writes each PE32 image as NAME.efi, guessing the name from a string the module carries.
"""
import argparse
import re
import struct
import sys

FFS_TYPE = {
    0x01: "RAW", 0x02: "FREEFORM", 0x03: "SECURITY_CORE", 0x04: "PEI_CORE", 0x05: "DXE_CORE",
    0x06: "PEIM", 0x07: "DRIVER", 0x08: "COMBINED_PEIM_DRIVER", 0x09: "APPLICATION", 0x0A: "SMM",
    0x0B: "FIRMWARE_VOLUME_IMAGE", 0x0C: "COMBINED_SMM_DXE", 0x0D: "SMM_CORE", 0x0E: "MM_STANDALONE",
    0x0F: "MM_CORE_STANDALONE",
}
SECTION_PE32 = 0x10
SECTION_UI = 0x15
SECTION_GUIDED = 0x02
SECTION_COMPRESSION = 0x01


def ffs_files(d, base, length):
    """[(offset, guid, type, size)] of the FFS files of the volume at base."""
    out = []
    pos = base + 0x48                      # past the FV header (HeaderLength is 0x48 in these images)
    end = base + length
    while pos + 24 <= end:
        guid = d[pos:pos + 16]
        ftype = d[pos + 18]
        size = d[pos + 20] | (d[pos + 21] << 8) | (d[pos + 22] << 16)
        if size < 24 or pos + size > end:
            break
        if guid == b"\xff" * 16:           # free space
            break
        out.append((pos, guid, ftype, size))
        pos += (size + 7) & ~7
    return out


def sections(d, start, end, depth=0):
    """[(type, offset, size)] of the sections of an FFS file or of a section's payload."""
    out = []
    pos = start
    while pos + 4 <= end and depth < 4:
        size = d[pos] | (d[pos + 1] << 8) | (d[pos + 2] << 16)
        stype = d[pos + 3]
        if size < 4 or pos + size > end:
            break
        out.append((stype, pos, size))
        if stype in (SECTION_COMPRESSION, SECTION_GUIDED) and size > 8:
            # a GUIDed/compressed section: its own sections start after a 4-byte header (+16 for guided)
            inner = pos + (20 if stype == SECTION_GUIDED else 8)
            out.extend(sections(d, inner, pos + size, depth + 1))
        pos += (size + 3) & ~3
    return out


def name_of(pe):
    """A name for a PE32 image, from the strings it carries (the module's own name appears in its debug/UI sections)."""
    for pat in (rb"(DisplayDxe|UFSDxe|SmemDxe|ClockDxe|RpmhDxe|PmicDxe|TLMMDxe|I2CDxe|SPIDxe|ChipInfoDxe|PIL[A-Za-z]*Dxe|"
                rb"Usb[A-Za-z]*Dxe|ButtonsDxe|TsensDxe|LimitsDxe|GpiDxe|UCDxe|RngDxe|DDRInfoDxe|FeatureEnablerDxe|"
                rb"SmBiosTableDxe|RamManagerDxe|AcpiTableDxe|GraphicsConsoleDxe|BdsDxe|DxeMain)",):
        m = re.search(pat, pe)
        if m:
            return m.group(1).decode()
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--out", help="write each PE32 image here as <name-or-guid>.efi")
    a = ap.parse_args()
    d = open(a.image, "rb").read()
    i = d.find(b"_FVH")
    if i < 0:
        sys.exit("no _FVH in the image: not a firmware volume")
    base = i - 0x28
    fvlen = struct.unpack("<Q", d[base + 0x20:base + 0x28])[0]
    print("firmware volume at 0x%x, length 0x%x (%d bytes)" % (base, fvlen, fvlen))
    files = ffs_files(d, base, fvlen)
    print("%d FFS files" % len(files))
    total = 0
    if a.out:
        import os
        os.makedirs(a.out, exist_ok=True)
    for pos, guid, ftype, size in files:
        kind = FFS_TYPE.get(ftype, "0x%02x" % ftype)
        g = "%08x-%04x-%04x-%s-%s" % (struct.unpack("<I", guid[0:4])[0], struct.unpack("<H", guid[4:6])[0],
                                      struct.unpack("<H", guid[6:8])[0], guid[8:10].hex(), guid[10:16].hex())
        secs = sections(d, pos + 24, pos + size)
        pe = [(t, o, s) for t, o, s in secs if t == SECTION_PE32]
        note = ""
        if pe:
            blob = d[pe[0][1] + 4:pe[0][1] + pe[0][2]]
            nm = name_of(blob)
            note = " PE32 %d bytes%s" % (pe[0][2] - 4, "  " + nm if nm else "")
            if a.out:
                fname = (nm or g) + ".efi"
                open(os.path.join(a.out, fname), "wb").write(blob)
                note += " -> " + fname
            total += 1
        print("  %08x  %-8s %6d bytes  %s%s" % (pos, kind, size, g[:18], note))
    print("%d PE32 images%s" % (total, " in " + a.out if a.out else ""))


if __name__ == "__main__":
    main()
