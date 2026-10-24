# Troubleshooting by evidence

| Symptom | Check first | Avoid |
| --- | --- | --- |
| No source trust dialog | Cable/data connection, unlock, pairing software, actual management restrictions | Assuming there must be a lock-screen password, resetting the device, or removing supervision |
| Tiny backup despite a large game | Actual per-app backup inventory, excluded caches, available normal export route | Calling the backup complete based on its checkbox |
| Android missing/unauthorized in ADB | Selected serial, unlocked screen, debugging authorization, server-port consistency | Installing repeatedly without a detected authorized device |
| Installer denied with no visible prompt | Model-specific USB-install permissions and actual phone-side state | Reporting success from sending the install command |
| Local client stuck loading | Exact build profile, complete manifests, genuine missing dependency, original initialization order | Forcing async tasks or cache hits to succeed |
| Title works, menu fails | Shared menu backgrounds/atlases and their dependencies | Rewriting the menu or declaring the whole game restored |
| Album preview exists but full image fails | Separate preview, full static, live-card prefab, shader/effect closure | Treating a preview as the actual card |
| Pink/missing material | Android GPU programs, matching properties, external PPtr mapping, reloaded typetree proof | Changing BuildTarget alone or swapping an arbitrary shader |
| File exists but asset still unavailable | Actual expected length/hash, closure, restarted runtime catalog | Repeated root-bundle conversions against stale in-memory state |
| Some stories fail while main/event stories work | Exact script, actor/background/effect resources, voice descriptor and all required clips | Blaming the Android phone model without a missing-resource report |
| A voice file is present but silent | Original cue descriptor/aliases, complete clip dependencies, actual AudioSource playback | Renaming a different voice or fabricating cue success |
| Guild rooms missing or levels disappear | Missing scene/furniture and whether the native client already persisted a filtered list | Replacing all progress with defaults or someone else's save |
| Room visible, no people | `guildspine/` model and its effect/material closure, rather than only `spine/` | Assuming the room background includes the character |
| Home characters changed | Original home assets were unavailable and a fallback layout may have been saved | Resetting the whole save or assuming ownership was lost |
| Data volume is smaller | Active versus duplicate/older bundles, iOS program, raw R media, remaining source-present gaps | Calling every omitted byte redundant or promising lossless migration from size alone |
| Source current-MD5 file absent | Valid older cache variants and internal bundle identity | Deleting all non-current cache files before checking |
| Large binary transferred but movie fails | Destination SHA and length; binary-safe ADB sync transfer | Trusting a zero exit code or using text-mode stdin for media |
| Authenticator login black screen/crash | Specific WebView/cookie stack, upstream fix status | Asking for the user's password or blindly applying an old app patch |
| No Google login available | A version-verified local common supplement, then exact missing dependencies | Claiming the full target works with Metal-only assets |

Use bounded resource batches and keep each defer report. A rejected conversion should not hide other independently verified resources; it also must not be silently included. The converter's explicit defer mode records failures while importing only successful, round-trip-verified entries.

When restoring a filtered home/guild configuration, fix resources first, preserve current ciphertext, change only the diagnosed fields from this user's own original save, assert all other fields unchanged, and verify encryption plus phone round-trip. A scene-transition cancellation alone is not proof of missing content.
