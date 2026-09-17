"""Continue the user-approved dry passage by eight bars, without added effects."""
import json,hashlib,time,math,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa,torch
from transformers import AutoProcessor,MusicgenForConditionalGeneration,StoppingCriteria,StoppingCriteriaList
from transformers.utils import logging
from finish_everyone import measure

ROOT=Path('.producer/projects/how-about-everyone-else/dry-next-v8')
PROJECT=ROOT.parent
SOURCE=PROJECT/'approved-b-next-v7/no-added-echo/B plus next eight bars - no added echo.wav'
MODEL_PATH=Path('.producer/models/musicgen-small-4c8334b')

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    prior=json.loads((PROJECT/'approved-b-next-v7/manifest.json').read_text())
    approved,sr=sf.read(SOURCE,dtype='float32',always_2d=True)
    n=round(prior['sections_s']['approved_B'][0]*sr);join=3*n
    context=approved[join-n:join];seconds=n/sr
    sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    event=dict(event='user_approval',user_words='Good i like it',file=str(SOURCE.resolve()),sha256=sha,scope='Dry B and its next eight bars',added_echo_enabled=False)
    line=json.dumps(event);journal=PROJECT/'feedback-events.jsonl'
    if line not in journal.read_text():
        with journal.open('a') as f:f.write(line+'\n')
    torch.set_num_threads(4);torch.set_num_interop_threads(2);torch.manual_seed(305);logging.set_verbosity_error()
    print('Loading local model for dry-reference continuation',flush=True)
    processor=AutoProcessor.from_pretrained(MODEL_PATH,local_files_only=True)
    model=MusicgenForConditionalGeneration.from_pretrained(MODEL_PATH,use_safetensors=True,local_files_only=True,attn_implementation='eager').eval()
    audio=librosa.resample(context.mean(axis=1),orig_sr=sr,target_sr=32000)
    inputs=processor(audio=audio,sampling_rate=32000,text=[prior['text_condition']],padding=True,return_tensors='pt')
    with torch.inference_mode():encoded=model.audio_encoder.encode(inputs['input_values'],padding_mask=inputs.get('padding_mask'))
    boundary=encoded.audio_codes.shape[-1]*640
    class Progress(StoppingCriteria):
        def __init__(self):self.last=time.monotonic()
        def __call__(self,input_ids,scores,**kwargs):
            if time.monotonic()-self.last>20:
                print('Sequence tokens: '+str(input_ids.shape[-1]),flush=True);self.last=time.monotonic()
            return False
    began=time.time();print('Generating eight bars from the approved dry audio',flush=True)
    with torch.inference_mode():
        raw=model.generate(**inputs,do_sample=True,max_new_tokens=math.ceil(seconds*50)+6,temperature=1.,guidance_scale=3.,stopping_criteria=StoppingCriteriaList([Progress()]))[0,0].cpu().numpy()
    sf.write(ROOT/'Raw codec output.wav',raw,32000,subtype='FLOAT')
    new=librosa.resample(raw[boundary:],orig_sr=32000,target_sr=sr)[:n]
    assert len(new)==n and np.isfinite(new).all() and np.sqrt(np.mean(new**2))>1e-5
    new=np.column_stack([new,new])
    rms=lambda a:float(np.sqrt(np.mean(a.astype(np.float64)**2)))
    requested_gain=float(np.clip(rms(context)/rms(new),.25,4.))
    gain=min(requested_gain,.75/float(abs(new).max()));new*=gain
    edge=round(.005*sr);new[:edge]*=np.linspace(0,1,edge)[:,None];new[-edge:]*=np.linspace(1,0,edge)[:,None]
    mix=np.concatenate([approved[:join],new,approved[join:]])
    assert np.array_equal(mix[:join],approved[:join]) and np.array_equal(mix[join+n:],approved[join:])
    wav=ROOT/'Dry approved passage plus next eight bars.wav';sf.write(wav,mix,sr,subtype='PCM_24')
    sf.write(ROOT/'New eight bars only.wav',new,sr,subtype='PCM_24')
    mp3=wav.with_suffix('.mp3')
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
    meters=measure(mp3);decoded,r=sf.read(mp3,dtype='float32',always_2d=True)
    assert r==sr and len(decoded)==len(mix) and np.isfinite(decoded).all() and meters['true_peak_dbfs']<0
    report=dict(approved_source_sha256=sha,approved_audio_preserved=True,seed=305,model_revision=prior['revision'],
        text_condition=prior['text_condition'],prompt_codec_frames=boundary//640,seconds_elapsed=time.time()-began,
        duration_s=len(mix)/sr,new_section_s=[join/sr,(join+n)/sr],original_returns_s=(join+n)/sr,
        generation_gain=gain,requested_rms_gain=requested_gain,added_echo=False,added_reverb=False,
        mp3_bytes=mp3.stat().st_size,meters=meters,status='New section awaits user listening; previous dry passage remains approved',
        limits='Local MusicGen private evaluation. No future conditioning or perceptual quality claim. Natural model ambience may remain.')
    (ROOT/'manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
