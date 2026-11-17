import json, struct, shutil, sys, time

SRC = r"E:\下载\OvRa_XiaomiPCManager_feature_p52_5.8.1.121_7fe7f58b.exe"
DST = r"E:\下载\XiaomiPCManager_5.8.1.121_patched.exe"
BASE = 12165120
JLEN = 136180
MODEL = "GL62 6QF"

t0 = time.time()
shutil.copyfile(SRC, DST)
print("copied in %.1fs" % (time.time() - t0))

with open(DST, "r+b") as f:
    f.seek(BASE)
    hdr = f.read(32)
    assert hdr[:4] == b"TS\x00\x00", hdr[:4]
    assert struct.unpack_from("<I", hdr, 28)[0] == JLEN
    f.seek(BASE + 32)
    raw = f.read(JLEN)
    obj = json.loads(raw.decode("utf-8"))
    for k in ("support_tm_list", "support_nfc_list", "support_distfile_list"):
        lst = obj[k]
        if MODEL not in lst:
            lst.append(MODEL)
    # also add uppercase variant just in case comparison is case-sensitive
    up = MODEL.upper()
    for k in ("support_tm_list", "support_nfc_list", "support_distfile_list"):
        if up not in obj[k]:
            obj[k].append(up)
    compact = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    print("compact len:", len(compact), "budget:", JLEN)
    if len(compact) > JLEN:
        sys.exit("does not fit")
    new = compact + b" " * (JLEN - len(compact))
    json.loads(new.decode("utf-8"))  # sanity
    f.seek(BASE + 32)
    f.write(new)
    f.flush()

# verify
with open(DST, "rb") as f:
    f.seek(BASE + 32)
    chk = json.loads(f.read(JLEN).decode("utf-8"))
print("tm_list has model:", MODEL in chk["support_tm_list"], "count:", len(chk["support_tm_list"]))
print("done")
