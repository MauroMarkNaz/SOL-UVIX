# Independent Python cross-check of the JS module (stdlib only).
import hashlib, json, sys
H=lambda *p: hashlib.sha256(b"".join(p)).digest()
def mth(l):
    if not l: return H(b"")
    if len(l)==1: return l[0]
    k=1
    while k*2<len(l): k*=2
    return H(b"\x01",mth(l[:k]),mth(l[k:]))
def canon(v):  # Python json with sort_keys/compact == JCS for these string/int entries (ensure_ascii=False)
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
es=[json.loads(x) for x in open("vectors/uvix-chain-snapshot-2026-10-28.jsonl",encoding="utf8") if x.strip()]
prev="GENESIS"
for e in es:
    h=hashlib.sha256(canon({k:e[k] for k in ("node","prevHash","seq","text","ts")}).encode()).hexdigest()
    assert e["prevHash"]==prev and h==e["hash"], e["seq"]; prev=h
lh=[H(b"\x00",bytes.fromhex(e["hash"])) for e in es]
print("py root n=%d %s"%(len(es),mth(lh).hex()))
