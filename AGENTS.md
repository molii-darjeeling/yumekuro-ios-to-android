# Instructions for the AI guiding a migration

## Entry point

When a user sends this repository and asks "Teach me how to do this" (in any language), start the actual guided workflow. Do not merely summarize the repository or tell a novice to read every document.

Read this file, `docs/AI_RUNBOOK.md`, `docs/DEVICE_ACCESS.md`, and `docs/MIGRATION.md`. Inspect an existing private `SESSION.md` before repeating work. Read additional references as their stage becomes relevant.

## Conversation and human checkpoints

1. Speak the user's language, even though the repository is English.
2. Initially ask for the iOS device/model/system version, the Android model, the computer OS, and a workspace location with enough free space. Ask only what cannot be inspected. Never request account passwords, private keys, or full saves in chat.
3. Explain one immediate goal and give one to three concrete human actions. **Stop and wait for the user's reply** for cable connection, USB debugging, trust/permission dialogs, device unlocking, software installation approval, account authorization, a proposed jailbreak, and visible/audio acceptance tests. A timeout is not confirmation.
4. Once the user completes a checkpoint, independently inspect the result before continuing. "Done" does not prove a device is authorized or a transfer finished.
5. Perform authorized computer work yourself: inventory, indexing, hashing, dependency mapping, conversion, build preparation, and reports. Do not repeatedly ask permission for routine reversible computer work already explained and authorized.
6. Do not operate the user's phone UI, foreground the game, capture their screen, or restart it while they are using it unless the current session authorizes that. If the user tests, work in the background and request a manual restart only after a complete batch is ready.
7. Keep concise progress updates during long operations. Say what was learned and what happens next, not just "working."

## Target and boundaries

Use the original Unity game client with a separate local package and the user's own save/resources. Do not substitute a webpage/gallery mockup or rewrite the game from screenshots. Do not alter the official Android app. Do not patch sign-in, payment, ownership, or progression checks to invent access. Retain original unlock decisions.

Do not make supervision/MDM removal, resetting, reflashing, downgrading, factory recovery, or uninstalling the source game part of this workflow. Ordinary export paths come first; full-container access is a separately explained compatibility decision, not a default assumption.

## Technical gates

- Never apply the included native addresses to a different binary. Enforce `project.require_profile()` before building or generating the runtime. A mismatch means inspect/re-map, not disable the gate.
- Keep immutable original app/data exports and APKs. Work on a separate package and copies; create and verify a save backup before replacing anything on Android.
- Use logical resource names to join the iOS and Android catalogs. Their numeric IDs are not interchangeable.
- Do not treat a filename, manifest row, or a successful copy command as proof of a working asset. Verify file length/hash and the recursive dependency closure; let Unity perform real loads.
- Do not make startup tasks complete artificially, suppress exceptions to pretend success, or report missing resources as cached.
- Preserve original non-shader objects, texture/audio streams, cue metadata, shader render states, and animation behavior. Reject unsupported conversions; report them explicitly.
- Never globally override PAD's in-memory `IsAssetCached` check. See `docs/TECHNICAL_REFERENCE.md`.
- Plan selections by resource type and bounded batch size. Importers buffer their selected payloads in RAM; do not select several gigabytes at once. Shared manifests must have one writer at a time.
- New manifests and runtime scripts require an app restart. Do not test against an old in-memory catalog and repeatedly reconvert the same files.
- Fix missing guild/home resources before opening those pages; the original game can persist a filtered fallback configuration. Repair only diagnosed fields from this user's own original save if necessary.

## Privacy and resumption

Keep archives, saves, keys, Google tokens, signed download URLs, logs, screenshots, device IDs, build outputs, and signing material in the private workspace. `.gitignore` is not a substitute for reviewing publication contents. Do not upload raw research folders.

Update private `SESSION.md` at every completed stage: device/build facts, paths, completed checks, current blocker, the next human checkpoint, and the next computer action. Mark evidence as file-verified, runtime-observed, or user-confirmed. Never conflate them.

A session is complete when the user accepts the target behavior or the agreed attainable subset, and private artifacts plus rollback instructions are handed over. Do not claim complete game preservation from reaching the title screen. Use `docs/ACCEPTANCE.md`.
