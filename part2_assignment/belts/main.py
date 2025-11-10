#!/usr/bin/env python3
"""
part2_assignment/belts/main.py

Reads JSON from stdin and writes a single JSON object to stdout (no extra prints).
Deterministic bounded-flow solver with node caps and lower bounds.

Input schema (flexible):
{
  "nodes": ["a","b","c"],                 # optional, node list
  "edges": [ {"from":"u","to":"v","lo":0,"hi":100}, ... ],
  "sources": {"s1": 900, "s2": 600},      # supply per source (fixed)
  "sink": "sink",                         # single sink node
  "node_caps": {"a":1500, "b": 1200}      # optional throughput caps (total in->out)
}

Output (feasible):
{
  "status":"ok",
  "max_flow_per_min": 1500.0,
  "flows": [
    {"from":"s1","to":"a","flow":900.0},
    ...
  ]
}

Output (infeasible):
{
  "status":"infeasible",
  "cut_reachable": ["s1","a","b"],
  "deficit": {
    "demand_balance": 300.0,
    "tight_nodes": ["b"],
    "tight_edges": [
      {"from":"b","to":"sink","flow_needed":300.0}
    ]
  }
}
"""
import sys
import json
from collections import defaultdict, deque

EPS = 1e-9
INF = 1e18

def read_json():
    try:
        return json.load(sys.stdin)
    except Exception as e:
        out = {"status": "error", "message": f"invalid json stdin: {e}"}
        sys.stdout.write(json.dumps(out, separators=(',', ':'), sort_keys=True))
        sys.exit(0)

def write_json(obj):
    sys.stdout.write(json.dumps(obj, separators=(',', ':'), sort_keys=True))

# Deterministic Dinic for floats
class Dinic:
    class Edge:
        __slots__ = ('to','rev','cap','flow')
        def __init__(self, to, rev, cap):
            self.to = to
            self.rev = rev
            self.cap = float(cap)
            self.flow = 0.0

    def __init__(self, n):
        self.n = n
        self.adj = [[] for _ in range(n)]

    def add_edge(self, u, v, cap):
        # deterministic append order
        a = Dinic.Edge(v, len(self.adj[v]), cap)
        b = Dinic.Edge(u, len(self.adj[u]), 0.0)
        self.adj[u].append(a)
        self.adj[v].append(b)
        # return handles if caller wants (u, index)
        return (u, len(self.adj[u]) - 1)

    def bfs_level(self, s, t):
        level = [-1]*self.n
        q = deque([s])
        level[s] = 0
        while q:
            u = q.popleft()
            for e in self.adj[u]:
                if level[e.to] < 0 and e.cap - e.flow > EPS:
                    level[e.to] = level[u] + 1
                    q.append(e.to)
        return level

    def dfs_flow(self, u, t, pushed, level, it):
        if u == t:
            return pushed
        adj_u = self.adj[u]
        i = it[u]
        while i < len(adj_u):
            e = adj_u[i]
            if e.cap - e.flow > EPS and level[e.to] == level[u] + 1:
                to_push = self.dfs_flow(e.to, t, min(pushed, e.cap - e.flow), level, it)
                if to_push > EPS:
                    e.flow += to_push
                    self.adj[e.to][e.rev].flow -= to_push
                    it[u] = i
                    return to_push
            i += 1
            it[u] = i
        return 0.0

    def max_flow(self, s, t, limit=INF):
        flow = 0.0
        while True:
            level = self.bfs_level(s, t)
            if level[t] < 0:
                break
            it = [0]*self.n
            while True:
                pushed = self.dfs_flow(s, t, limit - flow, level, it)
                if pushed <= EPS:
                    break
                flow += pushed
                if flow + EPS >= limit:
                    return flow
        return flow

    def reachable_from(self, s):
        vis = [False]*self.n
        q = deque([s])
        vis[s] = True
        while q:
            u = q.popleft()
            for e in self.adj[u]:
                if not vis[e.to] and e.cap - e.flow > EPS:
                    vis[e.to] = True
                    q.append(e.to)
        return vis

def run_belts(data):
    # Parse inputs with flexible keys
    nodes_in = list(data.get('nodes', []))
    edges_in = list(data.get('edges', []))
    sources = dict(data.get('sources', {}) or {})
    sink = data.get('sink')
    node_caps = dict(data.get('node_caps', {}) or {})

    if sink is None:
        return {"status":"error","message":"sink not specified"}

    # Build deterministic set of nodes including endpoints, sources, sink
    node_set = set(nodes_in)
    for e in edges_in:
        node_set.add(e['from'])
        node_set.add(e['to'])
    for s in sources.keys():
        node_set.add(s)
    node_set.add(sink)
    nodes = sorted(node_set)

    # Map original node -> (in_idx, out_idx)
    idx = 0
    orig_to_indices = {}
    for v in nodes:
        orig_to_indices[v] = (idx, idx+1)
        idx += 2

    # super source/sink for lower-bound transform
    sstar = idx; idx += 1
    tstar = idx; idx += 1

    G = Dinic(idx)

    # Keep deterministic edge_map list
    edge_map = []  # entries: {'from', 'to', 'lo', 'hi', 'u_out', 'v_in'}

    # demand imbalances from lower bounds: demand[node] positive => needs inflow
    demand = defaultdict(float)

    # Add node internal edges v_in -> v_out with capacity = node_caps[v] or INF
    for v in nodes:
        v_in, v_out = orig_to_indices[v]
        cap = float(node_caps.get(v, INF)) if v in node_caps else INF
        # deterministic: add in node order
        G.add_edge(v_in, v_out, cap)

    # Deterministic edge sorting key
    def edge_sort_key(e):
        return (e['from'], e['to'], float(e.get('lo', 0.0)), float(e.get('hi', INF)))

    for e in sorted(edges_in, key=edge_sort_key):
        u = e['from']; v = e['to']
        lo = float(e.get('lo', 0.0)); hi = float(e.get('hi', INF))
        if hi + EPS < lo:
            return {"status":"error","message":f"edge hi < lo for {u}->{v}"}
        cap = max(0.0, hi - lo)
        u_out = orig_to_indices[u][1]
        v_in = orig_to_indices[v][0]
        G.add_edge(u_out, v_in, cap)
        edge_map.append({'from':u, 'to':v, 'lo':lo, 'hi':hi, 'u_out':u_out, 'v_in':v_in})
        demand[u] -= lo
        demand[v] += lo

    # Incorporate fixed supplies at sources
    total_supply = 0.0
    for s in sorted(sources.keys()):
        supply = float(sources[s])
        total_supply += supply
        demand[s] -= supply
    # sink must absorb total_supply
    demand[sink] += total_supply

    # Connect s* and t* according to demand
    sum_pos_demands = 0.0
    for v in nodes:
        d = demand.get(v, 0.0)
        v_in, v_out = orig_to_indices[v]
        if d > EPS:
            G.add_edge(sstar, v_in, d)
            sum_pos_demands += d
        elif d < -EPS:
            G.add_edge(v_out, tstar, -d)

    # Run maxflow from s* to t*
    flowed = G.max_flow(sstar, tstar)

    if flowed + 1e-9 < sum_pos_demands:
        # infeasible, produce certificate
        reachable = G.reachable_from(sstar)
        # cut_reachable: nodes whose v_in is reachable
        cut_reachable = [v for v in nodes if reachable[orig_to_indices[v][0]]]
        demand_balance = float(sum_pos_demands - flowed)
        # tight_nodes: nodes where internal edge v_in->v_out is saturated and v_in is reachable
        tight_nodes = []
        for v in nodes:
            vi, vo = orig_to_indices[v]
            # we added v_in -> v_out as the first edge from vi (deterministic)
            if len(G.adj[vi]) == 0:
                continue
            e = G.adj[vi][0]
            if reachable[vi] and abs(e.cap - e.flow) <= 1e-6:
                tight_nodes.append(v)
        # tight_edges: edges crossing reachable->unreachable that are saturated
        tight_edges = []
        for rec in edge_map:
            u_out = rec['u_out']; v_in = rec['v_in']
            if reachable[u_out] and not reachable[v_in]:
                # find the edge object in adjacency of u_out
                for e in G.adj[u_out]:
                    if e.to == v_in:
                        if e.cap - e.flow <= 1e-6:
                            # estimate flow_needed as min(demand_balance, edge remaining capacity in original coordinates)
                            max_extra = rec['hi'] - rec['lo']
                            need = float(min(demand_balance, max(0.0, max_extra)))
                            tight_edges.append({'from': rec['from'], 'to': rec['to'], 'flow_needed': need})
                        break
        out = {
            'status': 'infeasible',
            'cut_reachable': cut_reachable,
            'deficit': {
                'demand_balance': demand_balance,
                'tight_nodes': sorted(tight_nodes),
                'tight_edges': tight_edges
            }
        }
        return out

    # feasible: reconstruct flows on original edges (add lo back)
    flows = []
    # For deterministic output, iterate edge_map in sorted order of (from,to)
    for rec in sorted(edge_map, key=lambda r: (r['from'], r['to'])):
        u_out = rec['u_out']; v_in = rec['v_in']
        flow_on_edge = 0.0
        # find the edge in adjacency
        for e in G.adj[u_out]:
            if e.to == v_in:
                flow_on_edge = e.flow
                break
        total_flow = flow_on_edge + rec['lo']
        flows.append({'from': rec['from'], 'to': rec['to'], 'flow': float(max(0.0, total_flow))})

    max_flow_per_min = float(total_supply)

    return {'status':'ok', 'max_flow_per_min': max_flow_per_min, 'flows': flows}

def main():
    data = read_json()
    out = run_belts(data)
    write_json(out)

if __name__ == "__main__":
    main()
