import os
import shlex
import subprocess
import json
import pytest
from collections import defaultdict

BELTS_CMD = os.environ.get("BELTS_CMD", "python belts/main.py")
TIMEOUT = 2  # seconds

def run_cli(cmd, inp):
    args = shlex.split(cmd)
    p = subprocess.run(args, input=json.dumps(inp).encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT)
    out = p.stdout.decode().strip()
    return json.loads(out)

def test_belts_sample_ok():
    # Two sources s1 (900) and s2 (600) -> sink via a,b,c
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

    out = run_cli(BELTS_CMD, inp)
    assert out.get("status") == "ok"
    assert out.get("max_flow_per_min") == pytest.approx(1500.0)
    flows = out.get("flows", [])
    # sum inflow to sink should equal total supply 1500
    sink_in = 0.0
    for f in flows:
        if f["to"] == "sink":
            sink_in += float(f["flow"])
    assert sink_in == pytest.approx(1500.0, rel=1e-9, abs=1e-9)

def test_belts_infeasible_due_to_node_cap():
    # Node 'a' has a small cap that can't pass both supplies
    inp = {
      "nodes": ["s1", "s2", "a", "sink"],
      "edges": [
        {"from":"s1","to":"a","lo":0,"hi":1000},
        {"from":"s2","to":"a","lo":0,"hi":1000},
        {"from":"a","to":"sink","lo":0,"hi":1000}
      ],
      "sources": {"s1":900, "s2":600},
      "sink": "sink",
      "node_caps": {"a": 500}  # too small to pass all 1500
    }
    out = run_cli(BELTS_CMD, inp)
    assert out.get("status") == "infeasible"
    assert isinstance(out.get("cut_reachable"), list)
    deficit = out.get("deficit", {})
    assert deficit.get("demand_balance", 0.0) > 0.0
    # tight_nodes should include 'a' (since it's the bottleneck)
    assert "a" in deficit.get("tight_nodes", []) or any(te.get("from") == "a" for te in deficit.get("tight_edges", []))
