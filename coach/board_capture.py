"""Capture a screen region and reconstruct the chess position via template matching."""
import json
import os

import cv2
import numpy as np

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")
TEMPLATE_DIR = os.path.join(ASSETS, "templates")

PIECES = ["P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]
EMPTY_FILLERS = ["empty_light", "empty_dark"]

# start-position map (standard): used by template extractor
START_POS = [
    "rnbqkbnr",
    "pppppppp",
    "........",
    "........",
    "........",
    "........",
    "PPPPPPPP",
    "RNBQKBNR",
]


def load_calibration(path=None):
    path = path or os.path.join(ASSETS, "calibration.json")
    with open(path) as f:
        return json.load(f)


def grab_region(region):
    import mss
    left, top, w, h = region
    with mss.MSS() as sct:
        img = np.array(sct.grab({"left": int(left), "top": int(top), "width": int(w), "height": int(h)}))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


def cell_images(img, board_w, flipped=False):
    """Yield (row_from_top, col_from_left, cell_bgr). Row 0 = top of captured image."""
    ch = img.shape[0] // 8
    cw = img.shape[1] // 8
    cells = []
    for r in range(8):
        row = []
        for c in range(8):
            cell = img[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw]
            row.append(cell)
        cells.append(row)
    return cells, ch, cw


def _ink_mask_vs_empties(f32, empty_masks_colors):
    """Pixels that differ from BOTH empty-square colors are certainly piece ink."""
    mask = None
    for color in empty_masks_colors:
        d = np.linalg.norm(f32 - color, axis=2)
        m = d > 45.0
        mask = m if mask is None else (mask & m)
    if mask is None:
        raise ValueError("empty templates required")
    return mask


_CENTER = slice(22, 42)


def _center_color(f32):
    """Median BGR of the central patch (piece bodies cover the square centre)."""
    patch = f32[_CENTER, _CENTER].reshape(-1, 3)
    return np.median(patch, axis=0)


def _border_bg(f32):
    """Per-square background from the border ring (robust to last-move highlights)."""
    h, w = f32.shape[:2]
    ring = 6
    parts = [
        f32[:ring, :].reshape(-1, 3),
        f32[-ring:, :].reshape(-1, 3),
        f32[:, :ring].reshape(-1, 3),
        f32[:, -ring:].reshape(-1, 3),
    ]
    return np.median(np.concatenate(parts, axis=0), axis=0)


def _ink_from_bg(f32, bg, thresh=28.0):
    return np.linalg.norm(f32 - bg, axis=2) > thresh


def classify_cell(cell, templates, _cache={"prep": None}):
    """Return piece char ('.','?',[PNBRQKpnbrqk]) for one square image.

    Uses per-cell border background so move-highlights don't look like ink,
    then matches ink-shape IoU + ink brightness (white vs black) to templates.
    """
    size = 64
    sub = cv2.resize(cell, (size, size), interpolation=cv2.INTER_AREA)
    sub_f = sub.astype(np.float32)
    bg = _border_bg(sub_f)
    sub_mask = _ink_from_bg(sub_f, bg)
    ink_px = int(sub_mask.sum())
    ink_frac = ink_px / float(size * size)

    # empty: almost no ink relative to THIS square's own background
    if ink_frac < 0.035:
        return "."

    ink_pixels = sub_f[sub_mask]
    ink_mean = ink_pixels.mean(axis=0) if len(ink_pixels) else _center_color(sub_f)
    ink_brightness = float(ink_mean.mean())  # white pieces are bright

    if _cache.get("prep") is None or _cache["prep"][0] != id(templates):
        prep = {}
        for name, t in templates.items():
            if name.startswith("empty_"):
                continue
            tf = cv2.resize(t, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
            tbg = _border_bg(tf)
            tm = _ink_from_bg(tf, tbg)
            tp = tf[tm]
            prep[name] = {
                "mask": tm,
                "brightness": float(tp.mean()) if len(tp) else 128.0,
                "ink_frac": float(tm.mean()),
            }
        _cache["prep"] = (id(templates), prep)

    _, prep = _cache["prep"]

    best, best_name = -1.0, None
    for name, meta in prep.items():
        tm = meta["mask"]
        inter = np.logical_and(sub_mask, tm).sum()
        union = np.logical_or(sub_mask, tm).sum()
        iou = inter / union if union else 0.0
        # white vs black: penalize brightness mismatch
        bpen = min(0.35, abs(ink_brightness - meta["brightness"]) / 220.0)
        s = iou - bpen
        if s > best:
            best, best_name = s, name

    if best_name is None or best < 0.10:
        # low confidence — if little ink, call empty
        if ink_frac < 0.08:
            return "."
        return "?"
    return _piece_of(best_name)


def _save_template_name(piece, suffix):
    """Case-insensitive-FS-safe template name: w/b prefix + type + square shade."""
    color = "w" if piece.isupper() else "b"
    return f"{color}_{piece.upper()}_{suffix}"


def _piece_of(tmpl_name):
    # names look like: w_K_light / b_p_dark / empty_light
    parts = tmpl_name.split("_")
    if parts[0] in ("w", "b") and len(parts) >= 2:
        p = parts[1]
        return p if parts[0] == "w" else p.lower()
    return "?"


def load_templates():
    templates = {}
    for fn in os.listdir(TEMPLATE_DIR):
        if fn.endswith(".png"):
            templates[fn[:-4]] = cv2.imread(os.path.join(TEMPLATE_DIR, fn))
    return templates


def _cell_edge_density(cell):
    g = cv2.cvtColor(cv2.resize(cell, (64, 64), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return float(cv2.Canny(g, 50, 120).mean()) / 255.0


def occupancy_grid(img, flipped=False, margin_frac=0.14, thresh=0.04):
    """8x8 bool grid: True = occupied. Image top row first (rank 8 if not flipped)."""
    cells, ch, cw = cell_images(img, img.shape[1])
    m = int(ch * margin_frac)
    grid = [[False] * 8 for _ in range(8)]
    for r in range(8):
        for c in range(8):
            sub = cells[r][c][m:ch - m, m:cw - m]
            grid[r][c] = _cell_edge_density(sub) >= thresh
    if flipped:
        grid = [row[::-1] for row in grid[::-1]]
    return grid


def occupancy_bitboard(grid):
    """python-chess style bitboard from rank-8-first occupancy grid."""
    import chess
    bb = 0
    for r in range(8):          # r=0 → rank 8
        for c in range(8):
            if grid[r][c]:
                sq = chess.square(c, 7 - r)
                bb |= chess.BB_SQUARES[sq]
    return bb


def board_occupancy(board):
    return int(board.occupied)


START_OCCUPANCY = None  # filled lazily


def starting_occupancy():
    global START_OCCUPANCY
    if START_OCCUPANCY is None:
        import chess
        START_OCCUPANCY = board_occupancy(chess.Board())
    return START_OCCUPANCY


def capture_occupancy(calib):
    """Screenshot board → occupancy grid + bitboard + image."""
    img = grab_region(calib["region"])
    grid = occupancy_grid(img, flipped=bool(calib.get("flipped", False)))
    return occupancy_bitboard(grid), grid, img


def capture_fen(calib, templates=None, movethresh=0.60):
    """Screenshot the calibrated region, recognize pieces, return FEN string + debug image scores."""
    templates = templates or load_templates()
    img = grab_region(calib["region"])
    cells, ch, cw = cell_images(img, calib["region"][2])
    rows = [[None] * 8 for _ in range(8)]
    min_tmpl = min(min(t.shape[0] for t in templates.values() if t is not None), ch, cw)
    for r in range(8):
        for c in range(8):
            # trim inner margin to reduce bleeding from neighbors
            m = int(ch * 0.14)
            sub = cells[r][c][m:ch - m, m:cw - m]
            # Prefer edge occupancy gate, then classify
            if _cell_edge_density(sub) < 0.04:
                rows[r][c] = "."
                continue
            scale = max(1, (44 + min_tmpl - 1) // max(sub.shape[0], 1))
            if scale > 1:
                sub = cv2.resize(sub, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            rows[r][c] = classify_cell(sub, templates)

    if calib.get("flipped"):
        ranks_grid = [row[::-1] for row in rows[::-1]]
    else:
        ranks_grid = rows

    fen_rows = []
    for r in range(8):
        row = ""
        empties = 0
        for c in range(8):
            v = ranks_grid[r][c]
            if v == ".":
                empties += 1
            else:
                if empties:
                    row += str(empties)
                    empties = 0
                row += v if v != "?" else "."
        if empties:
            row += str(empties)
        fen_rows.append(row)
    placement = "/".join(fen_rows)
    return placement, img, rows


def full_fen(placement, turn="w", castle="KQkq"):
    return f"{placement} {turn} {castle} - 0 1"


def find_board_region(img=None):
    """Auto-locate a chess.com green/cream board on screen. Returns [x,y,w,h] or None."""
    if img is None:
        import mss
        with mss.MSS() as sct:
            shot = np.array(sct.grab(sct.monitors[1]))
        img = cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)

    # Prefer colors from saved empty templates when available
    try:
        tl = cv2.imread(os.path.join(TEMPLATE_DIR, "empty_light.png"))
        td = cv2.imread(os.path.join(TEMPLATE_DIR, "empty_dark.png"))
        light = tl.mean(axis=(0, 1)).astype(np.float32)
        dark = td.mean(axis=(0, 1)).astype(np.float32)
    except Exception:
        light = np.array([211, 236, 235], dtype=np.float32)
        dark = np.array([90, 148, 122], dtype=np.float32)

    f = img.astype(np.float32)
    mask = ((np.linalg.norm(f - light, axis=2) < 42) |
            (np.linalg.norm(f - dark, axis=2) < 48)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if min(w, h) < 280:
            continue
        aspect = w / max(h, 1)
        if 0.88 <= aspect <= 1.12:
            cands.append((cv2.contourArea(c), x, y, min(w, h)))
    if not cands:
        return None
    cands.sort(reverse=True)
    _, x, y, side = cands[0]
    # Tighten using dark-square mask inside the candidate
    crop = img[y:y + side, x:x + side]
    dm = (np.linalg.norm(crop.astype(np.float32) - dark, axis=2) < 48).astype(np.uint8) * 255
    dm = cv2.morphologyEx(dm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # row/col projections to trim chrome
    row_s = dm.mean(axis=1)
    col_s = dm.mean(axis=0)
    thr = max(float(row_s.max()) * 0.25, 5.0)

    def span(arr):
        idx = np.where(arr >= thr)[0]
        if len(idx) == 0:
            return 0, len(arr)
        return int(idx[0]), int(idx[-1]) + 1

    r0, r1 = span(row_s)
    c0, c1 = span(col_s)
    side2 = min(r1 - r0, c1 - c0)
    if side2 < 280:
        return [int(x), int(y), int(side), int(side)]
    return [int(x + c0), int(y + r0), int(side2), int(side2)]


def focus_chess_com():
    """Bring a chess.com Chrome tab to the front (best-effort)."""
    import subprocess
    script = '''
    tell application "Google Chrome"
      activate
      repeat with w in windows
        set i to 0
        repeat with t in tabs of w
          set i to i + 1
          if URL of t contains "chess.com" then
            set active tab index of w to i
            set index of w to 1
            return true
          end if
        end repeat
      end repeat
      return false
    end tell
    '''
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
        return "true" in (r.stdout or "").lower()
    except Exception:
        return False


class PositionTracker:
    """Track the live game by occupancy diffs → legal moves (robust on chess.com)."""

    def __init__(self):
        import chess
        self.board = None
        self._last_occ = None
        self._chess = chess

    def reset_start(self):
        self.board = self._chess.Board()
        self._last_occ = board_occupancy(self.board)
        return self.board

    def update(self, occ_bb):
        """Update from a new occupancy bitboard. Returns (board_or_None, status)."""
        chess = self._chess
        if occ_bb == starting_occupancy():
            self.reset_start()
            return self.board, "starting position"

        if self.board is None:
            return None, "waiting for starting position (new game)…"

        if occ_bb == self._last_occ:
            return self.board, "unchanged"

        # Find a legal move (or two half-moves if we lagged) matching new occupancy
        matches = []
        for mv in self.board.legal_moves:
            b2 = self.board.copy(stack=False)
            b2.push(mv)
            if board_occupancy(b2) == occ_bb:
                matches.append((mv, b2))
        if len(matches) == 1:
            mv, b2 = matches[0]
            self.board = b2
            self._last_occ = occ_bb
            return self.board, f"played {mv.uci()}"
        if len(matches) > 1:
            # Ambiguous (rare) — pick first; UI can still help via FEN
            mv, b2 = matches[0]
            self.board = b2
            self._last_occ = occ_bb
            return self.board, f"played {mv.uci()} (ambiguous)"

        # Maybe two moves happened between polls — try depth-2
        for mv1 in self.board.legal_moves:
            b1 = self.board.copy(stack=False)
            b1.push(mv1)
            for mv2 in b1.legal_moves:
                b2 = b1.copy(stack=False)
                b2.push(mv2)
                if board_occupancy(b2) == occ_bb:
                    self.board = b2
                    self._last_occ = occ_bb
                    return self.board, f"played {mv1.uci()} then {mv2.uci()}"

        return self.board, "occupancy mismatch — click New Game or paste FEN"


# ---------- template extraction ----------
def extract_templates(out_dir=TEMPLATE_DIR, region=None, flipped=False):
    """
    Called while a fresh chess.com game (starting position) is on screen.
    calibration['region'] must be the BOARD area. Saves one PNG per piece +
    empty-light/dark squares.
    """
    os.makedirs(out_dir, exist_ok=True)
    img = grab_region(region)
    cells, ch, cw = cell_images(img, region[2])
    saved = []
    m = int(ch * 0.10)
    for r in range(8):          # r=0 is TOP of image
        for c in range(8):
            if flipped:
                piece = START_POS[7 - r][7 - c]
            else:
                piece = START_POS[r][c]
            cell = cells[r][c][m:ch - m, m:cw - m]
            is_light = ((r + c) % 2 == 0) ^ bool(flipped)
            suffix = "light" if is_light else "dark"
            if piece == ".":
                name = _save_template_name
                fname = f"empty_{suffix}"
                fp = os.path.join(out_dir, f"{fname}.png")
                if fname not in saved:
                    cv2.imwrite(fp, cell)
                    saved.append(fname)
            else:
                fname = _save_template_name(piece, suffix)
                cv2.imwrite(os.path.join(out_dir, f"{fname}.png"), cell)
                if fname not in saved:
                    saved.append(fname)
    return saved
