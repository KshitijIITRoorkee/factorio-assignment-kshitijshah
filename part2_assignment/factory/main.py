#!/usr/bin/env python3
"""
part2_assignment/factory/main.py

Reads JSON from stdin and writes a single JSON object to stdout (no extra prints).
Deterministic LP formulation using scipy.optimize.linprog (HiGHS).
"""

import sys
import json
from collections import defaultdict

EPS = 1e-9

def read_json():
    try:
        return json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"status":"error","message":f"invalid json stdin: {e}"}))
        sys.exit(0)

def write_json(obj):
    # deterministic key order in output for identical inputs
    sys.stdout.write(json.dumps(obj, separators=(",", ":"), sort_keys=True))

try:
    from scipy.optimize import linprog
except Exception as e:
    write_json({"status":"error","message":"scipy required: install scipy to run this tool (pip install scipy)"})
    sys.exit(0)

def build_lp(data, add_target_var=False, fixed_target=None):
    # Parse input
    machines = dict(data.get("machines", {}))
    recipes = dict(data.get("recipes", {}))
    modules = dict(data.get("modules", {}))
    limits = data.get("limits", {})
    raw_caps = dict(limits.get("raw_supply_per_min", {}))
    max_machines = dict(limits.get("max_machines", {}))
    target = data.get("target", {})
    target_item = target.get("item")
    target_rate = float(target.get("rate_per_min", 0.0)) if target else 0.0

    # Validate
    if target_item is None:
        return {"status":"error","message":"target item missing"}

    # Preprocess machines: speeds and module multipliers
    for mname, m in machines.items():
        m.setdefault("crafts_per_min", 0.0)
        mm = modules.get(mname, {})
        speed = float(mm.get("speed", 0.0))
        prod = float(mm.get("prod", 0.0))
        m["_speed_mult"] = 1.0 + speed
        m["_prod"] = prod

    # Sorted recipe list for deterministic ordering
    recipe_list = sorted(recipes.keys())
    R = len(recipe_list)

    # Build list of all items
    items = set()
    for rname in recipe_list:
        rr = recipes[rname]
        for k in rr.get("in", {}):
            items.add(k)
        for k in rr.get("out", {}):
            items.add(k)
    items.add(target_item)
    items = sorted(items)
    item_index = {it:i for i,it in enumerate(items)}
    I = len(items)

    # Compute eff crafts/min and per-recipe prod
    eff = []
    prod = []
    recipe_machine = []
    for rname in recipe_list:
        rr = recipes[rname]
        mname = rr["machine"]
        recipe_machine.append(mname)
        time_s = float(rr["time_s"])
        m = machines[mname]
        crafts_per_min = float(m["crafts_per_min"]) * float(m["_speed_mult"]) * 60.0 / time_s
        eff.append(crafts_per_min)
        prod.append(float(m["_prod"]))

    # Build coef matrix: for item i and recipe j: coef = out * (1+prod) - in
    coef = [[0.0]*R for _ in range(I)]
    for j,rname in enumerate(recipe_list):
        rr = recipes[rname]
        p = prod[j]
        for it, v in rr.get("out", {}).items():
            coef[item_index[it]][j] += float(v) * (1.0 + p)
        for it, v in rr.get("in", {}).items():
            coef[item_index[it]][j] -= float(v)

    # Variables: x[0..R-1] crafts/min ; optionally t at index R
    var_count = R + (1 if add_target_var else 0)
    # Objective: minimize total machines used = sum (1/eff_j) * x_j
    c = [1.0/eff_j for eff_j in eff]
    if add_target_var:
        c.append(-1.0)  # minimize -t -> maximize t

    # Bounds: x_j >= 0 ; t >= 0
    bounds = [(0.0, None)] * var_count

    A_eq = []
    b_eq = []
    A_ub = []
    b_ub = []

    # Target equality:
    targ_row = [coef[item_index[target_item]][j] for j in range(R)]
    if add_target_var:
        targ_row = targ_row + [-1.0]
        A_eq.append(targ_row)
        b_eq.append(0.0)
    else:
        A_eq.append(targ_row)
        b_eq.append(float(fixed_target if fixed_target is not None else target_rate))

    # Intermediates: produced by some recipe and not raw and not target => balance 0
    raw_items = set(raw_caps.keys())
    for it in items:
        if it == target_item: continue
        if it in raw_items: continue
        idx = item_index[it]
        row = [coef[idx][j] for j in range(R)]
        if any(abs(v) > EPS for v in row):
            if add_target_var:
                row = row + [0.0]
            A_eq.append(row)
            b_eq.append(0.0)

    # Raw items: two constraints per raw item:
    # 1) sum_out - sum_in <= 0  (cannot be net producer)
    # 2) sum_in - sum_out <= cap  -> -(sum_out - sum_in) <= cap
    for it in raw_items:
        if it not in item_index: continue
        idx = item_index[it]
        row = [coef[idx][j] for j in range(R)]
        row1 = row + ([0.0] if add_target_var else [])
        A_ub.append(row1)
        b_ub.append(0.0)
        row2 = [ -v for v in row ]
        row2 = row2 + ([0.0] if add_target_var else [])
        A_ub.append(row2)
        b_ub.append(float(raw_caps.get(it, 0.0)))

    # Machine caps: sum_j x_j / eff_j for recipes assigned to machine m <= max_machines[m]
    # Build deterministic ordering of machines
    for mname in sorted(machines.keys()):
        row = [0.0]*R
        for j in range(R):
            if recipe_machine[j] == mname:
                row[j] = 1.0/eff[j]
        if any(abs(v) > EPS for v in row):
            row = row + ([0.0] if add_target_var else [])
            A_ub.append(row)
            b_ub.append(float(max_machines.get(mname, 0.0)))

    # Call linprog (HiGHS). Provide small tolerances and deterministic method.
    try:
        res = linprog(c=c, A_ub=(A_ub if A_ub else None), b_ub=(b_ub if b_ub else None),
                      A_eq=(A_eq if A_eq else None), b_eq=(b_eq if b_eq else None),
                      bounds=bounds, method="highs", options={"tol":1e-9})
    except Exception as e:
        return {"status":"error","message":f"solver error: {e}"}

    return {
        "res": res,
        "recipe_list": recipe_list,
        "eff": eff,
        "recipe_machine": recipe_machine,
        "item_index": item_index,
        "coef": coef,
        "machines": machines,
        "raw_items": raw_items,
        "raw_caps": raw_caps,
        "max_machines": max_machines
    }

def build_ok_output(solved):
    res = solved["res"]
    recipe_list = solved["recipe_list"]
    eff = solved["eff"]
    recipe_machine = solved["recipe_machine"]
    coef = solved["coef"]
    item_index = solved["item_index"]
    raw_items = solved["raw_items"]

    x = [float(v) for v in res.x[:len(recipe_list)]]
    per_recipe = { recipe_list[i]: x[i] for i in range(len(recipe_list)) }

    per_machine_counts = defaultdict(float)
    for i, r in enumerate(recipe_list):
        m = recipe_machine[i]
        per_machine_counts[m] += x[i] / eff[i]
    per_machine_counts = { m: per_machine_counts[m] for m in sorted(per_machine_counts.keys()) }

    raw_consumption = {}
    for it in sorted(raw_items):
        idx = item_index.get(it)
        if idx is None:
            raw_consumption[it] = 0.0
            continue
        net = 0.0
        for j in range(len(recipe_list)):
            # coef is (out - in); net consumption = -(out - in) * x_j
            net += -coef[idx][j] * x[j]
        raw_consumption[it] = max(0.0, net)

    return {
        "status":"ok",
        "per_recipe_crafts_per_min": per_recipe,
        "per_machine_counts": per_machine_counts,
        "raw_consumption_per_min": raw_consumption
    }

def build_infeasible_output(solved):
    # solved should be from maximize-target run (t variable)
    res = solved["res"]
    recipe_list = solved["recipe_list"]
    eff = solved["eff"]
    recipe_machine = solved["recipe_machine"]
    coef = solved["coef"]
    item_index = solved["item_index"]
    raw_items = solved["raw_items"]
    max_machines = solved["max_machines"]
    raw_caps = solved["raw_caps"]

    if (not hasattr(res, "success")) or (not res.success and res.status != 4):
        max_t = 0.0
        x = [0.0]*len(recipe_list)
    else:
        max_t = float(res.x[-1])
        x = [float(v) for v in res.x[:len(recipe_list)]]

    # bottleneck hints: machines at cap, raw at cap
    hints = []
    machine_usage = defaultdict(float)
    for i in range(len(recipe_list)):
        m = recipe_machine[i]
        machine_usage[m] += x[i] / eff[i]
    for m in sorted(machine_usage.keys()):
        usage = machine_usage[m]
        cap = float(max_machines.get(m, 0.0))
        if usage >= cap - 1e-6:
            hints.append(f"{m} cap")
    for it in sorted(raw_items):
        idx = item_index.get(it)
        if idx is None: continue
        net = 0.0
        for j in range(len(recipe_list)):
            net += -coef[idx][j] * x[j]
        cap = float(raw_caps.get(it, 0.0))
        if net >= cap - 1e-6:
            hints.append(f"{it} supply")
    hints = sorted(list(dict.fromkeys(hints)))
    return {"status":"infeasible","max_feasible_target_per_min": max_t, "bottleneck_hint": hints}

def main():
    data = read_json()
    # Phase 1: try to find feasible x for requested target
    lp = build_lp(data, add_target_var=False, fixed_target=data.get("target",{}).get("rate_per_min", None))
    if isinstance(lp, dict) and lp.get("status") == "error":
        write_json(lp); return

    res = lp["res"]
    if res.success:
        out = build_ok_output(lp)
        write_json(out)
        return

    # Phase 2: maximize achievable target by adding t variable (we maximize t by minimizing -t)
    lp_max = build_lp(data, add_target_var=True, fixed_target=None)
    if isinstance(lp_max, dict) and lp_max.get("status") == "error":
        write_json(lp_max); return

    out = build_infeasible_output(lp_max)
    write_json(out)

if __name__ == "__main__":
    main()
