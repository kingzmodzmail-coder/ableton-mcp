"""Evidence-only diagnostics for generated candidates, never aesthetic approval."""
import hashlib,json
from pathlib import Path
import numpy as np
import librosa
import soundfile as sf
from finish_everyone import measure
ROOT=Path('.producer/projects/how-about-everyone-else/context-trial-v6')

def features(x,sr):
    y=librosa.resample(x.mean(axis=1),orig_sr=sr,target_sr=22050)
    onset=librosa.onset.onset_strength(y=y,sr=22050,hop_length=256)
    chroma=librosa.feature.chroma_stft(y=y,sr=22050).mean(axis=1)
    tempo=librosa.feature.tempo(onset_envelope=onset,sr=22050,hop_length=256,start_bpm=163)[0]
    bands={}
    spectrum=abs(np.fft.rfft(y))**2;freq=np.fft.rfftfreq(len(y),1/22050)
    for name,low,high in [('bass',30,250),('mid',250,3000),('high',3000,10000)]:
        bands[name]=float(spectrum[(freq>=low)&(freq<high)].sum()/max(spectrum.sum(),1e-10))
    return dict(tempo_hypothesis_bpm=float(tempo),chroma_mean=chroma.tolist(),band_fraction=bands)

def main():
    m=json.loads((ROOT/'manifest.json').read_text());rows=[]
    for c in m['candidates']:
        wav=ROOT/(c['candidate']+' - source then continuation then source.wav')
        x,sr=sf.read(wav,dtype='float32',always_2d=True);n=round(c['audition_boundaries_s'][0]*sr)
        a=features(x[:n],sr);b=features(x[n:2*n],sr)
        ca=np.array(a['chroma_mean']);cb=np.array(b['chroma_mean'])
        cosine=float(np.dot(ca,cb)/max(np.linalg.norm(ca)*np.linalg.norm(cb),1e-9))
        meters=measure(wav.with_suffix('.mp3'))
        assert meters['true_peak_dbfs']<0 and np.isfinite(x).all()
        rows.append(dict(candidate=c['candidate'],source=a,generated=b,chroma_cosine_similarity=cosine,
            score_kind='uncalibrated_descriptor_similarity_not_probability',delivery_meter=meters,
            verdict='pending_user_listening',limitations='Short-window tempo may be half/double time; chroma agreement does not establish harmonic or stylistic fit.'))
    weights=Path('.producer/models/musicgen-small-4c8334b/model.safetensors')
    h=hashlib.sha256()
    with weights.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    report=dict(model_revision=m['revision'],weights_sha256=h.hexdigest(),candidates=rows,
        listening_assessment='Not performed by an audio-language critic. User audition required.')
    (ROOT/'evidence.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
