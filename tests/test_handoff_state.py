import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import uuid

SCRIPT = Path(__file__).resolve().parents[1] / 'skill/cj-chatgpt-handoff/scripts/handoff_state.py'
spec = importlib.util.spec_from_file_location('handoff_state', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.project = self.base / 'project-a'
        self.project.mkdir()
        self.ledger = module.Ledger(self.project, self.base / 'state')
        self.chat = str(uuid.uuid4())
        self.source = str(uuid.uuid4())
        self.old_turn = str(uuid.uuid4())
        self.before = {'thread': {'id': self.chat, 'kind': 'chatgpt', 'status': {'type': 'idle'}},
                       'turns': [{'id': self.old_turn}]}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self):
        with self.ledger.lock():
            self.ledger.bind(self.chat, 'ui', 'TEST FIXTURE: selected 6 Pro')
            return self.ledger.prepare(self.source, 'Find the error in sum(xs) / (len(xs) - 1).', self.before)

    def reply(self, req, status='completed'):
        prompt = Path(req['prompt_path']).read_text(encoding='utf-8')
        return {'thread': self.before['thread'], 'turns': [{
            'id': str(uuid.uuid4()), 'status': status, 'error': None,
            'items': [{'type': 'userMessage', 'content': [{'type': 'text', 'text': prompt}]},
                      {'type': 'agentMessage', 'text': 'Use len(xs), and reject an empty list.'}]}]}

    def test_status_does_not_create_files(self):
        self.assertIsNone(self.ledger.status()['binding'])
        self.assertFalse(self.ledger.store.exists())

    def test_unknown_model_cannot_prepare(self):
        with self.assertRaises(ValueError):
            self.ledger.prepare(self.source, 'test', self.before)

    def test_success_persists_across_process_instances(self):
        req = self.prepare()
        with self.ledger.lock():
            self.ledger.dispatch(req['request_id'])
        restarted = module.Ledger(self.project, self.ledger.store)
        with restarted.lock():
            receipt = restarted.complete(req['request_id'], self.reply(req))
        self.assertTrue(receipt['transport_verified'])
        self.assertFalse(receipt['backend_model_independently_verified'])
        self.assertIsNone(restarted.state()['active_request'])
        self.assertTrue((restarted.request_dir(req['request_id']) / 'response.md').exists())

    def test_duplicate_dispatch_and_pending_rebind_rejected(self):
        req = self.prepare()
        with self.ledger.lock():
            self.ledger.dispatch(req['request_id'])
        restarted = module.Ledger(self.project, self.ledger.store)
        with self.assertRaises(ValueError):
            restarted.dispatch(req['request_id'])
        with self.assertRaises(ValueError):
            restarted.bind(self.chat, 'ui', 'test')

    def test_cross_project_chat_reuse_rejected(self):
        self.prepare()
        other = self.base / 'project-b'
        other.mkdir()
        second = module.Ledger(other, self.ledger.store)
        self.assertNotEqual(second.key, self.ledger.key)
        with self.assertRaises(ValueError):
            second.bind(self.chat, 'ui', 'test')

    def test_old_wrong_pending_and_duplicate_turns_rejected(self):
        req = self.prepare()
        self.ledger.dispatch(req['request_id'])
        cases = []
        old = self.reply(req)
        old['turns'][0]['id'] = self.old_turn
        cases.append(old)
        wrong = self.reply(req)
        wrong['thread'] = {**wrong['thread'], 'id': str(uuid.uuid4())}
        cases.append(wrong)
        cases.append(self.reply(req, 'inProgress'))
        wrong_prompt = self.reply(req)
        wrong_prompt['turns'][0]['items'][0]['content'][0]['text'] = 'Unrelated ' + req['request_id']
        cases.append(wrong_prompt)
        duplicate = self.reply(req)
        duplicate['turns'].append(copy.deepcopy(duplicate['turns'][0]))
        duplicate['turns'][1]['id'] = str(uuid.uuid4())
        cases.append(duplicate)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                self.ledger.complete(req['request_id'], case)
        self.assertEqual(self.ledger.state()['active_request'], req['request_id'])

    def test_modified_prompt_not_sent(self):
        req = self.prepare()
        Path(req['prompt_path']).write_text('Changed after review', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.ledger.dispatch(req['request_id'])

    def test_native_line_endings_and_trimmed_final_newline(self):
        req = self.prepare()
        self.ledger.dispatch(req['request_id'])
        reply = self.reply(req)
        item = reply['turns'][0]['items'][0]['content'][0]
        item['text'] = item['text'].rstrip('\n').replace('\n', '\r\n')
        receipt = self.ledger.complete(req['request_id'], reply)
        self.assertTrue(receipt['transport_verified'])
        import hashlib
        response = self.ledger.request_dir(req['request_id']) / 'response.md'
        self.assertEqual(receipt['response_sha256'], hashlib.sha256(response.read_bytes()).hexdigest())

    def test_completed_retry_recovers_active_pointer(self):
        req = self.prepare()
        self.ledger.dispatch(req['request_id'])
        self.ledger.complete(req['request_id'], self.reply(req))
        state = self.ledger.state()
        state['active_request'] = req['request_id']
        module.write_json(self.ledger.state_path, state)
        self.ledger.complete(req['request_id'], {})
        self.assertIsNone(self.ledger.state()['active_request'])

    def test_pending_target_rejected(self):
        self.ledger.bind(self.chat, 'ui', 'test')
        busy = copy.deepcopy(self.before)
        busy['thread']['status']['type'] = 'active'
        with self.assertRaises(ValueError):
            self.ledger.prepare(self.source, 'test', busy)

    def test_tool_wrapper_supported(self):
        wrapped = {'content': [{'type': 'text', 'text': json.dumps(self.before)}]}
        self.assertEqual(module.unwrap(wrapped), self.before)

    def test_lock_prevents_overlapping_writes(self):
        with self.ledger.lock():
            with self.assertRaises(ValueError):
                with self.ledger.lock():
                    pass

    def test_resolution_preserves_request_and_requires_model_recheck(self):
        req = self.prepare()
        self.ledger.release(req['request_id'], 'Test fixture was never sent')
        self.assertTrue(Path(req['prompt_path']).exists())
        self.assertIsNone(self.ledger.state()['active_request'])
        with self.assertRaises(ValueError):
            self.ledger.prepare(self.source, 'test', self.before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
