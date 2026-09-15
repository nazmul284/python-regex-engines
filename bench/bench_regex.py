"""re vs regex vs google-re2: throughput, and the failure mode nobody prices in.

The standard library's `re` uses a backtracking engine. On a pattern with nested
quantifiers and input that nearly matches, backtracking is exponential in the
input length, which is the ReDoS bug class. RE2 uses an automaton and cannot
backtrack, so it trades some features for a linear-time guarantee.

Three measurements:
  compile     - one-off cost per pattern
  throughput  - realistic patterns over a realistic corpus
  redos       - time to fail on a nested-quantifier pattern as input grows,
                measured in a subprocess with a hard timeout so a hang is
                recorded as a hang rather than stopping the benchmark
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parent
PY_ = str(ROOT / ".venv" / "bin" / "python")
REPS = 5

PATTERNS = {
    "email":   r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "ipv4":    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "iso_date": r"\b\d{4}-\d{2}-\d{2}\b",
    "loglevel": r"\b(?:DEBUG|INFO|WARNING|ERROR|CRITICAL)\b",
    "url":     r"https?://[^\s\"'<>]+",
}

CORPUS_SRC = r'''
import random
random.seed(7)
lvl = ["DEBUG","INFO","WARNING","ERROR","CRITICAL"]
lines = []
for i in range(40000):
    lines.append(
        f"2026-09-{i%28+1:02d} {lvl[i%5]} user{i}@example.com "
        f"10.{i%256}.{(i*7)%256}.{(i*13)%256} GET https://api.example.com/v1/items/{i} "
        f"took {i%900}ms")
CORPUS = "\n".join(lines)
'''

BENCH_SRC = CORPUS_SRC + r'''
import json, sys, time
ENGINE, NAME, PAT = sys.argv[1], sys.argv[2], sys.argv[3]

if ENGINE == "re":
    import re as eng
elif ENGINE == "regex":
    import regex as eng
else:
    import re2 as eng

t0 = time.perf_counter()
c = eng.compile(PAT)
compile_ms = (time.perf_counter() - t0) * 1000

c.findall(CORPUS)                       # warm
t0 = time.perf_counter()
n = len(c.findall(CORPUS))
scan_ms = (time.perf_counter() - t0) * 1000
print(json.dumps({"compile_ms": compile_ms, "scan_ms": scan_ms,
                  "matches": n, "corpus_bytes": len(CORPUS)}))
'''

REDOS_SRC = r'''
import json, sys, time
ENGINE, N = sys.argv[1], int(sys.argv[2])
if ENGINE == "re":
    import re as eng
elif ENGINE == "regex":
    import regex as eng
else:
    import re2 as eng
# classic nested quantifier; the trailing X guarantees a failed match
pat, text = r"(a+)+$", "a" * N + "X"
t0 = time.perf_counter()
m = eng.compile(pat).search(text)
print(json.dumps({"ms": (time.perf_counter() - t0) * 1000, "matched": bool(m)}))
'''

ENGINES = ["re", "regex", "re2"]

def run(src, *args, timeout):
    try:
        p = subprocess.run([PY_, "-c", src, *args], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:140]
    return json.loads(p.stdout.strip().splitlines()[-1]), None

def main():
    thr = []
    for name, pat in PATTERNS.items():
        for eng in ENGINES:
            samples, last, err = [], None, None
            for _ in range(REPS):
                d, err = run(BENCH_SRC, eng, name, pat, timeout=300)
                if d is None:
                    break
                samples.append(d["scan_ms"]); last = d
            if not samples:
                thr.append({"pattern": name, "engine": eng, "error": err})
                print(f"  {name:9} {eng:6} FAILED {err}")
                continue
            mb = last["corpus_bytes"] / 1e6
            thr.append({"pattern": name, "engine": eng,
                        "scan_ms": round(min(samples), 2),
                        "compile_ms": round(last["compile_ms"], 3),
                        "matches": last["matches"],
                        "mb_per_s": round(mb / (min(samples) / 1000), 1)})
            print(f"  {name:9} {eng:6} {min(samples):8.2f} ms  "
                  f"{mb/(min(samples)/1000):7.1f} MB/s  matches={last['matches']}", flush=True)

    redos = []
    for eng in ENGINES:
        for n in (18, 20, 22, 24, 26, 28, 30):
            d, err = run(REDOS_SRC, eng, str(n), timeout=10)
            ms = None if d is None else round(d["ms"], 3)
            redos.append({"engine": eng, "n": n, "ms": ms,
                          "status": "timeout(>10s)" if err == "timeout" else
                                    ("error" if err else "ok"), "error": err})
            print(f"  redos {eng:6} n={n:3} "
                  f"{'TIMEOUT >10s' if err == 'timeout' else f'{ms:10.3f} ms'}", flush=True)
            if err == "timeout":
                break
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "regex.json").write_text(json.dumps(
        {"reps": REPS, "throughput": thr, "redos": redos}, indent=2))
    print("\nwrote results/regex.json")

if __name__ == "__main__":
    main()
