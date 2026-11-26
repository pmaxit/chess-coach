# Chess Coach

Side-panel coach for [chess.com](https://www.chess.com): reads the live board, runs **Stockfish** in your browser, and draws **green / blue / gold** arrows for the best moves — with short plain-English explanations.

> **Fair play:** Use only for unrated games, vs bots/coach, training, or post-game review. Using an engine in *rated* games violates chess.com’s Fair Play Policy. No auto-play — you make every move.

---

## Chrome extension (recommended)

### Install

1. Open Chrome → `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select the `extension/` folder in this repo
4. Open a chess.com game (bot / coach / unrated)
5. Click the **Chess Coach** icon to open the side panel
6. Click **Analyze** (or leave **Auto: ON**)

Details: [`extension/INSTALL.md`](extension/INSTALL.md)

### Features

- Live FEN from the page DOM (no screen capture)
- Stockfish MultiPV (best / 2nd / 3rd)
- Chess.com-style arrows on the board
- Depth control in the side panel

---

## Desktop app (optional)

Python overlay that can screenshot a calibrated board region and coach with Stockfish locally.

```bash
python3 -m pip install -r requirements.txt
brew install stockfish   # or set path in coach/engine.py

python3 calibrate.py     # snip the 8×8 board
python3 make_templates.py  # once, from a starting position
python3 main.py
```

Requires macOS Screen Recording permission for capture.

---

## Repo layout

| Path | Purpose |
|------|---------|
| `extension/` | Chrome MV3 side-panel coach + Stockfish WASM |
| `main.py` / `coach/` | Desktop Tk coach |
| `calibrate.py` / `make_templates.py` | Desktop board setup |

## License

Stockfish is GPL. This project’s glue code is provided as-is for personal training use.
