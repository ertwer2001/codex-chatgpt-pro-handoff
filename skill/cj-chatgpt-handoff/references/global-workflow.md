# 全域 Pro 送出與回傳

所有路徑均以目前專案為準，Skill 腳本使用絕對路徑。原生工具和模型確認仍依 SKILL.md。這份流程只適用已確認 6 Pro 的「Pro 回傳」路由；沒有 Pro 或沒有原生工具時，直接以 Codex 用戶端可選的最高模型及推理強度完成，且不建立請求、不啟動接收器、不冒稱有 Pro 回傳。

```text
python <skill>/scripts/inbox.py --project <project> ensure
python <skill>/scripts/handoff_state.py --project <project> status
```

首次由瀏覽器自動建立 Chat、選 Pro、取得網址與原生身分後 bind；每個專案的 state.json 自動被共用接收服務發現，不需修改 config。

原生 read_thread 的回傳存成 before.json。context.md 放使用者需求及必要背景。

```text
python <skill>/scripts/handoff_state.py --project <project> prepare --autonomous --source-thread <current-thread-id> --context <context.md> --before <before.json>
python <skill>/scripts/handoff_state.py --project <project> dispatch --request <generated-id>
```

將 request.md 全文以 send_message_to_thread 傳一次，不填 model/thinking。之後：

```text
python <skill>/scripts/inbox.py --project <project> wait --request <generated-id> --timeout 2400
```

命令可回傳執行中的 session ID，等待該普通程序；不要另發 read_thread 輪詢或 heartbeat。工具等待返回收據時即取得結果。完成後 read_thread（maxOutputCharsPerItem 不超過20000），存 after.json，再執行：

```text
python <skill>/scripts/handoff_state.py --project <project> complete --request <generated-id> --after <after.json>
```

原生 Markdown 與網頁 innerText 的公式格式可能不同，保留原始回覆。連結／附件從本機收據交付到目前 Codex 任務，核對錯誤或讀取工具故障不能宣稱 native verified，仍保留已收原檔。

接收器以專案帳本、完整 prompt、Request-ID、來源 Codex thread、Chat thread 和檔案雜湊匹配。多專案可發送到不同 Chat；瀏覽器收件目前依單一接收工作序列化，失敗工作需先排除，其他等待不得覆寫它。

背景 CLI resume 已因 Desktop active-writer 衝突停用。活躍回合等待可收到結果，已結束回合不能承諾自動喚醒。晚到成果仍保存，下一次以同專案、同 request 接續。
