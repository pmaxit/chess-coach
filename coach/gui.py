"""Coach GUI: chess.com-style board + arrows, eval, move cards, explanations."""
import queue
import tkinter as tk

import chess

from coach.board_view import ARROW_COLORS, ArrowOverlay, BoardCanvas


def chess_start_fen():
    return chess.STARTING_FEN

BAR_W = 18


class CoachPanel(tk.Tk):
    def __init__(self, cmd_q, evt_q, board_region=None, flipped=False):
        super().__init__()
        self.title("Chess Coach")
        self.attributes("-topmost", True)
        self.configure(bg="#161a22")
        self.cmd_q = cmd_q
        self.evt_q = evt_q
        self.minsize(780, 560)
        self._last_fen = ""
        self._flipped = bool(flipped)
        self._board_region = list(board_region) if board_region else None
        self._hidden_for_capture = False
        # Sit BESIDE the chess.com board so we never screenshot ourselves
        self._place_beside_board(board_region)

        self.eval_var = tk.StringVar(value="waiting…")
        self.status_var = tk.StringVar(value="starting…")
        self.fen_var = tk.StringVar()
        self.overlay_var = tk.BooleanVar(value=False)

        # ---- header ----
        top = tk.Frame(self, bg="#161a22")
        top.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(top, textvariable=self.eval_var, font=("SF Mono", 20, "bold"),
                 fg="#7dd3fc", bg="#161a22").pack(side="left")
        tk.Label(top, textvariable=self.status_var, font=("SF Mono", 10),
                 fg="#94a3b8", bg="#161a22").pack(side="right")

        body = tk.Frame(self, bg="#161a22")
        body.pack(fill="both", expand=True, padx=10, pady=4)

        # ---- left: visual board ----
        left = tk.Frame(body, bg="#161a22")
        left.pack(side="left", fill="y", padx=(0, 12))
        tk.Label(left, text="Suggestions (arrows)", fg="#cbd5e1", bg="#161a22",
                 font=("Helvetica", 11, "bold")).pack(anchor="w", pady=(0, 4))

        legend = tk.Frame(left, bg="#161a22")
        legend.pack(anchor="w", pady=(0, 6))
        for rank, label in ((1, "best"), (2, "2nd"), (3, "3rd")):
            tk.Label(legend, text="●", fg=ARROW_COLORS[rank], bg="#161a22",
                     font=("Helvetica", 14)).pack(side="left")
            tk.Label(legend, text=f" {label}  ", fg="#94a3b8", bg="#161a22",
                     font=("Helvetica", 10)).pack(side="left")

        self.board = BoardCanvas(left, square=54)
        self.board.pack()
        self.board.set_position(chess_start_fen(), flipped=self._flipped)

        # ---- right: text cards ----
        right = tk.Frame(body, bg="#161a22")
        right.pack(side="left", fill="both", expand=True)

        self.cards_frame = tk.Frame(right, bg="#161a22")
        self.cards_frame.pack(fill="both", expand=True)

        self.fb = tk.Text(right, height=6, bg="#0f1319", fg="#e2e8f0",
                          font=("Helvetica", 12), wrap="word", relief="flat")
        self.fb.pack(fill="x", pady=(8, 0))

        # ---- footer controls ----
        frow = tk.Frame(self, bg="#161a22")
        frow.pack(fill="x", padx=10, pady=(6, 4))
        tk.Label(frow, text="FEN:", fg="#94a3b8", bg="#161a22",
                 font=("SF Mono", 10)).pack(side="left")
        ent = tk.Entry(frow, textvariable=self.fen_var, bg="#0f1319", fg="#e2e8f0",
                       insertbackground="#e2e8f0", relief="flat")
        ent.pack(side="left", fill="x", expand=True, padx=6)
        ent.bind("<Return>", self._fen_submit)

        brow = tk.Frame(self, bg="#161a22")
        brow.pack(fill="x", padx=10, pady=(0, 10))
        self.depth_btn = tk.Button(
            brow, text="⚙ Depth: normal", command=self._cycle_depth,
            bg="#1f2937", fg="#e2e8f0", relief="flat",
            activebackground="#334155", activeforeground="#fff",
        )
        self.depth_btn.pack(side="left")
        tk.Button(brow, text="Find board", command=self._find_board,
                  bg="#0f766e", fg="#e2e8f0", relief="flat").pack(side="left", padx=6)
        tk.Button(brow, text="New game sync", command=self._reset_game,
                  bg="#1f2937", fg="#e2e8f0", relief="flat").pack(side="left", padx=6)
        tk.Button(brow, text="Copy FEN", command=self._copy_fen,
                  bg="#1f2937", fg="#e2e8f0", relief="flat").pack(side="left", padx=6)
        tk.Button(brow, text="Flip", command=self._flip_board,
                  bg="#1f2937", fg="#e2e8f0", relief="flat").pack(side="left", padx=6)

        self.overlay_chk = tk.Checkbutton(
            brow, text="Overlay arrows on chess.com",
            variable=self.overlay_var, command=self._toggle_overlay,
            bg="#161a22", fg="#e2e8f0", selectcolor="#1f2937",
            activebackground="#161a22", activeforeground="#fff",
            highlightthickness=0,
        )
        self.overlay_chk.pack(side="left", padx=10)

        self.overlay = ArrowOverlay(self)
        if board_region:
            self.overlay.configure_region(board_region, flipped=self._flipped)

        self.after(150, self._poll_events)

    def _place_beside_board(self, region):
        """Park the coach panel to the right (or left) of the calibrated board."""
        w, h = 900, 640
        if not region:
            self.geometry(f"{w}x{h}+40+60")
            return
        bx, by, bw, bh = region
        sw = self.winfo_screenwidth()
        # Prefer right of board; fall back to left if it would clip
        x_right = bx + bw + 24
        if x_right + 480 <= sw:
            x = x_right
        else:
            x = max(8, bx - w - 24)
        y = max(40, by)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _hide_for_capture(self):
        """Make ourselves invisible so the board screenshot is clean."""
        if self._hidden_for_capture:
            return
        self._hidden_for_capture = True
        try:
            self.overlay.withdraw()
        except Exception:
            pass
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            self.withdraw()

    def _show_after_capture(self):
        if not self._hidden_for_capture:
            return
        self._hidden_for_capture = False
        try:
            self.deiconify()
            self.attributes("-alpha", 1.0)
        except tk.TclError:
            pass
        if self.overlay_var.get():
            self.overlay.set_enabled(True)
            self.overlay.show_arrows(getattr(self, "_last_arrows", []), flipped=self._flipped)

    # ---- events from worker ----
    def _poll_events(self):
        try:
            while True:
                kind, payload = self.evt_q.get_nowait()
                if kind == "analysis":
                    self.render(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "depth":
                    self.depth_btn.config(text=f"⚙ Depth: {payload}")
                elif kind == "pre_capture":
                    self._hide_for_capture()
                elif kind == "post_capture":
                    self._show_after_capture()
                elif kind == "calibration":
                    region = payload.get("region")
                    flipped = bool(payload.get("flipped", False))
                    self._flipped = flipped
                    if region:
                        self._board_region = list(region)
                        self.overlay.configure_region(region, flipped=flipped)
                        self._place_beside_board(region)
                    self.board.set_position(self._last_fen or chess_start_fen(), flipped=flipped,
                                            arrows=getattr(self, "_last_arrows", []))
        except queue.Empty:
            pass
        self.after(80, self._poll_events)

    def render(self, t):
        turn_icon = "⚪ White" if t["turn"] == "white" else "⚫ Black"
        self.eval_var.set(f"{t['eval_bar']}   ({turn_icon} to move)")

        fen = t.get("fen") or self._last_fen
        arrows = t.get("arrows") or []
        flipped = t.get("flipped", self._flipped)
        self._flipped = bool(flipped)
        self._last_fen = fen
        self._last_arrows = arrows
        self.remember_fen(fen)

        self.board.set_position(fen, flipped=self._flipped, arrows=arrows)
        self.overlay.show_arrows(arrows, flipped=self._flipped)

        for w in self.cards_frame.winfo_children():
            w.destroy()
        for c in t["cards"]:
            color = ARROW_COLORS.get(c["rank"], "#94a3b8")
            frame = tk.Frame(self.cards_frame, bg="#1c2331")
            frame.pack(fill="x", pady=4, ipady=4)
            hdr = tk.Frame(frame, bg="#1c2331")
            hdr.pack(fill="x", padx=8, pady=(6, 0))
            star = "★" if c["rank"] == 1 else " "
            tk.Label(hdr, text=f"{star}{c['rank']}", fg=color,
                     bg="#1c2331", font=("SF Mono", 12, "bold")).pack(side="left")
            tk.Label(hdr, text=f"  {c['san']}   {c['move_txt']}",
                     fg="#f1f5f9", bg="#1c2331", font=("Menlo", 14, "bold")).pack(side="left", padx=4)
            tk.Label(hdr, text="➔", fg=color, bg="#1c2331",
                     font=("Helvetica", 16, "bold")).pack(side="left")
            tk.Label(hdr, text=c["label"], fg="#34d399" if c["rank"] == 1 else "#cbd5e1",
                     bg="#1c2331", font=("Helvetica", 11)).pack(side="right")
            if c["rel_eval"]:
                tk.Label(frame, text=c["rel_eval"], fg="#94a3b8", bg="#1c2331",
                         font=("SF Mono", 10)).pack(anchor="w", padx=10)
            tk.Label(frame, text="WHY: " + c["why"], fg="#cbd5e1", bg="#1c2331",
                     font=("Helvetica", 11), wraplength=420, justify="left"
                     ).pack(anchor="w", padx=10, pady=(2, 2))
            tk.Label(frame, text="plan: " + c["pv"], fg="#64748b", bg="#1c2331",
                     font=("SF Mono", 9), wraplength=420, justify="left"
                     ).pack(anchor="w", padx=10, pady=(0, 8))

        self.fb.delete("1.0", "end")
        if t.get("last_feedback"):
            self.fb.insert("end", t["last_feedback"] + "\n")
        for wmsg in t.get("warnings", []):
            self.fb.insert("end", "⚠️ " + wmsg + "\n")
        self.fb.insert("end", t.get("tip", ""))

    # ---- commands ----
    def _cycle_depth(self):
        self.cmd_q.put(("depth", None))

    def _find_board(self):
        self.status_var.set("finding board…")
        self.cmd_q.put(("find_board", None))

    def _reset_game(self):
        self.status_var.set("syncing start position…")
        self.cmd_q.put(("reset_game", None))

    def _copy_fen(self):
        self.clipboard_clear()
        self.clipboard_append(getattr(self, "_last_fen", ""))
        self.status_var.set("copied FEN ✓")

    def _fen_submit(self, _evt=None):
        self.cmd_q.put(("manual_fen", self.fen_var.get()))

    def _flip_board(self):
        self._flipped = not self._flipped
        self.board.set_position(self._last_fen or chess_start_fen(), flipped=self._flipped,
                                arrows=getattr(self, "_last_arrows", []))
        if self.overlay._region:
            self.overlay.configure_region(self.overlay._region, flipped=self._flipped)
        self.overlay.show_arrows(getattr(self, "_last_arrows", []), flipped=self._flipped)

    def _toggle_overlay(self):
        self.overlay.set_enabled(self.overlay_var.get())
        self.overlay.show_arrows(getattr(self, "_last_arrows", []), flipped=self._flipped)

    def remember_fen(self, fen):
        self._last_fen = fen
