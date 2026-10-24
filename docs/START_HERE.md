# What your AI should do with you

You do not need to know what ADB, a resource bundle, or a shader is. Your AI should handle the computer side and explain only what you need to do next.

## The first conversation

Give the AI this repository link and say "Teach me how to do this." It should ask which iPhone/iPad, Android phone, and computer you have, then choose a folder for the work. It must check whether an ordinary export is enough before suggesting any system modification.

The original iOS installation contains the irreplaceable content. Keep it installed and avoid clearing its data, updating it unnecessarily, or freeing space by deleting game files while the migration is underway.

## When it will wait for you

Examples of a good checkpoint:

> Please connect your Android phone using a data-capable USB cable, unlock it, and tell me when it is connected. I will check whether the computer can see it.

> On the phone, allow the USB debugging prompt. If there is no prompt, tell me what you see. I will wait before attempting a transfer.

> We need an additional tool. It will be installed in the folder you selected and is used to inspect the game files. Please confirm before I install it.

> The local build and resources are ready. Please close and reopen the game, then open one card and one story CG. Tell me which screen is missing if either fails.

The AI should not rush past these steps, assume it saw a permission dialog, or repeatedly take control of a phone you are using for other things.

## What the result depends on

Your saved progress and your downloaded resources are different things. A card can be recorded as owned even when its artwork was not preserved. A story can be marked read while its voice files are absent. This workflow checks both, and reports actual missing files.

Most work happens on the computer once access is ready. Your AI may still need you for another permission, an optional download authorization, or testing. That is expected; connecting once does not remove all later human checkpoints.

## Continuing later

Tell the AI to pause whenever you need your devices. It should leave a private progress note. Next time, say "Continue from the migration session note." If you switch AI tools, point the new AI to this repository and the local `SESSION.md`. Do not post your full save or login details online.
