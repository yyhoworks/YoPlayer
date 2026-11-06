# Skin150: keep poster focus clear without an outer frame

This change follows Skin149/Home1.0.44 and fixes only the artwork focus rim.
It does not include the separately planned Home or cache performance changes.

Skin149 placed a rim 8px beyond each artwork edge. Its semantic mask used the
generic filled-focus rule, which replaced a transparent centre with alpha 28.
That tinted the artwork and made the outside gap appear as an extra frame.

Skin150 derives a two-pixel inner rim from the same landscape, portrait or
genre alpha mask used by the artwork. Its offset is zero and its dimensions
follow the artwork. The complete central half stays transparent. Library and
genre rims render after the artwork so an inner rim remains visible. Existing
106% focus scaling, shadows, actions, navigation and container clipping remain
unchanged. All five themes keep the rim; this small fix adds no new setting.

| Property | Skin149 | Skin150 |
| --- | --- | --- |
| Outward offset | 8px per edge | 0px |
| Centre alpha | 28/255 | 0 |
| Artwork shape | Recreated generic focus panel | Original artwork alpha mask |
| Focus zoom and shadow | Existing | Preserved |
| Home provider | 1.0.44 | Same runtime bytes |

`check_theme_delivery.py`, already run by CI, now checks the central region and
rejects a rim outside its artwork mask. It also checks the declared hollow-mask
classification, so switching it back to a filled focus mask cannot bypass the
pixel gate. Regressions exercise a centre filled with alpha 28, classification
tampering, generated output and zero-offset layout geometry.

Validation completed offline: both authoring `--check` commands, strict skin
references, repository structure, 23 theme-delivery checks (18 existing plus
5 focus checks), 12 theme-coverage checks and 23 existing playback-control
checks. All native actions/conditions/navigation and all animations match
Skin149. The old no-argument structure command still rejects an unreviewed
150 default contract; it is not counted as a pass.

XBT: one focus-rim entry replaced, two artwork-specific entries added; 2,748
existing entries retain their metadata and compressed payload. There are no
retired runtime paths. Skin package SHA256:
`3b10de4f24c199ba4abaf0706e47f8b9b2579bf97a51c21301f1a64156cfaca2`.

The preceding pixel comparison is deterministic source evidence, not CE/TV
rendering acceptance or a speed claim. A separate, non-playback Skin149 CE
baseline is being recorded before any performance implementation. Physical
television focus clarity and top-edge rendering still require device evidence.
