"""Verify package file hashes only; no installation, network, or credentials."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def verify(root):
    root = root.resolve(strict=True)
    manifest = json.loads((root / 'SHA256SUMS.json').read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('Expected a nonempty SHA256 manifest')
    checked = []
    for relative, expected in manifest.items():
        parts = PurePosixPath(relative)
        if parts.is_absolute() or '..' in parts.parts or '\\' in relative:
            raise ValueError('Unsafe manifest path: ' + relative)
        target = root / relative
        if not target.resolve().is_relative_to(root) or not target.is_file():
            raise ValueError('Missing or unsafe file: ' + relative)
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('SHA256 mismatch: ' + relative)
        checked.append(relative)
    skill_hashes = json.loads((root / 'skill-sha256.json').read_text(encoding='utf-8'))
    expected_skill = {'skill/cj-chatgpt-handoff/' + rel for rel in (
        'SKILL.md', 'agents/openai.yaml', 'references/native-workflow.md', 'references/global-workflow.md',
        'scripts/handoff_state.py', 'scripts/inbox.py', 'references/evidence-workflow.md',
        'scripts/handoff_evidence.py')}
    if set(skill_hashes) != expected_skill:
        raise ValueError('Skill hashes do not match the expected file set')
    for relative, expected in skill_hashes.items():
        if manifest.get(relative) != expected:
            raise ValueError('Skill and full manifest disagree: ' + relative)
    extras = sorted(p.relative_to(root).as_posix() for p in root.rglob('*')
                    if p.is_file() and p.relative_to(root).as_posix() not in manifest
                    and p.relative_to(root).as_posix() != 'SHA256SUMS.json')
    return {'status': 'VERIFIED', 'files_checked': len(checked),
            'skill_files_checked': len(skill_hashes), 'unlisted_files': extras,
            'manifest_self_excluded': True, 'digital_signature_verified': False,
            'installed_or_sent_to_chatgpt': False}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'STOPPED', 'error': str(exc)}, ensure_ascii=False))
        sys.exit(2)
