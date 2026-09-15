# 原生轉交操作

以下命令用目前可用的 Python；不安裝依賴。`<script>` 是本 Skill 內 `scripts/handoff_state.py` 的絕對路徑。`<project>` 是當前專案已解析的絕對路徑。所有 JSON／Markdown 用 UTF-8。

## 1. 檢查與綁定

```text
python <script> --project <project> status
python <script> --project <project> bind --thread <ChatGPT對話UUID> --evidence-kind ui --evidence "本次在該對話的選擇器看見 6 Pro"
```

無法讀取 UI 而由使用者確認時，使用 `--evidence-kind user_confirmed`，evidence 寫明本次確認內容與來源。只有親自觀察的設定才能記為 ui。腳本不替你驗證 UI、使用者授權或遠端身分，這些由操作代理先完成。綁定需先確認 `read_thread` 的 kind 為 chatgpt，且對話用途吻合；腳本拒絕跨專案共用同一對話。

## 2. 準備

先 `read_thread`，確認目標閒置並取得最新一頁回合 ID；把工具回傳的 JSON 存成 `before.json`（可用 structuredContent，或解析 content 裡的 JSON 文字）。準備 `context.md`，只包含獲准傳送的必要背景。檔案可以放在 status 所列專案紀錄目錄下的 `drafts/`；不覆蓋現有檔案。

```text
python <script> --project <project> prepare --source-thread <目前Codex任務UUID> --context <context.md> --before <before.json>
```

腳本輸出 request_id、request.md 路徑，將必要背景加上唯一 request_id、分析角色與回覆要求；讀回並檢查整份 request.md。request_id 路徑由腳本生成，不從遠端回覆決定。

## 3. 傳送一次

```text
python <script> --project <project> dispatch --request <request_id>
```

然後 `send_message_to_thread({threadId:<已綁定的ChatGPT對話UUID>, prompt:<request.md完整文字>})`，不要傳 model/thinking。傳送工具回覆無法確認、逾時或中斷時維持 dispatching；查找 request_id，不再次呼叫傳送。跨會話重啟也適用。

此腳本防止重複進入 dispatch，不能提供遠端 exactly-once 保證。若確認請求根本沒送出，先展示核對結果，再用 `release --request <id> --reason <原因>` 釋放；已送出或結果不明的請求不得釋放後重送。

## 4. 等待與核對

使用 `global-workflow.md` 的 `inbox.py wait` 等待本機收據，收到後才呼叫 `read_thread` 取完整原文；不使用模型定時輪詢。若有人新增訊息，必要時使用 cursor 讀前頁，尋找原始使用者訊息**與 request.md 相符**的回合。核對只容許 CRLF／LF 與尾端換行差異，其餘內容須相同。保存工具 JSON 為 `after.json`。

```text
python <script> --project <project> complete --request <request_id> --after <after.json>
```

腳本核對目標對話、kind、非既有回合、本次完整 prompt、completed 與非空 agentMessage，保存 response.md 和 receipt.json。pending 或舊回合不會標為完成。它只驗證文字往返，不能驗證後端模型身分或建議正確性。完成後 Codex 依 SKILL.md 核對並處理本地任務。

## 邊界

- 原生工具只提供既有 Chat 的 send/read；建立 Chat、選 Pro 由可用 UI 或使用者操作，不能把 ChatGPT Work 當替代方案。
- 每個新專案首次要綁定專用對話；之後可重用，但每次重新確認模型。
- CLI／IDE 若沒有這組 Codex app 工具，只能準備背景包並說明尚未傳送；全域安裝不保證每種用戶端都具備原生對話工具。
- `status` 是唯讀；`release` 保留所有請求與理由，不刪遠端訊息，也不取消模型運算。pending 請求先確認遠端終止或確定未傳送才可釋放。
- 本地證據目錄含使用者選擇傳送的片段和回覆，屬專案資料，不放進 Skill，也不自動上傳／提交 Git。
