import json
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa

source = Path(r'C:\Users\Gebruiker\.codex\codex-remote-attachments\01a092f1-d0de-7e30-81ba-fa19b7d0f1e7\16677F2B-FC2F-4ACD-ABC1-9F2154EF23F2\1-HOW-ABOUT-EVERYONE-ELSE-.mp3')
root = Path('.producer/projects/how-about-everyone-else')
root.mkdir(parents=True, exist_ok=True)
y, sr = sf.read(source, always_2d=True, dtype='float32')
sf.write(root / 'original-decoded.wav', y, sr, subtype='FLOAT')
mono = librosa.resample(y.mean(axis=1), orig_sr=sr, target_sr=22050)
onset = librosa.onset.onset_strength(y=mono, sr=22050)
tempo, beats = librosa.beat.beat_track(onset_envelope=onset, sr=22050, units='time')
energies = [dict(start_s=t, rms=float(np.sqrt(np.mean(y[int(t*sr):int(min(t+8,len(y)/sr)*sr)]**2)))) for t in range(0,int(len(y)/sr),8)]
report = dict(duration_s=len(y)/sr, sample_rate=sr, tempo_estimate=float(np.asarray(tempo).flat[0]), beat_times=beats.tolist(), energy=energies, peak=float(abs(y).max()))
(root / 'analysis.json').write_text(json.dumps(report, indent=2))
print(json.dumps({**report, 'beat_times': report['beat_times'][:20]}, indent=2))
