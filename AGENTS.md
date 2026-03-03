# VRC Fish Fishing

## 專案摘要

- Python 實作的 VRChat VRC Fish 自動釣魚程式。
- 基本流程：拋竿 → 等待咬鉤（提示音）→ 拉力計操作 → 回收魚獲。

## Skills 使用準則

Skill 文件位於 `.agents/skills/*/SKILL.md`。

- 遇到特定領域任務時，優先讀取對應 skill（例如 `uv-package-manager`、`python-pro`、`python-configuration`）。
- 進行該領域實作前，先吸收並遵循對應 skill 指引。

## 修改後檢查流程

請依序執行以下命令，確保品質與可執行性：

1. Auto Fix：`uv run ruff check --fix`
2. Format：`uv run ruff format`
3. Lint：`uv run ruff check`
4. Type Check：`uv run ty check`
5. Test：`uv run pytest`
6. Run CLI：`uv run python main.py`

補充：
- 先執行 Auto Fix 與 Format，可降低後續 Lint 雜訊。
- Type Check 與 Test 通過後，再執行 CLI 做最終行為確認。

## Agent Memory（`MEMORY.md`）

`MEMORY.md` 是本儲存庫 AI agents 的共享長期記憶索引。

### 強制執行流程（必須遵守）

1. 任務開始前：先讀取 `MEMORY.md`（必要時連同 `memory/*.md`）再進行分析或修改。
2. 任務完成前：檢查是否有可重用新知，必要時更新 `MEMORY.md` / `memory/*.md`。
3. 最終回覆前：確認已完成「讀取」與「更新檢查」，若無需更新需明確註記「No memory update needed」。
4. 若跳過上述流程，視為任務未完成，不可結案。

### 核心原則

- 規則與行為準則放在 `AGENTS.md`。
- 可重用的專案知識放在 `MEMORY.md`。
- 目標是減少重複探索（命令、架構、常見陷阱）。

### 檔案位置

- 主檔：根目錄 `MEMORY.md`
- 延伸主題：`memory/*.md`（例如 `memory/debugging.md`）
- `MEMORY.md` 維持精簡索引；長內容放在 `memory/*.md` 並連結。

### `MEMORY.md` 建議結構

- `## Quick Facts`：高價值事實與限制
- `## Commands`：已驗證的執行／測試／建置命令
- `## Architecture Notes`：關鍵模組關係與職責
- `## Pitfalls`：常見問題與可重現解法
- `## Decisions`：重要取捨與理由
- `## Last Updated`：日期與最新有效變更摘要

### 維護規則

- 進行重大變更前，先閱讀 `MEMORY.md`。
- AI agent 必須主動維護 `MEMORY.md`。
- 只記錄「可重用、跨任務仍有價值」的資訊。
- 優先使用精簡條列，避免任務流水帳。
- 新資訊加入時，同步清理或改寫過時內容。
- 重要項目放前面，便於快速檢索。
- 禁止記錄任何機敏資訊（secrets、token、個資、機器私有路徑）。

### 何時更新記憶

- 每次任務完成前，AI agent 應主動檢查是否需更新 `MEMORY.md`。
- 新增／更新已驗證的 workflow 或命令。
- 發現能穩定復用的除錯技巧。
- 確認會影響後續工作的架構限制。
- 找到可重現且有明確緩解方式的失敗模式。

### 品質標準

- 內容需具體、可執行，且限於本專案範圍。
- 避免空泛描述與一次性資訊。
- 以「未來 agent 可直接採用」為撰寫標準。
