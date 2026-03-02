# state_detector.py - 各階段視覺判斷
#
# 職責：
#   detect_exclaim(frame)      → bool   (WAITING: 「!」出現)
#   detect_tension_ui(frame)   → dict|None  (TENSION: 找到拉力計，回傳 UI 位置資訊)
#   detect_finish(frame)       → bool   (FINISH: 釣起魚 XP 浮字)
#
# 所有座標以 TARGET 解析度（1366x768）為基準，
# 呼叫前請先將 frame resize 至 TARGET。

import os
import cv2
import numpy as np
from config import (
    EXCLAIM_HSV_LOW, EXCLAIM_HSV_HIGH,
    EXCLAIM_MATCH_THRESH, EXCLAIM_DIFF_THRESH, EXCLAIM_TEMPLATE_DIR,
    TENSION_BLUE_HSV_LOW, TENSION_BLUE_HSV_HIGH,
    TENSION_BAR_ASPECT_MIN, TENSION_BAR_ASPECT_MAX,
    TENSION_BAR_AREA_MIN, TENSION_BAR_AREA_MAX,
    TENSION_PAIR_MAX_DIST,
    FINISH_YELLOW_HSV_LOW, FINISH_YELLOW_HSV_HIGH,
    FINISH_PIXEL_THRESH,
    TARGET_WIDTH, TARGET_HEIGHT,
)
from utils import log


class StateDetector:

    def __init__(self):
        self._exclaim_templates: list[np.ndarray] = []
        self._prev_frame: np.ndarray | None = None
        self._load_exclaim_templates()
        # 拉力計上幀位置快取（加速搜尋）
        self._last_tension_roi: tuple | None = None  # (x, y, w, h)

    # ── 模板載入 ──────────────────────────────────────────────────────────────

    def _load_exclaim_templates(self):
        if not os.path.isdir(EXCLAIM_TEMPLATE_DIR):
            log(f"[Detector] 找不到模板資料夾 {EXCLAIM_TEMPLATE_DIR}，跳過模板匹配")
            return
        for fname in os.listdir(EXCLAIM_TEMPLATE_DIR):
            if fname.lower().endswith((".png", ".jpg")):
                path = os.path.join(EXCLAIM_TEMPLATE_DIR, fname)
                tpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tpl is not None:
                    self._exclaim_templates.append(tpl)
        log(f"[Detector] 載入 {len(self._exclaim_templates)} 個「!」模板")

    # ═══════════════════════════════════════════════════════════════════════════
    # WAITING：偵測「!」咬勾提示
    # ═══════════════════════════════════════════════════════════════════════════

    def detect_exclaim(self, frame: np.ndarray) -> bool:
        """
        回傳 True 表示偵測到「!」提示。
        依序嘗試：模板匹配 → 顏色+形狀 Blob → 差分偵測，任一成功即回傳。
        """
        # 只搜尋畫面上半部（排除 HUD）
        search_h = int(TARGET_HEIGHT * 0.80)
        roi = frame[:search_h, :]

        if self._detect_exclaim_template(roi):
            return True
        if self._detect_exclaim_blob(roi):
            return True
        if self._detect_exclaim_diff(frame):
            return True
        return False

    def _detect_exclaim_template(self, roi: np.ndarray) -> bool:
        """模板匹配偵測。"""
        if not self._exclaim_templates:
            return False
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        for tpl in self._exclaim_templates:
            if tpl.shape[0] > gray.shape[0] or tpl.shape[1] > gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val >= EXCLAIM_MATCH_THRESH:
                log(f"[Detector] 模板匹配「!」score={max_val:.3f}")
                return True
        return False

    def _detect_exclaim_blob(self, roi: np.ndarray) -> bool:
        """
        顏色 + 形狀偵測：
        「!」本體為高亮白色細長矩形，外框帶藍紫色。
        先找藍紫色輪廓，再驗證其長寬比是否符合「!」形狀。
        """
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lo = np.array(EXCLAIM_HSV_LOW,  dtype=np.uint8)
        hi = np.array(EXCLAIM_HSV_HIGH, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        # 形態學閉合，填補輪廓間隙
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 40 or area > 6000:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w == 0:
                continue
            aspect = h / w
            # 「!」整體（上方長條 + 下方圓點）長寬比約 2.5 ~ 5.0
            if 2.2 <= aspect <= 6.0:
                log(f"[Detector] Blob「!」area={area} aspect={aspect:.2f}")
                return True
        return False

    def reset_diff(self):
        """重新進入 WAITING 時呼叫，清除差分基準幀避免誤觸。"""
        self._prev_frame = None

    def _detect_exclaim_diff(self, frame: np.ndarray) -> bool:
        """
        差分偵測：「!」出現時中央區域有明顯突發變化。
        只比較畫面中央 40% 寬 × 60% 高的區域，
        排除因鏡頭緩慢移動造成的全畫面背景差分。
        """
        h, w = frame.shape[:2]
        # 中央 ROI
        cx0 = int(w * 0.30); cx1 = int(w * 0.70)
        cy0 = int(h * 0.10); cy1 = int(h * 0.70)
        roi = frame[cy0:cy1, cx0:cx1]

        if self._prev_frame is None:
            self._prev_frame = roi.copy()
            return False

        diff = cv2.absdiff(roi, self._prev_frame)
        self._prev_frame = roi.copy()

        # 找突發高亮區塊（白色 + 藍紫外框的突然出現）
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY)
        bright_pixels = int(np.sum(thresh > 0))

        if bright_pixels > EXCLAIM_DIFF_THRESH:
            log(f"[Detector] 差分觸發 bright_pixels={bright_pixels}")
            return True
        return False

    # ═══════════════════════════════════════════════════════════════════════════
    # TENSION：偵測拉力計 UI
    # ═══════════════════════════════════════════════════════════════════════════

    def detect_tension_ui(self, frame: np.ndarray) -> dict | None:
        """
        動態搜尋拉力計藍色外框。
        回傳 dict：
            {
              "left_bar":  (x, y, w, h),   # 進度條 bounding box（TARGET 座標）
              "right_bar": (x, y, w, h),   # 拉力條 bounding box
              "ui_box":    (x, y, w, h),   # 整個 UI bounding box
            }
        找不到時回傳 None。
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lo = np.array(TENSION_BLUE_HSV_LOW,  dtype=np.uint8)
        hi = np.array(TENSION_BLUE_HSV_HIGH, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        # 篩選符合長寬比與面積的細長矩形
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (TENSION_BAR_AREA_MIN <= area <= TENSION_BAR_AREA_MAX):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w == 0:
                continue
            aspect = h / w
            if TENSION_BAR_ASPECT_MIN <= aspect <= TENSION_BAR_ASPECT_MAX:
                candidates.append((x, y, w, h))

        if len(candidates) < 2:
            self._last_tension_roi = None
            return None

        # 尋找水平距離最近的兩條（進度條 + 拉力條）
        best_pair = self._find_bar_pair(candidates)
        if best_pair is None:
            self._last_tension_roi = None
            return None

        left_bar, right_bar = best_pair
        # 確保 left_bar 在左側
        if left_bar[0] > right_bar[0]:
            left_bar, right_bar = right_bar, left_bar

        # 計算包含兩條的 UI bounding box
        xs = [left_bar[0], right_bar[0]]
        ys = [left_bar[1], right_bar[1]]
        x2s = [left_bar[0] + left_bar[2], right_bar[0] + right_bar[2]]
        y2s = [left_bar[1] + left_bar[3], right_bar[1] + right_bar[3]]
        ui_x = min(xs) - 4
        ui_y = min(ys) - 4
        ui_w = max(x2s) - ui_x + 4
        ui_h = max(y2s) - ui_y + 4

        result = {
            "left_bar":  left_bar,
            "right_bar": right_bar,
            "ui_box":    (ui_x, ui_y, ui_w, ui_h),
        }

        # 驗證內部結構
        if not self._validate_tension_structure(frame, result):
            return None

        self._last_tension_roi = (ui_x, ui_y, ui_w, ui_h)
        return result

    def _find_bar_pair(self, candidates: list) -> tuple | None:
        """找水平距離最近、且高度相近的兩個候選框。"""
        best = None
        best_dist = float("inf")
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                a, b = candidates[i], candidates[j]
                # 水平中心距離
                cx_a = a[0] + a[2] / 2
                cx_b = b[0] + b[2] / 2
                dist = abs(cx_a - cx_b)
                if dist > TENSION_PAIR_MAX_DIST:
                    continue
                # 高度相近（差距在 40% 以內）
                h_ratio = min(a[3], b[3]) / max(a[3], b[3]) if max(a[3], b[3]) > 0 else 0
                if h_ratio < 0.5:
                    continue
                # 垂直對齊（Y 重疊）
                overlap = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                if overlap < min(a[3], b[3]) * 0.5:
                    continue
                if dist < best_dist:
                    best_dist = dist
                    best = (a, b)
        return best

    def _validate_tension_structure(self, frame: np.ndarray, ui: dict) -> bool:
        """
        驗證 UI 區域內部是否同時存在：
        - 左側進度條：暗色（近黑）背景
        - 右側拉力條：白色區塊
        """
        x, y, w, h = ui["ui_box"]
        x, y = max(x, 0), max(y, 0)
        x2 = min(x + w, frame.shape[1])
        y2 = min(y + h, frame.shape[0])
        region = frame[y:y2, x:x2]
        if region.size == 0:
            return False

        # 左側 1/3 應含有暗色像素（進度條背景）
        mid = region.shape[1] // 3
        left_region = region[:, :mid]
        dark_ratio = np.mean(np.all(left_region < 60, axis=2))
        if dark_ratio < 0.15:
            return False

        # 右側應含有白色像素（拉力條白區）
        right_region = region[:, mid:]
        hsv_r = cv2.cvtColor(right_region, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hsv_r,
                                 np.array([0, 0, 200], dtype=np.uint8),
                                 np.array([180, 40, 255], dtype=np.uint8))
        white_ratio = np.sum(white_mask > 0) / white_mask.size
        if white_ratio < 0.05:
            return False

        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # FINISH：偵測釣起魚 XP 浮字
    # ═══════════════════════════════════════════════════════════════════════════

    def detect_finish(self, frame: np.ndarray) -> bool:
        """
        偵測畫面出現黃綠色「+XP」浮字。
        只搜尋畫面中央區域（排除 HUD）。
        """
        # 搜尋中間 50% 的水平範圍，以及上半部的垂直範圍
        h, w = frame.shape[:2]
        roi = frame[int(h * 0.3):int(h * 0.7), int(w * 0.2):int(w * 0.8)]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lo = np.array(FINISH_YELLOW_HSV_LOW,  dtype=np.uint8)
        hi = np.array(FINISH_YELLOW_HSV_HIGH, dtype=np.uint8)
        mask = cv2.inRange(hsv, lo, hi)

        pixel_count = int(np.sum(mask > 0))
        if pixel_count >= FINISH_PIXEL_THRESH:
            log(f"[Detector] FINISH 偵測到黃綠浮字 pixels={pixel_count}")
            return True
        return False
