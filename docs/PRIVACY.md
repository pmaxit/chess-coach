# Privacy Policy — Chess Coach

**Last updated:** November 26, 2026

Chess Coach (“the Extension”) is provided for personal chess training on chess.com.

## What we access
- The Extension runs on `https://www.chess.com/*` pages to read the visible board position (piece locations / FEN) so it can suggest moves.
- Analysis runs **locally in your browser** using Stockfish (WebAssembly). Board data is sent to the Extension’s side panel and engine worker on your device.

## What we do not do
- We do **not** collect, sell, or transmit your games, account data, or personal information to our servers.
- We do **not** require an account with us.
- We do **not** use analytics SDKs or advertising trackers in the Extension.

## Permissions
- **host permission (chess.com):** required to read the board and draw suggestion arrows.
- **storage / sidePanel / scripting / activeTab:** used only for the coach UI and injecting the content script when needed.

## Fair play
The Extension is intended for unrated games, bots/coach modes, training, and post-game study. Using engine assistance in rated games may violate chess.com’s Fair Play Policy.

## Contact
For privacy questions, open an issue at: https://github.com/pmaxit/chess-coach/issues

## Changes
We may update this policy in the repository; the “Last updated” date will change when we do.
