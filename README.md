# VRC Fish Fishing

一個用 Python 實作的 VRChat 自動釣魚腳本。
流程：拋竿 → 等咬勾（音訊/視覺）→ 拉力控制 → 收竿。

## 環境需求
- Windows
- Python 3.14+
- VRChat 視窗標題可被偵測（預設：`VRChat`）

## 安裝
這裡預計會整理成 toml 檔，很急著用的話先使用
```bash
pip install opencv-python numpy mss sounddevice scipy pywin32 pydirectinput
```

## 使用方式
1. 確認音效樣本存在：`assets/bite_sound_200ms.wav`
2. 啟動 VRChat 並進入可釣魚地圖
3. 執行：
```bash
python main.py
```

## 主要設定
請在 `config.py` 調整：
- `WINDOW_TITLE`：視窗名稱
- `WAIT_TIMEOUT`：等待咬勾秒數
- `BITE_CORR_THRESHOLD`：咬勾音觸發閾值
- `DEBUG_OVERLAY`：是否顯示除錯視窗

## 快捷鍵（除錯視窗）
- `q`：退出
- `p`：暫停 / 繼續

---
僅供學習與研究用途，請自行承擔使用風險。