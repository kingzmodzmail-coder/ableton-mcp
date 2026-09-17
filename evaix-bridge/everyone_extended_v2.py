"""Develop approved B into a full-length review render, with source coverage checks."""
import json
import hashlib
import subprocess
import struct
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, sawtooth
from everyone_passage import SOURCE

ROOT=Path('.producer/projects/how-about-everyone-else/extended-v2')
PASS=ROOT.parent/'passage-v2'
P=json.loads((PASS/'passage.json').read_text())
Q=json.loads((PASS/'quality.json').read_text())
SR=P['sr']; PERIOD=P['period']; N=round(256*PERIOD*SR)
SAMPLES=ROOT.parents[1]/'mental-acid-001/samples'

def render():
    ROOT.mkdir(parents=True,exist_ok=True)
    source,sr=sf.read(SOURCE,dtype='float32',always_2d=True)
    assert sr==SR and hashlib.sha256(SOURCE.read_bytes()).hexdigest()==P['source_sha256']
    layers={k:np.zeros((N,2),dtype=np.float32) for k in ['acid','drums','bass','fx']}
    notes=[]; hits=[]; rng=np.random.default_rng(163)
    def put(kind,a,beat,level=1,pan=0):
        start=round(beat*PERIOD*SR)
        if start>=N:return
        a=np.asarray(a,dtype=np.float32)
        if a.ndim==1:a=np.column_stack([a,a])
        a=a[:N-start].copy()*level
        a[:,0]*=min(1,1-pan);a[:,1]*=min(1,1+pan)
        layers[kind][start:start+len(a)]+=a
    def sample(name,hp=None):
        a,r=sf.read(SAMPLES/name,dtype='float32',always_2d=True)
        assert r==SR
        if hp:a=sosfilt(butter(2,hp,btype='highpass',fs=SR,output='sos'),a,axis=0)
        # Avoid truncated sample tails clicking at the next beat.
        edge=min(220,len(a)//4);a[-edge:]*=np.linspace(1,0,edge)[:,None]
        return a
    kick=sample('MTLOX - MTDN Kick 03.wav')
    hat=sample('MTLOX - Hihat 03.wav',2800)
    perc=sample('MTLOX - Percussion 05.wav',450)
    snare=sample('MTLOX - Snare 05.wav',650)
    impact=sample('MTLOX - Impact 03.wav',200)
    patterns=[[(.75,0,.22),(2.5,7,.18),(3.25,0,.28)],
              [(.5,0,.18),(1.75,12,.3),(3,7,.28)],
              [(.75,0,.2),(1.5,7,.16),(2.75,12,.3),(3.5,7,.18)],
              [(.5,0,.25),(1.75,7,.18),(2.5,12,.2),(3.25,0,.5)]]
    last=51
    for bar in range(64):
        # 8 bars breakdown; 8 build; 16 drop; 8 stripped response;
        # 16 intensified drop; 8 transition back to the complete source.
        breakdown=bar<8; build=8<=bar<16; stripped=32<=bar<40
        cutoff=(420+bar*55 if bar<16 else 1000+(bar%16)*100)
        if stripped:cutoff=700+(bar-32)*100
        pattern=patterns[(bar//4)%4]
        if breakdown:pattern=pattern[:1] if bar%2==0 else []
        if stripped:pattern=pattern[:2]
        if bar>=48 and bar%4==3:pattern=pattern+[(3.75,12,.12)]
        for j,(offset,interval,duration) in enumerate(pattern):
            pitch=51+interval
            count=round((duration*PERIOD+.09)*SR);t=np.arange(count)/SR
            freq=440*2**((pitch-69)/12); f=np.full(count,freq)
            if j==2:
                g=min(count,round(.035*SR));f[:g]=np.geomspace(440*2**((last-69)/12),freq,g)
            phase=2*np.pi*np.cumsum(f)/SR
            raw=.7*sawtooth(phase)+.3*np.sin(phase)
            c=cutoff+(350 if j==0 else 0)
            low=sosfilt(butter(2,c,fs=SR,output='sos'),raw)
            res=sosfilt(butter(2,[c*.72,c*1.15],btype='bandpass',fs=SR,output='sos'),raw)
            env=np.minimum(1,t/.004)*np.exp(-t/(duration*PERIOD*.6))
            env[-180:]*=np.linspace(1,0,180)
            a=np.tanh(1.6*(low+.7*res))*env
            level=.13 if breakdown else (.17 if build else .22)
            put('acid',a,bar*4+offset,level,pan=.12 if bar%2 else -.12)
            notes.append(dict(pitch=pitch,beat=bar*4+offset,duration=duration,velocity=108 if j==0 else 90,cutoff_hz=c))
            last=pitch
        if not breakdown:
            beats=range(4) if not build or bar>=12 else [0,2]
            for beat in beats:
                if bar in (15,31,55,63) and beat==3:continue
                level=.52 if build else .78
                put('drums',kick,bar*4+beat,level)
                hits.append(['kick',bar*4+beat])
                # New offbeat sub pulse, tuned a little below the acid root.
                if not build:
                    t=np.arange(round(.43*PERIOD*SR))/SR
                    phase=2*np.pi*(440*2**((27-69)/12))*t
                    sub=np.tanh(1.3*np.sin(phase)+.15*np.sin(phase*2))
                    env=np.sin(np.pi*np.linspace(0,1,len(t)))**1.3
                    put('bass',sub*env,bar*4+beat+.5,.18)
            for offset in ([.5,2.5] if stripped or build else [.5,1.5,2.5,3.5]):
                put('drums',hat,bar*4+offset,.065 if build else .10,.2)
            if not build:
                for offset in ([1.75,3.25] if bar%2 else [2.75]):
                    put('drums',perc,bar*4+offset,.15,-.2)
            if bar%8==7:
                for j,offset in enumerate([2.75,3.25,3.5,3.75]):
                    put('drums',snare,bar*4+offset,.065+j*.025)
        if bar in (0,16,40,56):put('fx',impact,bar*4,.12)
    dry=layers['acid'].copy();delay=round(.75*PERIOD*SR)
    for multiple,level in [(1,.20),(2,.07)]:
        d=delay*multiple;layers['acid'][d:]+=level*dry[:-d,::-1]
    # Newly synthesized suspended atmosphere and rising transition noise.
    t=np.arange(round(16*4*PERIOD*SR))/SR
    pad=sum(np.sin(2*np.pi*440*2**((pitch-69)/12)*t) for pitch in [39,46,58])/3
    env=np.minimum(1,t/2)*np.minimum(1,(t[-1]-t)/2)
    put('fx',pad*env,0,.09)
    for beat,length in [(48,16),(152,8),(248,8)]:
        count=round(length*PERIOD*SR);noise=rng.normal(0,1,count)
        noise=sosfilt(butter(2,[1300,6500],btype='bandpass',fs=SR,output='sos'),noise)
        env=np.linspace(0,1,count)**2;env[-440:]*=np.linspace(1,0,440)
        put('fx',noise*env,beat,.055)
    # One gain for all composed layers. Match the drop's energy to approved B,
    # with bounded gain; retain the deliberately quieter breakdown/build.
    mix=sum(layers.values());drop=mix[round(64*PERIOD*SR):round(128*PERIOD*SR)]
    rms=lambda a:float(np.sqrt(np.mean(np.square(a,dtype=np.float64))))
    scale=min(1.7,Q['b_rms']/max(rms(drop),1e-9))
    for k in layers:layers[k]*=scale
    insert=P['source_start_sample']+P['frames']
    fullsource=source*Q['source_gain']
    approved,_=sf.read(PASS/'B - Nieuwe acid en drums 16 maten.wav',dtype='float32',always_2d=True)
    # Restore source continuity at B's audition fades, without changing duration.
    first=P['source_start_sample'];n=P['frames'];edge=round(.01*SR)
    w=np.ones(n,dtype=np.float32);w[:edge]=np.linspace(0,1,edge);w[-edge:]=np.linspace(1,0,edge)
    fullsource[first:insert]=fullsource[first:insert]*(1-w[:,None])+approved*w[:,None]
    full=np.concatenate([fullsource[:insert],np.zeros((N,2),dtype=np.float32),fullsource[insert:]])
    # Only brief edge fades at the insertion; no source segment is omitted.
    cross=round(.01*SR)
    full[insert-cross:insert]*=np.linspace(1,0,cross)[:,None]
    full[insert+N:insert+N+cross]*=np.linspace(0,1,cross)[:,None]
    for k in layers:
        layers[k][:cross]*=np.linspace(0,1,cross)[:,None]
        layers[k][-cross:]*=np.linspace(1,0,cross)[:,None]
        full[insert:insert+N]+=layers[k]
    gain=min(1.,10**(-2/20)/float(np.max(abs(full))))
    full*=gain
    assert np.isfinite(full).all() and len(full)==len(source)+N
    # Prove coverage of both unchanged source spans independently of duration.
    assert np.max(abs(full[:first]-source[:first]*Q['source_gain']*gain))<1e-6
    assert np.max(abs(full[insert+N+cross:]-source[insert+cross:]*Q['source_gain']*gain))<1e-6
    wav=ROOT/'HOW ABOUT EVERYONE ELSE - Extended B v2.wav'
    sf.write(wav,full,SR,subtype='PCM_24')
    for k,a in layers.items():sf.write(ROOT/('New 64 bars - '+k+'.wav'),a*gain,SR,subtype='PCM_24')
    # Portable MIDI for the new acid development.
    def vlq(v):
        out=[v&127];v>>=7
        while v:out.insert(0,(v&127)|128);v>>=7
        return bytes(out)
    events=[]
    for note in notes:
        events += [(round(note['beat']*480),bytes([0x90,note['pitch'],note['velocity']])),(round((note['beat']+note['duration'])*480),bytes([0x80,note['pitch'],0]))]
    track=b'\x00\xff\x51\x03'+round(60000000/P['bpm']).to_bytes(3,'big');prev=0
    for tick,event in sorted(events,key=lambda a:a[0]):track+=vlq(tick-prev)+event;prev=tick
    track+=vlq(256*480-prev)+b'\xff\x2f\x00'
    (ROOT/'New acid 64 bars.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
    manifest=dict(source_sha256=P['source_sha256'],bpm=P['bpm'],duration_s=len(full)/SR,source_duration_s=len(source)/SR,
        new_bars=64,new_duration_s=N/SR,insert_at_s=insert/SR,source_resume_s=(insert+N)/SR,
        approved_B_s=[first/SR,insert/SR],source_coverage='All source intervals retained in original order; approved B replaces its matching passage; 10 ms seam fades',
        source_map=[dict(source_samples=[0,insert],output_samples=[0,insert]),dict(source_samples=[insert,len(source)],output_samples=[insert+N,len(full)])],
        sections=[dict(name=name,start_s=(insert+round(bar*4*PERIOD*SR))/SR) for name,bar in [('Breakdown',0),('Build',8),('Drop',16),('Sparse variation',32),('Second acid variation',40),('Return transition',56)]],
        notes=len(notes),kick_hits=len(hits),peak=float(abs(full).max()),rms=rms(full),final_gain=gain,drop_match_gain=scale,
        status='review mix; not mastered or perceptually certified')
    (ROOT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    (ROOT/'acid-notes.json').write_text(json.dumps(notes,indent=2))
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-codec:a','libmp3lame','-b:a','320k',str(wav.with_suffix('.mp3'))],check=True)
    # Decode the delivery file too: reject duration truncation and non-finite audio.
    decoded,dsr=sf.read(wav.with_suffix('.mp3'),dtype='float32',always_2d=True)
    assert dsr==SR and abs(len(decoded)-len(full))<SR*.05 and np.isfinite(decoded).all()
    print(json.dumps(manifest,indent=2),flush=True)

if __name__=='__main__':render()
