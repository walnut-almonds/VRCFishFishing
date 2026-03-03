# utils.py - 工具函式：日誌、debug overlay

import datetime
import os
import time

import cv2
import numpy as np

from src.config import DEBUG_FRAME_DIR, DEBUG_LOG, DEBUG_OVERLAY, DEBUG_SAVE_FRAMES

# ── 日誌 ──────────────────────────────────────────────────────────────────────


def log(msg: str):
    if DEBUG_LOG:
        ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] {msg}")


# ── Debug Overlay ──────────────────────────────────────────────────────────────


class DebugOverlay:
    """
    將偵測結果畫在截圖上並顯示於 OpenCV 視窗。
    按 'q' 鍵可在主迴圈外部關閉。
    """

    WINDOW_NAME = "VRC Fishing Bot - Debug"
    _frame_idx = 0

    @classmethod
    def show(
        cls,
        frame: np.ndarray,
        state: str,
        ui_info: dict | None = None,
        extra: dict | None = None,
    ):
        if not DEBUG_OVERLAY:
            return

        vis = frame.copy()
        h, w = vis.shape[:2]

        # 狀態標籤
        cv2.rectangle(vis, (0, 0), (220, 30), (0, 0, 0), -1)
        cv2.putText(
            vis,
            f"State: {state}",
            (5, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 128),
            2,
        )

        # 拉力計 UI bounding box
        if ui_info:
            _draw_box(vis, ui_info.get("ui_box"), (0, 255, 255), "UI")
            _draw_box(vis, ui_info.get("left_bar"), (0, 200, 255), "Progress")
            _draw_box(vis, ui_info.get("right_bar"), (255, 100, 0), "Tension")

        # 額外資訊（progress, white_cy, fish_cy 等）
        if extra:
            y_off = 55
            for k, v in extra.items():
                text = f"{k}: {v}"
                cv2.putText(
                    vis,
                    text,
                    (5, y_off),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (200, 200, 200),
                    1,
                )
                y_off += 20

        cv2.imshow(cls.WINDOW_NAME, vis)
        cv2.waitKey(1)

        # 儲存幀
        if DEBUG_SAVE_FRAMES:
            os.makedirs(DEBUG_FRAME_DIR, exist_ok=True)
            path = os.path.join(DEBUG_FRAME_DIR, f"{cls._frame_idx:06d}.png")
            cv2.imwrite(path, vis)
            cls._frame_idx += 1

    @classmethod
    def close(cls):
        cv2.destroyAllWindows()

    @classmethod
    def is_quit_pressed(cls) -> bool:
        """回傳是否按下 'q' 鍵（需先呼叫 show）。"""
        key = cv2.waitKey(1) & 0xFF
        return key == ord("q")

    @classmethod
    def is_pause_pressed(cls) -> bool:
        """回傳是否按下 'p' 鍵（需先呼叫 show）。"""
        key = cv2.waitKey(1) & 0xFF
        return key == ord("p")


def _draw_box(img: np.ndarray, box: tuple | None, color: tuple, label: str):
    if box is None:
        return
    x, y, w, h = box
    cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
    cv2.putText(
        img, label, (x, max(y - 4, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1
    )


# ── 統計計數器 ─────────────────────────────────────────────────────────────────


class Stats:
    def __init__(self):
        self.casts = 0
        self.bites = 0
        self.successes = 0
        self.failures = 0
        self._start_time = time.time()

    def report(self) -> str:
        elapsed = time.time() - self._start_time
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        return (
            f"運行 {h:02d}:{m:02d}:{s:02d} | "
            f"拋竿:{self.casts}  咬勾:{self.bites}  "
            f"成功:{self.successes}  失敗:{self.failures}"
        )
