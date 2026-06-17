#!/usr/bin/env python3
"""Hardened Phase 0.4 verification — ngspice reachability + design API."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
BASE = f"http://{HOST}:{PORT}"


def get(path: str, timeout: int = 30) -> dict:
    with urllib.request.urlopen(f"{BASE}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode())


def post(path: str, body: dict, timeout: int = 180) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main() -> int:
    print(f"=== Phase 0.4 verify @ {BASE} ===")
    fails = 0

    print("\n[1/3] Health probe x5")
    for i in range(1, 6):
        try:
            h = get("/api/health")
        except Exception as exc:
            print(f"  {i}/5 FAIL: {exc}")
            fails += 1
            continue
        ok = h.get("ngspice_available") is True and h.get("ngspice_probe") == "ok"
        mark = "OK" if ok else "FAIL"
        print(f"  {i}/5 {mark}: ngspice_available={h.get('ngspice_available')} probe={h.get('ngspice_probe')}")
        if not ok:
            fails += 1
        time.sleep(2)

    cases = [
        ("opamp", {"text": "RS722 high precision low offset op-amp", "budget": 60, "use_llm": False, "category": "opamp"}),
        ("comparator", {"spec": "tp<1us vos<5mV iq<10uA", "budget": 60, "use_llm": False, "category": "comparator"}),
    ]
    print("\n[2/3] POST /api/design x2")
    for name, body in cases:
        try:
            d = post("/api/design", body)
        except Exception as exc:
            print(f"  {name} FAIL: {exc}")
            fails += 1
            continue
        metrics = d.get("metrics") or {}
        non_null = {k: v for k, v in metrics.items() if v is not None}
        netlist = d.get("netlist") or ""
        ok = len(non_null) >= 2 and bool(netlist.strip())
        mark = "OK" if ok else "FAIL"
        print(f"  {name} {mark}: metrics={len(non_null)} netlist_lines={len(netlist.splitlines())}")
        if not ok:
            fails += 1
            print(f"    metrics={metrics}")

    print("\n[3/3] Netlist + schematic fields")
    try:
        d = post("/api/design", cases[0][1])
        nl_ok = "M1" in (d.get("netlist") or "")
        sch = d.get("schematic_svg") or ""
        if not sch and d.get("has_schematic"):
            with urllib.request.urlopen(f"{BASE}/api/schematic.svg", timeout=30) as r:
                sch = r.read().decode()
        sch_ok = "M1" in sch and "device graph" in sch
        print(f"  netlist_has_M1={nl_ok} schematic_device_graph={sch_ok}")
        if not (nl_ok and sch_ok):
            fails += 1
    except Exception as exc:
        print(f"  rendering check FAIL: {exc}")
        fails += 1

    if fails:
        print(f"\nPHASE 0.4 VERIFY FAILED ({fails} checks)")
        return 1
    print("\nPHASE 0.4 VERIFY PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
