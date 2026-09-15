"""Portable installer regression tests, initially developed in a ChatGPT cloud sandbox.

Every installer process receives explicit --codex-home and --backup-root
under separate tempfile.TemporaryDirectory roots. No real Codex installation
or native ChatGPT tools are used. Run from the package directory:
    python -X utf8 -B -m unittest discover -s tests -v
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
SKILL = 'cj-chatgpt-handoff'
FILES = ('SKILL.md', 'agents/openai.yaml', 'references/native-workflow.md', 'scripts/handoff_state.py', 'scripts/handoff_evidence.py', 'references/evidence-workflow.md')
AGENTS_ORIGINAL = '# Existing local rules\nDo not remove this rule.\n'.encode('utf-8')
CONFIG_ORIGINAL = b'model = "unchanged-test-model"\nmodel_reasoning_effort = "high"\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(root):
    """Record file contents and directory names to detect unintended writes."""
    if not root.exists():
        return None
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
            for p in root.rglob('*')}


class CloudPackageTests(unittest.TestCase):
    def setUp(self):
        temp_home = tempfile.TemporaryDirectory(prefix='cj-cloud-home-')
        temp_backup = tempfile.TemporaryDirectory(prefix='cj-cloud-backups-')
        self.addCleanup(temp_home.cleanup)
        self.addCleanup(temp_backup.cleanup)
        self.home_root = Path(temp_home.name)
        self.backup_root = Path(temp_backup.name)
        self.home = self.home_root / 'isolated Codex'
        self.backups = self.backup_root / 'receipts'
        self.home.mkdir()
        (self.home / 'AGENTS.md').write_bytes(AGENTS_ORIGINAL)
        (self.home / 'config.toml').write_bytes(CONFIG_ORIGINAL)
        self.env = dict(os.environ)
        self.env['CODEX_HOME'] = str(self.home)
        self.env['PYTHONDONTWRITEBYTECODE'] = '1'

    def cli(self, *extra, package=None, expected_code=0):
        package = package or PACKAGE
        command = [sys.executable, '-X', 'utf8', '-B', str(package / 'install.py'),
                   '--codex-home', str(self.home), '--backup-root', str(self.backups), *map(str, extra)]
        process = subprocess.run(command, cwd=package, env=self.env, capture_output=True,
                                 text=True, encoding='utf-8', timeout=30, check=False)
        self.assertEqual(process.returncode, expected_code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def installed(self):
        result = self.cli('--apply')
        self.assertEqual(result['status'], 'INSTALLED')
        self.assertFalse(result['runtime_handoff_tested'])
        return result

    def test_01_dry_run_has_no_writes(self):
        before_home = snapshot(self.home_root)
        before_backup = snapshot(self.backup_root)
        result = self.cli()
        self.assertEqual(result['status'], 'READY')
        self.assertEqual(len(result['files_to_change']), 7)
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)

    def test_02_apply_skill_files_match_sources(self):
        self.installed()
        for rel in FILES:
            self.assertEqual((self.home / 'skills' / SKILL / rel).read_bytes(),
                             (PACKAGE / 'skill' / SKILL / rel).read_bytes())

    def test_03_existing_agents_prefix_and_config_bytes_preserved(self):
        self.installed()
        after = (self.home / 'AGENTS.md').read_bytes()
        self.assertTrue(after.startswith(AGENTS_ORIGINAL))
        self.assertEqual(after.count(b'skills/cj-chatgpt-handoff/SKILL.md'), 1)
        self.assertEqual((self.home / 'config.toml').read_bytes(), CONFIG_ORIGINAL)

    def test_04_backup_and_receipt_sha256_match_actual_bytes(self):
        result = self.installed()
        receipt_path = Path(result['receipt'])
        self.assertTrue(receipt_path.is_relative_to(self.backup_root))
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        self.assertEqual(receipt['codex_home'], str(self.home.resolve()))
        self.assertEqual(len(receipt['files']), 7)
        self.assertEqual((receipt_path.parent / 'install.py').read_bytes(), (PACKAGE / 'install.py').read_bytes())
        for entry in receipt['files']:
            rel = entry['relative_path']
            self.assertEqual(sha((self.home / rel).read_bytes()), entry['after_sha256'])
            if entry['existed']:
                before = (receipt_path.parent / 'before' / rel).read_bytes()
                self.assertEqual(before, AGENTS_ORIGINAL)
                self.assertEqual(sha(before), entry['before_sha256'])
            else:
                self.assertIsNone(entry['before_sha256'])

    def test_05_reapply_is_noop_without_additional_backup(self):
        self.installed()
        before_home, before_backup = snapshot(self.home_root), snapshot(self.backup_root)
        result = self.cli('--apply')
        self.assertEqual(result['status'], 'ALREADY_INSTALLED')
        self.assertEqual(result['files_to_change'], [])
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)

    def test_06_restore_dry_run_has_no_writes(self):
        result = self.installed()
        before_home, before_backup = snapshot(self.home_root), snapshot(self.backup_root)
        restored = self.cli('--restore', result['receipt'])
        self.assertEqual(restored['status'], 'RESTORE_READY')
        self.assertEqual(restored['file_count'], 7)
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)

    def test_07_restore_originals_and_remove_only_new_skill_files(self):
        result = self.installed()
        restored = self.cli('--restore', result['receipt'], '--apply')
        self.assertEqual(restored['status'], 'RESTORED')
        self.assertEqual(restored['file_count'], 7)
        self.assertEqual((self.home / 'AGENTS.md').read_bytes(), AGENTS_ORIGINAL)
        self.assertEqual((self.home / 'config.toml').read_bytes(), CONFIG_ORIGINAL)
        for rel in FILES:
            self.assertFalse((self.home / 'skills' / SKILL / rel).exists())
        self.assertTrue(Path(result['receipt']).exists())

    def test_08_repeated_restore_is_noop(self):
        result = self.installed()
        self.cli('--restore', result['receipt'], '--apply')
        before = snapshot(self.home_root)
        restored = self.cli('--restore', result['receipt'], '--apply')
        self.assertEqual(restored['status'], 'RESTORED')
        self.assertEqual(restored['file_count'], 0)
        self.assertEqual(snapshot(self.home_root), before)

    def test_09_conflicting_skill_stops_before_any_writes(self):
        target = self.home / 'skills' / SKILL / 'SKILL.md'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'different local Skill; keep me')
        before_home, before_backup = snapshot(self.home_root), snapshot(self.backup_root)
        result = self.cli('--apply', expected_code=2)
        self.assertEqual(result['status'], 'STOPPED')
        self.assertIn('Existing Skill differs', result['error'])
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)

    def test_10_tampered_package_stops_before_any_install(self):
        copy = self.home_root / 'tampered package'
        shutil.copytree(PACKAGE, copy, ignore=shutil.ignore_patterns('__pycache__'))
        target = copy / 'skill' / SKILL / 'SKILL.md'
        target.write_bytes(target.read_bytes() + b'\ntampered\n')
        before_home, before_backup = snapshot(self.home_root), snapshot(self.backup_root)
        result = self.cli('--apply', package=copy, expected_code=2)
        self.assertIn('Package hash mismatch', result['error'])
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)

    def test_11_restore_refuses_later_user_change(self):
        result = self.installed()
        target = self.home / 'AGENTS.md'
        target.write_bytes(target.read_bytes() + b'\nnew user rule\n')
        before = snapshot(self.home_root)
        restored = self.cli('--restore', result['receipt'], '--apply', expected_code=2)
        self.assertIn('Subsequent change detected', restored['error'])
        self.assertEqual(snapshot(self.home_root), before)

    def test_12_restore_refuses_corrupt_backup(self):
        result = self.installed()
        backup = Path(result['receipt']).parent / 'before' / 'AGENTS.md'
        backup.write_bytes(b'corrupted backup')
        before = snapshot(self.home_root)
        restored = self.cli('--restore', result['receipt'], '--apply', expected_code=2)
        self.assertIn('Backup integrity failure', restored['error'])
        self.assertEqual(snapshot(self.home_root), before)

    def test_13_preexisting_identical_skill_survives_restore(self):
        shutil.copytree(PACKAGE / 'skill' / SKILL, self.home / 'skills' / SKILL)
        result = self.installed()
        self.assertEqual(result['files_to_change'], ['AGENTS.md'])
        self.cli('--restore', result['receipt'], '--apply')
        for rel in FILES:
            self.assertEqual((self.home / 'skills' / SKILL / rel).read_bytes(),
                             (PACKAGE / 'skill' / SKILL / rel).read_bytes())
        self.assertEqual((self.home / 'AGENTS.md').read_bytes(), AGENTS_ORIGINAL)

    def test_14_fresh_home_install_and_restore(self):
        assert self.home.resolve().is_relative_to(self.home_root.resolve())
        shutil.rmtree(self.home)
        before = snapshot(self.home_root)
        self.cli()
        self.assertEqual(snapshot(self.home_root), before)
        result = self.installed()
        self.assertFalse((self.home / 'config.toml').exists())
        self.cli('--restore', result['receipt'], '--apply')
        self.assertFalse((self.home / 'AGENTS.md').exists())
        self.assertEqual([p for p in self.home.rglob('*') if p.is_file()], [])

    def test_15_utf8_bom_crlf_agents_roundtrip(self):
        original = b'\xef\xbb\xbf' + '# 原有規則\r\n保留。\r\n'.encode('utf-8')
        (self.home / 'AGENTS.md').write_bytes(original)
        result = self.installed()
        after = (self.home / 'AGENTS.md').read_bytes()
        self.assertTrue(after.startswith(original))
        self.assertNotIn(b'\n', after.replace(b'\r\n', b''))
        self.cli('--restore', result['receipt'], '--apply')
        self.assertEqual((self.home / 'AGENTS.md').read_bytes(), original)

    def test_16_unrelated_project_and_evidence_retained(self):
        sentinels = {'projects/example/keep.txt': b'synthetic project only',
                     'pro-handoff/keep.txt': b'synthetic retained evidence only',
                     'skills/unrelated/SKILL.md': b'synthetic unrelated skill'}
        for rel, data in sentinels.items():
            p = self.home / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        result = self.installed()
        self.cli('--restore', result['receipt'], '--apply')
        for rel, data in sentinels.items():
            self.assertEqual((self.home / rel).read_bytes(), data)

    def test_17_all_python_files_compile_without_execution(self):
        for path in PACKAGE.rglob('*.py'):
            compile(path.read_text(encoding='utf-8'), str(path), 'exec')

    def test_18_state_status_is_readonly_in_explicit_store(self):
        project = self.home_root / 'synthetic project'
        project.mkdir()
        store = self.home_root / 'isolated ledger'
        before_home, before_backup = snapshot(self.home_root), snapshot(self.backup_root)
        command = [sys.executable, '-X', 'utf8', '-B',
                   str(PACKAGE / 'skill' / SKILL / 'scripts' / 'handoff_state.py'),
                   '--project', str(project), '--store', str(store), 'status']
        process = subprocess.run(command, env=self.env, capture_output=True, text=True,
                                 encoding='utf-8', timeout=30, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        status = json.loads(process.stdout)
        self.assertIsNone(status['binding'])
        self.assertIsNone(status['active_request'])
        self.assertFalse(store.exists())
        self.assertEqual(snapshot(self.home_root), before_home)
        self.assertEqual(snapshot(self.backup_root), before_backup)


if __name__ == '__main__':
    unittest.main(verbosity=2)
