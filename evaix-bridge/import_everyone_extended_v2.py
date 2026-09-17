"""Import full review mix and separately editable extension layers to Session."""
import json
from pathlib import Path
from ableton_cmd import send_command as send

root=Path('.producer/projects/how-about-everyone-else/extended-v2')
m=json.loads((root/'manifest.json').read_text())
journal=root/'live-journal.jsonl'
assert not journal.exists(), 'Inspect existing journal before any retry'
before=send('get_session_snapshot')
assert before['track_count']==15
assert before['tracks'][11]['name']=='EVERYONE v2 - A B TEST'
for index in (12,13,14):
    info=send('get_track_info',{'track_index':index})
    assert not info['clip_slots'][1]['has_clip'] and not info['clip_slots'][2]['has_clip']
(root/'before-live.json').write_text(json.dumps(before,indent=2))
def cmd(name,params):
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,params=params,status='pending'))+'\n')
    result=send(name,params,timeout=120)
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,status='done',result=result))+'\n')
    return result
cmd('create_audio_track',{'index':-1})
cmd('set_track_name',{'track_index':15,'name':'EVERYONE - Extended B v2 - 6m13'})
entries=[(15,0,'HOW ABOUT EVERYONE ELSE - Extended B v2.wav',m['duration_s']),
         (13,1,'New 64 bars - acid.wav',m['new_duration_s']),
         (14,1,'New 64 bars - drums.wav',m['new_duration_s']),
         (12,1,'New 64 bars - bass.wav',m['new_duration_s']),
         (12,2,'New 64 bars - fx.wav',m['new_duration_s'])]
verified=[]
for track,slot,file,duration in entries:
    target=dict(track_index=track,clip_index=slot)
    cmd('create_audio_clip',{**target,'path':str((root/file).resolve())})
    cmd('set_clip_audio',{**target,'warping':False})
    cmd('set_clip_loop',{**target,'looping':False,'start_marker':0,'end_marker':duration})
    cmd('set_clip_name',{**target,'name':Path(file).stem})
    info=send('get_clip_info',target)
    assert not info['warping'] and not info['looping'] and abs(info['end_marker']-duration)<.005
    verified.append(info)
    print('Verified: '+file,flush=True)
# Keep playback selection untouched: the user receives a Slack preview.
(root/'verified-live-clips.json').write_text(json.dumps(verified,indent=2))
(root/'after-live.json').write_text(json.dumps(send('get_session_snapshot'),indent=2))
