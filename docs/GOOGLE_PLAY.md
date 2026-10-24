# Optional Android assets: local supplement first, Google only when needed

Neither route retrieves a player's Yumekuro progress. Progress and personally cached content come from that user's iOS export.

## Route A: an existing authentic local supplement — no Google login

If the user has a matching Android resource supplement, use it offline. Do not make them register/login merely because a previous session did. The supplement must target the same game version/native profile and contain no saves, credentials, pairing codes, or authenticated URLs.

`tools/local_asset_pack.py export <private-output.zip>` exports only the current session's already verified **original Android** supplement entries, not its iOS archive, signing key, phone log, or save. This is useful for preparing a separately handled common pack. It does not publish the ZIP anywhere.

On the recipient's computer, prepare their own matching APKs/catalog and clone first, inspect the pack provenance/manifest, and pause for transfer authorization. Then:

```text
python tools/local_asset_pack.py import <local-pack.zip> --confirmed
```

Import checks the exact profile, every logical name/ID/dependency list, Android-index MD5, local SHA-256, ZIP CRC, and phone hashes. No Google authorization module is imported by this route. An invalid pack is rejected before transfer. The public repository includes the format/tooling, **not** a hosted game-resource pack or an assumed download URL. Keep distribution decisions separate from the code repository and retain all applicable content/tool terms.

If no pack or authorized download path is available, identify the actual missing dependencies. Do not pretend iOS Metal shaders work on Android or claim the target is complete.

## Route B: optional gplaydl authorization

The inspected downloader was [gplaydl](https://github.com/rehmatworks/gplaydl) 4.2.1 with its [Android authenticator](https://github.com/rehmatworks/gplaydl-authenticator). **This is third-party software, not a Google-provided migration service.** Its authenticator/dispenser design can sync account authorization into a token service/pool. Before installation or login, the AI must inspect the current upstream behavior, explain where authorization goes, offer the local-pack route, and wait for the user's explicit choice. Do not imply that credentials remain solely in a browser on the phone.

The user performs sign-in/2FA themselves. Never ask for their Google password or tokens in chat. Pairing codes are session-specific and are provided locally on stdin to the helper, not embedded in scripts. Keep the tool's private config directory, authenticated responses, and signed download URLs under the ignored workspace. Do not reuse another person's authorization.

After separate installation and authorization checkpoints:

```text
python tools/googleplay_probe.py status
python tools/googleplay_probe.py link
python tools/googleplay_probe.py query --version 551
```

The `link` command reads one pairing code from stdin. Inspect its success and actual account/device entitlement; an available APK does not prove optional resources are present.

To inspect a needed module, `fetch_play_asset_pack.py <pack>` requests metadata by default. Full downloads require `--download` and have a configured bound. For larger packs, use `import_play_pack.py <pack> --remote --prefix <exact-logical-prefix>` or explicit selections; `RemotePlayZip` caps transferred bytes and rejects a full response to a ranged request. Stage a new authorization only when necessary; do not retry account login indefinitely as a resource diagnosis.

Useful module families in the investigated release included shaders, story, sound/sound_other, menu backgrounds, masterdata, effects, furniture, and guildspine. Inspect actual entries and the original routing function. Offline Play packs did **not** contain every optional card, CG, or voice. A downloaded module is not a substitute for the user's own original cache.

## Reusable login-page crash diagnosis

An inspected authenticator revision could crash in `GoogleLoginActivity.onPageFinished` because `CookieManager.getCookie(url)` returned null before login cookies existed, and a downstream parser passed it into a regex matcher. This is distinct from an invalid password, denied Play entitlement, or a broken game resource.

The minimal source change is to return on a null cookie and wait for later page events:

```kotlin
val cookies = CookieManager.getInstance().getCookie(url) ?: return
```

The small [patch](../patches/gplaydl-null-cookie.patch) records that fix against upstream revision `32fc37413655d828437b435848f30523e40b7fd2`. Check whether the upstream version already fixed it before applying. A locally repaired build should use a distinct application ID/signing identity and must retain its upstream license/attribution. Do not repackage the entire third-party app into this repository. User installation is another checkpoint; the null guard is not a guarantee that all Android/WebView versions will support the login flow.

Once all required assets are local, routine offline play does not require this downloader or a new resource download on each launch. Discuss revoking/removing a no-longer-needed third-party authorization with the user using the current service's actual controls; do not claim an app uninstall alone revokes remote tokens.
