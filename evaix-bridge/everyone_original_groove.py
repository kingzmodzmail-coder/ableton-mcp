"""Replace generic extension rhythm with source-derived drum/bass phrases."""
import json
import subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import butter,sosfilt
from everyone_passage import SOURCE
from finish_everyone import measure, SR, BAR

ROOT=Path('.producer/projects/how-about-everyone-else/original-groove-v5')
PROJECT=ROOT.parent;P=PROJECT/'passage-v2';V2=PROJECT/'extended-v2';V3=PROJECT/'finished-v3';V4=PROJECT/'ending-development-v4'
p=json.loads((P/'passage.json').read_text());q=json.loads((P/'quality.json').read_text())
m2=json.loads((V2/'manifest.json').read_text());m4=json.loads((V4/'manifest.json').read_text())
def read(path):
    a,s=sf.read(path,dtype='float32',always_2d=True);assert s==SR;return a

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    source=read(SOURCE)*q['source_gain']
    bank=(read(P/'estimated-drums.wav')+read(P/'estimated-bass.wav'))*q['source_gain']
    source_rms=float(np.sqrt(np.mean(bank**2)))
    phrase_log=[]
    def rhythm(bars,which):
        n=round(bars*BAR*SR);out=np.zeros((n,2),dtype=np.float32)
        # Four-bar source phrases retain all internal transient timing, kick
        # tails, bass movement and percussion. Never resequence individual kicks.
        order=[0,4,8,12,4,12,0,8] if which=='middle' else [8,12,0,4,12,8,4,0]
        for block in range(bars//4):
            srcbar=order[block%len(order)];a=round(srcbar*BAR*SR);b=round((srcbar+4)*BAR*SR)
            dst=round(block*4*BAR*SR);end=round((block+1)*4*BAR*SR)
            chunk=bank[a:min(b,len(bank))].copy()
            if len(chunk)<end-dst:chunk=np.pad(chunk,((0,end-dst-len(chunk)),(0,0)))
            chunk=chunk[:end-dst]
            edge=44;chunk[:edge]*=np.linspace(0,1,edge)[:,None];chunk[-edge:]*=np.linspace(1,0,edge)[:,None]
            out[dst:end]=chunk
            phrase_log.append(dict(section=which,destination_bar=block*4,source_bar=srcbar,source_time_s=p['source_start_s']+srcbar*BAR))
        if which=='middle':
            knots=[(0,0),(7.5,0),(8,.28),(12,.5),(16,1),(31.5,1),(32,.75),(39.5,.75),(40,1),(55.5,1),(56,.9),(60,.85),(64,.85)]
        else:
            knots=[(0,.28),(8,.55),(16,.75),(24,1),(39.5,1),(40,.06),(47.5,.06),(48,.25),(52,.5),(56,1),(79.5,1),(80,.85),(88,.5),(92,.25),(96,.12)]
        env=np.interp(np.arange(n)/SR/BAR,[k[0] for k in knots],[k[1] for k in knots]).astype(np.float32)
        out*=env[:,None]
        return out
    midrhythm=rhythm(64,'middle');endrhythm=rhythm(96,'ending')
    # Recover the approved arrangement using its separate melodic/FX layers.
    # No generic extension drum, bass or outro-percussion WAV is read here.
    middle=midrhythm+read(V2/'New 64 bars - acid.wav')+read(V2/'New 64 bars - fx.wav')
    first=p['source_start_sample'];insert=first+p['frames']
    approved=read(P/'B - Nieuwe acid en drums 16 maten.wav');fade=round(.01*SR)
    w=np.ones(len(approved),dtype=np.float32);w[:fade]=np.linspace(0,1,fade);w[-fade:]=np.linspace(1,0,fade)
    source[first:insert]=source[first:insert]*(1-w[:,None])+approved*w[:,None]
    v3=read(V3/'HOW ABOUT EVERYONE ELSE - Premaster.wav')
    base=np.concatenate([source[:insert],middle,source[insert:]])
    base=np.pad(base,((0,len(v3)-len(base)),(0,0)))
    base+=read(V3/'Finishing acid.wav')+read(V3/'Transition FX.wav')
    ending=endrhythm+read(V4/'Development - Acid.wav')+read(V4/'Development - FX.wav')
    second=round(m4['insert_at_s']*SR)
    full=np.concatenate([base[:second],ending,base[second:]])
    for seam in [insert,insert+len(middle),second,second+len(ending)]:
        full[seam-fade:seam]*=np.linspace(1,0,fade)[:,None]
        full[seam:seam+fade]*=np.linspace(0,1,fade)[:,None]
    # The v3 ending's melodic resolution remains, but its generic kick layer
    # is absent. Its final output tail is explicitly faded.
    full[-round(1.8*SR):]*=np.linspace(1,0,round(1.8*SR))[:,None]
    assert len(full)==round(m4['deliveries']['Long Ending Mix']['duration_s']*SR)
    # Source preservation outside the approved passage and added regions.
    assert np.array_equal(full[:first],source[:first])
    for label,a in [('Middle - source groove',midrhythm),('Ending - source groove',endrhythm)]:sf.write(ROOT/(label+'.wav'),a,SR,subtype='PCM_24')
    # A concise comparison-in-context includes original music, the revised
    # entrance, build, and first drop, rather than an isolated kick demo.
    preview_start=round((m2['insert_at_s']-8*BAR)*SR);preview_end=round((m2['insert_at_s']+32*BAR)*SR)
    deliveries={}
    for label,a in [('Original Groove Revision',full),('Revised Transition Preview',full[preview_start:preview_end].copy())]:
        a=sosfilt(butter(2,24,btype='highpass',fs=SR,output='sos'),a,axis=0)
        mid=a.mean(axis=1);side=sosfilt(butter(2,110,btype='highpass',fs=SR,output='sos'),(a[:,0]-a[:,1])*.5)
        a=np.column_stack([mid+side,mid-side]).astype(np.float32)
        a[:fade]*=np.linspace(0,1,fade)[:,None];a[-fade:]*=np.linspace(1,0,fade)[:,None]
        assert np.isfinite(a).all()
        pre=ROOT/(label+' - Premaster.wav');sf.write(pre,a,SR,subtype='FLOAT')
        level=measure(pre);gain=min(2.,max(-2.,-10.5-level['integrated_lufs']))
        wav=ROOT/('HOW ABOUT EVERYONE ELSE - '+label+'.wav')
        filters=f'volume={gain}dB,aresample=176400,alimiter=limit=0.841395:attack=5:release=80:level=false:latency=true,aresample=44100'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(pre),'-af',filters,'-c:a','pcm_s24le',str(wav)],check=True)
        mp3=wav.with_suffix('.mp3')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
        meter=measure(mp3);decoded=read(mp3)
        assert meter['true_peak_dbfs']<=-1 and abs(len(decoded)-len(a))<SR*.02 and np.isfinite(decoded).all()
        deliveries[label]=dict(duration_s=len(a)/SR,mp3_bytes=mp3.stat().st_size,meters=meter)
        print(label+': '+json.dumps(deliveries[label]),flush=True)
    report=dict(deliveries=deliveries,rhythm_source='Estimated drums + bass from original MP3 47.485-71.044 seconds',
        estimated_stems=True,source_rhythm_rms=source_rms,removed=['Middle generic kick/percussion layer','Middle synthetic bass pulses','Ending generic kick/percussion layer','Ending synthetic bass pulses','v3 added outro kick/percussion'],
        kept=['Approved B passage','All original sections in order','Composed acid motifs','Transition FX'],
        phrase_policy='Four-bar source-derived drum/bass phrases with internal timing intact; reused with arrangement gain changes',
        preview_original_range_s=[preview_start/SR,preview_end/SR],phrase_map=phrase_log)
    (ROOT/'manifest.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()
