# MEMORY.md - VRC Fish Fishing Bot

## Quick Facts
- Python 3.14 venv 位於 `.venv/`，執行用 `d:/VRCFishFishing/.venv/Scripts/python.exe`
- 參考解析度 1366×768（sample_images 的截圖尺寸），所有 ROI 座標以此為基準
- 咬勾音效參考錄音放置於 `assets/bite_sound.wav`（使用者提供，WAV 16-bit 44100Hz）
- 模板匹配用的「!」圖示模板放置於 `assets/exclaim_templates/`

## Commands
```
# 執行 bot
d:/VRCFishFishing/.venv/Scripts/python.exe main.py

# 安裝依賴
pip install opencv-python numpy mss sounddevice scipy pywin32 pydirectinput
```

## Architecture Notes
- 狀態機：IDLE → WAITING → TENSION → FINISH → IDLE
- `main.py`：主迴圈與狀態切換
- `config.py`：所有可調參數集中管理
- `screen_capture.py`：`mss` 截圖 + `win32gui` 視窗定位 + 解析度縮放
- `state_detector.py`：`detect_exclaim` / `detect_tension_ui` / `detect_finish`
- `tension_handler.py`：分析進度條比例 + 白區/魚位置 → 按鍵決策
- `audio_detector.py`：背景執行緒監聽系統音訊（sounddevice loopback）
- `input_handler.py`：`win32api.mouse_event` 模擬左鍵（避免 VRChat Raw Input 攔截）
- `utils.py`：log、DebugOverlay（OpenCV 視窗）、Stats

## Pitfalls
- VRChat 使用 Raw Input，必須用 `win32api.mouse_event` 而非 `pyautogui.click`
- 拉力計 UI 位置隨鏡頭角度動態變化，不可用固定 ROI，需每幀全畫面掃描藍色外框
- UI 完全消失（鏡頭角度過大）時直接放棄本次，回 IDLE 重試，不做鏡頭移動
- sounddevice loopback 需要 WASAPI，在 Windows 上搜尋名稱含 "loopback" 的裝置
- `screen_capture.py` 的視窗邊框估算值（border=8, title_h=30）可能需依實際視窗微調
- 咬勾音效樣本過短（~0.1s）時，NCC 峰值易在 0.2~0.3 區間漂移；僅降 `BITE_CORR_THRESHOLD` 會提高誤判，需搭配「峰值-次峰 margin」與「連續命中」條件

## Decisions
- 音訊指紋（互相關）為主，視覺「!」偵測為輔，任一觸發即算咬勾
- 拉力計控制用位置控制（非 PID）：以死區避免頻繁切換
- FINISH 偵測用黃綠色浮字像素計數，不使用 OCR（速度考量）

## Last Updated
2026-03-02 - 音訊匹配穩定化：新增 `BITE_CORR_MARGIN`、`BITE_CORR_HIT_STREAK`，互相關加入次峰抑制與連續命中機制
