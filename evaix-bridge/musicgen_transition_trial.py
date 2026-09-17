"""Pinned local audio-conditioned continuation experiment; listening pending."""
import json,hashlib,time,math,subprocess
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
import torch
from transformers import AutoProcessor,MusicgenForConditionalGeneration,StoppingCriteria,StoppingCriteriaList
from everyone_passage import SOURCE

ROOT=Path('.producer/projects/how-about-everyone-else/context-trial-v6')
MODEL='facebook/musicgen-small';REV='4c8334b02c6ec4e8664a91979669a501ec497792'
MODEL_PATH=Path('.producer/models/musicgen-small-4c8334b')

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    p=json.loads((ROOT.parent/'passage-v2/passage.json').read_text())
    y,sr=sf.read(SOURCE,dtype='float32',always_2d=True)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==p['source_sha256']
    bars=8;seconds=bars*4*p['period'];n=round(seconds*sr)
    join=p['source_start_sample']+p['frames'];start=join-n
    context=y[start:join];after=y[join:join+n]
    sf.write(ROOT/'Source context.wav',context,sr,subtype='FLOAT')
    input_audio=librosa.resample(context.mean(axis=1),orig_sr=sr,target_sr=32000)
    torch.set_num_threads(4);torch.set_num_interop_threads(2)
    print('Loading pinned MusicGen weights; local CPU inference',flush=True)
    processor=AutoProcessor.from_pretrained(MODEL_PATH,local_files_only=True)
    model=MusicgenForConditionalGeneration.from_pretrained(MODEL_PATH,use_safetensors=True,local_files_only=True,attn_implementation='eager').eval()
    description='Instrumental underground mental acidcore and tribe tekno, around 163 BPM. Continue the recording with the same distorted rolling kick bass groove, hypnotic acid synthesizer, sparse percussion, no vocals.'
    inputs=processor(audio=input_audio,sampling_rate=32000,text=[description],padding=True,return_tensors='pt')
    tokens=math.ceil(seconds*50)+6
    # EnCodec 32k codec has a 640-sample hop. Align the generation boundary
    # using actual encoded prompt length, not a guessed WAV rounding offset.
    with torch.inference_mode():
        encoded=model.audio_encoder.encode(inputs['input_values'],padding_mask=inputs.get('padding_mask'))
    prompt_frames=encoded.audio_codes.shape[-1];prompt_samples=prompt_frames*640
    print(f'Context {len(input_audio)/32000:.3f}s; encoded frames {prompt_frames}; generating {tokens} tokens per candidate',flush=True)
    results=[]
    class Progress(StoppingCriteria):
        def __init__(self):self.last=time.monotonic()
        def __call__(self,input_ids,scores,**kwargs):
            if time.monotonic()-self.last>20:
                print('Generated sequence length: '+str(input_ids.shape[-1]),flush=True);self.last=time.monotonic()
            return False
    for name,seed,temp,guidance in [('A',163,0.85,2.0),('B',303,1.0,3.0)]:
        torch.manual_seed(seed);began=time.time()
        print('Generating candidate '+name,flush=True)
        with torch.inference_mode():
            decoded=model.generate(**inputs,do_sample=True,max_new_tokens=tokens,guidance_scale=guidance,temperature=temp,
                stopping_criteria=StoppingCriteriaList([Progress()]))[0,0].cpu().numpy()
        sf.write(ROOT/f'{name} - raw codec output.wav',decoded,32000,subtype='FLOAT')
        continuation=decoded[prompt_samples:]
        assert len(continuation)>=round(seconds*32000)-640,(len(decoded),prompt_samples)
        continuation=librosa.resample(continuation,orig_sr=32000,target_sr=sr)[:n]
        if len(continuation)<n:continuation=np.pad(continuation,(0,n-len(continuation)))
        generated=np.column_stack([continuation,continuation])
        assert np.isfinite(generated).all() and np.sqrt(np.mean(generated**2))>1e-5
        # Level-match to the source, with bounded gain. No drum layering,
        # copied rhythm loops, invented MIDI, or time-stretch correction.
        rms=lambda a:float(np.sqrt(np.mean(a.astype(np.float64)**2)))
        gain=float(np.clip(rms(context)/rms(generated),.25,4.))
        generated*=gain
        audition=np.concatenate([context,generated,after])
        edge=round(.005*sr)
        for seam in [n,2*n]:
            audition[seam-edge:seam]*=np.linspace(1,0,edge)[:,None]
            audition[seam:seam+edge]*=np.linspace(0,1,edge)[:,None]
        audition[:edge]*=np.linspace(0,1,edge)[:,None];audition[-edge:]*=np.linspace(1,0,edge)[:,None]
        headroom=min(1,10**(-3/20)/abs(audition).max());audition*=headroom
        wav=ROOT/f'{name} - source then continuation then source.wav';sf.write(wav,audition,sr,subtype='PCM_24')
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(wav.with_suffix('.mp3'))],check=True)
        row=dict(candidate=name,seed=seed,temperature=temp,guidance_scale=guidance,seconds_elapsed=time.time()-began,
            generation_boundary_s=prompt_samples/32000,audition_boundaries_s=[n/sr,2*n/sr],duration_s=len(audition)/sr,
            generated_rms_match_gain=gain,shared_headroom_gain=float(headroom),mp3_bytes=wav.with_suffix('.mp3').stat().st_size,
            status='awaiting_contextual_listening',limitations=['32 kHz mono model output','No future-audio conditioning','BPM, harmony and aesthetic fit not guaranteed'])
        results.append(row);print(json.dumps(row),flush=True)
        (ROOT/'manifest.json').write_text(json.dumps(dict(model=MODEL,revision=REV,license='CC-BY-NC-4.0 model weights; evaluation only',
            runtime=dict(torch=torch.__version__,transformers='4.46.3',device='cpu'),source_sha256=p['source_sha256'],
            source_context_s=[start/sr,join/sr],text_condition=description,prompt_frames=prompt_frames,candidates=results,
            evaluation='Signal validation only; no claim of perceptual listening or musical acceptance'),indent=2))

if __name__=='__main__':main()
