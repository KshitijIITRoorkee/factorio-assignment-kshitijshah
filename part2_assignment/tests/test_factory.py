import os
import shlex
import subprocess
import json
import math
import pytest

FACTORY_CMD = os.environ.get("FACTORY_CMD", "python factory/main.py")
TIMEOUT = 2  # seconds
EPS = 1e-6

def run_cli(cmd, inp):
    args = shlex.split(cmd)
    p = subprocess.run(args, input=json.dumps(inp).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    out = p.stdout.decode().strip()
    # Ensure no extraneous prints: stdout must be valid JSON
    return json.loads(out)

def approx_eq(a, b, eps=EPS):
    return abs(a-b) <= eps

def test_factory_sample_ok():
    # Example from the prompt (green circuit)
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

    out = run_cli(FACTORY_CMD, inp)
    assert out.get("status") == "ok"
    per_recipe = out.get("per_recipe_crafts_per_min", {})
    per_machine = out.get("per_machine_counts", {})
    raw_cons = out.get("raw_consumption_per_min", {})

    # Expected values from the prompt sample
    assert approx_eq(per_recipe.get("green_circuit", -1), 1800.0)
    assert approx_eq(per_recipe.get("iron_plate", -1), 1800.0)
    assert approx_eq(per_recipe.get("copper_plate", -1), 5400.0)

    # Machine counts: order-independent; test approximate equality
    assert approx_eq(per_machine.get("chemical", -1), 50.0)
    assert approx_eq(per_machine.get("assembler_1", -1), 60.0)

    # Raw consumption
    assert approx_eq(raw_cons.get("iron_ore", -1), 1800.0)
    assert approx_eq(raw_cons.get("copper_ore", -1), 5400.0)

def test_factory_infeasible_limits():
    # Make the raw caps too small so the target is infeasible
    inp = {
      "machines": {
        "assembler_1": {"crafts_per_min": 30},
      },
      "recipes": {
        "widget": {
          "machine": "assembler_1",
          "time_s": 1.0,
          "in": {"iron_ore": 10},
          "out": {"widget": 1}
        }
      },
      "modules": {},
      "limits": {
        "raw_supply_per_min": {"iron_ore": 100},  # too small to reach target
        "max_machines": {"assembler_1": 10}
      },
      "target": {"item": "widget", "rate_per_min": 200}
    }
    out = run_cli(FACTORY_CMD, inp)
    assert out.get("status") == "infeasible"
    # Expect max_feasible_target_per_min provided and some bottleneck hints
    assert "max_feasible_target_per_min" in out
    assert isinstance(out.get("bottleneck_hint", []), list)
    assert len(out["bottleneck_hint"]) >= 1

