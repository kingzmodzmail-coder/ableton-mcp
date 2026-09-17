"""Add v4 auditions into unused Session slots, preserving earlier versions."""
import json
from pathlib import Path
from ableton_cmd import send_command as send
root=Path('.producer/projects/how-about-everyone-else/ending-development-v4')
m=json.loads((root/'manifest.json').read_text());journal=root/'live-journal.jsonl'
assert not journal.exists(),'Inspect existing import journal before retry'
before=send('get_track_info',{'track_index':15})
assert before['name']=='EVERYONE - FINISHED 6m20'
assert all(not before['clip_slots'][i]['has_clip'] for i in [2,3])
(root/'before-live.json').write_text(json.dumps(before,indent=2))
def cmd(name,params):
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,params=params,status='pending'))+'\n')
    r=send(name,params,timeout=120)
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,status='done',result=r))+'\n')
    return r
verified=[]
for slot,label in [(2,'Long Ending Mix'),(3,'Ending Development Only')]:
    target=dict(track_index=15,clip_index=slot);duration=m['deliveries'][label]['duration_s']
    cmd('create_audio_clip',{**target,'path':str((root/('HOW ABOUT EVERYONE ELSE - '+label+'.wav')).resolve())})
    cmd('set_clip_audio',{**target,'warping':False})
    cmd('set_clip_loop',{**target,'looping':False,'start_marker':0,'end_marker':duration})
    cmd('set_clip_name',{**target,'name':'v4 - '+label})
    result=send('get_clip_info',target)
    assert not result['warping'] and not result['looping'] and abs(result['end_marker']-duration)<.005
    verified.append(result);print('Verified: '+label,flush=True)
(root/'verified-live.json').write_text(json.dumps(verified,indent=2))
