(() => {
  const $ = (id) => document.getElementById(id);
  const statusEl = $("status");
  const evalEl = $("eval");
  const cardsEl = $("cards");
  const warningsEl = $("warnings");
  const btnAnalyze = $("btnAnalyze");
  const btnAuto = $("btnAuto");
  const btnClear = $("btnClear");
  const btnRefresh = $("btnRefresh");
  const depthSel = $("depth");

  const engine = new CoachEngine();
  let auto = true;
  let analyzing = false;
  let lastFen = "";
  let lastFlipped = false;
  let ourColor = "w";

  function setStatus(msg) {
    statusEl.textContent = msg;
  }

  function fmtEval(kind, val) {
    if (kind === "mate") {
      return val > 0 ? `M${val}` : `-M${Math.abs(val)}`;
    }
    return `${val >= 0 ? "+" : ""}${(val / 100).toFixed(2)}`;
  }

  function explainMove(board, uci) {
    try {
      const from = uci.slice(0, 2);
      const to = uci.slice(2, 4);
      const promo = uci[4];
      const move = board.move({ from, to, promotion: promo || "q" });
      if (!move) return { san: uci, why: "Candidate move." };
      const bits = [];
      if (move.flags.includes("c") || move.flags.includes("e")) bits.push(`Captures on ${to}.`);
      if (move.flags.includes("k") || move.flags.includes("q")) bits.push("Castles for king safety / rook development.");
      if (move.san.includes("+")) bits.push("Gives check.");
      if (move.san.includes("#")) bits.push("Checkmate!");
      if (move.piece === "p" && (to[1] === "4" || to[1] === "5") && "de".includes(to[0])) {
        bits.push("Grabs central space.");
      }
      if (move.piece === "n") bits.push(`Knight hop ${from}→${to}.`);
      if (move.piece === "b") bits.push("Bishop develops onto an active diagonal.");
      if (move.piece === "r") bits.push("Rook enters the game / seizes a file.");
      if (move.piece === "q") bits.push("Queen enters the action.");
      if (!bits.length) bits.push(`Improves the position (${from}→${to}).`);
      const san = move.san;
      board.undo();
      return { san, why: bits.join(" "), from, to };
    } catch {
      return { san: uci, why: "Candidate move.", from: uci.slice(0, 2), to: uci.slice(2, 4) };
    }
  }

  /** Convert centipawn to win probability using a sigmoid. */
  function cpToWinProb(cp) {
    // logistic: 1 / (1 + exp(-cp/400))
    return 100 / (1 + Math.exp(-cp / 400));
  }

  function renderCards(board, lines, isOurTurn) {
    cardsEl.innerHTML = "";
    const arrows = [];
    const baseCp = lines[0]
      ? lines[0].kind === "mate"
        ? (lines[0].val > 0 ? 10000 : -10000)
        : lines[0].val
      : 0;

    // Only show predictions when it's our turn
    if (!isOurTurn) {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="card-head">
          <span class="san">⏳ Opponent to move</span>
        </div>
        <div class="why">Predictions appear when it's your turn.</div>
      `;
      cardsEl.appendChild(card);
      return { arrows, winProb: null };
    }

    lines.slice(0, 3).forEach((line, i) => {
      const uci = line.pv[0];
      const { san, why, from, to } = explainMove(board, uci);
      const rank = i + 1;
      arrows.push({ from, to, rank, san });

      const cp = line.kind === "mate" ? (line.val > 0 ? 10000 : -10000) : line.val;
      const loss = Math.max(0, baseCp - cp);
      const label = rank === 1 ? "★ Best" : loss < 30 ? "Good" : loss < 80 ? "OK" : "Alt";

      const card = document.createElement("div");
      card.className = `card rank-${rank}`;
      const pvSans = [];
      const b = new Chess(board.fen());
      for (const u of line.pv.slice(0, 8)) {
        const m = b.move({ from: u.slice(0, 2), to: u.slice(2, 4), promotion: u[4] || "q" });
        if (!m) break;
        pvSans.push(m.san);
      }

      card.innerHTML = `
        <div class="card-head">
          <span class="san">${rank}. ${san} <span style="opacity:.7">${from}→${to}</span></span>
          <span class="meta">${label} · ${fmtEval(line.kind, line.val)}</span>
        </div>
        <div class="why">${why}</div>
        <div class="pv">${pvSans.join(" ")}</div>
      `;
      cardsEl.appendChild(card);
    });

    const winProb = cpToWinProb(baseCp);
    return { arrows, winProb };
  }

  async function getActiveTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0];
  }

  async function askContent(message) {
    const tab = await getActiveTab();
    if (!tab?.id) throw new Error("No active tab");
    if (!tab.url || !tab.url.includes("chess.com")) {
      throw new Error("Focus a chess.com tab first");
    }
    try {
      return await chrome.tabs.sendMessage(tab.id, message);
    } catch {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
      await chrome.scripting.insertCSS({ target: { tabId: tab.id }, files: ["content.css"] }).catch(() => {});
      return await chrome.tabs.sendMessage(tab.id, message);
    }
  }

  async function analyzeNow(force = false) {
    if (analyzing) return;
    analyzing = true;
    btnAnalyze.disabled = true;
    try {
      setStatus("Reading board…");
      const pos = await askContent({ type: "GET_POSITION" });
      if (!pos?.ok) {
        setStatus(pos?.error || "Could not read board");
        return;
      }
      if (!force && pos.fen === lastFen) {
        setStatus("Position unchanged");
        return;
      }
      lastFen = pos.fen;
      lastFlipped = !!pos.flipped;
      ourColor = pos.ourColor || "w";

      let board;
      try {
        board = new Chess(pos.fen);
      } catch {
        setStatus("Invalid position read from page");
        return;
      }

      setStatus(`Analyzing (depth ${depthSel.value})…`);
      await engine.init();
      const lines = await engine.analyze(pos.fen, {
        depth: Number(depthSel.value),
        multipv: 3,
      });
      if (!lines?.length) {
        setStatus("Engine returned no lines");
        return;
      }

      const top = lines[0];
      evalEl.textContent = fmtEval(top.kind, top.val);
      const { arrows, winProb } = renderCards(board, lines, pos.isOurTurn);

      if (pos.isOurTurn) {
        // Draw static arrows
        await askContent({ type: "DRAW_ARROWS", arrows, flipped: lastFlipped });

        // If highly predictive of win (cp > 200 or mate), animate next 3 moves
        const topCp = top.kind === "mate" ? (top.val > 0 ? 10000 : -10000) : top.val;
        if (topCp > 200 && top.pv && top.pv.length >= 3) {
          await askContent({
            type: "ANIMATE_PV",
            pvMoves: top.pv.slice(0, 3),
            flipped: lastFlipped,
            winProb: cpToWinProb(topCp),
          });
        }
      } else {
        // Opponent's turn — just clear arrows
        await askContent({ type: "CLEAR_ARROWS" });
      }

      warningsEl.textContent = pos.isOurTurn
        ? `Your turn (${ourColor === "w" ? "White" : "Black"})`
        : `Opponent thinking…`;
      setStatus(`Updated · ${pos.pieceCount} pieces · ${new Date().toLocaleTimeString()}`);
    } catch (e) {
      setStatus(String(e.message || e));
    } finally {
      analyzing = false;
      btnAnalyze.disabled = false;
    }
  }

  btnAnalyze.addEventListener("click", () => analyzeNow(true));
  btnRefresh.addEventListener("click", () => analyzeNow(true));
  btnClear.addEventListener("click", async () => {
    try {
      await askContent({ type: "CLEAR_ARROWS" });
      setStatus("Arrows cleared");
    } catch (e) {
      setStatus(String(e.message || e));
    }
  });
  btnAuto.addEventListener("click", () => {
    auto = !auto;
    btnAuto.classList.toggle("on", auto);
    btnAuto.textContent = auto ? "Auto: ON" : "Auto: OFF";
  });

  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "POSITION_CHANGED" && auto) {
      analyzeNow(false);
    }
  });

  setStatus("Loading Stockfish…");
  engine
    .init()
    .then(() => setStatus("Ready — open a chess.com game"))
    .catch((e) => setStatus("Engine failed to load: " + e));

  setTimeout(() => analyzeNow(true), 600);
})();
