# tension_handler.py - 拉力計階段控制邏輯
#
# 職責：
#   給定拉力計 UI 位置（detect_tension_ui 的結果），
#   分析白色區域與魚圖示的相對位置，並輸出按鍵決策。
#
# 控制策略（簡易位置控制）：
#   魚在白區內   → 維持當前狀態（死區）
#   魚在白區下方 → 放開左鍵（白區往下掉，但魚更下所以不需要追）
#   魚在白區上方 → 按下左鍵（白區上升追魚）

import cv2
import numpy as np
from src.config import (
    WHITE_HSV_LOW, WHITE_HSV_HIGH,
    FISH_SAT_MIN, FISH_VAL_MIN, FISH_AREA_MIN, FISH_AREA_MAX,
    PROGRESS_GREEN_HSV_LOW, PROGRESS_GREEN_HSV_HIGH,
    PROGRESS_SUCCESS_RATIO, PROGRESS_FAIL_RATIO,
    TENSION_DEAD_ZONE,
)
from src.utils import log


class TensionResult:
    """單幀分析結果。"""
    SUCCESS  = "success"
    FAIL     = "fail"
    CONTINUE = "continue"
    NO_UI    = "no_ui"


class TensionHandler:

    def __init__(self):
        self._last_press = False  # 上一幀的按鍵狀態

    def analyze(self, frame: np.ndarray, ui_info: dict) -> tuple[str, bool]:
        """
        分析拉力計狀態。

        參數：
            frame   : 已縮放至 TARGET 解析度的 BGR 截圖
            ui_info : detect_tension_ui() 的回傳值

        回傳：
            (result, should_press_lmb)
            result         : TensionResult 中的常數
            should_press_lmb : True = 按住左鍵，False = 放開左鍵
        """
        if ui_info is None:
            return TensionResult.NO_UI, False

        # ── 進度條判斷 ────────────────────────────────────────────────────────
        progress = self._read_progress(frame, ui_info["left_bar"])
        log(f"[Tension] progress={progress:.2f}")

        if progress >= PROGRESS_SUCCESS_RATIO:
            return TensionResult.SUCCESS, False
        if progress <= PROGRESS_FAIL_RATIO:
            return TensionResult.FAIL, False

        # ── 拉力條控制 ────────────────────────────────────────────────────────
        should_press = self._compute_press(frame, ui_info["right_bar"])
        return TensionResult.CONTINUE, should_press

    # ── 進度條讀取 ────────────────────────────────────────────────────────────

    def _read_progress(self, frame: np.ndarray, bar_box: tuple) -> float:
        """
        讀取左側進度條的綠色填充比例（0.0 ~ 1.0）。
        進度條從底部向上填充，掃描整個條形區域。
        """
        x, y, w, h = bar_box
        x, y = max(x, 0), max(y, 0)
        x2 = min(x + w, frame.shape[1])
        y2 = min(y + h, frame.shape[0])
        region = frame[y:y2, x:x2]
        if region.size == 0:
            return 0.0

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        lo = np.array(PROGRESS_GREEN_HSV_LOW,  dtype=np.uint8)
        hi = np.array(PROGRESS_GREEN_HSV_HIGH, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        total_pixels = mask.shape[0] * mask.shape[1]
        if total_pixels == 0:
            return 0.0
        return float(np.sum(mask > 0)) / total_pixels

    # ── 拉力條控制 ────────────────────────────────────────────────────────────

    def _compute_press(self, frame: np.ndarray, bar_box: tuple) -> bool:
        """
        分析拉力條（右側），決定是否需要按住左鍵。

        邏輯：
          error = fish_center_y - white_center_y
          error < -DEAD_ZONE  → 魚在白區上方 → 按下（白區上升追魚）
          error > +DEAD_ZONE  → 魚在白區下方 → 放開
          |error| <= DEAD_ZONE → 維持上一幀狀態
        """
        x, y, w, h = bar_box
        x, y = max(x, 0), max(y, 0)
        x2 = min(x + w, frame.shape[1])
        y2 = min(y + h, frame.shape[0])
        region = frame[y:y2, x:x2]
        if region.size == 0:
            return self._last_press

        white_cy = self._find_white_center_y(region)
        fish_cy  = self._find_fish_center_y(region)

        log(f"[Tension] white_cy={white_cy} fish_cy={fish_cy}")

        if white_cy is None or fish_cy is None:
            # 無法偵測時維持上一幀狀態
            return self._last_press

        error = fish_cy - white_cy

        if error < -TENSION_DEAD_ZONE:
            # 魚在白區上方 → 按下左鍵讓白區上升
            decision = True
        elif error > TENSION_DEAD_ZONE:
            # 魚在白區下方 → 放開左鍵
            decision = False
        else:
            # 死區內維持
            decision = self._last_press

        self._last_press = decision
        return decision

    def _find_white_center_y(self, region: np.ndarray) -> float | None:
        """找白色區域的中心 Y（相對於 region 頂部）。"""
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        lo = np.array(WHITE_HSV_LOW,  dtype=np.uint8)
        hi = np.array(WHITE_HSV_HIGH, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        ys = np.where(mask > 0)[0]
        if len(ys) < 10:
            return None
        return float(np.mean(ys))

    def _find_fish_center_y(self, region: np.ndarray) -> float | None:
        """
        找魚圖示的中心 Y。
        魚圖示為小型像素風圖案，顏色多樣（非白非黑），
        以飽和色塊來定位。
        """
        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        # 排除白色與黑色，找有色彩的像素
        sat_mask = hsv[:, :, 1] >= FISH_SAT_MIN
        val_mask = hsv[:, :, 2] >= FISH_VAL_MIN
        # 排除明顯白色（低飽和高明度）
        not_white = hsv[:, :, 1] >= 50
        mask = (sat_mask & val_mask & not_white).astype(np.uint8) * 255

        # 形態學去噪
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        best_y    = None
        best_area = 0
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (FISH_AREA_MIN <= area <= FISH_AREA_MAX):
                continue
            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            cy = M["m01"] / M["m00"]
            # 保留面積最大的候選（最可能是魚圖示）
            if area > best_area:
                best_area = area
                best_y    = cy
        return best_y
