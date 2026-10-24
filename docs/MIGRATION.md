# Migration procedure for the guiding AI

Do not hand this entire page to a beginner as a command dump. Follow `AI_RUNBOOK.md`, pause for human actions, and run the computer steps yourself when possible. Commands below use `python` to mean the interpreter in the user's agreed environment. Working directory is the repository root. This is a Windows-first extracted reference workflow; validate tool equivalents before adapting it to another OS.

## 1. Prepare a private workspace

After installation approval, create a Python environment and install `requirements.txt`. Use an available supported interpreter; the reference tools ran on Python 3.11. Configure caches/temp files under the chosen workspace if disk placement matters. Install only the additional components actually needed: Android Platform Tools; Java and Android build-tools for APK signing; an official arm64 Frida Gadget for the local build; optionally iOS USB/SSH tools and the separate Play dependency set.

Copy `local-config.example.json` to ignored `local-config.json`. Change all paths and the device serial. Do not copy another person's config. Use a separate package such as the example `com.yumekuro.local`; official `com.gcrest.yumekuro` is rejected. Run:

```text
python tools/yume.py init
python tools/yume.py doctor
```

The private workspace is organized as follows:

```text
work/
  SESSION.md
  exports/yumekuro-archives/{app.tar,data.tar}
  android-original/{base.apk,split_config.arm64_v8a.apk}
  resource-analysis/                    # indexes, original metadata, private constants
  android-import/source-save/Production/
  offline-player/build/                 # private local signing files
  native-offline/build/                 # manifests, proofs, bounded selections
  native-offline/private-googleplay-auth/
  private/                             # host keys, backups, session-only data
```

Never commit this workspace. There is no reason to put game resources in the public Git history.

## 2. Preserve source containers

Follow `DEVICE_ACCESS.md`. If an ordinary export is sufficient, adapt its paths without pretending it is the SSH layout. For the demonstrated SSH route, verify identity/access and run:

```text
python tools/export_ios.py --app-container <discovered-app-container-parent> --data-container <discovered-data-container>
python tools/yume.py index
python tools/save_transfer.py extract
```

The app TAR is expected to contain `./ProductName.app/...`; the data TAR contains `./Documents/Production/...` and `./Library/...`. Confirm the actual layout. The exporter validates archive structure and records a local SHA-256. The save extractor reads only encrypted Production files, preserves their bytes, and records per-file hashes. It does not decrypt or fabricate progress. Retain the originals unchanged.

## 3. Acquire matching Android originals

Use the user's legitimate official installation/download. On a connected device, inspect `pm path --user 0 com.gcrest.yumekuro`, and pull its base and the arm64 split into `android-original/`. Read the installed version and ABI. A Play base APK alone may lack the correct native split and on-demand packs.

Run:

```text
python tools/yume.py extract-inputs
```

This extracts `assets/Octo/l`, `assets/Octo/octocacheevai`, IL2CPP metadata, and the arm64 `libil2cpp.so`, then checks the exact pinned profile. A mismatch stops the native route. Preserve the official APKs; do not re-sign them in place or disable the hash gate to keep going.

## 4. Decode and match the resource catalogs

The included local index-decoding research derives candidate constants from the user's own APK, rather than distributing keys:

```text
python tools/scan_android_resource_config.py
python tools/try_octo_manifest.py
python tools/yume.py decrypt-ios-index
```

The Android decoder requires AES padding and the resource-index payload checksum to agree. It writes `android-octo-index.bin` and private key/IV material under `resource-analysis/`; these are never public artifacts. The iOS decoder verifies its own internal checksum using those locally derived constants. If the format/key differs, investigate the input build and serialized Production settings. Do not continue with a plausible-looking but unverified protobuf.

`inspect_octo_index.fields` is the shared minimal wire parser. The relevant Android index fields are documented in `TECHNICAL_REFERENCE.md`. `SourceAssets` resolves iOS logical names against the TAR index and verifies source size and MD5 before any UnityPy conversion.

## 5. Build a local client, without borrowing another app

Generate a **new private signing key** in `offline-player/build/offline-player-private.p12`, alias `offline-player`, with a locally stored password file `signing-password-private.txt`. Use Java `keytool`, a distinct local identity, and restrictive permissions. Do not reuse a key from another account or publish the password. Keep this key for later updates of this installation.

Obtain official [Frida Gadget](https://frida.re/docs/gadget/) for Android arm64 from its upstream release. Record version/source/hash locally. Decompress it as `native-offline/build/libofflinegadget.so`; do not extract a Gadget from an unrelated game or include one in this repository. The runtime uses Frida APIs including `Interceptor.replaceFast`, QJS, and module export lookup; verify compatibility with the chosen release before use.

After source/profile validation:

```text
python tools/yume.py bootstrap
node --check <work>/native-offline/build/bootstrap.js
python tools/build_native.py
```

The builder updates the package/resources table and label, removes the clone's Internet permission, enables `debuggable`/`extractNativeLibs` in the existing manifest attributes, adds Gadget as a `libmain.so` dependency, and signs/validates both local APKs. It uses the private Java/build-tools paths in config. Do not assume missing manifest attributes were inserted: inspect the built package and confirm the intended flags before installation.

Human checkpoint: approve installing the separate local client, then use the explicitly selected device with `install-multiple` for the two signed APKs. Wait for phone installer dialogs; inspect the actual installed package and confirm `run-as <local-package> id` succeeds. Do not launch into restored home/guild pages before the required resources are ready.

## 6. Set up resource directories

Create the clone's `files/offline` private directory using `run-as`, and its external files directory `/sdcard/Android/data/<local-package>/files/offline`. The runtime script belongs in the external directory; resource payloads and manifests belong in private `files/offline`.

Push the generated `bootstrap.js` to the external directory and round-trip its hash. Copy the six initially empty supplements (including `raw-supplement.json`) created by `init` into private `files/offline`. Do not run the app with missing supplement files or an incomplete snapshot.

Preserve the original Android Octo `l` and encrypted `octocacheevai` bootstrap metadata in the original locations expected by this build, plus the source's Octo version marker. The observed private locations are `files/Octo/l`, `files/octo/pdb/11/1001/octocacheevai`, and `files/octo/v`; inspect this build before using a different layout. The authoritative local resource provider replaces delivery, not the game's need to initialize its original catalog. Avoid obsolete character-specific seeded cache folders.

## 7. Create the exact resource snapshot

```text
python tools/prepare_local_snapshot.py
python tools/inspect_android_shaders.py
```

The snapshot streams verified reconstructed bundles to the clone. It accepts only unchanged files or one-byte BuildTarget candidates whose **whole wrapped original MD5 and length match the Android index**. Hard-coded candidate offsets are merely a bounded search followed by an exact checksum gate; never use them as blind patches. The plain UnityFS payload is hashed again for the local manifest.

Initialize the target directories before this command. A complete pass produces `local-snapshot.json` with `complete: true` and an audit TSV. A transfer interruption is not success: rerun/resume after inspecting phone hashes and the snapshot completeness. Do not start the app against a partial catalog.

## 8. Recover validated non-identical resources

Exact reconstruction deliberately leaves out some iOS-specific bundles. Use the appropriate converter, rather than weakening its MD5 check:

| Kind | Tool | Required proof |
| --- | --- | --- |
| Master tables | `prepare_local_metadata.py` | Same typed table data before/after platform serialization |
| Cards, CG, rooms, character models, scripts, supported effect materials | `prepare_local_visuals.py --selection-file <file>` | Non-shader objects and streams unchanged; matching Android shaders; round-trip proof |
| Vorbis clips | `prepare_local_audio.py --selection-file <file>` | Original clip metadata/streams retained; platform-field-only decompressed changes |
| Cue descriptors | `prepare_local_cuesheets.py --selection-file <file>` | Original cues/tracks/references unchanged; every direct audio dependency present |
| Independent raw movies/audio | `prepare_local_raw.py` | Top-level field 4, exact Android MD5/size, separate R identity, phone SHA |
| Official Android PAD entries | `import_play_pack.py` | Exact Android-index MD5, ZIP CRC, phone SHA; see optional route |

For portable selections, use e.g. `python tools/yume.py plan --prefix unit/meister/cardimage/` to write a private `selection.json`. Repeat separately for fairy cards, live cards, `gallery/albumthumbnail/`, `story/background/`, scripts, guild scenes/furniture, `guildspine/`, and `spine/`. `plan` checks source existence, not converter compatibility; inspect object/shader types before submitting a batch. The visual converter's explicit prefix/type allowlist is intentional.

Partition by supported format and estimated source bytes. Keep each batch within available RAM (for example 32–64 MiB of source), not hundreds of megabytes just because a manifest can list them. Importers currently buffer selected output until transfer. One importer writes a shared manifest at a time. Phone hashes are checked before success is reported.

Use `--skip-unsupported-shaders` only to record and defer known unsupported names. It is not permission to substitute a superficially similar shader. A ComputeShader or invalid external reference remains a genuine conversion failure. Inventory a guild batch first and keep unsupported optional search/compute bundles separate from normal room scenes.

For audio, first import missing authentic clips, then only descriptors whose dependencies are complete. Some cue-sheet logical paths intentionally have different internal cue names: preserve those aliases. Use `inspect_cuesheet_sources.py` and the actual catalogs to form a type-correct queue, not a made-up fixed character list.

If the current index references an absent canonical file, inspect older cached versions before declaring content lost. Planning, visual, audio, and cue tools support opt-in `--allow-verified-cache-variants`. This validates the filename MD5 and exact internal AssetBundle logical name, rejects ambiguous versions, and uses the actual older bundle's dependency list. Older bytes remain adaptations, never exact current Android originals. Do not use the flag to bypass a corrupted canonical data file.

Raw media are not AssetBundles. Run `python tools/prepare_local_raw.py` after creating the payload directory. It uses one bounded PC temporary file, ADB sync push, and a device-local copy. On one Windows transport, binary shell stdin truncated at byte 0x1A; require final phone hashes even if a transfer exits successfully. R filenames must stay separate from A numeric IDs.

## 9. Fill shared Android dependencies when necessary

Use `docs/GOOGLE_PLAY.md` only if authentic Android shaders/shared assets are still missing and the user chooses that route. In the demonstrated release, key targets included `shaders/card`, effects, shared menu backgrounds, story emotion effects, common SE, room furniture, and cue descriptions. Inspect each actual pack and its expected index records; a pack name is not proof it contains optional CG or voice content.

## 10. Audit before first restored launch

Run `audit_resource_dependencies.py --selection-file <required-roots>` for the actual home/guild/card/story resources. Its report identifies missing authentic sources. `audit_card_assets.py` inventories card/CG availability, not ownership or unlock entitlement.

Make sure all local manifests exist and have `format: 1`. Merge by logical name in runtime order: exact snapshot → metadata → audio → cue sheets → visual adaptations → raw media → official Play imports. Official Play wins over a prior adaptation. Verify the actual files on the phone, not just PC rows. Run `python tools/audit_final_state.py --phone-verify` for the full export inventory and actual phone hashes. Follow `ACCEPTANCE.md` to interpret source-only names, cached candidates, and static fallbacks; a cached inventory candidate is not yet a validated conversion.

## 11. Import this user's encrypted progress

Human checkpoint: confirm the local app may be stopped and its save replaced with this user's verified export. Then:

```text
python tools/save_transfer.py import --confirmed
```

The command backs up an existing local Production directory, keeps it under a timestamped name on the phone, streams original encrypted files, and round-trips every file hash. It never writes the official package. If platform preferences are needed, inspect and map the relevant Unity settings from the user's own plist; do not copy iOS preferences blindly into Android SharedPreferences XML or change unrelated device/auth settings.

## 12. Acceptance, narrow repairs, and handover

Ask the user to restart once after a completed batch. Follow `ACCEPTANCE.md`. Use passive logs and coverage reports if the user is testing; do not steal their screen. A missing animated card uses the native static renderer only if its own full-size static asset and closure exist; complete animations follow the original path.

If the client previously filtered guild/home records, fix prerequisites first and compare original/current saves. `repair_save_fields.py` can prepare a minimal local repair after a locally derived, verified save key is available. It does not discover that key or upload/deploy the repair. Identify the actual main save by its decoded schema, not merely "largest file." The save key is distinct from the Octo resource-index key. Use locally inspected client code/metadata, validated PKCS#7 plus expected JSON schema, and no published key constants. Restore only diagnosed `_userGuildList` or `_userHomeConfigList` fields from this user's original. Back up current ciphertext, assert every other field unchanged, re-encrypt, deploy after stopping the app with user authorization, and round-trip SHA.

Finish by handing over local build/key/runtime paths, immutable exports, manifests, acceptance notes, and rollback instructions. A failed restore can be rolled back by stopping the **local** app and restoring its saved directory/ciphertext; never reset the source device as a troubleshooting step.
