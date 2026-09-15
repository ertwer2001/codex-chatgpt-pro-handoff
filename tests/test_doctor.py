"""Local diagnostics and CLI regression tests. No network or actual ChatGPT calls."""
import json
import subprocess
import sys
import unittest

import test_handoff_state as fixtures

module, SCRIPT = fixtures.module, fixtures.SCRIPT


class DoctorTests(unittest.TestCase):
    setUp = fixtures.HandoffTests.setUp
    tearDown = fixtures.HandoffTests.tearDown
    prepare = fixtures.HandoffTests.prepare
    reply = fixtures.HandoffTests.reply

    def snapshot(self):
        return {str(p.relative_to(self.base)): p.read_bytes() if p.is_file() else None
                for p in self.base.rglob('*')}

    def diagnose(self, code):
        before = self.snapshot()
        result = self.ledger.doctor()
        self.assertEqual(result['status'], code)
        self.assertEqual(before, self.snapshot())
        self.assertFalse(result['ready_to_send'])
        self.assertFalse(result['current_pro_model_verified'])
        self.assertTrue(result['read_only'])
        self.assertTrue(result['checks'][0]['next_step_zh'])
        # Diagnostics are safe to share: no actual chat IDs, paths, or prompt text.
        serialized = json.dumps(result)
        self.assertNotIn(self.chat, serialized)
        self.assertNotIn(str(self.project), serialized)
        return result

    def test_new_computer_no_files_created(self):
        self.diagnose('SETUP_REQUIRED')
        self.assertFalse(self.ledger.store.exists())

    def test_old_model_evidence_never_means_ready(self):
        self.ledger.bind(self.chat, 'ui', 'TEST ONLY')
        self.diagnose('MODEL_CHECK_REQUIRED')

    def test_prepared_and_dispatching_resume_without_mutation(self):
        req = self.prepare()
        self.diagnose('PREPARED')
        self.ledger.dispatch(req['request_id'])
        self.diagnose('CHECK_REMOTE')

    def test_tampered_prompt_stops_send(self):
        req = self.prepare()
        (self.ledger.request_dir(req['request_id'])/'request.md').write_text('changed', encoding='utf-8')
        self.diagnose('PROMPT_CHANGED')

    def test_missing_request_is_actionable(self):
        req = self.prepare()
        (self.ledger.request_dir(req['request_id'])/'request.json').unlink()
        self.diagnose('LOCAL_STATE_ERROR')

    def test_malformed_and_unsupported_state(self):
        module.write_json(self.ledger.state_path, {'schema_version': 999})
        self.diagnose('LOCAL_STATE_ERROR')
        self.ledger.state_path.write_text('{broken', encoding='utf-8')
        self.diagnose('LOCAL_STATE_ERROR')

    def test_lock_is_reported_but_never_removed(self):
        with self.ledger.lock():
            result = self.diagnose('LOCK_PRESENT')
            self.assertEqual(result['checks'][1]['code'], 'SETUP_REQUIRED')

    def test_completed_pointer_recovery_checks_response(self):
        req = self.prepare()
        self.ledger.dispatch(req['request_id'])
        self.ledger.complete(req['request_id'], self.reply(req))
        state = self.ledger.state()
        state['active_request'] = req['request_id']
        module.write_json(self.ledger.state_path, state)
        self.diagnose('FINALIZE_LOCAL')
        (self.ledger.request_dir(req['request_id'])/'response.md').write_text('tampered', encoding='utf-8')
        self.diagnose('LOCAL_STATE_ERROR')

    def test_wrong_receipt_is_not_recoverable(self):
        req = self.prepare()
        self.ledger.dispatch(req['request_id'])
        self.ledger.complete(req['request_id'], self.reply(req))
        state = self.ledger.state(); state['active_request'] = req['request_id']
        module.write_json(self.ledger.state_path, state)
        path = self.ledger.request_dir(req['request_id'])/'receipt.json'
        receipt = module.read_json(path); receipt['request_id'] = self.source
        module.write_json(path, receipt)
        self.diagnose('LOCAL_STATE_ERROR')

    def test_cli_read_only_with_unicode_path(self):
        project = self.base/'測試專案'; project.mkdir()
        before = self.snapshot()
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--project', str(project),
                              '--store', str(self.ledger.store), 'doctor'],
                             capture_output=True, text=True, encoding='utf-8', timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)['status'], 'SETUP_REQUIRED')
        self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
