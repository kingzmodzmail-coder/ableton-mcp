"""16-bar revision: preserve source timeline, separate evidence, compose new layers."""
import json
import hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa

ROOT = Path('.producer/projects/how-about-everyone-else/passage-v2')
SOURCE = Path(r'C:\Users\Gebruiker\.codex\codex-remote-attachments\01a092f1-d0de-7e30-81ba-fa19b7d0f1e7\16677F2B-FC2F-4ACD-ABC1-9F2154EF23F2\1-HOW-ABOUT-EVERYONE-ELSE-.mp3')


def prepare():
    ROOT.mkdir(parents=True, exist_ok=True)
    y,sr=sf.read(SOURCE, dtype='float32', always_2d=True)
    analysis=json.loads((ROOT.parent/'analysis.json').read_text())
    beats=np.array(analysis['beat_times'])
    steady=beats[(beats>50)&(beats<155)]
    period=float(np.polyfit(np.arange(len(steady)),steady,1)[0])
    # Select the first main section; refine detected beat to its preceding onset.
    start=float(beats[np.argmin(abs(beats-47.5))])
    mono=librosa.resample(y.mean(axis=1),orig_sr=sr,target_sr=22050)
    onsets=librosa.onset.onset_detect(y=mono,sr=22050,hop_length=128,backtrack=True,units='time')
    nearby=onsets[abs(onsets-start)<.08]
    if len(nearby): start=float(nearby[np.argmin(abs(nearby-start))])
    first=round(start*sr); count=round(64*period*sr)
    x=y[first:first+count]
    sf.write(ROOT/'source-16bars-float.wav',x,sr,subtype='FLOAT')
    pad=round(3*sr); context_start=max(0,first-pad)
    sf.write(ROOT/'separation-context.wav',y[context_start:first+count+pad],sr,subtype='FLOAT')
    chroma=librosa.feature.chroma_stft(y=librosa.resample(x.mean(axis=1),orig_sr=sr,target_sr=22050),sr=22050).mean(axis=1)
    minor=np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
    major=np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
    keys=sorted([(float(np.corrcoef(chroma,np.roll(profile,k))[0,1]),k,mode) for profile,mode in [(minor,'minor'),(major,'major')] for k in range(12)],reverse=True)
    report=dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),source_start_sample=first,
                source_start_s=first/sr,frames=count,sr=sr,bpm=60/period,period=period,
                context_offset=first-context_start,key_candidates=keys[:4],chroma=chroma.tolist())
    (ROOT/'passage.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)


def separate():
    import torch
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    torch.set_num_threads(4)
    torch.manual_seed(0)
    model=get_model('htdemucs')
    model.eval()
    device='cuda' if torch.cuda.is_available() else 'cpu'
    model.to(device)
    y,sr=sf.read(ROOT/'separation-context.wav',dtype='float32',always_2d=True)
    assert sr==model.samplerate
    x=torch.from_numpy(y.T.copy())
    mean=x.mean(); std=x.std()
    print('Separating with htdemucs on '+device,flush=True)
    with torch.no_grad():
        stems=apply_model(model,((x-mean)/std)[None],device=device,shifts=0,split=True,overlap=.25,progress=True)[0].cpu().numpy()
    stems=stems*float(std)+float(mean)/len(model.sources)
    p=json.loads((ROOT/'passage.json').read_text()); offset=p['context_offset']; n=p['frames']
    for name,a in zip(model.sources,stems):
        sf.write(ROOT/('estimated-'+name+'.wav'),a[:,offset:offset+n].T,sr,subtype='FLOAT')
    weights=[]
    for path in (Path(torch.hub.get_dir())/'checkpoints').glob('*.th'):
        weights.append(dict(name=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (ROOT/'separation.json').write_text(json.dumps(dict(model='htdemucs',demucs='4.0.1',torch=torch.__version__,device=device,weights=weights,sources=model.sources,shifts=0,overlap=.25),indent=2))
    print('Stem separation complete',flush=True)


def compose():
    from scipy.signal import butter, sosfilt, sawtooth
    import struct
    p=json.loads((ROOT/'passage.json').read_text()); sr=p['sr']; n=p['frames']; period=p['period']
    original,_=sf.read(ROOT/'source-16bars-float.wav',always_2d=True)
    stems={name:sf.read(ROOT/('estimated-'+name+'.wav'),always_2d=True)[0] for name in ['drums','bass','other','vocals']}
    residual=original-sum(stems.values())
    assert np.max(abs(original-(sum(stems.values())+residual)))<1e-10
    # All source samples remain in order. Retain vocal/music estimates and the
    # separation residual; make a little space in drums and bass for new parts.
    base=.82*stems['drums']+.93*stems['bass']+stems['other']+stems['vocals']+residual
    acid=np.zeros_like(original); drums=np.zeros_like(original)
    notes=[]; hits=[]
    tonic=int(p['key_candidates'][0][1])+48
    def add(target,sound,beat,level=1,pan=0):
        start=round(beat*period*sr)
        if start>=n:return
        a=np.asarray(sound)
        if a.ndim==1:a=np.column_stack([a,a])
        a=a[:n-start]*level
        a[:,0]*=min(1,1-pan); a[:,1]*=min(1,1+pan)
        target[start:start+len(a)]+=a
    # Composed call/response: rests in the first phrase, an octave answer in
    # bars 5-8, and a denser variation in bars 9-16. No copied source phrase.
    patterns=[[(.75,0,.22),(2.5,7,.18),(3.25,0,.28)],
              [(.5,0,.18),(1.75,12,.3),(3,7,.28)],
              [(.75,0,.2),(1.5,7,.16),(2.75,12,.3),(3.5,7,.18)],
              [(.5,0,.25),(1.75,7,.18),(2.5,12,.2),(3.25,0,.5)]]
    last_pitch=tonic
    for bar in range(16):
        for j,(offset,interval,duration) in enumerate(patterns[(bar//4)%4]):
            if bar<4 and bar%2==0 and j==1:continue
            pitch=tonic+interval
            count=round((duration*period+.09)*sr); t=np.arange(count)/sr
            freq=440*2**((pitch-69)/12)
            f=np.full(count,freq)
            if j==2:
                glide=min(count,round(.035*sr)); f[:glide]=np.geomspace(440*2**((last_pitch-69)/12),freq,glide)
            phase=2*np.pi*np.cumsum(f)/sr
            raw=.7*sawtooth(phase)+.3*np.sin(phase)
            cutoff=650+(bar/15)*1500+(350 if j==0 else 0)
            shaped=sosfilt(butter(2,cutoff,fs=sr,output='sos'),raw)
            resonant=sosfilt(butter(2,[cutoff*.72,cutoff*1.15],btype='bandpass',fs=sr,output='sos'),raw)
            env=np.minimum(1,t/.004)*np.exp(-t/(duration*period*.6))
            sound=np.tanh(1.6*(shaped+.7*resonant))*env
            add(acid,sound,bar*4+offset,.11 if bar<8 else .14,pan=.12 if bar%2 else -.12)
            notes.append(dict(pitch=pitch,start_time=bar*4+offset,duration=duration,velocity=90 if j else 108,mute=False))
            last_pitch=pitch
    dry=acid.copy()
    delay=round(.75*period*sr)
    acid[delay:]+=.2*dry[:-delay,::-1]
    samples=ROOT.parents[1]/'mental-acid-001'/'samples'
    def sample(name,highpass):
        a,r=sf.read(samples/name,always_2d=True)
        if r!=sr:a=librosa.resample(a,orig_sr=r,target_sr=sr,axis=0)
        return sosfilt(butter(2,highpass,btype='highpass',fs=sr,output='sos'),a,axis=0)
    kick=sample('MTLOX - MTDN Kick 03.wav',160)
    hat=sample('MTLOX - Hihat 03.wav',2800)
    perc=sample('MTLOX - Percussion 05.wav',450)
    snare=sample('MTLOX - Snare 05.wav',650)
    for bar in range(16):
        for beat in range(4):
            add(drums,kick,bar*4+beat,.11)
            hits.append(dict(instrument='kick transient',beat=bar*4+beat))
        for offset in ([.5,2.5] if bar<8 else [.5,1.5,2.5,3.5]):
            add(drums,hat,bar*4+offset,.065,pan=.2)
            hits.append(dict(instrument='hat',beat=bar*4+offset))
        for offset in ([1.75,3.25] if bar%2 else [2.75]):
            add(drums,perc,bar*4+offset,.11,pan=-.2)
            hits.append(dict(instrument='percussion',beat=bar*4+offset))
        if bar in (7,15):
            for j,offset in enumerate([2.75,3.25,3.5,3.75]):
                add(drums,snare,bar*4+offset,.06+j*.02)
                hits.append(dict(instrument='snare fill',beat=bar*4+offset))
    # Shared short edge fades are for audition only, not hidden section edits.
    fade=np.ones(n); edge=round(.005*sr)
    fade[:edge]=np.linspace(0,1,edge); fade[-edge:]=np.linspace(1,0,edge)
    a=original*fade[:,None]; b=(base+acid+drums)*fade[:,None]
    rms=lambda x:float(np.sqrt(np.mean(x*x)))
    match=rms(a)/rms(b)
    gain=10**(-3/20)/max(abs(a).max(),abs(b*match).max())
    a*=gain; b*=match*gain
    sf.write(ROOT/'A - Original 16 maten.wav',a,sr,subtype='PCM_24')
    sf.write(ROOT/'B - Nieuwe acid en drums 16 maten.wav',b,sr,subtype='PCM_24')
    layers={'01 Bron behouden':base,'02 Nieuwe acid':acid,'03 Nieuwe drums':drums}
    for name,arr in layers.items():sf.write(ROOT/(name+'.wav'),arr*fade[:,None]*match*gain,sr,subtype='PCM_24')
    sf.write(ROOT/'A dan B - vergelijking.wav',np.concatenate([a,np.zeros((sr,2)),b]),sr,subtype='PCM_24')
    (ROOT/'acid-notes.json').write_text(json.dumps(notes,indent=2))
    # Standard MIDI export makes the new motif independently editable.
    def vlq(v):
        data=[v&127];v>>=7
        while v:data.insert(0,(v&127)|128);v>>=7
        return bytes(data)
    events=[]
    for note in notes:
        tick=round(note['start_time']*480);end=round((note['start_time']+note['duration'])*480)
        events.extend([(tick,bytes([0x90,note['pitch'],note['velocity']])),(end,bytes([0x80,note['pitch'],0]))])
    track=b'\x00\xff\x51\x03'+round(60000000/p['bpm']).to_bytes(3,'big'); previous=0
    for tick,event in sorted(events,key=lambda e:e[0]):track+=vlq(tick-previous)+event;previous=tick
    track+=vlq(64*480-previous)+b'\xff\x2f\x00'
    (ROOT/'Nieuwe acid 16 maten.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
    quality=dict(duration_s=n/sr,bpm=p['bpm'],source_range_s=[p['source_start_s'],p['source_start_s']+n/sr],
                 source_samples_preserved_in_order=True,estimated_stems_only=True,acid_notes=len(notes),new_drum_hits=len(hits),
                 a_rms=rms(a),b_rms=rms(b),rms_difference_db=20*np.log10(rms(b)/rms(a)),
                 a_peak=float(abs(a).max()),b_peak=float(abs(b).max()),comparison='RMS matched; not a LUFS measurement',
                 source_gain=gain,remix_match_gain=match,tonic_midi=tonic,key_status='uncertain working hypothesis')
    assert len(a)==len(b)==n and abs(quality['rms_difference_db'])<.001
    assert max(quality['a_peak'],quality['b_peak'])<.71
    reconstructed=sum(sf.read(ROOT/(name+'.wav'),always_2d=True)[0] for name in layers)
    assert abs(reconstructed-b).max()<1e-6
    (ROOT/'quality.json').write_text(json.dumps(quality,indent=2))
    print(json.dumps(quality,indent=2),flush=True)


if __name__=='__main__':
    import sys
    {'prepare':prepare,'separate':separate,'compose':compose}[sys.argv[1]]()
