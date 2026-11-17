import json, struct, sys

path = r"E:\下载\OvRa_XiaomiPCManager_feature_p52_5.8.1.121_7fe7f58b.exe"
data = open(path, "rb").read()
print("size", len(data))

found = []
start = 0
while True:
    i = data.find(b'"companyName"', start)
    if i < 0:
        break
    start = i + 1
    j = data.rfind(b'{', 0, i)
    if j < 32:
        continue
    jlen = struct.unpack_from("<I", data, j - 4)[0]
    if jlen < 1024 or j + jlen > len(data):
        continue
    raw = data[j:j + jlen]
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        continue
    if isinstance(obj, dict) and "companyName" in obj:
        found.append((j, jlen, obj))
        print("MANIFEST at 0x%x len=%d keys=%s" % (j, jlen, list(obj.keys())[:20]))

for off, ln, obj in found[:3]:
    print("----")
    print("companyName:", obj.get("companyName"))
    for k in ("support_tm_list", "support_nfc_list", "support_distfile_list"):
        v = obj.get(k)
        if isinstance(v, list):
            print(k, "count=", len(v), "sample=", v[:10])
