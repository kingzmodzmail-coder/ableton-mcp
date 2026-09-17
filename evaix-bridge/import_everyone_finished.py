"""Add final mix without replacing earlier auditions; verify full duration."""
import json
from pathlib import Path
from ableton_cmd import send_command as send

root=Path('.producer/projects/how-about-everyone-else/finished-v3')
m=json.loads((root/'manifest.json').read_text())
journal=root/'live-journal.jsonl'
assert not journal.exists(),'Inspect previous import before retry'
before=send('get_session_snapshot')
assert before['tracks'][15]['name']=='EVERYONE - Extended B v2 - 6m13'
info=send('get_track_info',{'track_index':15})
assert not info['clip_slots'][1]['has_clip']
(root/'before-live.json').write_text(json.dumps(before,indent=2))
def cmd(name,params):
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,params=params,status='pending'))+'\n')
    result=send(name,params,timeout=120)
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,status='done',result=result))+'\n')
    return result
target=dict(track_index=15,clip_index=1)
cmd('create_audio_clip',{**target,'path':str((root/'HOW ABOUT EVERYONE ELSE - Finished Extended Mix.wav').resolve())})
cmd('set_clip_audio',{**target,'warping':False})
cmd('set_clip_loop',{**target,'looping':False,'start_marker':0,'end_marker':m['duration_s']})
cmd('set_clip_name',{**target,'name':'FINISHED Extended Mix - 6m20'})
cmd('set_track_name',{'track_index':15,'name':'EVERYONE - FINISHED 6m20'})
verified=send('get_clip_info',target)
assert not verified['warping'] and not verified['looping'] and abs(verified['end_marker']-m['duration_s'])<.005
(root/'verified-live-clip.json').write_text(json.dumps(verified,indent=2))
print(json.dumps(verified,indent=2),flush=True)
# Publish a single continuous full-length Arrangement clip only on this
# dedicated track and only when its arrangement is empty.
arr=send('get_arrangement_clips',{'track_index':15})
(root/'arrangement-before.json').write_text(json.dumps(arr,indent=2))
print('Arrangement before: '+json.dumps(arr),flush=True)
result=cmd('try_save_project',{})
(root/'save-result.json').write_text(json.dumps(result,indent=2))
print('Save capability: '+json.dumps(result),flush=True)
