# input_handler.py - 滑鼠輸入模擬
# 使用 win32api 直接發送滑鼠事件，避免被 VRChat 的輸入鉤子攔截

import time

import win32api
import win32con


class InputHandler:
    """
    封裝左鍵 press / release 操作。
    VRChat 使用 Raw Input，因此用 win32api.mouse_event 而非 SendInput 或 pyautogui。
    """

    def __init__(self):
        self._lmb_down = False  # 追蹤當前左鍵狀態，避免重複發送

    # ── 左鍵 ─────────────────────────────────────────────────────────────────

    def lmb_press(self):
        """按下左鍵（若已按下則忽略）。"""
        if not self._lmb_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            self._lmb_down = True

    def lmb_release(self):
        """放開左鍵（若已放開則忽略）。"""
        if self._lmb_down:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self._lmb_down = False

    def lmb_click(self, delay: float = 0.05):
        """按下後等待 delay 秒再放開（模擬短按）。"""
        self.lmb_press()
        time.sleep(delay)
        self.lmb_release()

    @property
    def is_lmb_down(self) -> bool:
        return self._lmb_down

    # ── 緊急釋放 ──────────────────────────────────────────────────────────────

    def release_all(self):
        """程式結束或發生異常時確保所有按鍵釋放。"""
        self.lmb_release()
