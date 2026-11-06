# CoreELEC Skin149 baseline before performance changes

Measured on 2026-11-07 with Skin2026.10.3.149/Home1.0.44. Installed runtime
members matched the delivered packages. No media was played or scanned.
The focus-only Skin150 change is tracked separately from performance work.

| Measurement | Result |
| --- | ---: |
| Same-version process restart: Home active | 2.418 s |
| First Home row with items | 21.916 s |
| All eight Home rows with items | 35.643 s |
| Five warm returns, median | 0.137 s (range 0.061–0.201 s) |
| One global refresh | 16 directory requests: 8 main rows + 8 probes |
| Non-playback Home navigation | 1,800.001 s, 179 memory/cache samples |
| Kodi RSS, start/end | 1,177.46 / 969.34 MiB |
| Kodi RSS, observed minimum/maximum | 934.13 / 1,626.68 MiB |
| Fixed Home/search/genre cache strings, final | 2,541,247 UTF-8 bytes across 10 keys |

Cold here means a normal Kodi process restart, without flushing OS caches.
Readiness means an active Home and nonzero container item counts; it does not
measure the first displayed frame or completion of all image decoding. The
cold restart is one sample, not a p95 estimate. RSS contains more than provider
caches, and its rise and fall cannot establish a cache leak.

Request counting used a separate debug-log phase, a verified debug sentinel,
and `CDirectoryProvider[plugin://plugin.video.yoplayer.home/...]: refreshing`
entries. Each route was requested twice, once as a main row and once as a
probe. These are directory jobs, not a count of all VideoLibrary JSON-RPC
calls. The original debug setting was restored. An initial failed logging
attempt was retained as unavailable, not counted as zero requests.

An additional, separate read-only directory workload used four normalized
sort selections over the same 36-item source. A repeated selection took
0.616 s initially and 0.382 s immediately afterward; three other selections
took 0.611–0.618 s each. Four Browse cache keys occupied 461,336 bytes. After
another 16 seconds all four still existed, at ages 17.99–23.59 seconds, beyond
their 15-second hit lifetime. This confirms expiry without reclamation on the
device, but is not a large-library or long-term-growth estimate. The UI stayed
on Home, and no playback or persistent browse-preference changes were made.

The fixed-cache total excludes dynamic Browse/Membership keys. The directory
workload measures only its four known Browse keys, not every Kodi cache.
The two workloads must not be presented as a single full-cache enumeration.

The baseline closed with the original theme/focus, complete empty playlists,
volume, six JSON files and all 879 skin-setting leaves preserved. The 898 GUI
setting leaves differed only in Kodi's total uptime. A fresh stopped-state
backup was verified by SHA256 and each member before the same-version restart;
the service returned to its original restart policy, with no temporary drop-in.

Next changes should be separate small PRs: first hidden-row probes and scoped
refresh, then cache size/count/expiry bounds with lazy or infrequent cleanup.
Cache-hit-path and large-directory changes need their own hotspot evidence.
Dead-branch deletion is maintenance work; the 22 script and 48 static-variable
candidates remain untouched. Package weight alone is not evidence of latency.
