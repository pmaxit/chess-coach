#!/usr/bin/env python3
"""One-time step 2: with a fresh chess.com STARTING position visible, extract piece templates."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from coach import board_capture as bc

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    calib = bc.load_calibration(os.path.join(HERE, "assets", "calibration.json"))
    print("Snapshotting in 3 s — make sure the STARTING position is on screen…")
    import time
    time.sleep(3)
    saved = bc.extract_templates(out_dir=os.path.join(HERE, "assets", "templates"),
                                 region=calib["region"], flipped=calib.get("flipped", False))
    print("Templates saved:", sorted(set(saved)))
    print("Sanity-check by running main.py — it should show '+/− eval' soon after a game starts.")


if __name__ == "__main__":
    main()
