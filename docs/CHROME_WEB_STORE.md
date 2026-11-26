# Publishing to the Chrome Web Store

## Package ready for upload

```
dist/chess-coach-extension.zip
```

## One-time developer setup

1. Open [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
2. Sign in with a Google account
3. Pay the **one-time $5** developer registration fee (if not already registered)
4. Accept the developer agreement

## Create the listing

1. **New item** → upload `dist/chess-coach-extension.zip`
2. Fill in the store listing (copy/paste below)
3. Privacy policy URL (required because of chess.com host permission):
   ```
   https://github.com/pmaxit/chess-coach/blob/main/docs/PRIVACY.md
   ```
4. Add at least **1 screenshot** (1280×800 or 640×400) of the side panel on chess.com
5. Set visibility: **Public** (or Unlisted for testing)
6. Submit for review

## Suggested listing text

**Name:** Chess Coach — Stockfish arrows for chess.com

**Summary (132 chars max):**
Side-panel Stockfish coach for chess.com with on-board arrows. For bots, unrated, and training only.

**Description:**
Chess Coach opens as a Chrome side panel on chess.com. It reads the current board, analyzes with Stockfish in your browser, and draws green / blue / gold arrows for the best candidate moves — plus short explanations.

Intended use:
• Play vs bots / Chess.com Coach
• Unrated / casual games (with consent)
• Training and post-game study

Not for rated games. Using an engine in rated play violates chess.com Fair Play Policy.

Features:
• Live board read (no screen capture)
• MultiPV suggestions (best / 2nd / 3rd)
• Chess.com-style arrows on the board
• Adjustable analysis depth
• Runs locally — game data stays on your device

**Category:** Sports (or Productivity)

**Language:** English

## Single purpose / permissions justification (review form)

Single purpose: provide local Stockfish analysis and teaching arrows while studying chess.com positions.

Permission justifications:
• `https://www.chess.com/*` — read piece positions and overlay suggestion arrows
• `sidePanel` — coach UI
• `storage` — remember depth / settings
• `scripting` / `activeTab` — ensure content script is available when analyzing

Remote code: none (Stockfish WASM is bundled).

## Review tip

In the listing and description, emphasize **training / bots / unrated only**. Reviewers and chess.com both care about engine assistance in rated play.
