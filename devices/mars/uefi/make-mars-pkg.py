#!/usr/bin/env python3
"""Make devices/mars/uefi/files/Platforms/Xiaomi/marsPkg from Mu-Silicium's venusPkg.

venus is the Xiaomi Mi 11 (SM8350, 1440x3200) -- the nearest neighbour a Mi 11 Pro has in Mu-Silicium. This script fetches
venus's platform files, renames them, and changes only what is this phone's: the SMBIOS strings, the platform GUID, and the
comments that name the phone. The SoC facts (the memory map, the configuration map, LahainaPkg, the panel's size) are the
same on both phones and are kept as they are.

Run it once, from the top of the common tree, then delete it: the files it writes are the port's, not a build step.
"""
import os
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/Project-Silicium/Mu-Silicium/main/Platforms/Xiaomi/venusPkg"
TOML = "https://raw.githubusercontent.com/Project-Silicium/Mu-Silicium/main/Resources/Configs/venus.toml"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "files", "Platforms", "Xiaomi", "marsPkg")

FILES = [
    "venus.dec",
    "venus.dsc",
    "venus.fdf",
    "DeviceBuild.py",
    "Include/APRIORI.inc",
    "Include/DXE.inc",
    "Include/RAW.inc",
    "Library/MemoryMapLib/MemoryMapLib.c",
    "Library/MemoryMapLib/MemoryMapLib.inf",
    "Library/ConfigurationMapLib/ConfigurationMapLib.c",
    "Library/ConfigurationMapLib/ConfigurationMapLib.inf",
]

GUID_FROM = "03624C85-9D74-4E7E-85FF-A6B77DC2EEFA"   # venus's PLATFORM_GUID
GUID_TO = "7C1E5D2A-4B93-4E6C-9F2D-3A8B6C5E1D74"     # mars's: made for this port

# the order matters: the longer, more specific strings first
RENAMES = [
    ("03624C85-9D74-4E7E-85FF-A6B77DC2EEFA", GUID_TO),
    ("M2011K2G", "M2102K1AC"),                       # venus's retail SKU -> mars's model number
    ('"K2G"', '"mars"'),                             # venus's board model -> this phone's codename
    ('"Mi 11"', '"Mi 11 Pro"'),                      # the SMBIOS model
    ("venusPkg", "marsPkg"),
    ("venus", "mars"),
]


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


def main():
    written = []
    for name in FILES:
        data = fetch(BASE + "/" + name).decode("utf-8")
        for old, new in RENAMES:
            data = data.replace(old, new)
        out = os.path.join(OUT, name.replace("venus", "mars"))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(data)
        written.append(os.path.relpath(out, HERE))

    # the boot shim's own configuration: the same file redwood and venus have (base 0x9FD00000, 2 MB)
    toml = fetch(TOML).decode("utf-8")
    out = os.path.join(HERE, "files", "Resources", "Configs", "mars.toml")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(toml)
    written.append(os.path.relpath(out, HERE))

    for w in written:
        print("wrote", w)
    # a rename that missed would be a silent copy of another phone's platform
    for w in written:
        text = open(os.path.join(HERE, w), encoding="utf-8", errors="replace").read()
        for word in ("venus", "Venus", "M2011K2G", GUID_FROM):
            if word in text:
                print("WARNING: %s still says %r" % (w, word))
    return 0


if __name__ == "__main__":
    sys.exit(main())
