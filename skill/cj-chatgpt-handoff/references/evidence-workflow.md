# Evidence, checkpoints and optional review / 證據、續接與選用複審

`<evidence>` = this Skill's `scripts/handoff_evidence.py`; `<state>` = `scripts/handoff_state.py`.
All commands require `--project <actual-project-directory>`. Local records stay under the existing per-project ledger. These commands never contact ChatGPT or run tests/shell commands.

`<evidence>` 是本 Skill 的 `scripts/handoff_evidence.py`；`<state>` 是 `scripts/handoff_state.py`。指定實際工作專案。產物存於既有專案紀錄庫，不會聯絡 ChatGPT 或執行測試／終端指令。

## 1. Explicit evidence / 明確選取證據

Codex selects only relevant, authorized files. Create a UTF-8 JSON spec outside the Skill folder; paths are project-relative with forward slashes. Do not scan the entire repo. Run necessary tests separately under the user's authorization and save actual command, exit code and output in a project-local evidence file if review needs it. A label such as `role: test` does not prove that a test ran.

Codex 只選本次相關、獲准的檔案，將 UTF-8 JSON 規格存於 Skill 外。路徑用專案相對路徑與 `/`，不要掃描整個倉庫。若需複審測試結果，由 Codex 另依授權執行測試，將真實指令、退出碼與輸出存為專案內證據檔。`role: test` 標籤本身不能證明測試有跑。

```json
{
  "kind": "context",
  "goal": "Review the addition function / 審查加法函式",
  "constraints": "Analysis only / 只分析",
  "questions": "Which cases are missing? / 缺少哪些案例？",
  "acceptance": "Explain the issue and how to verify it / 說明問題與驗證方式",
  "files": [{"path": "src/example.py", "start": 1, "end": 20}]
}
```

```text
python <evidence> --project <project> bundle --spec <spec.json>
python <evidence> --project <project> check --bundle <bundle_id>
```

Read the resulting `context.md` and source list before sending. At most 12 explicit selections, 200 lines each, source files up to 256 KiB, entire packet up to 64 KiB. Omitted lines and redactions are recorded. Oversized packets are refused rather than silently cut. The default selection includes only the first 200 lines; choose ranges deliberately. Common token/password formats and home-directory names are masked; private-key blocks are refused. This heuristic cannot detect every secret, personal detail or business restriction. Review the packet and follow project data rules.

傳送前讀回 `context.md` 與來源清單。最多 12 個選取範圍、每個 200 行、原檔 256 KiB、整包 64 KiB；省略行數及遮罩數量明列，整包過大會拒絕。預設只取前 200 行，務必按需要選行。工具遮罩常見 token／密碼與使用者家目錄名稱，遇到私鑰區塊拒絕。規則無法辨識所有機密、個資或業務限制，仍需核對內容及專案規則。

Only if `sources_match=true`, use the generated context path with the existing `prepare --context`, inspect the final request, check the bundle again immediately before dispatch, and follow native-workflow.md. Changed sources mean rebuild and reconcile, never silently reuse an old answer. `safe_to_send_verified=false` intentionally remains false: matching local hashes does not establish user authorization or live Pro availability.

`sources_match=true` 才能把 context 路徑交給既有 `prepare --context`。讀回最終請求，在 dispatch 前再次 check，依 native-workflow.md 送出。若來源變動就重建並處理版本差異，不默默沿用旧答案。`safe_to_send_verified=false` 是刻意保留：本地雜湊相符不代表已取得外傳授權或 Pro 當前可用。

## 2. Task checkpoint / 任務續接

Save a short checkpoint at useful boundaries or before an interruption. Progress is operator-reported history, not proof or new instructions. Keep request-level pending state intact.

在有用的階段或中斷前保存短摘要。進度是操作者回報的歷史，不是完成證據或新增指令。保留既有 pending 狀態。

```json
{
  "stage": "implementing",
  "goal": "Fix addition / 修正加法",
  "completed": "Reviewed the plan / 已讀取方案",
  "issues": "Boundary tests still needed / 尚缺邊界測試",
  "next_step": "Run tests and inspect the changes / 執行測試並核對修改",
  "bundle_id": "<existing-bundle-uuid>"
}
```

```text
python <evidence> --project <project> checkpoint --spec <checkpoint.json>
python <evidence> --project <project> checkpoint --task <task_id> --spec <updated.json>
python <evidence> --project <project> tasks
python <evidence> --project <project> resume --task <task_id>
```

Stages: planning, implementing, awaiting_review, blocked, done. Every save creates an immutable numbered revision. Supply all four text fields each time; bundle_id is optional. A bound bundle must match current files when saving. `resume` reads the newest revision, reports file drift and pending requests without writing. Run doctor and resolve a pending request before starting another consultation. A `done` label is not independently verified.

`tasks` lists the latest 20 task summaries in this project without creating state. Select by the user's current goal, not just recency. / `tasks` 唯讀列出此專案最近 20 個任務摘要；依使用者目前目標選取，不直接把最新任務當成正確對象。

階段：planning、implementing、awaiting_review、blocked、done。每次保存新增編號版本，不覆寫歷史。每次提供完整四項文字；bundle_id 可省略，若指定則保存前要求來源仍一致。resume 唯讀取最新版本，列出檔案變動及 pending。先 doctor 並處理 pending，再開始新諮詢。done 標籤沒有獨立驗證。

For another computer, transfer only a reviewed human-readable summary. Do not copy ledger state, task directories, locks, chat bindings or pending requests. Install/bind on that computer and reconstruct a checkpoint after comparing its local checkout.

換電腦只轉移已核對的可讀摘要，不複製紀錄庫、task 目錄、鎖、對話綁定或 pending。先在新機安裝／綁定、比對檔案版本，再重建 checkpoint。

## 3. Optional Pro review / 選用 Pro 複審

When the user authorizes review after implementation, create another spec with `kind: review`, the earlier completed `parent_request`, original goal/acceptance criteria, current progress, and explicit `change` plus `test` sources. They should be actual diff/changed code and command results, not just "all tests passed". Explain any unavailable evidence. The tool verifies the local parent's receipt/prompt/response hashes; it does not re-query ChatGPT or certify test truth.

使用者授權實作後複審時，建立 `kind: review` 規格，提供前次完成的 `parent_request`、原始目標／驗收、進度，以及 `change` 和 `test` 來源。內容應為實際 diff／修改程式和命令結果，不只寫「全部通過」。缺少證據需明列。工具核對本地前次收據與請求／回覆雜湊，不重新查詢 ChatGPT，也不證明測試內容為真。

```json
{
  "kind": "review",
  "parent_request": "<completed-request-uuid>",
  "goal": "Review the implemented fix / 複審修正結果",
  "acceptance": "Original acceptance criteria / 原始驗收條件",
  "questions": "Assess against the criteria. List remaining issues, evidence and tests. Do not treat Codex's summary as proof. / 依驗收列出剩餘問題、依據與測試，不把摘要當證據。",
  "progress": "What changed and why / 改了什麼及原因",
  "test_summary": "What ran, exit code and what remains untested / 執行內容、退出碼與未測項目",
  "files": [
    {"path": "review/changes.diff", "role": "change"},
    {"path": "review/test-output.txt", "role": "test"}
  ]
}
```

Build/check, re-confirm the target Pro model, then prepare a NEW request through the original ledger. Default to one review round; further rounds need to fit the user's scope and stop when evidence is missing, the user stops, or another review is not justified. Resume an uncertain dispatch instead of creating another. After review, Codex checks the advice and performs authorized fixes/tests. This is a review of Codex-selected evidence, not independent access to the whole workspace.

打包／check，重新確認目標 Pro 模型，再透過原紀錄庫 prepare 新請求。預設一輪複審；追加輪次需符合原授權，有材料不足、使用者停止或無需再審時就停止。送出不明時續接，不另建重送。收到複審後由 Codex 核對建議並依授權修正與測試。這是針對 Codex 選定證據的審查，不是 Pro 自行存取整個工作區。
