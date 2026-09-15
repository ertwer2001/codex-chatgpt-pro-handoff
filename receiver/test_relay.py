import hashlib,json,tempfile,unittest,threading,urllib.request,urllib.error,shutil
from pathlib import Path
from http.server import HTTPServer
from relay import Receiver,save,handler

RID='33333333-4444-4555-8666-777777777777';THREAD='11111111-2222-4333-8444-555555555555';CHAT='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.config={k:str(self.root/k) for k in ['ledger','inbox','downloads','sessions','project']};self.config.update(token='test-token',port=0,codex_exe='codex.exe')
  self.r=Receiver(self.config);p=self.root/'ledger/requests'/RID;p.mkdir(parents=True)
  self.prompt='Request-ID: '+RID+'\n需求';(p/'request.md').write_text(self.prompt,encoding='utf-8')
  save(p/'request.json',dict(request_id=RID,status='dispatching',target_thread_id=CHAT,source_thread_id=THREAD,prompt_sha256=hashlib.sha256(self.prompt.encode()).hexdigest()))
  self.data=dict(request=RID,conversation=CHAT,prompt=self.prompt,text='Request-ID: '+RID+'\n結果',files=[],attachmentExpected=False)
 def tearDown(self):self.tmp.cleanup()
 def test_auto_discovery_and_duplicate(self):
  self.assertEqual(self.r.requests()[0]['request'],RID);self.r.receive(self.data);self.assertEqual(self.r.requests(),[])
  self.assertTrue(self.r.receive(self.data)['duplicate']);self.assertTrue((self.root/'inbox'/RID/'response.txt').exists())
  receipt=json.loads((self.root/'inbox'/RID/'receipt.json').read_text())
  self.assertEqual(hashlib.sha256((self.root/'inbox'/RID/'response.txt').read_bytes()).hexdigest(),receipt['response_sha256'])
 def test_wrong_prompt_and_chat(self):
  for key,value in [('prompt','wrong'),('conversation','wrong'),('text','wrong')]:
   with self.assertRaises(ValueError):self.r.receive({**self.data,key:value})
 def test_multiple_projects_and_no_crosstalk(self):
  projects=self.root/'projects'
  for key in ['project-a','project-b']:
   shutil.copytree(self.root/'ledger',projects/key)
   save(projects/key/'state.json',{'project_key':key,'binding':{'thread_id':CHAT}})
  self.config['projects_root']=str(projects)
  # Duplicate request IDs in two ledgers must be rejected, never routed arbitrarily.
  with self.assertRaises(ValueError):self.r.receive(self.data)
  other='22222222-3333-4444-8555-666666666666'
  d=projects/'project-b/requests';(d/RID).rename(d/other)
  record=json.loads((d/other/'request.json').read_text());record['request_id']=other
  record['target_thread_id']='aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
  save(d/other/'request.json',record)
  self.assertEqual({j['request'] for j in self.r.requests()},{RID,other})
  receipt=Path(self.r.receive(self.data)['receipt'])
  self.assertEqual(json.loads(receipt.read_text())['project_ledger'],str(projects/'project-a'))
  with self.assertRaises(ValueError):self.r.receive({**self.data,'request':other})
 def test_active_wait_never_launches_cli(self):
  self.config['notification_mode']='active_wait'
  path=Path(self.r.receive(self.data)['receipt'])
  self.assertFalse(self.r.notify_once(path,lambda *a,**kw:self.fail('CLI must not launch')))
 def test_files_verified(self):
  p=self.root/'downloads/CodexProInbox'/RID/'a.html';p.parent.mkdir(parents=True);p.write_text('<html>test</html>')
  result=self.r.receive({**self.data,'files':[str(p)],'attachmentExpected':True})
  self.assertEqual(len(json.loads(Path(result['receipt']).read_text())['files']),1)
 def test_no_escape_or_false_attachment(self):
  p=self.root/'outside.html';p.write_text('x')
  with self.assertRaises(ValueError):self.r.receive({**self.data,'files':[str(p)]})
  with self.assertRaises(ValueError):self.r.receive({**self.data,'attachmentExpected':True})
 def test_notify_once_only_when_idle(self):
  receipt=Path(self.r.receive(self.data)['receipt']);s=self.root/'sessions';s.mkdir();session=s/('rollout-'+THREAD+'.jsonl')
  session.write_text(json.dumps({'type':'event_msg','payload':{'type':'task_started'}})+'\n')
  self.assertFalse(self.r.notify_once(receipt,lambda *a,**k:None))
  session.write_text(json.dumps({'type':'event_msg','payload':{'type':'task_complete'}})+'\n')
  calls=[]
  class Process:pid=123
  def launch(args,**kw):calls.append(args);return Process()
  self.assertTrue(self.r.notify_once(receipt,launch));self.assertFalse(self.r.notify_once(receipt,launch));self.assertEqual(len(calls),1)
  self.assertIn(THREAD,calls[0]);self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',calls[0])
 def test_real_http_auth_and_receive(self):
  server=HTTPServer(('127.0.0.1',0),handler(self.r));self.config['port']=server.server_port
  worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start();base=f'http://127.0.0.1:{server.server_port}'
  try:
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/jobs')
   req=urllib.request.Request(base+'/result',data=json.dumps(self.data).encode(),headers={'Authorization':'Bearer test-token','Content-Type':'application/json'})
   self.assertTrue(json.load(urllib.request.urlopen(req))['received'])
  finally:server.shutdown();server.server_close();worker.join()
if __name__=='__main__':unittest.main()
