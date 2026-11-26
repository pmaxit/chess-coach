# Chess Coach — Chrome extension

Side panel for **chess.com** that reads the live board, runs Stockfish in your browser, and draws **green / blue / gold arrows** for the best 3 moves.

> **Fair play:** Use only for unrated games, vs bots/coach, training, or post-game review. Using an engine in rated games violates chess.com’s Fair Play Policy.

## Install (unpacked)

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode** (top right)
3. Click **Load unpacked**
4. Select this folder:
   ```
   ~/Projects/reinforcement/chess_coach/extension
   ```
5. Pin **Chess Coach** from the extensions puzzle menu
6. Open [chess.com](https://www.chess.com) (Play Coach / vs bot / unrated)
7. Click the Chess Coach icon — the **side panel** opens
8. Click **Analyze** (or leave **Auto: ON**)

## What you get

- Live FEN from the page’s pieces (no screen capture)
- Stockfish MultiPV suggestions in the side panel
- Chess.com-style arrows on the board (best / 2nd / 3rd)
- Depth control: Fast → Very deep

## Tips

- Keep the chess.com **game tab** focused when analyzing
- If arrows don’t show, click **Re-read board**
- If the board is flipped (you’re Black), arrows follow orientation automatically

## Files

| Path | Role |
|------|------|
| `manifest.json` | MV3 extension config |
| `sidepanel.*` | Coach UI |
| `content.js` | Reads pieces + draws SVG arrows |
| `worker/stockfish.js` | Stockfish 16 (single-thread WASM) |
| `engine.js` | UCI bridge |
