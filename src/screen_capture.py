# screen_capture.py - 畫面擷取模組
# 定位 VRChat 視窗並進行截圖，支援解析度縮放

import cv2
import mss
import numpy as np
import win32gui

from src.config import TARGET_HEIGHT, TARGET_WIDTH, WINDOW_TITLE


class ScreenCapture:
    def __init__(self):
        self._sct = mss.mss()
        self.hwnd: int = 0
        self.win_rect: dict = {}  # {"left", "top", "width", "height"}
        self.scale_x: float = 1.0
        self.scale_y: float = 1.0
        self._locate_window()

    # ── 視窗定位 ──────────────────────────────────────────────────────────────

    def _locate_window(self) -> bool:
        """尋找 VRChat 視窗並記錄位置與縮放比例，回傳是否成功。"""

        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if WINDOW_TITLE.lower() in title.lower():
                    results.append(hwnd)

        results = []
        win32gui.EnumWindows(_cb, None)

        if not results:
            return False

        self.hwnd = results[0]
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        # 去除視窗標題列與邊框（估算值，大多數視窗適用）
        border = 8
        title_h = 30
        self.win_rect = {
            "left": left + border,
            "top": top + title_h,
            "width": right - left - border * 2,
            "height": bottom - top - title_h - border,
        }
        w = self.win_rect["width"]
        h = self.win_rect["height"]
        self.scale_x = w / TARGET_WIDTH
        self.scale_y = h / TARGET_HEIGHT
        return True

    def refresh_window(self) -> bool:
        """在視窗移動或大小改變時重新定位。"""
        return self._locate_window()

    # ── 截圖 ──────────────────────────────────────────────────────────────────

    def grab_window(self) -> np.ndarray | None:
        """截取整個遊戲視窗，回傳 BGR numpy array。"""
        if not self.win_rect:
            if not self._locate_window():
                return None
        try:
            raw = self._sct.grab(self.win_rect)
        except Exception:
            self._locate_window()
            return None
        # mss 回傳 BGRA，轉為 BGR
        frame = np.array(raw)[:, :, :3]
        return frame

    def grab_region(self, x: int, y: int, w: int, h: int) -> np.ndarray | None:
        """
        截取視窗內的特定區域（座標以 TARGET 解析度為基準）。
        自動套用 scale_x / scale_y 轉換至實際像素位置。
        """
        rx = int(x * self.scale_x)
        ry = int(y * self.scale_y)
        rw = int(w * self.scale_x)
        rh = int(h * self.scale_y)
        region = {
            "left": self.win_rect["left"] + rx,
            "top": self.win_rect["top"] + ry,
            "width": max(rw, 1),
            "height": max(rh, 1),
        }
        try:
            raw = self._sct.grab(region)
        except Exception:
            return None
        return np.array(raw)[:, :, :3]

    def to_target_coords(self, x: int, y: int):
        """將視窗座標（實際像素）轉換回 TARGET 解析度座標。"""
        return int(x / self.scale_x), int(y / self.scale_y)

    def to_screen_coords(self, x: int, y: int):
        """
        將 TARGET 解析度座標轉換為螢幕絕對座標（供滑鼠輸入使用）。
        """
        sx = self.win_rect["left"] + int(x * self.scale_x)
        sy = self.win_rect["top"] + int(y * self.scale_y)
        return sx, sy

    # ── 工具 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def to_hsv(frame: np.ndarray) -> np.ndarray:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    @staticmethod
    def resize_to_target(frame: np.ndarray) -> np.ndarray:
        """將截圖縮放至 TARGET 解析度，方便與固定 ROI 座標對齊。"""
        return cv2.resize(
            frame, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR
        )
