"""Build a portable release from an explicit list of public files. No network."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '0.1.0'
FILES = [
    'README.md', 'START_HERE.md', 'LICENSE', 'CHANGELOG.md', 'VALIDATION.md',
    '.gitignore', '.gitattributes', 'install.py', 'verify_package.py', 'build_release.py',
    'skill-sha256.json', 'test-results.txt',
    'tests/test_cloud_package.py', 'tests/test_handoff_state.py',
    'skill/cj-chatgpt-handoff/SKILL.md', 'skill/cj-chatgpt-handoff/agents/openai.yaml',
    'skill/cj-chatgpt-handoff/references/native-workflow.md',
    'skill/cj-chatgpt-handoff/scripts/handoff_state.py',
]


def main():
    manifest = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    skill = {name: digest for name, digest in manifest.items() if name.startswith('skill/')}
    if skill != json.loads((ROOT / 'skill-sha256.json').read_text(encoding='utf-8')):
        raise ValueError('Skill sources changed; review and update skill-sha256.json before packaging')
    (ROOT / 'SHA256SUMS.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    archive = dist / ('codex-chatgpt-pro-handoff-v' + VERSION + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name in FILES + ['SHA256SUMS.json']:
            info = zipfile.ZipInfo('codex-chatgpt-pro-handoff/' + name, date_time=(2026, 9, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, (ROOT / name).read_bytes())
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise ValueError('ZIP CRC verification failed')
        for name, digest in manifest.items():
            if hashlib.sha256(z.read('codex-chatgpt-pro-handoff/' + name)).hexdigest() != digest:
                raise ValueError('ZIP hash mismatch: ' + name)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (dist / 'SHA256SUMS.txt').write_text(checksum + '  ' + archive.name + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'archive': str(archive), 'files': len(FILES) + 1, 'sha256': checksum}, ensure_ascii=False))


if __name__ == '__main__':
    main()
