# main.py - 主程式入口，狀態機迴圈
#
# 執行方式：
#   python main.py
#
# 快捷鍵（需 debug overlay 視窗在前台）：
#   q  → 安全退出
#   p  → 暫停 / 繼續

import time
import random
import sys

from src.screen_capture import ScreenCapture
from src.state_detector  import StateDetector
from src.tension_handler import TensionHandler, TensionResult
from src.audio_detector  import AudioDetector
from src.input_handler   import InputHandler
from src.utils           import log, DebugOverlay, Stats
from src.config          import (
    LOOP_INTERVAL,
    CAST_DELAY_MIN, CAST_DELAY_MAX,
    WAIT_TIMEOUT,
    BITE_REACT_MIN, BITE_REACT_MAX,
    TENSION_DISAPPEAR_FRAMES,
    FINISH_WAIT,
    DEBUG_OVERLAY,
)


# ── 狀態常數 ──────────────────────────────────────────────────────────────────

class State:
    IDLE    = "IDLE"
    WAITING = "WAITING"
    TENSION = "TENSION"
    FINISH  = "FINISH"


# ── 主類別 ────────────────────────────────────────────────────────────────────

class FishingBot:

    def __init__(self):
        log("[Bot] 初始化中...")
        self.capture  = ScreenCapture()
        self.detector = StateDetector()
        self.tension  = TensionHandler()
        self.audio    = AudioDetector()
        self.input    = InputHandler()
        self.stats    = Stats()
        self.state    = State.IDLE
        self._paused  = False
        self._running = True
        self._tension_miss_frames = 0  # 連續找不到拉力計的幀數
        self._last_ui_info: dict | None = None  # 供 debug overlay 使用

        if not self.capture.win_rect:
            log("[Bot] ⚠  找不到 VRChat 視窗，請確認遊戲已開啟，程式將持續嘗試...")

        # 啟動音訊監聽（在整個生命週期內持續運行）
        self.audio.start()
        log("[Bot] 初始化完成，狀態機啟動")

    # ── 主迴圈 ────────────────────────────────────────────────────────────────

    def run(self):
        try:
            while self._running:
                # 暫停檢查
                if self._paused:
                    time.sleep(0.1)
                    continue

                # 截圖
                frame = self.capture.grab_window()
                if frame is None:
                    self.capture.refresh_window()
                    time.sleep(0.5)
                    continue

                # 縮放至 TARGET 解析度
                frame_t = ScreenCapture.resize_to_target(frame)

                # 執行當前狀態處理
                if   self.state == State.IDLE:    self._handle_idle(frame_t)
                elif self.state == State.WAITING:  self._handle_waiting(frame_t)
                elif self.state == State.TENSION:  self._handle_tension(frame_t)
                elif self.state == State.FINISH:   self._handle_finish(frame_t)

                # Debug overlay（WAITING / FINISH 的內部迴圈自行處理，TENSION 透過 _last_ui_info 傳遞）
                if self.state not in (State.WAITING, State.FINISH):
                    DebugOverlay.show(frame_t, self.state, ui_info=self._last_ui_info)
                    if DEBUG_OVERLAY:
                        if DebugOverlay.is_quit_pressed():
                            log("[Bot] 使用者按下 q，退出")
                            break
                        if DebugOverlay.is_pause_pressed():
                            self._paused = not self._paused
                            log(f"[Bot] {'暫停' if self._paused else '繼續'}")

                time.sleep(LOOP_INTERVAL[self.state])

        except KeyboardInterrupt:
            log("[Bot] 收到 Ctrl+C，退出")
        finally:
            self._cleanup()

    # ── IDLE ──────────────────────────────────────────────────────────────────

    def _handle_idle(self, frame):
        """
        IDLE：按下左鍵拋竿，等待短暫延遲後轉入 WAITING。
        加入隨機延遲模擬人類行為。
        """
        delay = random.uniform(CAST_DELAY_MIN, CAST_DELAY_MAX)
        log(f"[IDLE] 準備拋竿，延遲 {delay:.2f}s")
        time.sleep(delay)

        self.input.lmb_click(delay=0.06)
        self.stats.casts += 1
        log(f"[IDLE] 拋竿完成 (第 {self.stats.casts} 次)")

        # 重置音訊觸發旗標、差分基準幀、UI 快取
        self.audio.clear()
        self.detector.reset_diff()
        self._last_ui_info = None
        self._transition(State.WAITING)

    # ── WAITING ───────────────────────────────────────────────────────────────

    def _handle_waiting(self, frame):
        """
        WAITING：等待咬勾。
        音訊偵測（主）或視覺「!」偵測（輔）任一觸發即點擊。
        超過 WAIT_TIMEOUT 秒未咬勾則重新拋竿。
        """
        timeout_end = time.time() + WAIT_TIMEOUT
        log(f"[WAITING] 開始等待咬勾（上限 {WAIT_TIMEOUT}s）")

        while self._running:
            # 暫停中只等待
            if self._paused:
                time.sleep(0.1)
                continue

            # 音訊偵測（非阻塞查詢）
            if self.audio.triggered.is_set():
                self._on_bite()
                return

            # 視覺偵測
            # frame = self.capture.grab_window()
            # if frame is not None:
            #     frame_t = ScreenCapture.resize_to_target(frame)
            #     if self.detector.detect_exclaim(frame_t):
            #         log("[WAITING] 視覺「!」觸發")
            #         self._on_bite()
            #         return
            #     DebugOverlay.show(frame_t, self.state)
            #     if DEBUG_OVERLAY:
            #         if DebugOverlay.is_quit_pressed():
            #             self._running = False
            #             return
            #         if DebugOverlay.is_pause_pressed():
            #             self._paused = not self._paused
            #             log(f"[Bot] {'暫停' if self._paused else '繼續'}")

            # 超時
            if time.time() >= timeout_end:
                log("[WAITING] 超時未咬勾，重新拋竿")
                self._transition(State.IDLE)
                return

            time.sleep(LOOP_INTERVAL["WAITING"])

    def _on_bite(self):
        """咬勾後加入隨機延遲再點擊，模擬人類反應。"""
        react = random.uniform(BITE_REACT_MIN, BITE_REACT_MAX)
        time.sleep(react)
        self.input.lmb_click(delay=0.06)
        self.stats.bites += 1
        self.audio.clear()
        log(f"[WAITING] 咬勾！點擊完成 (第 {self.stats.bites} 次)")
        self._tension_miss_frames = 0
        self._transition(State.TENSION)

    # ── TENSION ───────────────────────────────────────────────────────────────

    def _handle_tension(self, frame):
        """
        TENSION：每幀分析拉力計並控制左鍵。
        進度條滿 → FINISH；進度條空 → IDLE；UI 長時間消失 → IDLE。
        """
        ui_info = self.detector.detect_tension_ui(frame)

        if ui_info is None:
            self._tension_miss_frames += 1
            log(f"[TENSION] 找不到 UI ({self._tension_miss_frames}/{TENSION_DISAPPEAR_FRAMES})")
            if self._tension_miss_frames >= TENSION_DISAPPEAR_FRAMES:
                log("[TENSION] UI 持續消失，放棄本次釣魚")
                self.input.lmb_release()
                self.stats.failures += 1
                self._transition(State.IDLE)
            return
        else:
            self._tension_miss_frames = 0

        result, should_press = self.tension.analyze(frame, ui_info)
        self._last_ui_info = ui_info  # 供主迴圈 DebugOverlay 使用

        # 執行按鍵決策
        if should_press:
            self.input.lmb_press()
        else:
            self.input.lmb_release()

        if result == TensionResult.SUCCESS:
            log("[TENSION] 進度條滿！釣魚成功")
            self.input.lmb_release()
            self.stats.successes += 1
            self._transition(State.FINISH)

        elif result == TensionResult.FAIL:
            log("[TENSION] 進度條清空，失敗")
            self.input.lmb_release()
            self.stats.failures += 1
            self._transition(State.IDLE)

    # ── FINISH ────────────────────────────────────────────────────────────────

    def _handle_finish(self, frame):
        """
        FINISH：等待 XP 浮字出現確認成功，
        然後稍等後按左鍵結束，回到 IDLE。
        """
        log(f"[FINISH] 等待 {FINISH_WAIT}s 後繼續...")
        deadline = time.time() + FINISH_WAIT + 1.0

        while time.time() < deadline:
            if self._paused:
                time.sleep(0.1)
                continue
            f = self.capture.grab_window()
            if f is not None:
                ft = ScreenCapture.resize_to_target(f)
                DebugOverlay.show(ft, self.state)
                if DEBUG_OVERLAY:
                    if DebugOverlay.is_quit_pressed():
                        self._running = False
                        return
                    if DebugOverlay.is_pause_pressed():
                        self._paused = not self._paused
                        log(f"[Bot] {'暫停' if self._paused else '繼續'}")
            time.sleep(LOOP_INTERVAL["FINISH"])

        self.input.lmb_click(delay=0.06)
        log(f"[FINISH] 完成。{self.stats.report()}")
        self._transition(State.IDLE)

    # ── 工具 ──────────────────────────────────────────────────────────────────

    def _transition(self, new_state: str):
        log(f"[Bot] 狀態切換：{self.state} → {new_state}")
        self.state = new_state

    def _cleanup(self):
        log("[Bot] 清理資源...")
        self.input.release_all()
        self.audio.stop()
        DebugOverlay.close()
        log(f"[Bot] 結束。{self.stats.report()}")


# ── 入口 ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  VRC Fish Fishing Bot")
    print("  Ctrl+C 或 debug 視窗按 q 退出")
    print("=" * 50)
    bot = FishingBot()
    bot.run()
