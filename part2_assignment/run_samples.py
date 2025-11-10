#!/usr/bin/env python3
"""
part2_assignment/run_samples.py

Runs sample test cases for the Factory and Belts tools.
Usage:
    python run_samples.py "python factory/main.py" "python belts/main.py"

If you omit the arguments, defaults are used.
"""

import os
import sys
import subprocess
import json
import shlex
import textwrap

DEFAULT_FACTORY_CMD = "python factory/main.py"
DEFAULT_BELTS_CMD = "python belts/main.py"
TIMEOUT = 2 # seconds
def run_cli(cmd, inp):
    args = shlex.split(cmd)
    try:
        p = subprocess.run(args, input=json.dumps(inp).encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=2)
    except subprocess.TimeoutExpired:
        # Retry once with a longer timeout
        p = subprocess.run(args, input=json.dumps(inp).encode(),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=10)
    out = p.stdout.decode().strip()
    return json.loads(out)


def run_factory_sample(factory_cmd):
    print("▶ Running Factory sample…")
    inp = {
      "machines": {
        "assembler_1": {"crafts_per_min": 30},
        "chemical": {"crafts_per_min": 60}
      },
      "recipes": {
        "iron_plate": {
          "machine": "chemical",
          "time_s": 3.2,
          "in": {"iron_ore": 1},
          "out": {"iron_plate": 1}
        },
        "copper_plate": {
          "machine": "chemical",
          "time_s": 3.2,
          "in": {"copper_ore": 1},
          "out": {"copper_plate": 1}
        },
        "green_circuit": {
          "machine": "assembler_1",
          "time_s": 0.5,
          "in": {"iron_plate": 1, "copper_plate": 3},
          "out": {"green_circuit": 1}
        }
      },
      "modules": {
        "assembler_1": {"prod": 0.1, "speed": 0.15},
        "chemical": {"prod": 0.2, "speed": 0.1}
      },
      "limits": {
        "raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 5000},
        "max_machines": {"assembler_1": 300, "chemical": 300}
      },
      "target": {"item": "green_circuit", "rate_per_min": 1800}
    }
    out = run_cli(factory_cmd, inp)
    if not out:
        return
    if out.get("status") == "ok":
        print("✅ Factory sample passed:")
        print(json.dumps(out, indent=2))
    else:
        print("⚠️ Factory returned non-ok:", json.dumps(out, indent=2))

def run_belts_sample(belts_cmd):
    print("\n▶ Running Belts sample…")
    inp = {
      "nodes": ["s1", "s2", "a", "b", "c", "sink"],
      "edges": [
        {"from":"s1","to":"a","lo":0,"hi":1000},
        {"from":"s2","to":"a","lo":0,"hi":1000},
        {"from":"a","to":"b","lo":0,"hi":1000},
        {"from":"b","to":"sink","lo":0,"hi":900},
        {"from":"a","to":"c","lo":0,"hi":1000},
        {"from":"c","to":"sink","lo":0,"hi":600}
      ],
      "sources": {"s1":900, "s2":600},
      "sink": "sink",
      "node_caps": {}
    }
    out = run_cli(belts_cmd, inp)
    if not out:
        return
    if out.get("status") == "ok":
        print("✅ Belts sample passed:")
        print(json.dumps(out, indent=2))
    else:
        print("⚠️ Belts returned non-ok:", json.dumps(out, indent=2))

def main():
    factory_cmd = sys.argv[1] if len(sys.argv) >= 2 else DEFAULT_FACTORY_CMD
    belts_cmd = sys.argv[2] if len(sys.argv) >= 3 else DEFAULT_BELTS_CMD
    print(textwrap.dedent(f"""
    =====================================================
    ERP.AI Engineering Assessment — Part 2 Sample Runner
    =====================================================
    Factory command: {factory_cmd}
    Belts command:   {belts_cmd}
    -----------------------------------------------------
    """).strip())

    run_factory_sample(factory_cmd)
    run_belts_sample(belts_cmd)
    print("\nAll sample runs completed.\n")

if __name__ == "__main__":
    main()
