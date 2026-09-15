# Local handoff diagnosis / 本地交接自檢

Local pilot: `0.1.2-local.1`. Not included in the published v0.1.1 ZIP.

本地試行版本：`0.1.2-local.1`，公開的 v0.1.1 ZIP 尚未包含此功能。

Ask Codex / 在 Codex 輸入：

> $cj-chatgpt-handoff 請做交接自檢，告訴我下一步，先不要傳送 Pro。

Or run the installed script / 或執行已安裝的腳本：

```text
python -X utf8 <skill-directory>/scripts/handoff_state.py --project <project-directory> doctor
```

The command reads only the specified project's local evidence and the shared lock's existence. It never creates a ledger, sends a message, deletes locks, or resets pending requests. Its output omits private chat IDs, paths and prompt/response contents.

指令只讀指定專案的本地證據及共用鎖是否存在；不建立紀錄庫、不傳送、不刪鎖、不清除待處理請求。輸出不包含私人對話 ID、路徑或請求／回覆原文。

| Code | Next step | 下一步 |
| --- | --- | --- |
| SETUP_REQUIRED | Check native tools and bind a dedicated Pro Chat. | 確認原生工具，綁定專用 Pro 對話。 |
| MODEL_CHECK_REQUIRED | Check the current model before a new request. | 下次傳送前確認目前模型。 |
| PREPARED | Resume the existing prepared request after live checks. | 完成即時確認後，續接已準備的請求。 |
| CHECK_REMOTE | Read the bound Chat; match the full prompt. Never blindly resend. | 查對話並比對完整請求，不盲目重送。 |
| PROMPT_CHANGED | Stop sending and inspect original evidence. | 停止傳送，檢查原始證據。 |
| FINALIZE_LOCAL | Resume complete to finish the interrupted local bookkeeping. | 續接 complete，完成中斷的本地記帳。 |
| LOCAL_STATE_ERROR | Inspect missing/corrupt evidence and verified backups. | 檢查缺失／損壞證據及已核對備份。 |
| LOCK_PRESENT | Inspect the owner/process before any writes. | 任何寫入前先檢查持有鎖的程序。 |

`status` is the first finding; inspect all entries in `checks`. CLI exit 0 means a diagnosis was produced, not that sending is safe. `ready_to_send` remains false: this command cannot verify native tool availability, live model selection, or remote completion. Local diagnostics are a point-in-time snapshot and cannot prevent concurrent changes.

`status` 是第一項發現，請閱讀全部 `checks`。退出碼 0 只表示成功產出診斷，不代表能傳送。`ready_to_send` 固定為 false：此工具無法驗證原生工具、當前模型或遠端完成狀態。本地診斷是當下快照，不能阻止其他程序同時修改。
