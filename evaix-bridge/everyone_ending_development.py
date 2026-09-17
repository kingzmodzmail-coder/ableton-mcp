"""Develop the user-selected closing motif into 96 newly sequenced bars."""
import json
import struct
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, sawtooth
from finish_everyone import measure, PERIOD, BAR, SR, SAMPLES

ROOT=Path('.producer/projects/how-about-everyone-else/ending-development-v4')
V3=ROOT.parent/'finished-v3'
M=json.loads((V3/'manifest.json').read_text())
N=round(96*BAR*SR)

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    layers={k:np.zeros((N,2),dtype=np.float32) for k in ['Acid','Drums','Bass','FX']}
    notes=[];hits=[];rng=np.random.default_rng(4196)
    def put(kind,a,beat,level=1,pan=0):
        start=round(beat*PERIOD*SR)
        if start>=N:return
        a=np.asarray(a,dtype=np.float32)
        if a.ndim==1:a=np.column_stack([a,a])
        a=a[:N-start].copy()*level
        a[:,0]*=min(1,1-pan);a[:,1]*=min(1,1+pan)
        layers[kind][start:start+len(a)]+=a
    def sample(name,hp):
        a,r=sf.read(SAMPLES/name,dtype='float32',always_2d=True);assert r==SR
        a=sosfilt(butter(2,hp,btype='highpass',fs=SR,output='sos'),a,axis=0)
        a[-220:]*=np.linspace(1,0,220)[:,None]
        return a
    kick=sample('MTLOX - MTDN Kick 03.wav',35)
    hat=sample('MTLOX - Hihat 03.wav',2800)
    perc=sample('MTLOX - Percussion 05.wav',500)
    snare=sample('MTLOX - Snare 05.wav',650)
    impact=sample('MTLOX - Impact 03.wav',300)
    last_pitch=51
    for bar in range(96):
        # 8 motif, 16 growing groove, 16 first drop, 8 break, 8 build,
        # 24 second drop, 16 staged outro. All events sequenced afresh.
        intro=bar<8;groove=8<=bar<24;drop=24<=bar<40 or 56<=bar<80
        broken=40<=bar<48;build=48<=bar<56;outro=bar>=80
        progress=(bar-80)/16 if outro else 0
        cutoff=1050 if intro else (1150+(bar%16)*70)
        if broken:cutoff=600+(bar-40)*50
        if build:cutoff=900+(bar-48)*150
        if outro:cutoff=1650-progress*1100
        # Retain the closing root note, its .75-beat placement and sparse rests.
        pattern=[(.75,51,.35)] if bar%2==0 else []
        if groove:pattern=pattern+([(2.75,58,.24)] if bar%4==3 else [])
        if drop:
            pattern=[(.75,51,.35),(2.75,51,.20)] if bar%2==0 else [(1.75,58,.25)]
            if bar>=64 and bar%4==3:pattern += [(3.25,63,.32)]
            if bar>=72 and bar%2==0:pattern += [(3.5,58,.16)]
        if build:pattern=[(.75,51,.35),(2.75,51,.22)] if bar>=52 else pattern
        if broken and bar%4!=0:pattern=[]
        if outro and bar>=88:pattern=[(.75,51,.35)] if bar%4==0 else []
        for j,(offset,pitch,duration) in enumerate(pattern):
            t=np.arange(round((duration*PERIOD+.1)*SR))/SR
            frequency=np.full(len(t),440*2**((pitch-69)/12))
            if drop and j>0:
                g=min(len(t),round(.025*SR));frequency[:g]=np.geomspace(440*2**((last_pitch-69)/12),frequency[-1],g)
            phase=2*np.pi*np.cumsum(frequency)/SR
            raw=.7*sawtooth(phase)+.3*np.sin(phase)
            c=cutoff+(200 if j==0 and drop else 0)
            low=sosfilt(butter(2,c,fs=SR,output='sos'),raw)
            res=sosfilt(butter(2,[c*.72,c*1.15],btype='bandpass',fs=SR,output='sos'),raw)
            env=np.minimum(1,t/.004)*np.exp(-t/(duration*PERIOD*.6))
            env[-220:]*=np.linspace(1,0,220)
            signal=np.tanh(1.6*(low+.7*res))*env
            level=.095 if intro or broken else (.16 if drop else .12)
            if outro:level=.12*(1-progress*.65)
            beat=bar*4+offset
            put('Acid',signal,beat,level,.12 if bar%2 else -.12)
            for d,gain in [(1,.20),(2,.07)]:put('FX',signal,beat+d*.75,level*gain,-.12 if bar%2 else .12)
            notes.append(dict(beat=beat,pitch=pitch,duration=duration,velocity=100 if j==0 else 87,cutoff_hz=c))
            last_pitch=pitch
        kickbeats=[] if broken else list(range(4))
        if intro:kickbeats=[0,2]
        if build and bar<52:kickbeats=[0,2]
        if outro and bar>=88:kickbeats=[0,2] if bar<92 else [0]
        if bar in (23,39,55,79,95):kickbeats=[b for b in kickbeats if b<3]
        for beat in kickbeats:
            level=.28 if intro else (.56 if drop else .40)
            if outro:level=.44*(1-progress*.8)
            put('Drums',kick,bar*4+beat,level)
            hits.append(dict(instrument='kick',beat=bar*4+beat))
            if drop or groove:
                t=np.arange(round(.4*PERIOD*SR))/SR
                freq=440*2**((27-69)/12)
                pulse=np.tanh(1.3*np.sin(2*np.pi*freq*t)+.15*np.sin(4*np.pi*freq*t))
                pulse*=np.sin(np.pi*np.linspace(0,1,len(t)))**1.3
                put('Bass',pulse,bar*4+beat+.5,.12 if drop else .07)
        if not broken:
            offsets=[.5,2.5] if not drop else [.5,1.5,2.5,3.5]
            if outro and bar>=92:offsets=[]
            for offset in offsets:put('Drums',hat,bar*4+offset,.07*(1-progress*.8),.15)
            if bar<88:
                offsets=[2.75] if not drop or bar%2==0 else [1.75,3.25]
                for offset in offsets:put('Drums',perc,bar*4+offset,.11*(1-progress),-.15)
        if bar in (23,39,55,71,79):
            for j,beat in enumerate([2.75,3.25,3.5,3.75]):put('Drums',snare,bar*4+beat,.035+j*.02)
        if bar in (24,56,80):put('FX',impact,bar*4,.09)
    # Suspended root/fifth atmosphere in the break, and noise ramps into drops.
    t=np.arange(round(8*BAR*SR))/SR
    pad=(np.sin(2*np.pi*440*2**((39-69)/12)*t)+.4*np.sin(2*np.pi*440*2**((46-69)/12)*t))/1.4
    pad*=np.minimum(1,t/1.5)*np.minimum(1,(t[-1]-t)/1.5)
    put('FX',pad,160,.065)
    for beat in (88,216):
        count=round(8*PERIOD*SR);a=rng.normal(0,1,count)
        a=sosfilt(butter(2,[1300,6200],btype='bandpass',fs=SR,output='sos'),a)
        env=np.linspace(0,1,count)**2;env[-440:]*=np.linspace(1,0,440)
        put('FX',a*env,beat,.04)
    # The old closing four bars resolve the full track after this development.
    # Standalone audition gets its own final fade and short silent tail.
    mix=sum(layers.values())
    mix=sosfilt(butter(2,24,btype='highpass',fs=SR,output='sos'),mix,axis=0).astype(np.float32)
    # Gradual first eight bars start at the original outro's restrained level.
    envelope=np.ones(N,dtype=np.float32)
    ramp=round(8*BAR*SR);envelope[:ramp]=np.linspace(.55,1,ramp)
    # Lift the developed section toward the existing drop's level while
    # retaining its quiet opening and breakdown. Apply equally to stem exports.
    envelope*=1.7
    mix*=envelope[:,None]
    old,r=sf.read(V3/'HOW ABOUT EVERYONE ELSE - Premaster.wav',dtype='float32',always_2d=True);assert r==SR
    insert=round((M['outro_s']+4*BAR)*SR)
    full=np.concatenate([old[:insert],mix,old[insert:]])
    # Short seam fades retain every old sample index and original section.
    fade=round(.01*SR)
    for seam in (insert,insert+N):
        full[seam-fade:seam]*=np.linspace(1,0,fade)[:,None]
        full[seam:seam+fade]*=np.linspace(0,1,fade)[:,None]
    assert np.array_equal(full[:insert-fade],old[:insert-fade])
    assert np.array_equal(full[insert+N+fade:],old[insert+fade:])
    standalone=np.pad(mix,((0,round(2*SR)),(0,0)))
    standalone[:fade]*=np.linspace(0,1,fade)[:,None]
    tail=round(2*PERIOD*SR);standalone[N-tail:N]*=np.linspace(1,0,tail)[:,None]
    manifests={}
    for label,a in [('Long Ending Mix',full),('Ending Development Only',standalone)]:
        assert np.isfinite(a).all()
        pre=ROOT/(label+' - Premaster.wav');sf.write(pre,a,SR,subtype='FLOAT')
        before=measure(pre)
        gain=min(2.,max(-2.,-10.5-before['integrated_lufs']))
        wav=ROOT/('HOW ABOUT EVERYONE ELSE - '+label+'.wav')
        filters=f'volume={gain}dB,aresample=176400,alimiter=limit=0.841395:attack=5:release=80:level=false:latency=true,aresample=44100'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(pre),'-af',filters,'-c:a','pcm_s24le',str(wav)],check=True)
        mp3=wav.with_suffix('.mp3')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
        meter=measure(mp3)
        decoded,r=sf.read(mp3,dtype='float32',always_2d=True)
        assert r==SR and abs(len(decoded)-len(a))<SR*.02 and np.isfinite(decoded).all()
        assert meter['true_peak_dbfs']<=-1 and np.sqrt(np.mean(decoded[-2205:]**2))<.001
        manifests[label]=dict(duration_s=len(a)/SR,mp3_bytes=mp3.stat().st_size,wav_bytes=wav.stat().st_size,meters=meter)
        print(label+': '+json.dumps(manifests[label]),flush=True)
    for name,a in layers.items():sf.write(ROOT/('Development - '+name+'.wav'),a*envelope[:,None],SR,subtype='PCM_24')
    def vlq(v):
        out=[v&127];v>>=7
        while v:out.insert(0,(v&127)|128);v>>=7
        return bytes(out)
    events=[]
    for note in notes:
        events.extend([(round(note['beat']*480),bytes([0x90,note['pitch'],note['velocity']])),(round((note['beat']+note['duration'])*480),bytes([0x80,note['pitch'],0]))])
    track=b'\x00\xff\x51\x03'+round(PERIOD*1000000).to_bytes(3,'big');prev=0
    for tick,event in sorted(events,key=lambda e:e[0]):track+=vlq(tick-prev)+event;prev=tick
    track+=vlq(384*480-prev)+b'\xff\x2f\x00'
    (ROOT/'Ending development 96 bars.mid').write_bytes(b'MThd'+struct.pack('>IHHH',6,0,1,480)+b'MTrk'+struct.pack('>I',len(track))+track)
    report=dict(bpm=60/PERIOD,new_bars=96,new_notes=len(notes),new_kick_hits=len(hits),insert_at_s=insert/SR,new_duration_s=N/SR,
        original_preservation='All v3 premaster samples retained in order; 10 ms seam fades; mastering reapplied from premaster',
        sections=[dict(name=name,standalone_s=bar*BAR,full_mix_s=insert/SR+bar*BAR) for name,bar in [('Closing motif',0),('Growing groove',8),('First drop',24),('Break',40),('Build',48),('Second drop',56),('Outro',80)]],deliveries=manifests)
    (ROOT/'manifest.json').write_text(json.dumps(report,indent=2));(ROOT/'notes.json').write_text(json.dumps(notes,indent=2))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
