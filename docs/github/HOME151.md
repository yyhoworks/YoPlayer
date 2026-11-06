# Home151: one provider per row and scoped refresh

Skin151/Home1.0.45 replaces the eight offscreen probe lists with completion
state published by each primary row. Loading, empty and failed rows remain
distinct. Hidden rows resolve to an empty URL and also return before any data
fetch if an older Kodi job reaches the provider. Each row has its own revision;
scoped refresh no longer rebuilds unrelated rows. Empty rows are made loadable
again before refresh, and late results cannot publish over a newer revision.

Five portable regressions cover full/scoped refresh, stale completion, empty
and failed rows, hidden fetch prevention and all eight XML/provider bindings.
Existing theme, strict-reference, repository and playback-control checks pass.
The historical no-argument structure gate still rejects an unreviewed151
default contract and is not counted as a pass.

CE comparison with the previously recorded149 baseline, using actual
`CDirectoryProvider` debug entries with explicit UI wake events:

| Operation | Baseline149 | Skin151 |
| --- | ---: | ---: |
| Global Home refresh | 16 directory jobs | 8 |
| Scoped continue/history refresh | All Home URLs previously shared a revision | 1 continue job |
| Global refresh with daily hidden | Not measured previously | 7, no daily job |
| Reveal daily | Not measured previously | 1 daily job |

All eight row counts match the baseline: 25/11/12/25/25/18/16/25 in the defined
row order. Debug and the original hidden setting were restored. The first
observer attempt mixed delayed idle refreshes into adjacent phases; its output
was rejected and retained, not used as acceptance. A corrected observer uses
explicit checks because assertions are optimized out in embedded Kodi Python.

This is a request-count improvement, not a measured 50% latency improvement.
Cold-start and long-duration timing are recorded separately with the final
candidate. No fonts, artwork, playback engine or user media state were changed.
