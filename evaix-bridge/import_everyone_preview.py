from pathlib import Path
from ableton_cmd import send_command as cmd
root=Path('.producer/projects/how-about-everyone-else')
s=cmd('get_session_info')
assert not s['is_playing']
i=s['track_count']
cmd('create_audio_track',{'index':-1})
cmd('set_track_name',{'track_index':i,'name':'EVERYONE ELSE - FULL 6m13 PREVIEW'})
cmd('create_audio_clip',{'track_index':i,'clip_index':0,'path':str((root/'HOW ABOUT EVERYONE ELSE - Extended v1.wav').resolve())},timeout=90)
cmd('set_clip_audio',{'track_index':i,'clip_index':0,'warping':False})
cmd('set_clip_loop',{'track_index':i,'clip_index':0,'looping':False,'start_marker':0,'end_marker':372.9002721088435})
cmd('set_track_solo',{'track_index':10,'solo':False})
cmd('set_track_solo',{'track_index':i,'solo':True})
print(cmd('get_clip_info',{'track_index':i,'clip_index':0}))
