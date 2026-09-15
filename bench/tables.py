"""Render the article/README tables from the result JSON."""
from __future__ import annotations
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent / "results"
D = json.loads((R / "regex.json").read_text())
ENG = ["re", "regex", "re2"]
TH = {}
for r in D["throughput"]:
    if "mb_per_s" in r: TH.setdefault(r["pattern"], {})[r["engine"]] = r

def row(c, w): return "".join(str(x).ljust(n) for x, n in zip(c, w)).rstrip()
def rule(w):   return "-" * sum(w)

def throughput() -> str:
    w = [12, 14, 14, 14, 10]
    out = [row(["pattern","re (stdlib)","regex","google-re2","fastest"], w), rule(w)]
    for pat, g in TH.items():
        vals = {e: g[e]["mb_per_s"] for e in ENG}
        best = max(vals, key=vals.get)
        out.append(row([pat] + [f"{vals[e]:.0f} MB/s" for e in ENG] + [best], w))
    spread = {e: max(g[e]["scan_ms"] for g in TH.values()) /
                 min(g[e]["scan_ms"] for g in TH.values()) for e in ENG}
    out += ["", "spread between the fastest and slowest pattern, per engine:",
            "  " + "   ".join(f"{e}={spread[e]:.2f}x" for e in ENG)]
    return "\n".join(out)

def redos() -> str:
    by = {}
    for r in D["redos"]: by.setdefault(r["engine"], {})[r["n"]] = r
    ns = sorted({r["n"] for r in D["redos"]})
    w = [14] + [9] * len(ns)
    out = [row(["input chars"] + [str(n) for n in ns], w), rule(w)]
    for e in ENG:
        cells = []
        for n in ns:
            r = by[e].get(n)
            if r is None: cells.append("-")
            elif r["ms"] is None: cells.append("HANG")
            elif r["ms"] >= 1000: cells.append(f"{r['ms']/1000:.1f}s")
            else: cells.append(f"{r['ms']:.2f}ms")
        out.append(row([e] + cells, w))
    out += ["", "Matching (a+)+$ against 'a'*n + 'X'. HANG = still running at 10 s.",
            "Every measurement is a fresh subprocess with a hard timeout."]
    return "\n".join(out)

if __name__ == "__main__":
    print("===== THROUGHPUT =====\n" + throughput())
    print("\n===== REDOS =====\n" + redos())
