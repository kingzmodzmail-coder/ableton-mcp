"""Import audition A/B and three editable rendered layers into Live Session."""
import json
from pathlib import Path
from ableton_cmd import send_command as send

root=Path('.producer/projects/how-about-everyone-else/passage-v2')
quality=json.loads((root/'quality.json').read_text())
snapshot=send('get_session_snapshot')
journal=root/'live-journal.jsonl'
assert not journal.exists(), 'Import already attempted; inspect journal'
assert snapshot['track_count']<=12, 'Insufficient free tracks in Live Intro'
(root/'before-live.json').write_text(json.dumps(snapshot,indent=2))
def cmd(name,params):
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,params=params,status='pending'))+'\n')
    result=send(name,params,timeout=90)
    with journal.open('a') as f:f.write(json.dumps(dict(command=name,status='done',result=result))+'\n')
    return result
cmd('stop_playback',{})
cmd('set_tempo',{'tempo':quality['bpm']})
first=snapshot['track_count']
tracks=[('EVERYONE v2 - A B TEST',['A - Original 16 maten.wav','B - Nieuwe acid en drums 16 maten.wav']),
        ('v2 - Bron behouden',['01 Bron behouden.wav']),
        ('v2 - Nieuwe acid',['02 Nieuwe acid.wav']),
        ('v2 - Nieuwe drums',['03 Nieuwe drums.wav'])]
for offset,(name,files) in enumerate(tracks):
    index=first+offset
    cmd('create_audio_track',{'index':-1})
    cmd('set_track_name',{'track_index':index,'name':name})
    for slot,filename in enumerate(files):
        target=dict(track_index=index,clip_index=slot)
        cmd('create_audio_clip',{**target,'path':str((root/filename).resolve())})
        cmd('set_clip_audio',{**target,'warping':False})
        cmd('set_clip_loop',{**target,'looping':False,'start_marker':0,'end_marker':quality['duration_s']})
        cmd('set_clip_name',{**target,'name':Path(filename).stem})
        info=send('get_clip_info',target)
        assert info['warping'] is False and info['looping'] is False
        assert abs(info['end_marker']-quality['duration_s'])<.005
    print('Ready: '+name,flush=True)
for track in snapshot['tracks']:
    if track['soloed']:cmd('set_track_solo',{'track_index':track['index'],'solo':False})
cmd('set_track_solo',{'track_index':first,'solo':True})
after=send('get_session_snapshot')
(root/'after-live.json').write_text(json.dumps(after,indent=2))
# A and B occupy two clips on the same soloed track: starting one replaces the
# other, so the comparison cannot double the two full mixes.
cmd('fire_clip',{'track_index':first,'clip_index':1})
print('B audition launched on track '+str(first),flush=True)
