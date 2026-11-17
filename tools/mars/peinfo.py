import struct, sys

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]
def u64(b, o): return struct.unpack_from("<Q", b, o)[0]

def sections(b):
    pe = u32(b, 0x3C)
    nsec = u16(b, pe + 6)
    opt = u16(b, pe + 20)
    optoff = pe + 24
    magic = u16(b, optoff)
    base = 0x70 if magic == 0x20b else 0x60  # PE32+ vs PE32 data dir start
    ddoff = optoff + base
    secs = []
    soff = optoff + opt
    for i in range(nsec):
        o = soff + i * 40
        name = b[o:o+8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rsize, raddr = u32(b,o+8), u32(b,o+12), u32(b,o+16), u32(b,o+20)
        secs.append((name, vaddr, vsize, raddr, rsize))
    return secs, ddoff, magic

def rva2off(secs, rva):
    for name, vaddr, vsize, raddr, rsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr)
    return None

def imports(path):
    b = open(path, "rb").read()
    secs, ddoff, magic = sections(b)
    imp_rva = u32(b, ddoff + 8)
    if not imp_rva:
        print("no imports"); return
    off = rva2off(secs, imp_rva)
    out = []
    while True:
        ilt, ts, fc, name_rva, iat = struct.unpack_from("<IIIII", b, off)
        if name_rva == 0: break
        no = rva2off(secs, name_rva)
        dll = b[no:b.index(b"\0", no)].decode("latin1")
        funcs = []
        t = rva2off(secs, ilt) if ilt else rva2off(secs, iat)
        if t:
            while True:
                thunk = u64(b, t) if magic == 0x20b else u32(b, t)
                if thunk == 0: break
                if not (thunk >> (63 if magic==0x20b else 31)):
                    fo = rva2off(secs, thunk & 0x7fffffff)
                    if fo: funcs.append(b[fo+2:b.index(b"\0", fo+2)].decode("latin1"))
                else:
                    funcs.append("#%d" % (thunk & 0xffff))
                t += 8 if magic == 0x20b else 4
        out.append((dll, funcs))
        off += 20
    for dll, funcs in out:
        print("%s (%d): %s" % (dll, len(funcs), ", ".join(funcs[:12]) + (" ..." if len(funcs)>12 else "")))

def exports(path):
    b = open(path, "rb").read()
    secs, ddoff, magic = sections(b)
    exp_rva = u32(b, ddoff)
    if not exp_rva:
        print("no exports"); return
    off = rva2off(secs, exp_rva)
    name_rva = u32(b, off+12)
    nfuncs = u32(b, off+20)
    nnames = u32(b, off+24)
    funcs_rva = u32(b, off+28)
    names_rva = u32(b, off+32)
    fo = rva2off(secs, funcs_rva)
    no = rva2off(secs, names_rva)
    names = []
    for i in range(nnames):
        nr = u32(b, no + i*4)
        o = rva2off(secs, nr)
        names.append(b[o:b.index(b"\0", o)].decode("latin1"))
    print("exports:", nfuncs, "names:", names)
    # forwarders
    fwd = []
    for i in range(nfuncs):
        frva = u32(b, fo + i*4)
        if frva and exp_rva <= frva < exp_rva + 0x200:
            o = rva2off(secs, frva)
            fwd.append(b[o:b.index(b"\0", o)].decode("latin1"))
    if fwd: print("forwarders:", fwd[:20], "... total", len(fwd))

if __name__ == "__main__":
    path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "imports"
    print("==", path, mode)
    if mode == "imports": imports(path)
    else: exports(path)
