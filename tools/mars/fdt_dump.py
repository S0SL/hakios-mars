#!/usr/bin/env python3
"""Dump an FDT subtree and resolve phandles for clocks/pinctrl."""
import struct, sys
from pathlib import Path

FDT_BEGIN_NODE, FDT_END_NODE, FDT_PROP, FDT_NOP, FDT_END = 1, 2, 3, 4, 9


def parse(path):
    data = Path(path).read_bytes()
    (magic, totalsize, off_struct, off_strings, off_rsv, version,
     last_comp, boot_cpuid, size_strings, size_struct) = struct.unpack_from(
        ">10I", data, 0)
    assert magic == 0xD00DFEED
    strings = data[off_strings:off_strings + size_strings]
    pos = off_struct
    stack = []         # property dicts, one per depth
    node_path = []

    def cstr(off):
        end = strings.index(b"\0", off)
        return strings[off:end].decode("ascii", "replace")

    out = []
    while True:
        tok = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if tok == FDT_BEGIN_NODE:
            end = data.index(b"\0", pos)
            name = data[pos:end].decode("ascii", "replace")
            pos = (end + 4) & ~3
            node_path.append(name)
            stack.append({})
        elif tok == FDT_END_NODE:
            out.append(("/".join(node_path), stack.pop()))
            node_path.pop()
            if not stack:
                break
        elif tok == FDT_PROP:
            plen, nameoff = struct.unpack_from(">II", data, pos)
            pos += 8
            blob = data[pos:pos + plen]
            pos += plen
            pos += (4 - (plen & 3)) & 3
            stack[-1][cstr(nameoff)] = blob
        elif tok == FDT_NOP:
            continue
        elif tok == FDT_END:
            break
        else:
            raise ValueError(f"token {tok} at {pos}")
    return out


def u32s(b):
    return list(struct.unpack(">%dI" % (len(b) // 4), b))


def main():
    nodes = parse(sys.argv[1])
    want = sys.argv[2] if len(sys.argv) > 2 else "spi@a8c000"
    phmap = {}
    for path, props in nodes:
        if "phandle" in props:
            ph = u32s(props["phandle"])[0]
            phmap[ph] = path
        elif "linux,phandle" in props:
            ph = u32s(props["linux,phandle"])[0]
            phmap[ph] = path
    target = [ (p, pr) for p, pr in nodes if want in p ]
    for path, props in target:
        print("=" * 60)
        print("NODE /" + path)
        for k, v in props.items():
            if k in ("clock-names", "pinctrl-names", "qcom,spi-prototype",
                     "compatible", "status", "label") or b"\0" in v:
                try:
                    s = v.split(b"\0")
                    print(f"  {k} = {[x.decode('ascii','replace') for x in s if x]}")
                    continue
                except Exception:
                    pass
            if k in ("clocks", "interrupts", "interrupt-parent", "reg",
                     "qcom,se-irq", "reset-gpios", "gpios", "spi-max-frequency",
                     "pinctrl-0", "pinctrl-1", "power-supply", "se_phys",
                     "qcom,gpio-tblmm", "qcom,gpio-dge") or len(v) % 4 == 0:
                vals = u32s(v) if len(v) % 4 == 0 else None
                if vals is not None:
                    print(f"  {k} = {[hex(x) for x in vals]}")
                    if k in ("clocks", "interrupt-parent", "pinctrl-0", "pinctrl-1"):
                        for x in vals:
                            if x in phmap:
                                print(f"      phandle {x} -> /{phmap[x]}")
                    continue
            print(f"  {k} = {v.hex()}")

    # print pinctrl sub-nodes referenced
    print("\n--- referenced pin/clock nodes ---")
    seen = set()
    for path, props in target:
        for key in ("pinctrl-0", "pinctrl-1", "clocks"):
            if key in props and len(props[key]) % 4 == 0:
                for x in u32s(props[key]):
                    if x in phmap and x not in seen:
                        seen.add(x)
                        sub = [(p, pr) for p, pr in nodes if p == phmap[x]]
                        for p, pr in sub:
                            print(f"/{p}")
                            for k, v in pr.items():
                                if len(v) % 4 == 0 and k != "phandle":
                                    print(f"  {k} = {[hex(i) for i in u32s(v)]}")
                                else:
                                    try:
                                        print(f"  {k} = {v.split(chr(0).encode())[0].decode()}")
                                    except Exception:
                                        print(f"  {k} = {v.hex()}")


if __name__ == "__main__":
    main()
