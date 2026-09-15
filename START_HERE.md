# Start here｜從這裡開始

**Codex-only ChatGPT Pro handoff Skill｜Codex 專用 ChatGPT Pro 協作 Skill**

Read [README.md](README.md) for the bilingual guide and requirements. Download and extract the release ZIP, then run from its root directory:<br>
先讀 [README.md](README.md) 的中英教學與使用條件。下載並解壓 Release ZIP，在套件根目錄執行：

```text
python -X utf8 verify_package.py
python -X utf8 install.py
python -X utf8 install.py --apply
```

- Verify hashes, preview the plan, then install. / 核對雜湊、預覽計畫，再執行安裝。
- Reload Codex Skills and confirm the three required native chat tools. / 重新載入 Codex Skills，確認三個必要原生對話工具。
- Use a dedicated Chat per computer/project and confirm 6 Pro. / 每台電腦／每個專案使用專用 Chat，並確認 6 Pro。
- Verify one non-sensitive Request-ID roundtrip; installation alone is not integration proof. / 完成一次無機密 Request-ID 往返；安裝成功不等於整合已驗收。

Use `$cj-chatgpt-handoff` when you want Pro assistance. Signing into ChatGPT on another computer does not install the local Skill.<br>
需要 Pro 協助時使用 `$cj-chatgpt-handoff`；在別台電腦登入 ChatGPT，不會自動安裝本地 Skill。

No personal chats, credentials, machine state, or backups are included. Restore instructions and limits are in README.<br>
公開套件不含私人對話、登入資料、機器狀態或備份。還原方式與限制見 README。
