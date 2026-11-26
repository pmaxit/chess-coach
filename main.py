#!/usr/bin/env python3
"""Chess Coach — main app.

Worker thread: poll chess.com board occupancy → track moves → Stockfish tips.
UI thread: coach panel with chess.com-style arrows.
"""
import json
import os
import queue
import threading
import time
import traceback

import chess

from coach import board_capture as bc
from coach import explain as ex
from coach.engine import EngineAnalyzer
from coach.gui import CoachPanel

ASSETS_FEN_FILE = "assets/last_fen.txt"
CALIB_PATH = os.path.join(os.path.dirname(__file__), "assets", "calibration.json")


class Worker(threading.Thread):
    def __init__(self, cmd_q, evt_q):
        super().__init__(daemon=True)
        self.cmd_q = cmd_q
        self.evt_q = evt_q
        self.calib = None
        self.templates = None
        self.engine = None
        self.depth_time = 1.2
        self.prev_analysis = None
        self.tracker = bc.PositionTracker()
        self._last_analyzed_fen = None

    def emit(self, kind, payload=None):
        self.evt_q.put((kind, payload))

    def run(self):
        self.engine = EngineAnalyzer()
        self.emit("status", "loading…")
        try:
            self.calib = bc.load_calibration()
            try:
                self.templates = bc.load_templates()
            except FileNotFoundError:
                self.templates = {}
            self.emit("calibration", {
                "region": self.calib["region"],
                "flipped": bool(self.calib.get("flipped", False)),
            })
        except FileNotFoundError as e:
            self.emit("status", f"setup needed: {e} — click Find board")
            while True:
                try:
                    self._handle_cmds()
                    time.sleep(0.25)
                except Exception:
                    traceback.print_exc()
                    time.sleep(2)
            return

        self.emit("status", "watching chess.com… keep the board visible")
        while True:
            try:
                self._handle_cmds()
                self._tick()
                time.sleep(0.7)
            except Exception:
                traceback.print_exc()
                self.emit("status", "worker error (see console)")
                time.sleep(2)

    def _handle_cmds(self):
        try:
            while True:
                kind, payload = self.cmd_q.get_nowait()
                if kind == "depth":
                    times = {"fast": 0.6, "normal": 1.2, "deep": 4.0}
                    keys = list(times.keys())
                    cur = next((k for k in keys if times[k] == self.depth_time), "normal")
                    nxt = keys[(keys.index(cur) + 1) % len(keys)]
                    self.depth_time = times[nxt]
                    self.emit("depth", nxt)
                elif kind == "manual_fen":
                    try:
                        b = chess.Board(payload.strip())
                    except ValueError:
                        self.emit("status", "invalid FEN")
                        continue
                    self.tracker.board = b
                    self.tracker._last_occ = bc.board_occupancy(b)
                    self._analyze_board(b, note="manual FEN")
                elif kind == "find_board":
                    self._find_board()
                elif kind == "reset_game":
                    self.tracker.reset_start()
                    self._analyze_board(self.tracker.board, note="reset to start")
        except queue.Empty:
            pass

    def _find_board(self):
        self.emit("status", "finding chess.com board…")
        bc.focus_chess_com()
        time.sleep(0.8)
        self.emit("pre_capture", None)
        time.sleep(0.15)
        try:
            region = bc.find_board_region()
        finally:
            self.emit("post_capture", None)
        if not region:
            self.emit("status", "board not found — open chess.com and try again")
            return
        flipped = bool((self.calib or {}).get("flipped", False))
        self.calib = {"region": region, "flipped": flipped}
        os.makedirs(os.path.dirname(CALIB_PATH), exist_ok=True)
        with open(CALIB_PATH, "w") as f:
            json.dump(self.calib, f, indent=2)
        try:
            import cv2
            cv2.imwrite("assets/calibration_preview.png", bc.grab_region(region))
        except Exception:
            pass
        self.emit("calibration", self.calib)
        self.emit("status", f"board locked {region} — start or resume a game")
        self.tracker = bc.PositionTracker()

    def _tick(self):
        if not self.calib:
            return
        self.emit("pre_capture", None)
        time.sleep(0.1)
        try:
            occ, grid, img = bc.capture_occupancy(self.calib)
        finally:
            self.emit("post_capture", None)

        board, status = self.tracker.update(occ)
        if board is None:
            # Mid-game bootstrap: try one-shot piece recognition if templates exist
            if self.templates:
                try:
                    placement, _, _ = bc.capture_fen(self.calib, self.templates)
                    if placement.count("K") == 1 and placement.count("k") == 1:
                        # Prefer black to move if white already left base (rough)
                        fen = bc.full_fen(placement, turn="w")
                        b = chess.Board(fen)
                        # Fix castling guess lightly
                        if bc.board_occupancy(b) == occ:
                            self.tracker.board = b
                            self.tracker._last_occ = occ
                            self._analyze_board(b, note="bootstrapped from board")
                            return
                except Exception:
                    traceback.print_exc()
            self.emit("status", status + " — or paste FEN / click New game sync at start")
            return
        if status == "unchanged":
            self.emit("status", "watching…")
            return
        if "mismatch" in status:
            self.emit("status", status)
            return

        self.emit("status", status)
        self._analyze_board(board, note=status)

    def _analyze_board(self, board, note=""):
        fen = board.fen()
        if fen == self._last_analyzed_fen:
            return
        self._last_analyzed_fen = fen

        self.emit("status", f"analyzing… {note}")
        result = self.engine.analyze(fen, movetime=self.depth_time, multipv=3)

        played_q = None
        teach = ex.teach(result, prev_result={
            "board": board,
            "played_move_quality": played_q,
        })
        teach["fen"] = fen
        teach["flipped"] = bool((self.calib or {}).get("flipped", False))
        self.prev_analysis = result
        self.emit("analysis", teach)
        self.emit("status", f"updated {time.strftime('%H:%M:%S')} — {note}")
        try:
            with open(ASSETS_FEN_FILE, "w") as f:
                f.write(fen)
        except OSError:
            pass


def main():
    cmd_q, evt_q = queue.Queue(), queue.Queue()
    region, flipped = None, False
    try:
        calib = bc.load_calibration()
        region = calib.get("region")
        flipped = bool(calib.get("flipped", False))
    except FileNotFoundError:
        pass
    panel = CoachPanel(cmd_q, evt_q, board_region=region, flipped=flipped)
    w = Worker(cmd_q, evt_q)
    w.start()
    panel.mainloop()


if __name__ == "__main__":
    main()
