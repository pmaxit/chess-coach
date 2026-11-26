(() => {
  if (window.__chessCoachInjected) return;
  window.__chessCoachInjected = true;

  const PIECE_MAP = {
    wp: "P", wn: "N", wb: "B", wr: "R", wq: "Q", wk: "K",
    bp: "p", bn: "n", bb: "b", br: "r", bq: "q", bk: "k",
  };

  const ARROW_COLORS = {
    1: "#96bc4b",
    2: "#5c8ae6",
    3: "#f0c24b",
  };

  let lastFen = "";
  let overlayHost = null;
  let svg = null;
  let animTimer = null;
  let animStep = 0;
  let animArrows = [];
  let animFlipped = false;
  let animRunning = false;

  function findBoardEl() {
    return (
      document.querySelector("wc-chess-board") ||
      document.querySelector("chess-board") ||
      document.querySelector("#board-layout-chessboard chess-board") ||
      document.querySelector("[class*='board'][class*='chess']") ||
      document.querySelector("#board-board")
    );
  }

  function boardFlipped(board) {
    if (!board) return false;
    if (board.classList?.contains("flipped")) return true;
    if (board.getAttribute?.("flipped") != null) return true;
    const bottom = document.querySelector(".clock-bottom, .board-player-bottom");
    if (bottom && /black|♚/i.test(bottom.textContent || "")) return true;
    return false;
  }

  function decodeSquare(token) {
    const m = String(token).match(/square-(\d)(\d)/);
    if (!m) return null;
    const file = Number(m[1]);
    const rank = Number(m[2]);
    if (file < 1 || file > 8 || rank < 1 || rank > 8) return null;
    return String.fromCharCode(96 + file) + String(rank);
  }

  function readPieces(board) {
    const root = board?.shadowRoot || board;
    const pieces = root?.querySelectorAll?.(".piece") || board?.querySelectorAll?.(".piece") || [];
    const map = {};
    pieces.forEach((el) => {
      const cls = typeof el.className === "string" ? el.className : el.getAttribute("class") || "";
      let piece = null;
      let sq = null;
      cls.split(/\s+/).forEach((c) => {
        if (PIECE_MAP[c]) piece = PIECE_MAP[c];
        const d = decodeSquare(c);
        if (d) sq = d;
      });
      if (!sq && el.dataset?.square) sq = el.dataset.square;
      if (piece && sq) map[sq] = piece;
    });
    return map;
  }

  function piecesToPlacement(pieceMap) {
    const rows = [];
    for (let rank = 8; rank >= 1; rank--) {
      let row = "";
      let empty = 0;
      for (let file = 1; file <= 8; file++) {
        const sq = String.fromCharCode(96 + file) + rank;
        const p = pieceMap[sq];
        if (!p) empty += 1;
        else {
          if (empty) { row += String(empty); empty = 0; }
          row += p;
        }
      }
      if (empty) row += String(empty);
      rows.push(row);
    }
    return rows.join("/");
  }

  function countMovesInList() {
    const nodes = document.querySelectorAll(
      ".move-list-component .node, .vertical-move-list .node, [data-ply], .main-line-ply, wc-move-list .node"
    );
    if (nodes.length) return nodes.length;
    const texts = document.querySelectorAll(".move-text-component, .node-highlight-content");
    return texts.length;
  }

  function guessTurn() {
    const active = document.querySelector(
      ".clock-player-turn, .clock-top.clock-player-turn, .clock-bottom.clock-player-turn"
    );
    if (active) {
      if (active.classList.contains("clock-bottom")) {
        return boardFlipped(findBoardEl()) ? "b" : "w";
      }
      if (active.classList.contains("clock-top")) {
        return boardFlipped(findBoardEl()) ? "w" : "b";
      }
    }
    const ply = countMovesInList();
    return ply % 2 === 0 ? "w" : "b";
  }

  function castleRights(pieceMap) {
    let rights = "";
    if (pieceMap.e1 === "K") {
      if (pieceMap.h1 === "R") rights += "K";
      if (pieceMap.a1 === "R") rights += "Q";
    }
    if (pieceMap.e8 === "k") {
      if (pieceMap.h8 === "r") rights += "k";
      if (pieceMap.a8 === "r") rights += "q";
    }
    return rights || "-";
  }

  function readPosition() {
    const board = findBoardEl();
    if (!board) return { ok: false, error: "no board on page" };
    const pieceMap = readPieces(board);
    const n = Object.keys(pieceMap).length;
    if (n < 2) return { ok: false, error: "pieces not found yet" };
    const placement = piecesToPlacement(pieceMap);
    const turn = guessTurn();
    const flipped = boardFlipped(board);
    const fen = `${placement} ${turn} ${castleRights(pieceMap)} - 0 1`;
    const kings = (placement.match(/K/g) || []).length === 1 && (placement.match(/k/g) || []).length === 1;
    // "our" color = bottom of the board
    const ourColor = flipped ? "b" : "w";
    return {
      ok: kings,
      fen,
      placement,
      turn,
      flipped,
      ourColor,
      isOurTurn: turn === ourColor,
      pieceCount: n,
      url: location.href,
    };
  }

  function ensureOverlay(board) {
    const hostParent = board;
    if (!hostParent) return null;
    let layer = hostParent.querySelector?.("#chess-coach-arrow-layer");
    if (layer) { svg = layer; overlayHost = hostParent; return layer; }
    const mount = hostParent.shadowRoot || hostParent;
    layer = mount.querySelector?.("#chess-coach-arrow-layer");
    if (layer) { svg = layer; overlayHost = mount; return layer; }
    const style = getComputedStyle(hostParent);
    if (style.position === "static") hostParent.style.position = "relative";
    layer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    layer.setAttribute("id", "chess-coach-arrow-layer");
    layer.setAttribute("viewBox", "0 0 8 8");
    layer.setAttribute("preserveAspectRatio", "none");
    (mount.appendChild ? mount : hostParent).appendChild(layer);
    svg = layer;
    overlayHost = mount;
    return layer;
  }

  function sqCenter(sq, flipped) {
    const file = sq.charCodeAt(0) - 97;
    const rank = Number(sq[1]) - 1;
    const col = flipped ? 7 - file : file;
    const row = flipped ? rank : 7 - rank;
    return [col + 0.5, row + 0.5];
  }

  function clearArrows() {
    if (svg) while (svg.firstChild) svg.removeChild(svg.firstChild);
  }

  function _makeArrow(from, to, color, width, flipped, opacity) {
    const [x1, y1] = sqCenter(from, flipped);
    const [x2, y2] = sqCenter(to, flipped);
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    const shorten = 0.28;
    const sx = x1 + ux * 0.18;
    const sy = y1 + uy * 0.18;
    const ex = x2 - ux * shorten;
    const ey = y2 - uy * shorten;

    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", sx);
    line.setAttribute("y1", sy);
    line.setAttribute("x2", ex);
    line.setAttribute("y2", ey);
    line.setAttribute("stroke", color);
    line.setAttribute("stroke-width", String(width));
    line.setAttribute("stroke-linecap", "round");
    line.setAttribute("opacity", String(opacity ?? 0.85));
    line.classList.add("cc-arrow-shaft");

    const head = 0.38;
    const ang = Math.atan2(dy, dx);
    const p1 = [ex, ey];
    const p2 = [ex - head * Math.cos(ang - 0.45), ey - head * Math.sin(ang - 0.45)];
    const p3 = [ex - head * Math.cos(ang + 0.45), ey - head * Math.sin(ang + 0.45)];
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polygon");
    poly.setAttribute("points", `${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`);
    poly.setAttribute("fill", color);
    poly.setAttribute("opacity", String(opacity ?? 0.9));
    poly.classList.add("cc-arrow-head");

    return [line, poly];
  }

  function drawArrows(arrows, flipped) {
    stopAnimation();
    const board = findBoardEl();
    if (!board) return;
    ensureOverlay(board);
    if (!svg) return;
    clearArrows();
    const sorted = [...(arrows || [])].sort((a, b) => (b.rank || 0) - (a.rank || 0));
    for (const a of sorted) {
      const color = ARROW_COLORS[a.rank] || ARROW_COLORS[1];
      const width = a.rank === 1 ? 0.22 : 0.16;
      const els = _makeArrow(a.from, a.to, color, width, flipped);
      els.forEach(el => svg.appendChild(el));
    }
  }

  /* ── Animated PV sequence ── */
  function stopAnimation() {
    if (animTimer) { clearTimeout(animTimer); animTimer = null; }
    animRunning = false;
    animStep = 0;
    animArrows = [];
  }

  function animatePV(pvMoves, flipped, winProb) {
    const board = findBoardEl();
    if (!board) return;
    ensureOverlay(board);
    if (!svg) return;
    stopAnimation();

    // Build a sequence of arrow groups (one per PV move)
    const moves = (pvMoves || []).slice(0, 3);
    if (!moves.length) return;

    animArrows = moves.map((m, i) => ({
      from: m.slice(0, 2),
      to: m.slice(2, 4),
      color: i === 0 ? "#96bc4b" : (i === 1 ? "#5c8ae6" : "#f0c24b"),
      width: i === 0 ? 0.24 : 0.17,
    }));
    animFlipped = flipped;
    animStep = 0;
    animRunning = true;

    // Show win probability badge
    showWinBadge(winProb);

    function showStep() {
      if (!animRunning) return;
      clearArrows();
      // Draw arrows up to current step (fading previous ones)
      for (let i = 0; i <= animStep && i < animArrows.length; i++) {
        const a = animArrows[i];
        const opacity = i === animStep ? 0.95 : Math.max(0.2, 0.6 - (animStep - i) * 0.2);
        const els = _makeArrow(a.from, a.to, a.color, a.width, animFlipped, opacity);
        els.forEach(el => svg.appendChild(el));
      }
      animStep++;
      if (animStep < animArrows.length) {
        animTimer = setTimeout(showStep, 700);
      } else {
        // Hold final frame, then fade out
        animTimer = setTimeout(() => {
          if (!animRunning) return;
          clearArrows();
          hideWinBadge();
          animRunning = false;
        }, 2500);
      }
    }
    showStep();
  }

  function showWinBadge(prob) {
    let el = document.getElementById("chess-coach-win-badge");
    if (!el) {
      el = document.createElement("div");
      el.id = "chess-coach-win-badge";
      el.style.cssText = `
        position:fixed; bottom:60px; right:16px; z-index:999999;
        background:#161a22; color:#34d399; font:bold 14px/1.3 system-ui,sans-serif;
        padding:10px 16px; border-radius:10px; border:1px solid #334155;
        box-shadow:0 8px 24px rgba(0,0,0,0.35); pointer-events:none;
        opacity:0; transition:opacity 0.3s;
      `;
      document.documentElement.appendChild(el);
    }
    el.textContent = `⚡ Win probability: ${Math.round(prob)}%`;
    el.style.opacity = "1";
  }

  function hideWinBadge() {
    const el = document.getElementById("chess-coach-win-badge");
    if (el) el.style.opacity = "0";
  }

  function flashBadge(text) {
    let el = document.getElementById("chess-coach-badge");
    if (!el) {
      el = document.createElement("div");
      el.id = "chess-coach-badge";
      document.documentElement.appendChild(el);
    }
    el.textContent = text;
    el.classList.add("visible");
    clearTimeout(flashBadge._t);
    flashBadge._t = setTimeout(() => el.classList.remove("visible"), 1800);
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "GET_POSITION") {
      sendResponse(readPosition());
      return true;
    }
    if (msg?.type === "DRAW_ARROWS") {
      drawArrows(msg.arrows || [], !!msg.flipped);
      sendResponse({ ok: true });
      return true;
    }
    if (msg?.type === "ANIMATE_PV") {
      animatePV(msg.pvMoves || [], !!msg.flipped, msg.winProb || 0);
      sendResponse({ ok: true });
      return true;
    }
    if (msg?.type === "CLEAR_ARROWS") {
      stopAnimation();
      clearArrows();
      hideWinBadge();
      sendResponse({ ok: true });
      return true;
    }
    if (msg?.type === "PING") {
      sendResponse({ ok: true, href: location.href });
      return true;
    }
    return false;
  });

  const obs = new MutationObserver(() => {
    const pos = readPosition();
    if (!pos.ok) return;
    if (pos.fen === lastFen) return;
    lastFen = pos.fen;
    chrome.runtime.sendMessage({ type: "POSITION_CHANGED", position: pos }).catch(() => {});
  });

  function armObserver() {
    const board = findBoardEl();
    if (!board) return;
    obs.observe(board, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    if (board.shadowRoot) {
      obs.observe(board.shadowRoot, { childList: true, subtree: true, attributes: true });
    }
  }

  armObserver();
  setInterval(armObserver, 2000);
  flashBadge("Chess Coach ready — open the side panel");
})();
