# AI runbook: follow this state machine

Read `AGENTS.md` first. Each stage has an automated part, a human checkpoint, and evidence required to leave the stage. Stop only for a real dependency on the human; continue independent authorized analysis in the meantime.

## 0. Intake and workspace

Find out the user's computer OS, source iOS model/system/build, destination Android model, and whether an existing export exists. Ask whether the game still opens and whether content can be viewed there. Do not make the user test every story now. Select a workspace with capacity for original app/data archives, APKs, build intermediates, and a reserve. Estimate from device storage; a tiny OS backup is not a full resource export.

Human checkpoint: confirm a workspace and any required installation. Create local config from `local-config.example.json`, adjust tool paths rather than imposing the example drive, and initialize a private session. A computer-enabled agent can then run `tools/yume.py doctor`.

Exit evidence: actual available disk space, tool availability, and the selected route. No device mutations.

## 1. Source access — ordinary export first

Follow `DEVICE_ACCESS.md`. Inspect a backup's actual per-app contents if available. Do not decide from its name or from an "app data" checkbox. Identify both save records and bulk resources.

If a supported full-container method is needed, explain that requirement and verify the current device/system compatibility against official sources. The human must consent and complete any required device-side actions. Do not provide an automatic jailbreak or attempt management removal.

Human checkpoints: connect/unlock source, trust the computer if offered, approve a proposed access tool, configure SSH only if needed, verify SSH host identity and enter the terminal password locally. Do not request Apple credentials in chat.

Exit evidence: a verified read-only path to the correct game containers, or a sufficient backup/export. If no supported path exists, stop this dependent stage honestly and preserve what is available.

## 2. Preserve and index

Identify app and data containers by their bundle identifiers, not an old UUID. Close the source game before export. Export app and data with separate archives, retain hashes, validate archive members, and index them without unpacking the entire resource collection.

`export_ios.py` is an SSH exporter once access exists; it is not a pairing/jailbreak tool. A user-provided ordinary backup may need a different adapter. Do not pretend it has the same TAR layout unless you verified that.

Exit evidence: original hashes, archive readability, game identity/version, save file inventory, and resource index/cache presence. Keep originals unchanged.

## 3. Android connection and matching originals

Human checkpoints: connect the destination, enable developer options/USB debugging with model-appropriate instructions, authorize this computer, and approve any installation. Read ADB's actual state: `unauthorized` means wait; `offline` or no device means repair the connection first.

Acquire the user's official base APK and correct ABI split. Record versionCode, ABI, and hashes. Extract the resource index and native metadata/library locally. Apply the included native profile only when all exact hashes match. Different builds require reverse engineering, even if their displayed version is similar.

Exit evidence: an explicitly selected device/user, official APK identities, and a passed profile gate. No clone installation yet.

## 4. Map and plan resources

Read both Octo catalogs. Map logical names to platform-specific IDs; build the Android dependency graph. Extract encrypted original save records without rewriting them. Produce a private coverage report grouped by card, CG, actor, story, voice, room, furniture, and shared UI.

Separate: exact Android reconstructions, validated platform adaptations, matching original Play resources, unavailable source content, and unsupported conversions. Do not equate these categories. Plan bounded batches and retain resource-ID mappings privately.

Exit evidence: real source availability and dependency closure, not just a list of expected filenames.

## 5. Build the separate native local client

Follow `MIGRATION.md`. Use a distinct package, fresh private signing key, and a verified official Android-arm64 Frida Gadget. Keep the original Unity UI, loaders, async tasks, and save/unlock behavior. The runtime replaces asset delivery with actual local files; it does not simulate a successful server.

Human checkpoint: approve installation of this separate local app and any phone-side installer dialog. Do not overwrite or uninstall the official game.

Exit evidence: signed APK verification, installed package identity, correct native library profile, successful `run-as`, and private/external directories ready. Do not count reaching the title as acceptance.

## 6. Import resources and the user's save

Prepare exact snapshots, Android shader inventory, validated metadata/visual/audio/cue adaptations, and any optional Play assets. Shared manifests have a single writer. Take source hashes seriously; stream output to the phone rather than making repeated multi-gigabyte PC copies.

Populate shared menu assets, guild scenes/furniture, character models, and the user's home resources **before first opening the restored game** where possible. The native client may filter and save unavailable settings. Verify the phone resource hashes and dependency graph.

Human checkpoint: stop the local app and import the user's original encrypted `Production` data, with a verified backup of any previous Android-local save. Never reuse another person's save, preferences, or guild/character list.

Exit evidence: every imported save file round-trips to the source hash, required resources exist, manifests are complete, and the actual generated runtime matches its PC copy. Re-read `TECHNICAL_REFERENCE.md` before making availability changes.

## 7. Targeted user acceptance and diagnosis

Tell the user a complete batch is ready, then ask them to close/reopen the app. Test according to `ACCEPTANCE.md`; a user can own all UI testing while the AI passively reads logs. Diagnose a specific screen and actual missing dependencies rather than repeatedly browsing all pages.

If guild/home settings were already filtered, first fix the resource cause. Compare this user's original and current saves privately. Only then prepare a narrow restoration of the affected fields, with an encrypted backup and unchanged-field assertions. Do not reset everything to a reference account.

Exit evidence: user-confirmed original UI, own progress, usable stories/CG/cards/audio/rooms within available content, and explicit remaining missing resources. Mark files-only, runtime, and human evidence separately.

## 8. Finish and hand over

Keep the final installed APK pair, signing material, generated runtime, verified exports, manifests, and the private session in the user's chosen storage. Explain that routine offline play does not require the optional download/login tool. Give rollback instructions for the separate local app and retain the source device until accepted.

Record accepted limitations and stop at the user's agreed result. Do not continue expanding into battles or former online services without a new request.

## Private SESSION.md format

```text
Current stage:
Source device/system and game build:
Destination device/user and game build:
Workspace/tool paths:
Original archive and APK hashes:
Completed steps + evidence level:
Current local manifest revision:
App restart pending: yes/no
Missing authentic resources / unsupported conversions:
Human action currently awaited:
Next independent computer action:
Rollback/backup locations:
```

Keep passwords, tokens, and signed URLs out of this note. It is still private because device/build details and paths can identify a user.
