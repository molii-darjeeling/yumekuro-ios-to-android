# Reusable technical findings

These findings explain the demonstrated route. They are not a dump of a player's account or a promise that every offline game uses the same formats. Native addresses below are RVAs for the pinned arm64 binary only.

## 1. Save state and resource availability are separate

The encrypted `Documents/Production` records can preserve ownership, levels, read flags, home configuration, and guild progress while the actual images, clips, or model bundles are absent. Restoring a save does not recover excluded/downloadable content. A working title/home screen is not proof that albums, voices, or guild life work.

Storage size also does not prove completeness. A full iOS export includes an iOS program, its embedded resources, data/cache files, and potentially obsolete versions; the Android installation uses a different program and one active local resource catalog. Some source resources can be omitted because no supported conversion or complete dependency closure exists. Report that explicitly instead of attributing the entire size difference to compression or deduplication.

## 2. Join by logical resource name

The decoded Octo protobuf's top-level repeated field 2 contains AssetBundles (A IDs). Top-level repeated field 4 contains independent raw media (R IDs). Include both families in final coverage reports. Relevant record fields:

| Field | Meaning in the inspected release |
| --- | --- |
| 1 | Platform-specific resource ID |
| 3 | Logical resource name, UTF-8 |
| 4 | Expected original bundle byte length |
| 8, repeated | Direct dependency IDs in this platform's index |
| 10 | Expected original MD5 string |

Map the same logical name between iOS and Android. Never copy an iOS numeric filename to the same Android number without this join. Build dependencies from the Android index, not an assumed naming convention.

For an iOS ID, let `enc = ("A" + str(id)).encode().hex()`. Observed source paths:

```text
data.tar: ./Library/octo/v1/11/<enc[-1]>/<enc>/<iOS MD5>
app.tar:  ./ProductName.app/Data/Octo/<enc[-1]>/<enc>
```

The production namespace in this build is **11**. A development default of 10 found in code is not its shipped Production setting. Inspect the serialized Production object. Export caches and application-embedded bundles; some resources exist in only one.

For raw media use `R` instead of `A` in the identity. The data-cache MD5 filename also has the logical name's extension. These are ordinary media bytes, not wrapped UnityFS. The local provider keys Octo lookups by ID **and** logical name to avoid A/R numeric collisions, and stores raw payloads as `R<ID>.<ext>`. Raw availability hooks include 0x46B5EFC and 0x46BBE30; 0x46BBCD0 is a cached-size query, not an availability function.

An older cache entry is not automatically junk or a valid substitute. Opt-in recovery verifies the filename MD5 and exact internal `AssetBundle.m_Name`; distinct valid versions are rejected as ambiguous. Preserve its actual internal dependencies, require those names in the Android catalog, then apply normal conversion proofs. Inventory-only candidates stay unverified until that completes.

## 3. Octo envelope versus UnityFS

Some original indexed files have a reversible 48-byte transport envelope. The verified inspected form is:

```text
wrapped = b'\x1f' + xor_ff(plain[1:48]) + plain[48:]
plain   = b'U'    + xor_ff(wrapped[1:48]) + wrapped[48:]
```

Only accept this form when signatures and the expected whole-file MD5 validate. The original index may hash the wrapped form while Play supplies plain UnityFS. The local Unity loader consumes plain UnityFS; retain a separate SHA-256 for those actual local bytes.

The encrypted resource-index container is a different format: version byte, AES-CBC content, PKCS#7 padding, and a 16-byte MD5 of its protobuf body. Derive constants locally and validate all those conditions. Do not publish resource keys or confuse them with the save's encryption key.

## 4. Exact reconstruction and adaptations

Many bundles differ only by a serialized Unity BuildTarget value (iOS 9, Android 13). A candidate byte change counts as an **exact Android reconstruction** only if its full length and Android-index MD5 match. Searching candidate offsets is acceptable because a whole-file checksum gate follows; blindly changing byte offsets is not.

Other bundles require deliberate platform adaptation. Their recompressed bytes do **not** match the original Android bundle MD5. Record them as adaptations, preserving every non-shader object and resource stream, and validate the reloaded serialization. Do not relabel them as official Android originals.

## 5. Real local asset provider

The separate client uses the original Unity UI, async tasks, file loaders, card renderers, and save logic. A Frida Gadget script supplies real local PAD/Octo locations:

```text
private:  /data/user/0/<local-package>/files/offline/payload/<Android resource ID>
private:  /data/user/0/<local-package>/files/offline/*-supplement.json
external: /sdcard/Android/data/<local-package>/files/offline/bootstrap.js
```

The script calls original `ReplaceAssetNamesBasedOnRules` (0x308BC5C) to derive real pack/path routing. Character-story clips can route to `sound1`, fairy stories to `sound2`, main/event clips to other numbered sound packs, and common stories to `sound_other`; string prefixes alone do not determine the pack.

Both legacy Octo and PAD must agree on the same actual local files. A usable resource requires its own file and recursive dependencies with the expected lengths. IOcto caching implementations can bypass their generic interface, so patching only the interface is insufficient.

Key inspected RVAs:

| RVA | Role |
| --- | --- |
| 0x46B5D08, 0x46BBC78 | Concrete Octo resource availability |
| 0x46B687C, 0x46BC2B0 | Legacy disk cache state |
| 0x46B6970, 0x46BC2C8 | Legacy actual file path |
| 0x46B6844, 0x46BC2A8 | In-app/embedded cache distinction |
| 0x46A79E8 | Download callback; locally unavailable files must really fail |
| 0x308D0B4 | PAD `IsAssetCached` — **in-memory loaded-object semantics** |
| 0x5168244 | Standalone disk-availability query |

**Do not globally force PAD `IsAssetCached` true because a disk file exists.** That bypasses the actual bundle load and causes invalid in-memory states. Do not hook global IL2CPP throws to suppress failures; that disrupts native exception unwinding. Return real async tasks and real failure callbacks.

The provider builds its catalog once at startup. Writing new files/manifests does not update the running catalog. Restart once after a completed batch; do not diagnose against stale runtime state.

## 6. Shaders and external references

Changing BuildTarget does not turn Metal GPU programs into Android programs. Use original Android shaders with matching names and property definitions, from the user's original APK or an authentic matching Android asset pack. Inventory the actual embedded/split serialized assets.

When replacing a Shader object's data, external PPtr `m_FileID` values refer to positions in that serialized file's external-reference list. Match by exact external file path and preserve `m_PathID`; do not copy the source file number blindly. Reject an absent/ambiguous dependency or an internal non-null reference that would require importing another object. Shader `m_Dependencies` and `m_NonModifiableTextures` require inspection.

With UnityPy, `get_raw_data()` can still read the original reader immediately after assigning/saving a typetree. Use the returned serialized bytes from `save_typetree`, repack, reload, and compare the **reloaded** raw bytes/tree to the expected replacement. Preserve non-shader raw objects and texture/resource stream hashes.

The included PMA Multiply port is deliberately constrained. It verifies neutral material color and texture transform, absence of relevant animated material properties, matching original Metal fragment bytes, and vertex equivalence after the specific neutral-uniform simplification. Only then does it use original Android `Spine/Skeleton` GPU programs while retaining the original Multiply pass states and properties. This is not a generic shader replacement recipe. PMA Additive and ComputeShader cases remain separate unsupported work unless equally strong equivalence is established.

## 7. Cards and story CG use several resources

Typical logical names:

```text
gallery/albumthumbnail/<unit>_card_sun_thumb    # album preview
unit/meister/cardimage/<unit>_card_sun         # full static card
unit/meister/livecardimage/<unit>_livecard_sun # animated card prefab + dependencies
gallery/albumthumbnail/<unit>_stl_sun_thumb    # story CG preview
story/background/<unit>_stl_sun               # full story CG
```

Moon uses `mon`, Pure uses `pur`, and evolved fairy cards use their own `unit/fairy/..._evo` family. Main-story CG uses `story/background/main_stl_...`. A preview is not the large card/CG. Inventory both.

The static-display policy retains the original native route:

- If a full animation dependency closure is available, keep the original animated renderer and unlock decisions.
- If animation resources are incomplete but this exact card's original full-size static resource and closure are present, call the original static readiness check and original static loader.
- If neither full asset is available, report it as missing. Do not upscale a thumbnail and label it recovered.

Original functions: `CheckCardAssetReady` 0x3089194; `CheckLiveCardAssetReady` 0x3089274; `CheckCardDisplayAssetReady` 0x3089380; `UICardContainer.LoadCard` 0x380C3F8; `LoadLiveCard` 0x380C6A8. Both loaders return a real UniTask struct (source pointer plus token storage); preserving the actual ABI matters. A pointer-only replacement is incorrect.

## 8. Guild disappearance is a persisted consequence

The original guild-page preparation checks room/furniture availability, builds a filtered guild list, and can save it. A missing room can therefore cause a guild/level to disappear from the current list even though the original export retains it. A missing model can leave a room visible with no people.

Fix scene/furniture and `guildspine/` resources first. Different resources serve `spine/` character previews and `guildspine/` room characters; one does not replace the other. Do not manufacture default guilds or levels. If already filtered, restore only `_userGuildList` from this user's original after comparing schemas and preserving every other current save field. A similar availability fallback can alter `_userHomeConfigList`; use the same narrow principle.

A single `OperationCanceledException` while leaving a scene can be normal cancellation of its old animation task. Evaluate what failed and whether the new scene loaded; do not classify every cancellation as corruption.

## 9. Voice requires clips and descriptors

An AudioClip alone may not be playable through the original sound system without its original cue-sheet descriptor and all required clips. Preserve cue names, aliases, tracks, external references, and direct dependency lists. Internal cue-sheet names need not equal their logical resource path.

The portable audio converter accepts the inspected Vorbis AudioClip format, retains all decompressed metadata/audio stream bytes, and changes only the platform field. Unsupported codecs are not assumed portable. The cue converter accepts the actual `Sge.AudioClipSoundCueSheet` schema and refuses incomplete direct dependencies.

For a diagnostic, observing the original track controller's `PlayNormalStart`/`PlayLoopStart` and Unity AudioSource `isPlaying` is stronger evidence than logging that an audio filename was requested. The runtime includes passive observations; human confirmation remains necessary for audible output and correct timing.

## 10. Optional Play delivery and reusable local supplements

The ordinary APK delivery response is not the on-demand module API. The inspected route requests `fdfe/assetModuleDelivery`, based on the protocol in [microG's AssetModule definitions](https://github.com/microg/GmsCore/blob/master/vending-app/src/main/proto/AssetModule.proto). Authenticated responses and signed URLs stay private.

Large packs can be inspected through bounded HTTP range reads of ZIP directory/selected entries. Require HTTP 206 and correct Content-Range, enforce byte budgets, check ZIP CRC and original Android-index MD5, and phone-verify every imported payload. Do not silently download the full multi-gigabyte pack when a server ignores Range.

Matching original Android resources are common game content, not a player's save. A previously obtained local supplement can therefore be technically reused for the same validated build without each recipient logging into Google. `local_asset_pack.py` restricts its export to verified original Android entries and revalidates the recipient's index on import. It excludes accounts and progress. It is a supplement, not an entire game or a promise that personal optional content is present.
