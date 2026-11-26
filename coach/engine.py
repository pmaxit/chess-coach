"""Stockfish analysis wrapper."""
import chess
import chess.engine


class EngineAnalyzer:
    def __init__(self, path="/opt/homebrew/bin/stockfish"):
        self.path = path
        self._eng = None

    @property
    def eng(self):
        if self._eng is None:
            self._eng = chess.engine.SimpleEngine.popen_uci(self.path)
        return self._eng

    def close(self):
        if self._eng:
            try:
                self._eng.quit()
            except Exception:
                pass
            self._eng = None

    def analyze(self, fen, movetime=1.2, multipv=3):
        """Returns dict: score_cp (white POV), best (san), lines [(san, cp, pv_str)], mate info."""
        board = chess.Board(fen)
        info = self.eng.analyse(
            board,
            chess.engine.Limit(time=movetime),
            multipv=multipv,
            info=chess.engine.INFO_ALL,
        )
        infos = info if isinstance(info, list) else [info]
        lines = []
        for inf in infos:
            pv = inf.get("pv") or []
            if not pv:
                continue
            mv = pv[0]
            san = board.san(mv)
            pv_san = []
            b2 = board.copy()
            for m in pv[:10]:
                pv_san.append(b2.san(m))
                b2.push(m)
            rel = inf["score"].relative
            cp = rel.score(mate_score=10000)  # mover POV
            lines.append({
                "san": san,
                "cp": cp,
                "mate": rel.mate(),
                "pv": " ".join(pv_san),
                "uci": mv.uci(),
                "from_sq": chess.square_name(mv.from_square),
                "to_sq": chess.square_name(mv.to_square),
            })
        lines.sort(key=lambda l: -l["cp"])
        best_cp_white = -infos[0]["score"].relative.score(mate_score=10000) \
            if board.turn == chess.BLACK else infos[0]["score"].relative.score(mate_score=10000)
        return {
            "fen": fen,
            "turn": "white" if board.turn == chess.WHITE else "black",
            "best": lines[0]["san"] if lines else None,
            "score_best_white": best_cp_white,
            "lines": lines,
            "board": board,
        }
