# Validation scope｜驗證範圍

## Public test suites｜公開測試套件

```text
python -X utf8 -B -m unittest discover -s tests -v
```

| Suite | English | 繁體中文 |
| --- | --- | --- |
| 18 installer tests | Dry-run, real isolated installation, idempotence, SHA256 backups, preservation, restore, later-edit protection, corruption rejection, readonly status. | dry-run、真實隔離安裝、重跑不重複、SHA256 備份、保留設定、還原、後續改動保護、毀損拒絕與唯讀狀態。 |
| 13 state tests | Exact roundtrip matching, CRLF handling, project binding, duplicate-send guards, rejection of pending/old/incomplete turns. | 完整往返比對、CRLF 處理、專案綁定、重複傳送防護及 pending／舊回合／不完整請求拒絕。 |

The 31 tests passed on Windows for v0.1.0; the runtime code and test suites are unchanged in v0.1.1. The retained log in [test-results.txt](test-results.txt) identifies that baseline. The bilingual release additionally checks Markdown links, packaging, and file integrity. No ChatGPT calls are made by these tests.<br>
31 項測試於 Windows 的 v0.1.0 通過；v0.1.1 未變更執行程式及測試套件。[test-results.txt](test-results.txt) 保留並標明該基準版本。中英文件版另檢查 Markdown 連結、打包及檔案完整性。這些測試不呼叫 ChatGPT。

## Earlier integration evidence｜既有整合實測

The maintainer verified a native send/read roundtrip on Windows MSI with Codex Desktop 0.154.0-alpha.6.2, confirmed the 6 Pro UI selection, implemented and tested Pro's advice locally, and loaded the user-scope Skill in three projects. Tool and account availability may differ by version.<br>
維護者曾於 Windows MSI、Codex Desktop 0.154.0-alpha.6.2 完成原生 send/read 往返、6 Pro 介面確認、採用建議後的本地修正與測試，並於三個專案載入使用者範圍 Skill。工具與帳號可用性可能因版本而異。

The 18 installer tests also originated from a run in a ChatGPT Linux cloud sandbox with Python 3.13.5. That verifies Python installer behavior, not a Linux Codex native-chat integration.<br>
18 項安裝測試亦源於 ChatGPT Linux 雲端沙箱、Python 3.13.5 的實測。此結果驗證 Python 安裝行為，不代表 Linux Codex 原生對話整合已驗收。

## Not verified｜尚未驗證

- Other users, new computers, and macOS native integration. / 其他使用者、新電腦及 macOS 的原生整合。
- Actual Python 3.10 minimum-version runtime. / Python 3.10 最低版本實際執行。
- Tool availability in arbitrary CLI/IDE clients. / 任意 CLI／IDE 的工具可用性。
- Independent backend model identity, token savings, or quota savings. / 後端模型身分的獨立驗證、token 或額度節省幅度。

Private Chat links and original receipts are not public. Each user must verify a non-sensitive roundtrip in their own environment.<br>
私人 Chat 連結與原始收據不公開。每位使用者須於自己的環境驗證一次無機密往返。
