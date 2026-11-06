# 154: expose a Home row only after its revision is ready

The final152 test reproduced a reveal race: making a hidden row visible before
publishing its new URL revision could start both an old and a new directory job.
The next candidate exposed a second acknowledgement race: builtin return could
precede GUI condition evaluation, causing a false confirmation dialog.

This small follow-up publishes the revision while the URL is still empty, then
changes visibility and waits up to one second for Kodi to acknowledge it. The
wait can abort, never resends the command and keeps the existing failure path.
Two added regressions verify ordering and delayed acknowledgement, bringing
Home checks to seven. Original152/153 packages and failed observations remain.

CE154: full refresh8, continue scope1, hidden full7, reveal1. Four additional
reveal repetitions each produced one daily request. Initial Home reconstruction
with daily hidden produced exactly seven jobs and no daily request. The final
normal settings save restored all original preferences and debug state; no
viewing-history, playlist or volume change remains.

The full final evidence and timing limits are in VALIDATION154.md. This PR
contains only this follow-up and current release documentation; Home151 and
cache152 remain separate PRs. It does not change cache bounds, directory
metadata, artwork, focus geometry or playback behaviour.
