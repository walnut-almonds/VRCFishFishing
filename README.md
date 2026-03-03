# VRC Fish Fishing

一個用 Python 實作的 VRChat 自動釣魚腳本。

## ⚠️ 開發狀態

目前還在早期開發階段，因為是半成品所以可能無法正常運作，有相當多的錯誤等著解決

## 環境需求
- Windows
- Python 3.14+
- VRChat 視窗標題可被偵測（預設：`VRChat`）

## 安裝
```bash
pip install -r requirements.txt
```
或者
```bash
uv sync
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

## 📝 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## ⚖️ 免責聲明

本工具僅供學習和研究使用。使用本工具可能違反遊戲的服務條款，請自行承擔使用風險。作者不對因使用本工具而導致的任何後果負責。