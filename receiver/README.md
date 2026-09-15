# Receiver source 0.3.1

Shared per-user loopback service; discovers registered project ledgers. Browser extension receives text and downloads attachments. Waiting uses ordinary code, not model polling. Active Codex waiting works; background CLI resume conflicts with Desktop and is disabled. FIFO receiving; all relevant Pro tabs must stay open. No guarantee during sleep/offline.

This source snapshot is not yet a complete portable installer. Extend the existing reversible installer to include receiver runtime and a durable extension path, reconcile CODEX_HOME consistently, and avoid shipping machine config or tokens.
