"""Install/reuse a per-user loopback receiver; safe to run from any project."""
from pathlib import Path
import json,secrets,subprocess,sys,urllib.request,shutil,time,os
root=Path(__file__).resolve().parent
home=Path.home();directory=home/'.codex/pro-inbox';runtime=directory/'runtime';runtime.mkdir(parents=True,exist_ok=True)
for name in ['relay.py','setup_relay.py']:
 source=root/name;destination=runtime/name
 if source.resolve()!=destination.resolve():shutil.copy2(source,destination)
config_path=directory/'config.json'
config=json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {'token':secrets.token_urlsafe(32),'port':18765,'inbox':str(directory/'results'),'downloads':str(home/'Downloads'),'sessions':str(home/'.codex/sessions')}
config.update(projects_root=str(home/'.codex/pro-handoff/projects'),notification_mode='active_wait')
config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
# Only the installed extension receives the machine-local secret; never print it.
if (root/'extension').is_dir():
 (root/'extension/local-config.js').write_text('// Machine-local secret; do not publish.\nconst RELAY = '+json.dumps({'url':'http://127.0.0.1:'+str(config['port']),'token':config['token']})+';\n',encoding='utf-8')
request=urllib.request.Request('http://127.0.0.1:'+str(config['port'])+'/health',headers={'Authorization':'Bearer '+config['token']})
def healthy():
 with urllib.request.urlopen(request,timeout=2) as response:
  data=json.load(response)
  if not data.get('multi_project') or data.get('notification_mode')!='active_wait':raise RuntimeError('An older receiver is running; verified process restart required')
  return data
try:
 healthy();print('ALREADY_RUNNING');sys.exit(0)
except (urllib.error.URLError,TimeoutError):pass
with (directory/'service.log').open('ab') as log:
 process=subprocess.Popen([sys.executable,'-X','utf8',str(runtime/'relay.py'),'--config',str(config_path)],stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
(directory/'process.json').write_text(json.dumps({'pid':process.pid,'script':str(runtime/'relay.py')}),encoding='utf-8')
for _ in range(20):
 try:healthy();print('STARTED',process.pid);break
 except urllib.error.URLError:
  if process.poll() is not None:raise RuntimeError('Receiver exited; inspect service.log')
  time.sleep(.2)
else:raise RuntimeError('Receiver health not ready')
