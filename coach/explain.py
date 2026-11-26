"""Plain-English teaching explanations for engine analysis."""
import chess

SYMBOL = {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
          "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"}

LABELS = [(400, "🔥 Blunder"), (250, "❌ Mistake"), (120, "⚠️ Inaccuracy"),
          (40, "👍 Good"), (-15, "✅ Excellent"), (-999999, "⭐ Best move")]

DIRS_TEXT = {}


def sq_dist(a, b):
    fa, ra = ord(a[0]), int(a[1])
    fb, rb = ord(b[0]), int(b[1])
    return max(abs(fa - fb), abs(ra - rb))


def direction_text(from_sq, to_sq):
    df = ord(to_sq[0]) - ord(from_sq[0])
    dr = int(to_sq[1]) - int(from_sq[1])
    parts = []
    if df > 0:
        parts.append("toward the kingside")
    elif df < 0:
        parts.append("toward the queenside")
    if dr > 0:
        parts.append("up the board")
    elif dr < 0:
        parts.append("back")
    if len(parts) == 2:
        return parts[0] + ", " + parts[1]
    return parts[0] if parts else "in place"


def label_for(loss_cp):
    """loss_cp >= 0 : how much worse than best (mover POV)."""
    if loss_cp <= 15:
        return "⭐ Best"
    for t, lbl in LABELS[:-1]:
        if loss_cp <= t:
            return lbl
    return "🔥 Blunder"


def fmt_eval(cp_white, turn):
    """cp from white POV. Show from mover's perspective."""
    v = cp_white if turn == "white" else -cp_white
    if abs(v) >= 9900:
        m = (10000 - abs(v)) // 100 + 1
        return ("M" + str(max(1, m))) if v > 0 else ("-M" + str(max(1, m)))
    return f"{v/100:+.2f}"


def arrow_glyph(from_sq, to_sq):
    """ASCII arrow approximating the move direction on a grid."""
    df = ord(to_sq[0]) - ord(from_sq[0])
    dr = int(to_sq[1]) - int(from_sq[1])
    horiz = "→" if df > 0 else ("←" if df < 0 else "")
    vert = "↑" if dr > 0 else ("↓" if dr < 0 else "")
    diag_chars = {(1, 1): "↗", (-1, 1): "↖", (1, -1): "↘", (-1, -1): "↙"}
    if horiz and vert and abs(df) == abs(dr):
        return diag_chars[(1 if df > 0 else -1, 1 if dr > 0 else -1)]
    return (horiz + vert) or "•"


def explain(line, board):
    """Human explanation for a candidate move."""
    san = line["san"]
    mv = board.parse_san(san)
    piece = board.piece_at(mv.from_square)
    pt = piece.symbol().upper() if piece else "?"
    pname = {"K": "King", "Q": "Queen", "R": "Rook", "B": "Bishop",
             "N": "Knight", "P": "Pawn"}[pt]
    frm, to = line["from_sq"], line["to_sq"]
    bits = []

    if board.is_castling(mv):
        ks = board.is_kingside_castling(mv)
        bits.append(f"Castles {'short (kingside)' if ks else 'long (queenside)'}: "
                    f"kings safety, connects rooks.")
    if san.endswith("#"):
        bits.append("CHECKMATE — game over!")
    elif board.gives_check(mv):
        bits.append("Gives check — forces the opponent to react.")

    # capture?
    if board.is_capture(mv):
        victim = board.piece_at(mv.to_square)
        vn = {"K": "king", "Q": "queen", "R": "rook", "B": "bishop",
              "N": "knight", "P": "pawn"}[victim.symbol().upper()]
        bits.append(f"Takes the {vn} on {to}.")

    if pt == "N":
        bits.append(f"Knight leap {arrow_glyph(frm,to)} {frm}→{to} — jumps over blockers, "
                    f"lands on a protected/outpost-ish square.")
    elif pt == "B":
        bits.append(f"Bishop develops {direction_text(frm,to)}, opens long diagonals.")
    elif pt == "R":
        if board.is_castling(mv):
            pass
        else:
            bits.append(f"Rook slides {direction_text(frm,to)} — opens files/ranks.")
    elif pt == "Q":
        bits.append(f"Queen enters the action {direction_text(frm,to)}.")
    elif pt == "P":
        if to in ("e4", "e5", "d4", "d5") and frm in ("e2", "e7", "d2", "d7"):
            bits.append("Central pawn — grabs space and opens diagonals for bishops.")
        else:
            bits.append(f"Pawn push {frm}→{to} — gains space, possibly restricting enemy pieces.")

    # promoting?
    if mv.promotion:
        bits.append("PAWN PROMOTION!")

    if not bits:
        bits.append(f"Improves coordination {arrow_glyph(frm, to)} {frm}→{to}.")
    return " ".join(bits)


def threat_warnings(board):
    """Simple heuristics: hanging pieces & checks against mover."""
    out = []
    mover = board.turn
    for sq in chess.SquareSet(board.occupied_co[mover]):
        attackers = board.attackers(not mover, sq)
        defenders = board.attackers(mover, sq)
        if attackers and not defenders:
            p = board.piece_at(sq)
            val = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 99}[p.symbol().upper()]
            if val >= 3:
                out.append(f"Your {SYMBOL[p.symbol()]}"
                           f"{chess.square_name(sq)} is HANGING (attacked, undefended).")
    return out


def teach(result, prev_result=None):
    """Main entry: build full teaching payload from engine result."""
    board = result["board"]
    ev_best = fmt_eval(result["score_best_white"], result["turn"])
    cards = []
    for i, ln in enumerate(result["lines"][:3]):
        loss = max(0, result["lines"][0]["cp"] - ln["cp"])
        cards.append({
            "rank": i + 1,
            "san": ln["san"],
            "glyph": arrow_glyph(ln["from_sq"], ln["to_sq"]),
            "move_txt": f"{ln['from_sq']}→{ln['to_sq']}",
            "eval_me": fmt_eval(-result['lines'][0]['cp'] + ln['cp'] + result['lines'][0]['cp'],
                                result['turn']) if False else fmt_eval(
                                    result["score_best_white"] - (result["lines"][0]["cp"] - ln["cp"])
                                    * (1 if result["turn"] == "white" else -1),
                                "white"),
            "rel_eval": ("" if i == 0 else f"−{loss/100:.2f} vs best"),
            "label": label_for(loss),
            "why": explain(ln, board),
            "pv": ln["pv"],
        })

    changed = ""
    if prev_result:
        pb = prev_result["board"]
        try:
            mv = pb.peek() if pb.move_stack else None
        except Exception:
            mv = None
        if prev_result.get("played_move_quality") is not None:
            q = prev_result["played_move_quality"]
            if q == 0:
                changed = "🎯 Last move matched best — nice!"
            elif q <= 15:
                changed = "👌 Last move nearly best."
            elif q <= 120:
                changed = f"🤏 Last move slightly imprecise (−{q/100:.2f})."
            else:
                changed = f"😬 Last move lost ~{q/100:.2f}. Watch out!"

    warns = threat_warnings(board)
    tip = "Tip: green / blue / gold arrows = best / 2nd / 3rd suggestion (chess.com style)."
    arrows = [
        {"from": ln["from_sq"], "to": ln["to_sq"], "rank": i + 1, "san": ln["san"]}
        for i, ln in enumerate(result["lines"][:3])
    ]
    return {
        "eval_bar": ev_best,
        "turn": result["turn"],
        "cards": cards,
        "arrows": arrows,
        "fen": board.fen(),
        "warnings": warns,
        "last_feedback": changed,
        "tip": tip,
    }
