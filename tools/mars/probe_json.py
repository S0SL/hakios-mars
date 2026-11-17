import json, struct

path = r"E:\下载\OvRa_XiaomiPCManager_feature_p52_5.8.1.121_7fe7f58b.exe"
f = open(path, "rb")
f.seek(12165120)
head = f.read(200 * 1024)
print("head:", head[:40].hex(" "))
print("head ascii:", head[:40])

i = head.find(b"{")
dec = json.JSONDecoder()
obj, end = dec.raw_decode(head[i:].decode("utf-8", "replace"))
print("json offset in block:", i, "consumed:", end)
print("keys:", list(obj.keys()))
for k, v in obj.items():
    if isinstance(v, list):
        print(k, "list len", len(v), "sample", v[:8])
    elif isinstance(v, str) and len(v) > 80:
        print(k, "str len", len(v))
    else:
        print(k, "=", v)

# check length field
print("len field @12165124:", struct.unpack_from("<I", head, 4)[0])
print("next 4:", struct.unpack_from("<I", head, 8)[0])
