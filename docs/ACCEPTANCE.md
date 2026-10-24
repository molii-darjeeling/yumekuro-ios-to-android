# Final confirmation: find gaps before calling the migration complete

This is a required stage, not an optional check after reaching the title screen. Compare against **this user's own export**, including older cached versions and independent raw media. Installed size alone proves nothing.

## A. Inventory the complete export

Check all relevant source locations and both Octo record kinds:

- Top-level field **2**, AssetBundles using **A** IDs: cards, previews, CG, story scripts, actors, models, furniture, materials, AudioClips, and cue sheets.
- Top-level field **4**, independent resources using **R** IDs: `.mp4`, `.mov`, `.mp3`, `.caf`, and `.wav` media. These are not metadata just because their filenames have an extension.
- App-embedded and downloaded caches. A missing current MD5 is not proof that the original device contains no usable file.
- Older cache variants for the same iOS ID. Validate the file against its cached MD5 and its actual internal `AssetBundle.m_Name`; an ID alone is insufficient. Prefer a verified canonical resource. Defer ambiguous multiple variants and unsupported formats.

An older cached bundle is an explicitly recorded adaptation, not an exact Android original. Preserve its real dependency list, object data, and stream bytes. Do not discard old caches as "junk" before this check.

## B. Compare the current local catalog

Produce a private report with these distinct outcomes for each relevant logical resource:

| Outcome | Meaning / action |
| --- | --- |
| Local file and closure complete | Candidate ready for actual testing |
| Source exists, not imported | Prepare a type-correct bounded batch and import it |
| Root imported, dependency missing | Recover the named dependency; do not reconvert the root blindly |
| Verified older source variant available | Validate internal identity/format and import as an adaptation |
| Only preview exists | Report missing full asset; do not silently upscale it |
| iOS-only logical name, no Android index entry | Preserve/report it; do not alias an unrelated Android asset |
| Source media exists but Android name/format differs | Diagnose the specific mapping/format; never relabel arbitrary media |
| Unsupported shader/codec/schema | Defer with an explicit reason; keep originals |
| Not present anywhere in the export | Report genuinely unavailable content, separately from missed conversion |

Recheck ownership and progress privately. A missing owned-card presentation matters; an unavailable unowned card must not be unlocked to make a coverage table look complete. Keep original save/unlock decisions.

## C. Verify on the actual destination

Check phone SHA-256 against every published manifest row for the final required content and dependency closure. Include raw media using their separate R filenames. A successful command, matching filename, or matching total size does not prove a transfer is complete.

In particular, binary media must not be passed through a text-mode shell path. A Windows ADB stdin path was observed to stop at byte `0x1A`, and a large raw stream could finish at the client with truncated remote files. A reliable fallback is: write one bounded temporary PC file, ADB **push** it to `/data/local/tmp/`, copy it into the debuggable app's files with `run-as`, then verify the destination hash. Delete only the specific temporary files created by this operation. Some Android versions deny `run-as` reads from `/sdcard/Android/data/...`; do not keep retrying that route or disable access controls.

Hash the generated/deployed runtime as well. Check that every supplement exists, the snapshot is complete, shared manifests have no concurrent writer, A and R IDs cannot collide, and no file in a ready closure is merely a PC-side row.

## D. Let the user test a small representative set

Tell the user the complete batch is ready, then ask for one manual restart so the new in-memory catalog loads. If they test, do not take over their phone.

| Feature | What the user confirms |
| --- | --- |
| Home and menu | Original Unity interface opens; own layout/progress is recognizable |
| Cards | Original full images open in the album/card page; available animation still moves |
| Static fallback | The exact card's full-size original image displays only when animation is incomplete |
| Story CG | Preview and full CG both open; a thumbnail alone is not success |
| Stories | Dialogue, backgrounds, actors, and shared expression effects work; try a character story as well as main/event stories |
| Voice | Audible playback and timing; a requested filename is not proof of sound |
| Guilds | Switch more than one guild; original progress, room furniture, and people remain present |
| Independent media | A relevant locally available story/movie or other raw-media entry actually plays |
| Pure local use | Required accepted paths work without a new Play download or account login |

Do not demand a full replay of every chapter. Use the coverage report plus a few user-selected checks, and investigate exact names/pages if something fails. Passive runtime diagnostics may supplement the user's report.

## E. Record the accepted result

Separate **source-verified**, **phone-hash-verified**, **runtime-observed**, and **user-confirmed** evidence. List remaining missing/unsupported items and their visible impact. Do not describe incomplete battle/skill systems or former online features as restored merely because they have some files.

After the user accepts the agreed result, hand over the private session, original exports, local build/signing material, manifests, mappings, and rollback paths. Only generic code and findings belong in the public repository.
