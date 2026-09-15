"""Evidence packaging, recovery and review binding under isolated workspaces."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

import test_handoff_state as fixtures

SCRIPT = fixtures.SCRIPT.with_name('handoff_evidence.py')
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('handoff_evidence', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceTests(unittest.TestCase):
    tearDown = fixtures.HandoffTests.tearDown
    prepare = fixtures.HandoffTests.prepare
    reply = fixtures.HandoffTests.reply

    def setUp(self):
        fixtures.HandoffTests.setUp(self)
        self.evidence = module.Evidence(self.ledger)
        (self.project / 'demo.py').write_text('def add(a, b):\n    return a + b\n', encoding='utf-8')
        (self.project / 'tests.txt').write_text('Command: python -m unittest\nExit code: 0\n3 tests passed\n', encoding='utf-8')

    def bundle_spec(self):
        return {'kind': 'context', 'goal': 'Review addition', 'acceptance': '2 + 3 equals 5',
                'files': [{'path': 'demo.py'}]}

    def checkpoint_spec(self, bundle=None):
        return {'stage': 'implementing', 'goal': 'Review addition', 'completed': 'Prepared evidence',
                'issues': 'Need review', 'next_step': 'Compare actual output', 'bundle_id': bundle}

    def snapshot(self):
        return {str(p.relative_to(self.base)): p.read_bytes() if p.is_file() else None
                for p in self.base.rglob('*')}

    def test_explicit_selection_and_omissions(self):
        spec = self.bundle_spec(); spec['files'][0].update(start=2, end=2)
        before = (self.project/'demo.py').read_bytes()
        result = self.evidence.bundle(spec)
        text = Path(result['context_path']).read_text(encoding='utf-8')
        self.assertIn('return a + b', text)
        self.assertNotIn('def add', text)
        self.assertEqual(result['sources'][0]['omitted_lines'], 1)
        self.assertFalse(result['sent'])
        self.assertEqual((self.project/'demo.py').read_bytes(), before)
        self.assertFalse(self.ledger.state_path.exists())

    def test_changes_and_deleted_files_detected_read_only(self):
        bundle = self.evidence.bundle(self.bundle_spec())
        before = self.snapshot()
        self.assertTrue(self.evidence.check(bundle['bundle_id'])['sources_match'])
        self.assertEqual(before, self.snapshot())
        source = self.project/'demo.py'; source.write_text('changed', encoding='utf-8')
        self.assertEqual(self.evidence.check(bundle['bundle_id'])['changes'][0]['status'], 'changed')
        source.unlink()
        self.assertEqual(self.evidence.check(bundle['bundle_id'])['changes'][0]['status'], 'unavailable')

    def test_packet_tampering_rejected(self):
        bundle = self.evidence.bundle(self.bundle_spec())
        Path(bundle['context_path']).write_text('tampered', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'packet changed'):
            self.evidence.check(bundle['bundle_id'])

    def test_credentials_redacted_in_fields_and_source(self):
        token = 'ghp_' + 'X'*30
        (self.project/'demo.py').write_text('token = '+token+'\npassword: mypassword\n', encoding='utf-8')
        spec = self.bundle_spec(); spec['goal'] = 'Review '+token
        bundle = self.evidence.bundle(spec)
        text = Path(bundle['context_path']).read_text(encoding='utf-8')
        self.assertNotIn(token, text); self.assertNotIn('mypassword', text)
        self.assertGreaterEqual(bundle['redactions'], 3)
        self.assertFalse(bundle['secret_scan_complete'])

    def test_private_key_refused_before_writes(self):
        (self.project/'demo.py').write_text('-----BEGIN RSA PRIVATE KEY-----', encoding='utf-8')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Private-key'):
            self.evidence.bundle(self.bundle_spec())
        self.assertEqual(before, self.snapshot())

    def test_path_escape_sensitive_paths_and_absolute_paths_rejected(self):
        for path in ['../outside.txt', '.env', '.ssh/key', 'private.pem', '.codex/state.json',
                     'C:/Users/test/a.txt', '/etc/passwd', '..\\outside.txt']:
            spec = self.bundle_spec(); spec['files'][0]['path'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.evidence.bundle(spec)

    def make_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                raise
            run = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(link), str(target)],
                                 capture_output=True, timeout=10)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_symlink_or_windows_junction_escape(self):
        outside = self.base/'outside'; outside.mkdir()
        (outside/'file.txt').write_text('private', encoding='utf-8')
        self.make_link(self.project/'linked', outside)
        spec = self.bundle_spec(); spec['files'][0]['path'] = 'linked/file.txt'
        with self.assertRaises(ValueError):
            self.evidence.bundle(spec)

    def test_alias_cannot_bypass_sensitive_directory(self):
        private = self.project/'.ssh'; private.mkdir()
        (private/'file.txt').write_text('private', encoding='utf-8')
        self.make_link(self.project/'linked', private)
        spec = self.bundle_spec(); spec['files'][0]['path'] = 'linked/file.txt'
        with self.assertRaises(ValueError):
            self.evidence.bundle(spec)

    def test_binary_oversize_and_invalid_ranges(self):
        for content in [b'a\0b', b'x'*(module.MAX_FILE+1), b'\xff']:
            (self.project/'demo.py').write_bytes(content)
            with self.assertRaises(ValueError):
                self.evidence.bundle(self.bundle_spec())
        (self.project/'demo.py').write_text('a\nb\n', encoding='utf-8')
        for start,end in [(0,1),(2,1),(1,3),(True,2)]:
            spec=self.bundle_spec();spec['files'][0].update(start=start,end=end)
            with self.assertRaises(ValueError): self.evidence.bundle(spec)

    def test_packet_limit_is_not_silent_truncation(self):
        (self.project/'demo.py').write_text('x'*module.MAX_PACKET, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Packet exceeds'):
            self.evidence.bundle(self.bundle_spec())
        self.assertFalse(self.ledger.store.exists())

    def test_resume_checkpoint_versions_and_source_drift(self):
        bundle=self.evidence.bundle(self.bundle_spec())
        first=self.evidence.checkpoint(self.checkpoint_spec(bundle['bundle_id']))
        updated=self.checkpoint_spec(bundle['bundle_id']);updated['stage']='awaiting_review'
        second=self.evidence.checkpoint(updated, first['task_id'])
        self.assertEqual(second['revision'],2)
        self.assertEqual(len(list(self.evidence.task_dir(first['task_id']).glob('*.json'))),2)
        (self.project/'demo.py').write_text('new work',encoding='utf-8')
        before=self.snapshot(); resume=self.evidence.resume(first['task_id'])
        self.assertFalse(resume['evidence_check']['sources_match'])
        self.assertEqual(before,self.snapshot())
        self.assertFalse(resume['checkpoint']['grants_authority'])

    def test_pending_request_survives_checkpoint_and_resume(self):
        req=self.prepare();self.ledger.dispatch(req['request_id'])
        checkpoint=self.evidence.checkpoint(self.checkpoint_spec())
        resume=self.evidence.resume(checkpoint['task_id'])
        self.assertEqual(resume['pending_request'],req['request_id'])
        self.assertEqual(self.ledger.request(req['request_id'])['status'],'dispatching')

    def test_checkpoint_does_not_reuse_unknown_task(self):
        with self.assertRaisesRegex(ValueError,'Task not found'):
            self.evidence.checkpoint(self.checkpoint_spec(),str(uuid.uuid4()))

    def test_task_discovery_is_local_readonly_and_shows_latest_revision(self):
        before=self.snapshot()
        self.assertEqual(self.evidence.tasks()['tasks'],[])
        self.assertEqual(before,self.snapshot())
        first=self.evidence.checkpoint(self.checkpoint_spec())
        update=self.checkpoint_spec();update['stage']='blocked'
        self.evidence.checkpoint(update,first['task_id'])
        before=self.snapshot();items=self.evidence.tasks()['tasks']
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['stage'],'blocked')
        self.assertEqual(before,self.snapshot())

    def test_checkpoint_secret_and_invalid_stage(self):
        spec=self.checkpoint_spec();spec['issues']='password: dontpersist'
        result=self.evidence.checkpoint(spec)
        self.assertNotIn('dontpersist',json.dumps(result))
        spec['stage']='send_now'
        with self.assertRaises(ValueError):self.evidence.checkpoint(spec)

    def test_review_requires_completed_parent_and_both_evidence_roles(self):
        req=self.prepare()
        spec=self.bundle_spec();spec.update(kind='review',parent_request=req['request_id'])
        with self.assertRaises((ValueError,OSError)):self.evidence.bundle(spec)
        self.ledger.dispatch(req['request_id']);self.ledger.complete(req['request_id'],self.reply(req))
        with self.assertRaisesRegex(ValueError,'change and test'):self.evidence.bundle(spec)
        spec['files']=[{'path':'demo.py','role':'change'},{'path':'tests.txt','role':'test'}]
        result=self.evidence.bundle(spec)
        self.assertEqual(result['parent_request'],req['request_id'])
        self.assertTrue(self.evidence.check(result['bundle_id'])['sources_match'])
        self.assertIsNone(self.ledger.state()['active_request'])
        (self.ledger.request_dir(req['request_id'])/'response.md').write_text('tampered',encoding='utf-8')
        with self.assertRaises(ValueError):self.evidence.check(result['bundle_id'])

    def test_bundle_cross_project_rejected(self):
        bundle=self.evidence.bundle(self.bundle_spec())
        folder=self.evidence.bundle_dir(bundle['bundle_id'])
        manifest=module.read_json(folder/'manifest.json');manifest['project_key']='another'
        module.write_json(folder/'manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'identity'):self.evidence.check(bundle['bundle_id'])

    def test_cli_utf8_bundle_to_existing_prepare(self):
        spec=self.bundle_spec();spec['goal']='檢查加法';spec_path=self.base/'spec.json'
        spec_path.write_text(json.dumps(spec,ensure_ascii=False),encoding='utf-8')
        run=subprocess.run([sys.executable,'-X','utf8','-B',str(SCRIPT),'--project',str(self.project),
                            '--store',str(self.ledger.store),'bundle','--spec',str(spec_path)],
                           capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(run.returncode,0,run.stderr)
        result=json.loads(run.stdout)
        context=Path(result['context_path']).read_text(encoding='utf-8')
        self.ledger.bind(self.chat,'ui','TEST ONLY')
        req=self.ledger.prepare(self.source,context,self.before)
        self.assertIn('檢查加法',Path(req['prompt_path']).read_text(encoding='utf-8'))
        self.assertEqual(self.ledger.request(req['request_id'])['status'],'prepared')


if __name__ == '__main__': unittest.main()
