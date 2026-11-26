#!/usr/bin/env python3
"""One-time step 1: snip the board region on screen -> assets/calibration.json"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import mss
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
WIN = "snip the board — ENTER confirm | c cancel | then answer Y/n in terminal"


def grab_screen():
    with mss.MSS() as sct:
        shot = np.array(sct.grab(sct.monitors[0]))
    return cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR)


def main():
    print("=== Board calibration ===")
    print("1. Open chess.com with a board visible.")
    print("2. Press ENTER here when ready — then switch to chess.com during the countdown.")
    print("3. Drag tightly around the 64 squares, ENTER/SPACE to confirm.")
    print("   Empty selection or cancel → retake screenshot.")
    input("Press ENTER to start… ")

    while True:
        for i in range(3, 0, -1):
            print(f"  capturing in {i}… (switch to chess.com)", flush=True)
            time.sleep(1)
        img = grab_screen()
        print("Drag a TIGHT rectangle around the 64 squares, then ENTER/SPACE. 'c' = cancel/retake.")
        roi = cv2.selectROI(WIN, img, showCrosshair=True, fromCenter=False)
        cv2.destroyAllWindows()
        x, y, w, h = map(int, roi)
        if w == 0 or h == 0:
            again = input("No selection. Retake screenshot? [Y/n]: ").strip().lower()
            if again in ("n", "no"):
                print("Bye.")
                return
            continue

        preview = img[y : y + h, x : x + w].copy()
        # Scale preview so it's easy to check
        scale = min(800 / max(preview.shape[1], 1), 800 / max(preview.shape[0], 1), 1.0)
        if scale < 1.0:
            preview = cv2.resize(preview, None, fx=scale, fy=scale)
        cv2.imshow("preview — does this look like ONLY the 64 squares?  y=yes  n=retake", preview)
        print("Preview window open — press 'y' if good, 'n' to retake.", flush=True)
        while True:
            key = cv2.waitKey(50) & 0xFF
            if key in (ord("y"), ord("Y"), 13, 32):  # y / Enter / Space
                ok = True
                break
            if key in (ord("n"), ord("N"), 27):  # n / Esc
                ok = False
                break
        cv2.destroyAllWindows()
        if not ok:
            continue

        white_bottom = input("Is WHITE at the BOTTOM of the board? [Y/n]: ").strip().lower() not in ("n", "no")
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, "calibration.json")
        with open(path, "w") as f:
            json.dump(
                {"region": [x, y, w, h], "flipped": not white_bottom},
                f,
                indent=2,
            )
        cv2.imwrite(os.path.join(OUT, "calibration_preview.png"), img[y : y + h, x : x + w])
        print(f"Saved {path}: region=[{x}, {y}, {w}, {h}] flipped={not white_bottom}")
        print("Preview also at assets/calibration_preview.png")
        return


if __name__ == "__main__":
    main()
