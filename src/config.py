# config.py - 全域設定檔
# 所有可調整的參數集中在此，實測後微調

import os

# ── 視窗 ─────────────────────────────────────────────────────────────────────
WINDOW_TITLE = "VRChat"          # win32gui 搜尋用的視窗標題子字串
TARGET_WIDTH  = 1366             # 參考解析度寬（sample_images 的截圖尺寸）
TARGET_HEIGHT = 768              # 參考解析度高

# ── 狀態機迴圈間隔（秒）────────────────────────────────────────────────────────
LOOP_INTERVAL = {
    "IDLE":    0.20,
    "WAITING": 0.004,   # ~240fps, 等待狀態需要盡快偵測咬勾聲音
    "TENSION": 0.016,   # ~60fps
    "FINISH":  0.20,
}

# ── IDLE ──────────────────────────────────────────────────────────────────────
CAST_DELAY_MIN = 0.4             # 拋竿前最小隨機延遲（秒）
CAST_DELAY_MAX = 0.7             # 拋竿前最大隨機延遲（秒）

# ── WAITING ───────────────────────────────────────────────────────────────────
WAIT_TIMEOUT        = 60.0       # 等待咬勾上限（秒），超過後重新拋竿
BITE_REACT_MIN      = 0.05       # 咬勾後點擊前最小隨機延遲（秒）
BITE_REACT_MAX      = 0.12       # 咬勾後點擊前最大隨機延遲（秒）

# 視覺：「!」偵測
EXCLAIM_TEMPLATE_DIR = os.path.join("assets", "exclaim_templates")  # 存放多尺寸模板
EXCLAIM_MATCH_THRESH = 0.72      # matchTemplate 相似度閾值

# 「!」的藍紫色外框顏色範圍（HSV）
EXCLAIM_HSV_LOW  = (110, 100, 150)
EXCLAIM_HSV_HIGH = (145, 255, 255)

# 差分偵測：中央區域中超過閾值的高亮素數（十公尺為單位）
EXCLAIM_DIFF_THRESH = 120

# 音訊
AUDIO_SAMPLE_RATE   = 44100      # Hz
AUDIO_CHUNK_SIZE    = 4096       # 每次讀取的樣本數（~46ms @ 44100Hz）
AUDIO_CHANNELS      = 1
BITE_SOUND_PATH     = os.path.join("assets", "bite_sound_200ms.wav")
# 互相關容許值（越低越寬鬆、越容易觸發；越高越嚴格）
# 建議調校範圍：0.25 ~ 0.55
BITE_CORR_THRESHOLD = 0.25
# 峰值與次峰的最小差距（避免短音效在背景聲中誤觸）
BITE_CORR_MARGIN = 0.05
# 需連續命中幾次才觸發（降低偶發誤判）
BITE_CORR_HIT_STREAK = 2
AUDIO_COOLDOWN      = 2        # 觸發後冷卻時間（秒）


AUDIO_DEBUG_CORR = True          # 是否在每次分析時輸出互相關峰值（用於調整 BITE_CORR_THRESHOLD）
# 音訊除錯：連續顯示目前監聽裝置的 RMS（用於確認裝置是否有聲音）
AUDIO_DEBUG_RMS = False
AUDIO_DEBUG_RMS_INTERVAL = 0.1   # 秒

# RMS 備援方案（無錄音檔時啟用）
BITE_RMS_MULTIPLIER = 100        # 超過靜默基準的倍數才觸發
BITE_RMS_BANDPASS   = (800, 4000) # bandpass 頻率範圍（Hz）

# ── TENSION ───────────────────────────────────────────────────────────────────
# 藍色霓虹外框顏色範圍（HSV）
TENSION_BLUE_HSV_LOW  = (100, 130, 130)
TENSION_BLUE_HSV_HIGH = (135, 255, 255)

# 拉力計 UI 幾何特徵
TENSION_BAR_ASPECT_MIN = 3.0     # 長寬比最小值（高/寬）
TENSION_BAR_ASPECT_MAX = 10.0    # 長寬比最大值
TENSION_BAR_AREA_MIN   = 400     # 輪廓面積最小值（像素）
TENSION_BAR_AREA_MAX   = 8000    # 輪廓面積最大值
TENSION_PAIR_MAX_DIST  = 80      # 兩條 bar 水平距離上限（像素）

# UI 消失判定：連續 N 幀找不到藍框即視為 TENSION 結束
TENSION_DISAPPEAR_FRAMES = 10

# 進度條（左側）：綠色像素偵測範圍（HSV）
PROGRESS_GREEN_HSV_LOW  = (40, 80, 80)
PROGRESS_GREEN_HSV_HIGH = (90, 255, 255)
PROGRESS_SUCCESS_RATIO  = 0.88   # 綠色填充比例超過此值 → 成功
PROGRESS_FAIL_RATIO     = 0.04   # 綠色填充比例低於此值 → 失敗

# 拉力條（右側）：白色區域偵測（HSV）
WHITE_HSV_LOW  = (0, 0, 200)
WHITE_HSV_HIGH = (180, 40, 255)

# 魚圖示偵測（非白色、非黑色的飽和色塊）
FISH_SAT_MIN = 80                # 最小飽和度
FISH_VAL_MIN = 80                # 最小明度
FISH_AREA_MIN = 30               # 最小面積（像素）
FISH_AREA_MAX = 600              # 最大面積（像素）

# 拉力控制死區：誤差在此範圍內不改變按鍵狀態
TENSION_DEAD_ZONE = 8            # 像素

# ── FINISH ────────────────────────────────────────────────────────────────────
# 黃綠色 XP 浮字偵測（HSV）
FINISH_YELLOW_HSV_LOW  = (25, 150, 180)
FINISH_YELLOW_HSV_HIGH = (65, 255, 255)
FINISH_PIXEL_THRESH    = 200     # 偵測到超過此數量的黃綠像素即判定 FINISH

FINISH_WAIT = 1.5                # 釣起魚後等待時間（秒）再按左鍵

# ── Debug ─────────────────────────────────────────────────────────────────────
DEBUG_OVERLAY   = True           # 是否顯示 OpenCV debug 視窗
DEBUG_LOG       = True           # 是否輸出 log
DEBUG_SAVE_FRAMES = False        # 是否儲存每幀截圖（會產生大量檔案）
DEBUG_FRAME_DIR = "debug_frames"
