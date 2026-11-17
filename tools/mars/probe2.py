import json, struct

path = r"E:\下载\OvRa_XiaomiPCManager_feature_p52_5.8.1.121_7fe7f58b.exe"
BASE = 12165120
f = open(path, "rb")
f.seek(BASE)
hdr = f.read(32)
magic = hdr[:4]
jlen = struct.unpack_from("<I", hdr, 28)[0]
print("magic:", magic, "jsonlen:", jlen, "hdr8:", struct.unpack_from("<I", hdr, 8)[0])
raw = f.read(jlen)
f.close()
print("read:", len(raw), "starts:", raw[:2], "ends:", raw[-2:])
obj = json.loads(raw.decode("utf-8"))
print("top keys:", list(obj.keys()))
for k in ("support_tm_list", "support_nfc_list", "support_distfile_list"):
    v = obj.get(k)
    if isinstance(v, list):
        print(k, len(v), v)
    else:
        print(k, "MISSING/", type(v))
print("companyName:", obj.get("companyName"))
print("productName:", obj.get("productName"))
print("defaultInstallDir:", obj.get("defaultInstallDir"))
print("version:", obj.get("version"), obj.get("productVersion"))
