# Browse152: bounded lazy snapshots

Skin152/Home1.0.46 retains the existing 15-second Browse cache, but bounds it
to eight snapshots, four MiB of total UTF-8 payload and two MiB per item.
Least-recently-used entries are evicted on insertion. Expired entries are
reclaimed on access, at most once per five seconds; an accessed expired item
is always rejected. There is no filesystem directory scan and no periodic
background worker. The only disk operation is a nonblocking OS lock file for
the in-memory registry; a busy lock falls back to an uncached read.

The existing full-directory sort/filter and metadata remain intact. Snapshots
are also rejected after a library-change epoch. Cache failures are optional:
they do not block browsing, write history, change media paths or add pagination.
Normal stopped-state deployment clears the preceding process's unregistered
Window caches; no historical cache/profile recovery is run.

Seven CI regressions cover cache hits and epoch changes, TTL removal, quantity
and LRU bounds, total/item bytes, sweep throttling without directory scans,
busy-lock fallback and corrupt payload rejection. The five Home151 behaviour
regressions and the existing theme/reference/repository/playback checks pass.

CE read-only comparison over the same 36-item source as the149 baseline:

| Measurement | Baseline149 | Skin152 |
| --- | ---: | ---: |
| First same-selection directory call | 0.616 s | 0.647 s |
| Immediate repeated call | 0.382 s | 0.383 s |
| Other three sort selections | 0.611–0.618 s | 0.619–0.630 s |
| Beyond eight combinations | Unbounded design | Observed at most 8 keys |
| Next access after expiry | Old keys remained | Registry reduced to one fresh key |

The additional ten exact-query selections are empty-result cases, used to
exercise the quantity limit without changing the library. Device payloads
stayed below the configured byte ceiling; the byte and oversized-item limits
are additionally exercised with generated large payloads in the portable tests.
This is a bounded-memory/lifecycle fix, not a speed claim: the repeated-call
benefit is preserved, and a single first-call measurement is not statistically
meaningful. The cache's UTF-8 payload budget excludes small index/allocator
overhead and is not a ceiling on Kodi RSS.

The 30-minute final Home workload and one final process-cold timing run are
recorded separately before release. The old149 baseline remains unchanged.
