"""Portable installation; local files only, no network or credentials. Python 3.10+."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid

PACKAGE = Path(__file__).resolve().parent
SKILL = 'cj-chatgpt-handoff'
SKILL_FILES = ['SKILL.md', 'agents/openai.yaml', 'references/native-workflow.md', 'references/global-workflow.md',
               'scripts/handoff_state.py', 'scripts/inbox.py', 'references/evidence-workflow.md',
               'scripts/handoff_evidence.py']
RECEIVER_FILES = ['relay.py', 'setup_relay.py', 'extension/background.js', 'extension/content.js',
                  'extension/local-config.js', 'extension/manifest.json', 'extension/popup.html',
                  'extension/popup.js']
ROUTE = '''

## GPT-6 Pro 協作

使用者要求「請 Pro 分析／審查／幫忙」或呼叫 `$cj-chatgpt-handoff` 時，讀取 [cj-chatgpt-handoff](skills/cj-chatgpt-handoff/SKILL.md)。已確認 6 Pro 且接收器可用時，將必要背景交給專用 ChatGPT Pro，核對收據後把成果回到原 Codex 任務；沒有 Pro、額度不足、模型未確認或原生工具不可用時，不做普通 Chat 降級轉交，直接用 Codex 用戶端可選的最高模型與推理強度完成，並標示為 Codex 替代結果。一般任務不自動傳送；不增加各專案原有授權與資料存取範圍。
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


def save(path, data):
    atomic(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def remove_empty_install_dirs(target, destination):
    """Remove only empty directories created below the two installer-owned roots."""
    anchors = {destination / 'skills', destination / 'pro-inbox'}
    parent = target.parent
    while parent not in anchors and parent.is_relative_to(destination):
        try:
            parent.rmdir()
        except OSError:
            break
        parent = parent.parent


def restore(receipt_path, apply):
    receipt_path = receipt_path.resolve(strict=True)
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    destination = Path(receipt['codex_home']).resolve()
    allowed = {'AGENTS.md'} | {'skills/' + SKILL + '/' + rel for rel in SKILL_FILES}
    allowed |= {'pro-inbox/bootstrap/' + rel for rel in RECEIVER_FILES}
    operations = []
    for entry in receipt['files']:
        rel = entry['relative_path']
        if rel not in allowed:
            raise ValueError('Unexpected restore target')
        target = destination / rel
        if not target.resolve().is_relative_to(destination):
            raise ValueError('Restore target escapes Codex home')
        # An interrupted install may leave an original file untouched or a new file absent.
        current = target.read_bytes() if target.exists() else None
        before = None
        if entry['existed']:
            original = receipt_path.parent / 'before' / rel
            if not original.resolve().is_relative_to(receipt_path.parent):
                raise ValueError('Backup escapes receipt directory')
            before = original.read_bytes()
            if digest(before) != entry['before_sha256']:
                raise ValueError('Backup integrity failure')
        if current == before:
            continue
        if current is None or digest(current) != entry['after_sha256']:
            raise ValueError('Subsequent change detected; refusing to overwrite ' + rel)
        operations.append((target, before))
    if apply:
        for target, before in operations:
            if before is None:
                target.unlink()
                remove_empty_install_dirs(target, destination)
            else:
                atomic(target, before)
            if before is not None and target.read_bytes() != before:
                raise ValueError('Restore verification failed')
    return {'status': 'RESTORED' if apply else 'RESTORE_READY', 'file_count': len(operations),
            'evidence_and_chats_retained': True}


def install(destination, backup_root, apply):
    destination = destination.expanduser().resolve()
    skill_hashes = json.loads((PACKAGE / 'skill-sha256.json').read_text(encoding='utf-8'))
    package_hashes = json.loads((PACKAGE / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    changes = []
    sources = [('skill/' + SKILL + '/' + rel, 'skills/' + SKILL + '/' + rel) for rel in SKILL_FILES]
    sources += [('receiver/' + rel, 'pro-inbox/bootstrap/' + rel) for rel in RECEIVER_FILES]
    for package_rel, relative in sources:
        data = (PACKAGE / package_rel).read_bytes()
        expected = package_hashes.get(package_rel)
        if expected is None or digest(data) != expected:
            raise ValueError('Package hash mismatch: ' + package_rel)
        if package_rel.startswith('skill/') and skill_hashes.get(package_rel) != expected:
            raise ValueError('Missing Skill hash: ' + package_rel)
        target = destination / relative
        if not target.resolve().is_relative_to(destination):
            raise ValueError('Install target escapes Codex home')
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('Existing Skill differs; ask Codex to compare before any replacement: ' + str(target))
        else:
            changes.append((relative, None, data))
    agents = destination / 'AGENTS.md'
    if not agents.resolve().is_relative_to(destination):
        raise ValueError('AGENTS.md escapes Codex home')
    old = agents.read_bytes() if agents.exists() else None
    text = old.decode('utf-8-sig') if old is not None else ''
    if 'skills/cj-chatgpt-handoff/SKILL.md' not in text.replace('\\', '/'):
        nl = '\r\n' if old and b'\r\n' in old else '\n'
        changes.append(('AGENTS.md', old, (old or b'') + ROUTE.replace('\n', nl).encode('utf-8')))
    summary = {'status': 'READY' if changes else 'ALREADY_INSTALLED', 'codex_home': str(destination),
               'files_to_change': [entry[0] for entry in changes], 'runtime_handoff_tested': False}
    if not apply or not changes:
        return summary
    backup = backup_root.expanduser().resolve() / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-pro-handoff-' + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, exist_ok=False)
    receipt = {'schema_version': 1, 'codex_home': str(destination), 'files': []}
    for relative, before, after in changes:
        entry = {'relative_path': relative, 'existed': before is not None,
                 'before_sha256': digest(before) if before is not None else None,
                 'after_sha256': digest(after)}
        if before is not None:
            saved = backup / 'before' / relative
            atomic(saved, before)
            if saved.read_bytes() != before:
                raise ValueError('Backup read-back failed')
        receipt['files'].append(entry)
    save(backup / 'receipt.json', receipt)
    shutil.copy2(Path(__file__), backup / 'install.py')
    for relative, before, after in changes:
        target = destination / relative
        actual = target.read_bytes() if target.exists() else None
        if actual != before:
            raise ValueError('Concurrent change; installation stopped; use backup receipt for recovery')
        atomic(target, after)
        if target.read_bytes() != after:
            raise ValueError('Installation read-back failed')
    summary.update(status='INSTALLED', receipt=str(backup / 'receipt.json'), backup=str(backup))
    return summary


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply after reviewing the plan')
    parser.add_argument('--codex-home', type=Path, default=Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex'))
    parser.add_argument('--backup-root', type=Path, default=Path.home() / 'cj-codex-backups')
    parser.add_argument('--restore', type=Path, help='Restore from a receipt; --apply performs it')
    args = parser.parse_args()
    try:
        result = restore(args.restore, args.apply) if args.restore else install(args.codex_home, args.backup_root, args.apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({'status': 'STOPPED', 'error': str(error)}, ensure_ascii=False))
        sys.exit(2)
