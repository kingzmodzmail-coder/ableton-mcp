"""Finish the approved extended arrangement; retain a reversible premaster."""
import json
import re
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, sawtooth

ROOT=Path('.producer/projects/how-about-everyone-else/finished-v3')
V2=ROOT.parent/'extended-v2'
P=json.loads((ROOT.parent/'passage-v2/passage.json').read_text())
M=json.loads((V2/'manifest.json').read_text())
SR=44100; PERIOD=P['period']; BAR=4*PERIOD
SAMPLES=ROOT.parents[1]/'mental-acid-001/samples'

def measure(path):
    r=subprocess.run(['ffmpeg','-hide_banner','-i',str(path),'-af','ebur128=peak=true','-f','null','NUL'],capture_output=True,text=True,check=True)
    tail=r.stderr.rsplit('Summary:',1)[1]
    return dict(integrated_lufs=float(re.search(r'I:\s+([-\d.]+)',tail)[1]),
        loudness_range_lu=float(re.search(r'LRA:\s+([-\d.]+)',tail)[1]),
        true_peak_dbfs=float(re.search(r'Peak:\s+([-\d.]+)',tail)[1]))

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    old,sr=sf.read(V2/'HOW ABOUT EVERYONE ELSE - Extended B v2.wav',dtype='float32',always_2d=True)
    assert sr==SR
    origin=P['source_start_s']; insertion=M['insert_at_s']; resume=M['source_resume_s']
    reprise=origin+160*BAR
    outro=origin+216*BAR
    end=outro+8*BAR+2.4
    n=max(len(old),round(end*SR))
    base=np.pad(old,((0,n-len(old)),(0,0)))
    music=np.zeros_like(base);fx=np.zeros_like(base);out=np.zeros_like(base)
    notes=[];rng=np.random.default_rng(20260913)
    def put(target,a,seconds,level=1,pan=0):
        start=round(seconds*SR)
        a=np.asarray(a,dtype=np.float32)
        if a.ndim==1:a=np.column_stack([a,a])
        a=a[:n-start].copy()*level
        a[:,0]*=min(1,1-pan);a[:,1]*=min(1,1+pan)
        target[start:start+len(a)]+=a
    def sample(name,hp=None):
        a,r=sf.read(SAMPLES/name,dtype='float32',always_2d=True);assert r==SR
        if hp:a=sosfilt(butter(2,hp,btype='highpass',fs=SR,output='sos'),a,axis=0)
        a[-220:]*=np.linspace(1,0,220)[:,None]
        return a
    # A beat-synchronous echo carries the approved acid into the breakdown;
    # no extra kick or whole-master repeats are introduced at this seam.
    acid,r=sf.read(ROOT.parent/'passage-v2/02 Nieuwe acid.wav',dtype='float32',always_2d=True)
    tail=acid[-round(2*PERIOD*SR):]
    for j in range(1,6):
        filtered=sosfilt(butter(2,2400/(1+j*.3),fs=SR,output='sos'),tail,axis=0)
        put(fx,filtered,insertion+(j-1)*.75*PERIOD,.42*.62**(j-1),pan=.2 if j%2 else -.2)
    # Finish the return phrase: taper its extra bass, darken its drums, and
    # carry only the acid delay past the join into the existing track.
    start=round(insertion*SR);count=round(M['new_duration_s']*SR)
    bass,_=sf.read(V2/'New 64 bars - bass.wav',dtype='float32',always_2d=True)
    drums,_=sf.read(V2/'New 64 bars - drums.wav',dtype='float32',always_2d=True)
    newacid,_=sf.read(V2/'New 64 bars - acid.wav',dtype='float32',always_2d=True)
    env=np.ones(count,dtype=np.float32);ramp=round(4*BAR*SR)
    env[-ramp:]=np.linspace(1,.25,ramp)
    base[start:start+count]+=bass*(env[:,None]-1)
    dark=sosfilt(butter(2,2400,fs=SR,output='sos'),drums,axis=0).astype(np.float32)
    w=np.zeros(count,dtype=np.float32);w[-ramp:]=np.linspace(0,.55,ramp)
    base[start:start+count]+=(dark-drums)*w[:,None]
    phrase=newacid[-round(2*PERIOD*SR):]
    for j in range(3):put(fx,phrase,resume+j*.75*PERIOD,.28*.5**j)
    impact=sample('MTLOX - Impact 03.wav',350)
    put(fx,impact,resume,.065)
    # Low-level motif reprises connect the late original drop to the new
    # development, while leaving room for its already mastered source parts.
    def acid_note(seconds,pitch,duration,cutoff,level,pan=0):
        t=np.arange(round((duration*PERIOD+.1)*SR))/SR
        phase=2*np.pi*440*2**((pitch-69)/12)*t
        raw=.7*sawtooth(phase)+.3*np.sin(phase)
        low=sosfilt(butter(2,cutoff,fs=SR,output='sos'),raw)
        res=sosfilt(butter(2,[cutoff*.72,cutoff*1.15],btype='bandpass',fs=SR,output='sos'),raw)
        env=np.minimum(1,t/.004)*np.exp(-t/(duration*PERIOD*.6))
        env[-220:]*=np.linspace(1,0,220)
        signal=np.tanh(1.6*(low+.7*res))*env
        put(music,signal,seconds,level,pan)
        put(fx,signal,seconds+.75*PERIOD,level*.18,-pan)
        notes.append(dict(time_s=seconds,pitch=pitch,duration_beats=duration,cutoff_hz=cutoff,level=level))
    for bar in range(16):
        pattern=[(.75,51,.22),(3.25,58,.24)] if bar%2==0 else [(1.75,63,.25)]
        if bar>=12:pattern+=[(2.75,51,.18)]
        for off,pitch,duration in pattern:
            acid_note(reprise+bar*BAR+off*PERIOD,pitch,duration,950+bar*60,.06 if bar<8 else .075,.12 if bar%2 else -.12)
    # An eight-bar percussion outro reduces parts in stages and resolves to
    # a low root with a fading delay. Existing source tail remains underneath.
    kick=sample('MTLOX - MTDN Kick 03.wav',35)
    hat=sample('MTLOX - Hihat 03.wav',2800)
    perc=sample('MTLOX - Percussion 05.wav',500)
    for bar in range(8):
        for beat in (range(4) if bar<4 else ([0,2] if bar<6 else [0])):
            put(out,kick,outro+bar*BAR+beat*PERIOD,.26*(1-bar/9))
        if bar<6:
            for beat in [.5,2.5]:put(out,hat,outro+bar*BAR+beat*PERIOD,.06*(1-bar/7),.15)
        if bar<4:put(out,perc,outro+bar*BAR+2.75*PERIOD,.09*(1-bar/6),-.15)
        if bar in (0,2,4,6):acid_note(outro+bar*BAR+.75*PERIOD,51,.35,1250-bar*110,.08*(1-bar/9))
    acid_note(outro+7*BAR,39,1.4,600,.08)
    # Keep the rumble controlled and the deep bass centered; source musical
    # content and all added layers remain available in the premaster.
    premaster=base+music+fx+out
    premaster=sosfilt(butter(2,24,btype='highpass',fs=SR,output='sos'),premaster,axis=0)
    mid=premaster.mean(axis=1);side=(premaster[:,0]-premaster[:,1])*.5
    side=sosfilt(butter(2,110,btype='highpass',fs=SR,output='sos'),side)
    premaster=np.column_stack([mid+side,mid-side]).astype(np.float32)
    # Explicit fade-in and natural tail, never a dropped source interval.
    edge=round(.008*SR);premaster[:edge]*=np.linspace(0,1,edge)[:,None]
    tailn=round(1.8*SR);premaster[-tailn:]*=np.linspace(1,0,tailn)[:,None]
    assert len(premaster)>=len(old) and np.isfinite(premaster).all()
    pre=ROOT/'HOW ABOUT EVERYONE ELSE - Premaster.wav'
    sf.write(pre,premaster,SR,subtype='FLOAT')
    for name,a in [('Finishing acid',music),('Transition FX',fx),('Outro percussion',out)]:
        sf.write(ROOT/(name+'.wav'),a,SR,subtype='PCM_24')
    print('Arrangement and premaster written',flush=True)
    before=measure(pre)
    boost=min(2.,max(-2.,-10.5-before['integrated_lufs']))
    wav=ROOT/'HOW ABOUT EVERYONE ELSE - Finished Extended Mix.wav'
    # Oversampled lookahead limiter: preserve transient envelope, disable
    # automatic make-up gain, compensate latency, leave MP3 peak headroom.
    filters=f'volume={boost}dB,aresample=176400,alimiter=limit=0.841395:attack=5:release=80:level=false:latency=true,aresample=44100'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(pre),'-af',filters,'-c:a','pcm_s24le',str(wav)],check=True)
    mp3=wav.with_suffix('.mp3')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k','-metadata','title=HOW ABOUT EVERYONE ELSE - Finished Extended Mix',str(mp3)],check=True)
    meters={name:measure(path) for name,path in [('wav',wav),('mp3',mp3)]}
    for name,path in [('wav',wav),('mp3',mp3)]:
        a,r=sf.read(path,dtype='float32',always_2d=True)
        assert r==SR and abs(len(a)-n)<SR*.02 and np.isfinite(a).all()
        assert meters[name]['true_peak_dbfs']<=-1.0,meters
        assert np.sqrt(np.mean(a[-round(.05*SR):]**2))<.001
    manifest=dict(duration_s=n/SR,bpm=P['bpm'],approved_version='Extended B v2',original_source_map=M['source_map'],
        original_sections_retained=True,reprise_s=reprise,outro_s=outro,new_finishing_notes=len(notes),premaster=before,master=meters,master_gain_db=boost,
        finishing=['Acid delay bridge into breakdown','Four-bar bass/drum transition into original','Late-drop acid motif reprise','Eight-bar diminishing percussion outro','24 Hz rumble filter','Bass stereo width control below 110 Hz','Oversampled lookahead limiting'],
        checks=['Finite samples','WAV and MP3 complete duration','True peak <= -1 dBFS','Faded tail','Original source timeline retained'],
        delivery_sizes={p.name:p.stat().st_size for p in [wav,mp3]})
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (ROOT/'finishing-notes.json').write_text(json.dumps(notes,indent=2))
    print(json.dumps(manifest,indent=2),flush=True)

if __name__=='__main__':main()
