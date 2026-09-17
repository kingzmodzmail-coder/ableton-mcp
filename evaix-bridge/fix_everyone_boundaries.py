import json
from pathlib import Path
from ableton_cmd import send_command as cmd
root=Path('.producer/projects/how-about-everyone-else')
m=json.loads((root/'extended-manifest.json').read_text())
info=cmd('get_track_info',{'track_index':10})
assert info['name']=='HOW ABOUT EVERYONE ELSE - EXT v1'
tempo=cmd('get_session_info')['tempo']
clips=cmd('get_arrangement_clips',{'track_index':10})['clips']
assert len(clips)==8 and all(c['file_path'].startswith(str(root.resolve())) for c in clips)
# Only rebuild clips created by this task; sources and Session clips remain.
for i in reversed(range(8)):
    cmd('delete_arrangement_clip',{'track_index':10,'arrangement_clip_index':i})
for i,s in enumerate(m['sections']):
    cmd('set_clip_loop',{'track_index':10,'clip_index':i,'looping':False,'start_marker':0,'end_marker':s['duration_s']*tempo/60})
    cmd('duplicate_session_clip_to_arrangement',{'track_index':10,'clip_index':i,'destination_time':s['start_s']*tempo/60})
after=cmd('get_arrangement_clips',{'track_index':10})
for c,s in zip(after['clips'],m['sections']):
    assert abs(c['start_time']-s['start_s']*tempo/60)<.001
    assert abs(c['end_time']-(s['start_s']+s['duration_s'])*tempo/60)<.001
(root/'verified-live-arrangement.json').write_text(json.dumps(after,indent=2))
cmd('set_current_song_time',{'time':0})
print('Verified eight contiguous clips, total %.2f seconds' % m['duration_s'])
