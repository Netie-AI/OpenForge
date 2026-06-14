import json
import urllib.request

req = json.load(open("scripts/req.json"))
data = json.dumps(req).encode()
r = urllib.request.urlopen(
    urllib.request.Request(
        "http://127.0.0.1:8080/api/design",
        data=data,
        headers={"Content-Type": "application/json"},
    ),
    timeout=120,
)
d = json.load(r)
print("meets_all:", d.get("meets_all"), " score:", d.get("score"))
print("part:", d.get("spec", {}).get("part"), " source:", d.get("spec", {}).get("source"))
print("metrics:", d.get("metrics"))
print("devices:", len(d.get("devices", [])), " netlist_lines:", len(d.get("netlist", "").splitlines()))
print("--- compliance ---")
for k, v in d.get("compliance", {}).items():
    print(f"  {k:10s} target={v['target']} measured={v['measured']} pass={v['pass']}")
print("--- netlist head ---")
print("\n".join(d.get("netlist", "").splitlines()[:12]))
