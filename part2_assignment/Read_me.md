# ERP.AI Engineering Assessment – Part 2  
## Factory Steady State & Bounded Belts

This submission provides two deterministic command-line tools that read JSON on **stdin** and write JSON on **stdout**, with **no extra output**.  
Each tool completes in ≤2 seconds per case on a normal laptop.

---

## 🏭 Factory (`factory/main.py`)

### **Problem**
Given machines, recipes, modules, and capacity limits, compute non-negative per-recipe craft rates such that:
- The **target item** is produced at the requested rate (exactly).
- All **intermediate items** are perfectly balanced (steady state).
- **Raw items** are consumed but not produced, and remain within supply caps.
- **Machine count limits** per machine type are respected.

If infeasible, report the **maximum feasible target rate** and key bottlenecks.

---

### **Modeling & LP Formulation**

Let `x_r ≥ 0` be the number of crafts/min of recipe `r`.

#### **Conservation (steady state)**  
For each item `i`:
Σ_r [ out_r[i] * (1 + prod_m) * x_r ] − Σ_r [ in_r[i] * x_r ] = b[i]

where:
- `b[target_item] = target_rate`
- `b[intermediates] = 0`
- `b[raw_items] ≤ 0` (limited by raw cap)

#### **Machine usage constraints**
For each machine type `m`:

Σ_{r using m} x_r / eff_crafts_per_min(r) ≤ max_machines[m]

where

eff_crafts_per_min(r) = base_speed_m * (1 + speed_mod) * 60 / recipe_time_s


#### **Objective**
Minimize total machines:

minimize Σ_r x_r / eff_crafts_per_min(r)

This acts as a tie-breaker for multiple feasible solutions.

#### **Infeasibility detection**
Two-phase LP:
1. Try to satisfy the requested target rate exactly.
2. If infeasible, add an auxiliary variable `t` (target) and **maximize** it by minimizing `−t`.

---

### **Handling Details**
- **Cycles & byproducts:** handled naturally by the steady-state equations (`b[i] = 0`).
- **Modules:** applied per machine type; speed affects time scaling, productivity multiplies outputs only.
- **Determinism:**  
  - Recipes and machines processed in lexicographic order.  
  - Solver: `scipy.optimize.linprog` with `method="highs"` and fixed tolerance `1e−9`.
- **Tolerance:**  
  - Conservation: `|balance| < 1e−9`  
  - Caps: ≤ cap + `1e−9`
- **Infeasible output** includes bottleneck hints like `"assembler_1 cap"` or `"iron_ore supply"`.

---

## 🔀 Belts (`belts/main.py`)

### **Problem**
Given a directed conveyor graph with:
- edge lower/upper bounds (`lo ≤ f ≤ hi`)
- node throughput caps
- fixed supplies (multiple sources)
- single sink with demand equal to total supply

Determine if there exists a feasible flow satisfying all constraints.

---

### **Algorithm Overview**

#### **1. Node-splitting for capacity caps**
For each capped node `v`:
- Replace `v` by `v_in → v_out` with capacity `cap(v)`.
- Redirect all incoming edges to `v_in`, outgoing edges from `v_out`.

#### **2. Lower-bound transformation**
For each edge `(u→v)` with `[lo, hi]`:
- Reduce capacity to `hi−lo`.
- Add imbalance `+lo` at `v` and `−lo` at `u`.

#### **3. Feasibility check**
Build a temporary network with a super-source `s*` and super-sink `t*`:
- Connect `s* → node` for positive imbalance.
- Connect `node → t*` for negative imbalance.
- Run **max-flow** (`Dinic`) from `s*` to `t*`.
- If all demands are satisfied (flow = Σ demands), the lower bounds are feasible.

#### **4. Flow recovery**
After feasibility check:
- Add back the lower bounds to recover original flows.
- Report a deterministic valid flow.

---

### **Infeasibility Certificate**
If the lower-bound flow is infeasible:
- `cut_reachable`: nodes reachable from `s*` in the residual graph.
- `deficit.demand_balance`: total unmet demand.
- `deficit.tight_nodes`: nodes at capacity (v_in→v_out fully used).
- `deficit.tight_edges`: saturated edges crossing the cut (bottlenecks).

---

### **Numeric & Determinism**
- Float capacities, tolerance `1e−9`
- Deterministic Dinic (BFS + DFS with sorted adjacency)
- Lexicographic ordering for nodes/edges ensures identical outputs for identical inputs

---

### **Failure Modes & Edge Cases**
- **Cycles in recipes:** naturally handled in Factory LP.
- **Unreachable sink:** yields infeasible Belts result with a meaningful cut.
- **Node caps too small:** reported as tight nodes.
- **Edge `hi < lo`:** rejected early.
- **Disconnected components:** gracefully ignored in max-flow computation.

---

### **Implementation Notes**
- Both tools are self-contained, dependency-free except for `scipy` (Factory LP).
- Both emit a **single JSON** object to stdout, no logs or prints.
- Consistent floating-point results ensure repeatable grading.

---

### **Performance**
Each test case completes well under 2 seconds for ≤ few hundred recipes/nodes.

---

### **Deterministic Tie-breaking**
- Sort order of recipes, items, and edges.
- Use deterministic BFS/DFS in max-flow.
- Consistent rounding tolerances (±1e−9).

---

### **Authors**
Developed for the ERP.AI Engineering Assessment (Part 2).
