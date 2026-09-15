"""Per-project access to the shared Pro receiver. Waiting never invokes a model."""
import argparse,hashlib,json,subprocess,sys,time,urllib.request
from pathlib import Path
from handoff_state import Ledger,read_json,write_json

def validate_receipt(ledger,rid,config):
    request=ledger.request(rid)
    directory=Path(config['inbox']).resolve()/rid
    path=directory/'receipt.json'
    if not path.exists():return None
    receipt=read_json(path)
    if receipt['request_id']!=rid or receipt['source_thread']!=request['source_thread_id'] or receipt['conversation']!=request['target_thread_id']:
        raise ValueError('Receipt belongs to another request or thread')
    if Path(receipt['project_ledger']).resolve()!=ledger.directory.resolve():raise ValueError('Wrong project ledger')
    response=Path(receipt['response_path']).resolve()
    if response!=directory/'response.txt':raise ValueError('Unexpected response path')
    if hashlib.sha256(response.read_bytes()).hexdigest()!=receipt['response_sha256']:raise ValueError('Response checksum mismatch')
    for item in receipt.get('files',[]):
        f=Path(item['path']).resolve();allowed=Path(config['downloads']).resolve()/'CodexProInbox'/rid
        if not f.is_relative_to(allowed) or hashlib.sha256(f.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Attachment integrity failed')
    return path,receipt

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('ensure')
    wait=sub.add_parser('wait');wait.add_argument('--request',required=True);wait.add_argument('--timeout',type=int,default=2400)
    args=parser.parse_args();ledger=Ledger(args.project)
    base=Path.home()/'.codex/pro-inbox'
    if args.command=='ensure':
        subprocess.run([sys.executable,'-X','utf8',str(base/'runtime/setup_relay.py')],check=True)
        config=read_json(base/'config.json')
        req=urllib.request.Request('http://127.0.0.1:'+str(config['port'])+'/health',headers={'Authorization':'Bearer '+config['token']})
        with urllib.request.urlopen(req,timeout=3) as r:health=json.load(r)
        print(json.dumps({'project':ledger.root,'registered':bool(ledger.state()['binding']),'health':health},ensure_ascii=False));return
    if not 1<=args.timeout<=2400:raise ValueError('timeout must be 1..2400 seconds')
    config=read_json(base/'config.json');ledger.request(args.request)
    end=time.monotonic()+args.timeout
    while True:
        result=validate_receipt(ledger,args.request,config)
        if result:
            path,receipt=result
            receipt['notification']='received_by_active_codex_turn';write_json(path,receipt)
            print(json.dumps({'status':'received','receipt':str(path),'response':receipt['response_path'],'files':receipt['files']},ensure_ascii=False),flush=True);return
        if time.monotonic()>=end:
            print(json.dumps({'status':'still_pending','request':args.request,'receiver_continues':True}),flush=True);return
        time.sleep(1)

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,subprocess.CalledProcessError) as e:
        print(json.dumps({'ok':False,'error':str(e)},ensure_ascii=False));sys.exit(1)
