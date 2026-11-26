"""Chess.com-style board canvas with multi-PV suggestion arrows."""
import math
import tkinter as tk

import chess

# chess.com-ish palette
LIGHT = "#ebecd0"
DARK = "#779556"
LIGHT_HL = "#f6f669"
DARK_HL = "#baca2b"
BORDER = "#312e2b"
COORD = "#f0f0f0"

# Suggestion arrows (best → alternatives), chess.com analysis vibes
ARROW_COLORS = {
    1: "#96bc4b",  # best — green
    2: "#5c8ae6",  # 2nd — blue
    3: "#f0c24b",  # 3rd — gold
}

PIECE_GLYPH = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}


def _sq_xy(sq_name, size, flipped):
    """Center of square in canvas coords (files a–h left→right when not flipped)."""
    file_i = ord(sq_name[0]) - ord("a")
    rank_i = int(sq_name[1]) - 1
    if flipped:
        col, row = 7 - file_i, rank_i
    else:
        col, row = file_i, 7 - rank_i
    return col * size + size / 2, row * size + size / 2


class BoardCanvas(tk.Canvas):
    def __init__(self, master, square=52, **kw):
        self.sq = square
        side = square * 8
        kw.setdefault("width", side)
        kw.setdefault("height", side)
        kw.setdefault("bg", BORDER)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        super().__init__(master, **kw)
        self.fen = chess.STARTING_FEN
        self.flipped = False
        self.arrows = []  # [{from, to, rank}]
        self._highlights = set()

    def set_position(self, fen, flipped=False, arrows=None):
        self.fen = fen or chess.STARTING_FEN
        self.flipped = bool(flipped)
        self.arrows = list(arrows or [])
        self._highlights = set()
        for a in self.arrows:
            self._highlights.add(a["from"])
            self._highlights.add(a["to"])
        self.redraw()

    def redraw(self):
        self.delete("all")
        s = self.sq
        try:
            board = chess.Board(self.fen)
        except ValueError:
            board = chess.Board()

        # squares
        for row in range(8):
            for col in range(8):
                file_i = 7 - col if self.flipped else col
                rank_i = row if self.flipped else 7 - row
                sq = chess.square(file_i, rank_i)
                name = chess.square_name(sq)
                is_light = (file_i + rank_i) % 2 == 1
                if name in self._highlights:
                    color = LIGHT_HL if is_light else DARK_HL
                else:
                    color = LIGHT if is_light else DARK
                x0, y0 = col * s, row * s
                self.create_rectangle(x0, y0, x0 + s, y0 + s, fill=color, outline="")

                # coords on rim squares
                if col == 0:
                    self.create_text(
                        x0 + 3, y0 + 3, anchor="nw",
                        text=str(rank_i + 1),
                        fill=DARK if is_light else LIGHT,
                        font=("Helvetica", max(8, s // 6)),
                    )
                if row == 7:
                    self.create_text(
                        x0 + s - 3, y0 + s - 3, anchor="se",
                        text=chr(ord("a") + file_i),
                        fill=DARK if is_light else LIGHT,
                        font=("Helvetica", max(8, s // 6)),
                    )

        # pieces
        font = ("Arial Unicode MS", int(s * 0.72))
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece:
                continue
            name = chess.square_name(sq)
            cx, cy = _sq_xy(name, s, self.flipped)
            glyph = PIECE_GLYPH[piece.symbol()]
            # soft disc so black pieces stay visible on dark squares
            pad = s * 0.38
            self.create_oval(cx - pad, cy - pad, cx + pad, cy + pad,
                             fill="#cdd2b8" if piece.color == chess.BLACK else "#f4f5e8",
                             outline="")
            self.create_text(cx + 1, cy + 1, text=glyph, font=font, fill="#000000")
            self.create_text(
                cx, cy, text=glyph, font=font,
                fill="#f8f8f8" if piece.color == chess.WHITE else "#111111",
            )

        # arrows on top (best last so it sits above)
        for a in sorted(self.arrows, key=lambda x: -x.get("rank", 9)):
            self._draw_arrow(a["from"], a["to"], ARROW_COLORS.get(a.get("rank", 1), "#96bc4b"),
                             width=max(6, s // 7) if a.get("rank") == 1 else max(4, s // 9))

    def _draw_arrow(self, frm, to, color, width=8):
        s = self.sq
        x1, y1 = _sq_xy(frm, s, self.flipped)
        x2, y2 = _sq_xy(to, s, self.flipped)
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1.0
        ux, uy = dx / dist, dy / dist

        # shorten so tip sits inside destination square, not under the piece center
        shorten = s * 0.28
        x2s = x2 - ux * shorten
        y2s = y2 - uy * shorten
        x1s = x1 + ux * (s * 0.18)
        y1s = y1 + uy * (s * 0.18)

        # shaft
        self.create_line(
            x1s, y1s, x2s, y2s,
            fill=color, width=width,
            capstyle=tk.ROUND, stipple="gray75",
        )
        # solid tip for clarity
        head = max(14, s * 0.38)
        ang = math.atan2(dy, dx)
        left = (x2s - head * math.cos(ang - 0.45), y2s - head * math.sin(ang - 0.45))
        right = (x2s - head * math.cos(ang + 0.45), y2s - head * math.sin(ang + 0.45))
        self.create_polygon(
            x2s, y2s, left[0], left[1], right[0], right[1],
            fill=color, outline=color,
        )


class ArrowOverlay(tk.Toplevel):
    """Semi-transparent always-on-top arrows over the calibrated screen board."""

    def __init__(self, master):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", 0.55)
        except tk.TclError:
            pass
        self.configure(bg="#010101")
        self.canvas = tk.Canvas(self, bg="#010101", highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._region = None
        self._flipped = False
        self.enabled = False

    def configure_region(self, region, flipped=False):
        """region = [left, top, w, h] in screen coords."""
        self._region = list(region)
        self._flipped = bool(flipped)

    def set_enabled(self, on):
        self.enabled = bool(on)
        if not on or not self._region:
            self.withdraw()
        else:
            self._place()

    def _place(self):
        if not self._region:
            return
        x, y, w, h = self._region
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.deiconify()
        self.lift()

    def show_arrows(self, arrows, flipped=None):
        if flipped is not None:
            self._flipped = bool(flipped)
        self.canvas.delete("all")
        if not self.enabled or not self._region:
            self.withdraw()
            return
        self._place()
        _, _, w, h = self._region
        self.canvas.config(width=w, height=h)
        # fill with near-black (will look dark translucent via window alpha)
        self.canvas.create_rectangle(0, 0, w, h, fill="#010101", outline="")
        sq_w, sq_h = w / 8, h / 8
        flipped = self._flipped

        def center(sq_name):
            file_i = ord(sq_name[0]) - ord("a")
            rank_i = int(sq_name[1]) - 1
            if flipped:
                col, row = 7 - file_i, rank_i
            else:
                col, row = file_i, 7 - rank_i
            return col * sq_w + sq_w / 2, row * sq_h + sq_h / 2

        for a in sorted(arrows or [], key=lambda x: -x.get("rank", 9)):
            color = ARROW_COLORS.get(a.get("rank", 1), "#96bc4b")
            x1, y1 = center(a["from"])
            x2, y2 = center(a["to"])
            dx, dy = x2 - x1, y2 - y1
            dist = math.hypot(dx, dy) or 1
            ux, uy = dx / dist, dy / dist
            shorten = min(sq_w, sq_h) * 0.28
            x2s, y2s = x2 - ux * shorten, y2 - uy * shorten
            x1s, y1s = x1 + ux * (min(sq_w, sq_h) * 0.15), y1 + uy * (min(sq_w, sq_h) * 0.15)
            width = max(8, min(sq_w, sq_h) * (0.18 if a.get("rank") == 1 else 0.12))
            self.canvas.create_line(x1s, y1s, x2s, y2s, fill=color, width=width, capstyle=tk.ROUND)
            head = max(16, min(sq_w, sq_h) * 0.35)
            ang = math.atan2(dy, dx)
            left = (x2s - head * math.cos(ang - 0.45), y2s - head * math.sin(ang - 0.45))
            right = (x2s - head * math.cos(ang + 0.45), y2s - head * math.sin(ang + 0.45))
            self.canvas.create_polygon(x2s, y2s, left[0], left[1], right[0], right[1],
                                       fill=color, outline=color)
