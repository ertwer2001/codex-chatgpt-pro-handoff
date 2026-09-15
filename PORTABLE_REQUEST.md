# User request / 使用者需求

將目前 Codex 專用 Skill 與接收器做成其他 Windows 電腦可用的完整安裝 ZIP，包含中英對照說明、升級與回復、驗证方式與交接 Markdown，並供 GitHub 開源發布。請依實際程式自行完成可攜化、測試及打包，不只給方案。保留使用者說「丟給PRO分析」即可依專案轉交的流程。

## Known facts / 已確認事實

- Latest live receiver version: 0.3.1. Public release: v0.1.1; prior source improvements 0.1.2-local.2 not yet released. Please produce release candidate v0.3.1.
- Live Skill copied into this snapshot; existing install.py and checksum/build helpers still describe the old file set and require updating.
- Local tests passed: 12 JavaScript receiver tests, 9 Python receiver/global helper tests. Source test_global.py was not included because it imports a machine-installed Skill; make portable tests.
- Actual Pro math and stock responses were automatically saved locally. Native completed turn and exact request were separately verified. No clean second-computer installation has been tested.
- Global Skill is loaded and enabled. Two separate project paths reused the shared local service. Per-project first Chat creation remains dependent on native/browser tools and login.
- Receiver uses active waiting, maximum 40 minutes. Late results remain on disk. Background Codex wake is not working; do not advertise it. CLI resume was disabled after an active-writer conflict.
- Browser management page blocks automation; user must manually load/reload unpacked extension. Do not bypass security controls.
- Plain innerText can lose formula formatting and source hyperlinks; native completed response preserves Markdown. Keep this limitation visible or fix serialization with tests.
- No personal chat content, ledger, real pairing key, or credentials included. Generate fresh local configuration on the destination machine.

## Deliverables / 交付

Actual downloadable ZIP containing full reviewed source, installer, extension, bilingual README and handoff, tests and checksums. Provide one primary ZIP download to work with the currently verified single-file receiver. Include other documents inside ZIP. Do not run external publishing; Codex will validate and publish GitHub. Report tests and remaining limits honestly.
