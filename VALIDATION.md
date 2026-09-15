# 驗證範圍

## 公開版測試

執行方式：`python -X utf8 -B -m unittest discover -s tests -v`。

- 18 項隔離安裝測試：dry-run、真實寫入、重跑不重複、SHA256 備份、保留既有規則和模型設定、還原、後續修改保護、毀損套件／備份拒絕、readonly status。
- 13 項狀態腳本測試：完整往返比對、CRLF 相容、跨專案綁定防護、重複傳送攔截、pending／舊回合／不完整請求拒絕等。
- 發布前另核對 ZIP 解壓、完整性清單及私人資料排除。

實際公開版測試結果見 [test-results.txt](test-results.txt)。這些測試不呼叫 ChatGPT，不消耗 Pro 對話額度。

## 來源版本已有實測

維護者曾在 Windows MSI、Codex Desktop 0.154.0-alpha.6.2 完成原生 send/read 往返、6 Pro 介面確認、Pro 建議後的本地修正／測試，以及三個專案的使用者範圍 Skill 載入。原生工具與帳號可用性可能因版本而異。公開版保留同一核心 Skill 與安裝器。

ChatGPT 雲端 Linux／Python 3.13.5 曾執行本套件安裝器的 18 項隔離測試；此測試來源納入公開版。雲端 Python 測試不代表 Linux Codex 原生工具已完成整合。

## 尚未涵蓋

- 其他使用者帳號、新電腦與 macOS 上的真實 Codex ↔ ChatGPT 整合。
- Python 3.10 最低版本實際執行；請以本機環境重新測試。
- 任意 CLI／IDE 的工具可用性。
- 後端模型身分的獨立驗證、token 或額度節省幅度。

不公開私人 Chat 網址或原始收據。新使用者須自行完成 README 的一次無機密往返驗收。
