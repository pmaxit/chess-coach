/* Stockfish wrapper for the side panel (MV3 + wasm, single-threaded). */
(() => {
  class CoachEngine {
    constructor() {
      this.worker = null;
      this.ready = null;
      this._resolver = null;
      this._lines = new Map();
    }

    async init() {
      if (this.ready) return this.ready;
      this.ready = new Promise((resolve, reject) => {
        try {
          // stockfish-nnue-16-single.js auto-enters worker mode when imported as Worker
          this.worker = new Worker(
            chrome.runtime.getURL("worker/stockfish.js")
          );
        } catch (e) {
          reject(e);
          return;
        }

        let resolved = false;
        const done = () => {
          if (!resolved) {
            resolved = true;
            resolve(true);
          }
        };

        this.worker.onmessage = (e) => {
          const line = typeof e.data === "string" ? e.data : "";
          if (!line) return;
          if (line.includes("uciok")) {
            this.worker.postMessage("isready");
          }
          if (line.includes("readyok")) done();
          this._onEngineLine(line);
        };
        this.worker.onerror = (err) => {
          console.error("stockfish worker error", err);
          if (!resolved) reject(err);
        };

        // Give the wasm a moment to boot, then send uci
        setTimeout(() => this.worker.postMessage("uci"), 200);
        setTimeout(done, 5000); // don't hang forever
      });
      return this.ready;
    }

    _onEngineLine(line) {
      if (line.startsWith("info ") && line.includes(" pv ")) {
        const mp = /multipv (\d+)/.exec(line);
        const multipv = mp ? Number(mp[1]) : 1;
        const sc = /score (cp|mate) (-?\d+)/.exec(line);
        const pvMatch = / pv (.+)$/.exec(line);
        if (!sc || !pvMatch) return;
        this._lines.set(multipv, {
          kind: sc[1],
          val: Number(sc[2]),
          pv: pvMatch[1].trim().split(/\s+/),
        });
      }
      if (line.startsWith("bestmove")) {
        if (this._resolver) {
          const resolver = this._resolver;
          this._resolver = null;
          const lines = Array.from(this._lines.entries())
            .sort((a, b) => a[0] - b[0])
            .map(([, v]) => v);
          resolver(lines);
        }
      }
    }

    async analyze(fen, { depth = 15, multipv = 3 } = {}) {
      await this.init();
      this._lines = new Map();
      return new Promise((resolve) => {
        this._resolver = resolve;
        this.worker.postMessage("stop");
        this.worker.postMessage("ucinewgame");
        this.worker.postMessage(`setoption name MultiPV value ${multipv}`);
        this.worker.postMessage(`position fen ${fen}`);
        this.worker.postMessage(`go depth ${depth}`);
        setTimeout(() => {
          if (this._resolver) this.worker.postMessage("stop");
        }, 25000);
      });
    }
  }

  window.CoachEngine = CoachEngine;
})();
