"""Create an editable extended stereo arrangement, with source provenance."""
import json
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt
from ableton_cmd import send_command

root = Path('.producer/projects/how-about-everyone-else')
source = Path(r'C:\Users\Gebruiker\.codex\codex-remote-attachments\01a092f1-d0de-7e30-81ba-fa19b7d0f1e7\16677F2B-FC2F-4ACD-ABC1-9F2154EF23F2\1-HOW-ABOUT-EVERYONE-ELSE-.mp3')
y, sr = sf.read(source, dtype='float32', always_2d=True)
assert np.isfinite(y).all()
report = json.loads((root / 'analysis.json').read_text())
beats = np.asarray(report['beat_times'])
# Fit the steady main groove, avoiding intro and final silence.
steady = beats[(beats > 50) & (beats < 155)]
period = float(np.polyfit(np.arange(len(steady)), steady, 1)[0])
bpm = 60 / period
assert 155 < bpm < 170
length = round(64 * period * sr)
def cut(t, count):
    i = round(t * sr)
    return y[i:i+count].copy()
def nearest(t):
    return float(beats[np.argmin(abs(beats-t))])
intro_end, break_start, outro_start = [round(nearest(t)*sr) for t in (47.5,165,267)]
intro = cut(nearest(48), length)
low = sosfilt(butter(2, 900, fs=sr, output='sos'), intro, axis=0)
mix = np.linspace(0, .75, len(intro))[:,None]
intro = (low*(1-mix)+intro*mix)*np.linspace(.22,.65,len(intro))[:,None]
breakdown = cut(nearest(166), length)
filtered = sosfilt(butter(2, [350,3500], btype='bandpass', fs=sr, output='sos'), breakdown, axis=0)
breakdown = filtered * np.linspace(.48,.85,len(filtered))[:,None]
# A one-beat vacuum before the original breakdown strengthens the transition.
breakdown[-round(period*sr):] *= np.linspace(1,0,round(period*sr))[:,None]
climax = cut(nearest(235), length)
outro = cut(nearest(235), length)
low = sosfilt(butter(2, 1100, fs=sr, output='sos'), outro, axis=0)
mix = np.linspace(0,1,len(outro))[:,None]
outro = (outro*(1-mix)+low*mix)*np.linspace(.85,.08,len(outro))[:,None]
sections = [('01 DJ intro',intro),('02 Original intro',y[:intro_end].copy()),
            ('03 Main movement',y[intro_end:break_start].copy()),('04 Tension extension',breakdown),
            ('05 Breakdown and return',y[break_start:outro_start].copy()),('06 Extra climax',climax),
            ('07 DJ outro',outro),('08 Original tail',y[outro_start:].copy())]
gain = 10**(-2/20) / max(float(abs(a).max()) for _,a in sections)
manifest=[]
position=0
for name,a in sections:
    n=min(round(.008*sr),len(a)//2)
    a[:n]*=np.linspace(0,1,n)[:,None]
    a[-n:]*=np.linspace(1,0,n)[:,None]
    a*=gain
    path=root/(name+'.wav')
    sf.write(path,a,sr,subtype='PCM_24')
    manifest.append(dict(name=name,path=str(path.resolve()),start_s=position/sr,duration_s=len(a)/sr))
    position+=len(a)
sf.write(root/'HOW ABOUT EVERYONE ELSE - Extended v1.wav',np.concatenate([a for _,a in sections]),sr,subtype='PCM_24')
(root/'extended-manifest.json').write_text(json.dumps(dict(bpm_estimate=bpm,original_duration_s=len(y)/sr,duration_s=position/sr,gain=gain,sections=manifest),indent=2))
print(json.dumps(dict(bpm=bpm,original_seconds=len(y)/sr,extended_seconds=position/sr,sections=manifest)),flush=True)

# Preserve the other song's global tempo; unwarped clips retain original pitch
# and speed, with arrangement positions converted using the current Live tempo.
before=send_command('get_session_info')
assert not before['is_playing'], 'Playback started; import paused'
(root/'before-live-import.json').write_text(json.dumps(before,indent=2))
journal=root/'import-journal.jsonl'
assert not journal.exists(), 'Import started previously; inspect journal'
def command(cmd,params):
    with journal.open('a') as f: f.write(json.dumps(dict(command=cmd,params=params,status='pending'))+'\n')
    result=send_command(cmd,params,timeout=90)
    with journal.open('a') as f: f.write(json.dumps(dict(command=cmd,status='done',result=result))+'\n')
    return result
index=before['track_count']
command('create_audio_track',{'index':-1})
command('set_track_name',{'track_index':index,'name':'HOW ABOUT EVERYONE ELSE - EXT v1'})
for slot,s in enumerate(manifest):
    target=dict(track_index=index,clip_index=slot)
    command('create_audio_clip',{**target,'path':s['path']})
    command('set_clip_audio',{**target,'warping':False})
    command('set_clip_loop',{**target,'looping':False})
    command('set_clip_name',{**target,'name':s['name']})
    command('duplicate_session_clip_to_arrangement',{**target,'destination_time':s['start_s']*before['tempo']/60})
    print('Imported '+s['name'],flush=True)
clips=send_command('get_arrangement_clips',{'track_index':index})
(root/'after-live-import.json').write_text(json.dumps(clips,indent=2))
print(json.dumps(clips),flush=True)
command('set_track_solo',{'track_index':index,'solo':True})
command('switch_to_arrangement_view',{})
