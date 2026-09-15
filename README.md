# python-regex-engines

`re` vs `regex` vs `google-re2`: throughput on realistic patterns, and the failure
mode nobody prices in. Measured **2026-09-15** on Apple M2, 4 performance + 4 efficiency cores, 8 GB, macOS 26.6.2, CPython 3.14.7.

## Throughput

```
pattern     re (stdlib)   regex         google-re2    fastest
----------------------------------------------------------------
email       64 MB/s       11 MB/s       38 MB/s       re
ipv4        70 MB/s       202 MB/s      37 MB/s       regex
iso_date    94 MB/s       414 MB/s      39 MB/s       regex
loglevel    105 MB/s      149 MB/s      38 MB/s       regex
url         329 MB/s      187 MB/s      39 MB/s       re

spread between the fastest and slowest pattern, per engine:
  re=5.17x   regex=37.04x   re2=1.05x
```

No engine wins. `regex` is 4.4x faster than `re` on a date pattern and 5.7x slower on
an email one. What stands out is the last line: across five very different patterns
`re2` varies by 1.05x, `re` by 5.17x and `regex` by 37x. The automaton that makes RE2
ReDoS-proof also makes it predictable.

## The failure mode

```
input chars   18       20       22       24       26       28       30
-----------------------------------------------------------------------------
re            17.19ms  69.74ms  268.50ms 1.1s     4.3s     HANG     -
regex         0.26ms   0.17ms   0.19ms   0.20ms   0.22ms   0.26ms   0.25ms
re2           0.10ms   0.04ms   0.04ms   0.03ms   0.04ms   0.03ms   0.04ms

Matching (a+)+$ against 'a'*n + 'X'. HANG = still running at 10 s.
Every measurement is a fresh subprocess with a hard timeout.
```

`re` quadruples for every two characters added, which is what exponential backtracking
looks like. At 26 characters it takes 4.3 seconds. At 28 it was still running when the
10-second timeout fired.

Both alternatives are flat. That `regex` is also immune is worth knowing: the usual
advice is that only RE2 protects you.

## Method

- Corpus: 40,000 synthetic log lines, about 4.3 MB, seeded for reproducibility.
- Five patterns a real log parser would use: email, IPv4, ISO date, log level, URL.
- Warm-up scan before timing, then five timed runs, minimum reported.
- The ReDoS test runs in a fresh subprocess with a hard 10-second timeout, so a hang is
  recorded as a hang instead of stopping the benchmark.

## Limits

- One corpus and five patterns. A different pattern mix moves the throughput table.
- `re2` is a Python binding around a C++ library; its near-constant throughput suggests
  binding overhead dominates at this corpus size, so it would likely look better on
  much larger inputs. The ReDoS result is a property of the engine and does not depend
  on that.
- RE2 deliberately omits backreferences and lookaround. Some patterns cannot be ported.
- `(a+)+$` is the textbook pathological case, not a pattern anyone writes on purpose.
  The point is that it takes one careless nested quantifier plus untrusted input.

## Reproducing

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python bench/bench_regex.py
python3 bench/tables.py
```

MIT.
