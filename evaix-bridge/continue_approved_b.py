"""Eight-bar continuation of explicitly approved B; preserve approved PCM."""
import json,hashlib,time,math,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa,torch
from scipy.signal import butter,sosfilt
from transformers import AutoProcessor,MusicgenForConditionalGeneration,StoppingCriteria,StoppingCriteriaList
from transformers.utils import logging
from finish_everyone import measure

ROOT=Path('.producer/projects/how-about-everyone-else/approved-b-next-v7')
PREV=ROOT.parent/'context-trial-v6'
MODEL_PATH=Path('.producer/models/musicgen-small-4c8334b')
REV='4c8334b02c6ec4e8664a91979669a501ec497792'

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    p=json.loads((ROOT.parent/'passage-v2/passage.json').read_text())
    prev=json.loads((PREV/'manifest.json').read_text());c=prev['candidates'][1]
    source=PREV/'subtle-echo/B - subtle echo.wav'
    approved,sr=sf.read(source,dtype='float32',always_2d=True)
    n=round(c['audition_boundaries_s'][0]*sr);seconds=n/sr
    context=approved[n:2*n]
    audio=librosa.resample(context.mean(axis=1),orig_sr=sr,target_sr=32000)
    torch.set_num_threads(4);torch.set_num_interop_threads(2);torch.manual_seed(304)
    logging.set_verbosity_error()
    print('Loading local model; approved B is the audio context',flush=True)
    proc=AutoProcessor.from_pretrained(MODEL_PATH,local_files_only=True)
    model=MusicgenForConditionalGeneration.from_pretrained(MODEL_PATH,use_safetensors=True,local_files_only=True,attn_implementation='eager').eval()
    prompt=prev['text_condition']
    inputs=proc(audio=audio,sampling_rate=32000,text=[prompt],padding=True,return_tensors='pt')
    with torch.inference_mode():
        enc=model.audio_encoder.encode(inputs['input_values'],padding_mask=inputs.get('padding_mask'))
    boundary=enc.audio_codes.shape[-1]*640
    class Progress(StoppingCriteria):
        def __init__(self):self.last=time.monotonic()
        def __call__(self,input_ids,scores,**kwargs):
            if time.monotonic()-self.last>20:
                print('Sequence tokens: '+str(input_ids.shape[-1]),flush=True);self.last=time.monotonic()
            return False
    print('Generating next eight bars',flush=True);began=time.time()
    with torch.inference_mode():
        decoded=model.generate(**inputs,do_sample=True,max_new_tokens=math.ceil(seconds*50)+6,temperature=1.,guidance_scale=3.,
            stopping_criteria=StoppingCriteriaList([Progress()]))[0,0].cpu().numpy()
    sf.write(ROOT/'Raw codec output.wav',decoded,32000,subtype='FLOAT')
    new=librosa.resample(decoded[boundary:],orig_sr=32000,target_sr=sr)[:n]
    assert len(new)==n and np.isfinite(new).all() and np.sqrt(np.mean(new**2))>1e-5
    new=np.column_stack([new,new])
    rms=lambda x:float(np.sqrt(np.mean(x.astype(np.float64)**2)))
    gain=float(np.clip(rms(context)/rms(new),.25,4.));new*=gain
    # Preserve the approved source and B exactly, then insert only the new
    # continuation. Move B's existing echo tail so it bridges into the new part.
    dry_prev,_=sf.read(PREV/'B - source then continuation then source.wav',dtype='float32',always_2d=True)
    inherited_tail=approved[2*n:]-dry_prev[2*n:]
    mix=np.concatenate([approved[:2*n],new,dry_prev[2*n:]])
    mix[2*n:3*n]+=inherited_tail
    feed=np.zeros_like(mix);feed[2*n:3*n]=new
    feed=sosfilt(butter(2,[600,5500],btype='bandpass',fs=sr,output='sos'),feed,axis=0)
    delay=round(.75*p['period']*sr)
    for tap in range(1,5):
        d=delay*tap;pan=np.array([1,.45]) if tap%2 else np.array([.45,1])
        mix[d:]+=feed[:-d]*pan*.13*.38**(tap-1)
    edge=round(.005*sr)
    # Fade only the new material at the joins, leaving approved B untouched.
    mix[2*n:2*n+edge]*=np.linspace(0,1,edge)[:,None]
    mix[3*n-edge:3*n]*=np.linspace(1,0,edge)[:,None]
    assert np.array_equal(mix[:2*n],approved[:2*n])
    peak=float(abs(mix).max())
    if peak>.84:
        # Bound only the candidate contribution, not the approved passage.
        mix[2*n:3*n]*=.84/peak
    wav=ROOT/'Approved B plus next eight bars.wav';sf.write(wav,mix,sr,subtype='PCM_24')
    mp3=wav.with_suffix('.mp3')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
    meters=measure(mp3);out,r=sf.read(mp3,dtype='float32',always_2d=True)
    assert r==sr and len(out)==len(mix) and np.isfinite(out).all() and meters['true_peak_dbfs']<0
    report=dict(approved_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),approved_B_preserved_in_WAV=True,
        revision=REV,seed=304,text_condition=prompt,temperature=1.,guidance_scale=3.,seconds_elapsed=time.time()-began,
        duration_s=len(mix)/sr,sections_s=dict(original=[0,n/sr],approved_B=[n/sr,2*n/sr],new_continuation=[2*n/sr,3*n/sr],original_return=[3*n/sr,len(mix)/sr]),
        new_rms_match_gain=gain,echo=dict(delay_ms=delay/sr*1000,send=.13,feedback=.38,filter_hz=[600,5500]),
        mp3_bytes=mp3.stat().st_size,meters=meters,status='new eight bars pending listening; B remains approved',
        limits='Local 32kHz mono MusicGen evaluation; no future-context conditioning or aesthetic scoring')
    (ROOT/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
