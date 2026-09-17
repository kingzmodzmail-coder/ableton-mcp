"""Measured signal properties, not aesthetic scores or a substitute for listening."""
import hashlib
import io
import math
import os
import tempfile
import wave
from pathlib import Path

import numpy as np

MAX_WAV_BYTES = 256 * 1024 * 1024


def db(value):
    return float(20 * np.log10(max(float(value), 1e-12)))


def read_wav(path):
    with wave.open(io.BytesIO(path) if isinstance(path, bytes) else str(path), 'rb') as f:
        channels, width, rate, frames = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        if not 1 <= rate <= 192000 or frames * channels * width > MAX_WAV_BYTES:
            raise ValueError('PCM preview exceeds sample-rate or 256 MiB decoded size limit')
        if frames / rate > 600 or channels > 8:
            raise ValueError('Use a PCM WAV preview no longer than 10 minutes and at most 8 channels')
        raw = f.readframes(frames)
    if width == 1:
        values = (np.frombuffer(raw, dtype=np.uint8).astype(float) - 128) / 128
    elif width in (2, 4):
        values = np.frombuffer(raw, dtype='<i%d' % width).astype(float) / (2 ** (8 * width - 1))
    elif width == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        values = ((values ^ 0x800000) - 0x800000).astype(float) / 8388608
    else:
        raise ValueError('Expected 8/16/24/32-bit integer PCM WAV')
    if not frames or len(values) != frames * channels:
        raise ValueError('Empty or truncated WAV')
    return values.reshape(-1, channels), rate


def measure(samples, rate, bpm, beats_per_bar=4):
    if not math.isfinite(rate) or not 1 <= rate <= 192000:
        raise ValueError('Invalid sample rate')
    if not math.isfinite(bpm) or not 20 <= bpm <= 300 or not 0 < beats_per_bar <= 32:
        raise ValueError('Invalid tempo or meter')
    x = np.asarray(samples, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not 1 <= x.shape[1] <= 8 or not np.isfinite(x).all():
        raise ValueError('Expected finite frames × channels audio')
    peak, rms = np.max(np.abs(x)), np.sqrt(np.mean(x ** 2))
    size = 8192
    power = np.zeros(size // 2 + 1)
    window = np.hanning(size)[:, None]
    for offset in range(0, len(x), size):
        block = x[offset:offset + size]
        if len(block) < size:
            block = np.pad(block, ((0, size - len(block)), (0, 0)))
        power += np.mean(np.abs(np.fft.rfft(block * window, axis=0)) ** 2, axis=1)
    frequencies = np.fft.rfftfreq(size, 1 / rate)
    denominator = float(power.sum())
    bands = {name: float(power[(frequencies >= lo) & (frequencies < hi)].sum() / max(denominator, 1e-30))
             for name, lo, hi in [('sub_30_80', 30, 80), ('low_80_250', 80, 250),
                                  ('mid_250_3000', 250, 3000), ('presence_3000_6000', 3000, 6000),
                                  ('air_6000_20000', 6000, 20000)]}
    bar_frames = rate * 60 / bpm * beats_per_bar
    envelopes = []
    for bar in range(int((len(x) + .5) / bar_frames)):
        block = x[round(bar * bar_frames):round((bar + 1) * bar_frames)]
        envelopes.append(db(np.sqrt(np.mean(block ** 2))))
    correlation = None
    if x.shape[1] == 2 and np.std(x[:, 0]) > 1e-9 and np.std(x[:, 1]) > 1e-9:
        correlation = float(np.corrcoef(x[:, 0], x[:, 1])[0, 1])
    issues = []
    if peak < 1e-5:
        issues.append('Silent capture: check the selected output and transport before judging music.')
    if peak >= .999:
        issues.append('Samples reach full scale; inspect gain staging. This is not a true-peak measurement.')
    if correlation is not None and correlation < 0:
        issues.append('Negative stereo correlation: audition mono compatibility.')
    return {'duration_seconds': len(x) / rate, 'sample_rate': rate, 'channels': x.shape[1],
            'sample_peak_dbfs': db(peak), 'rms_dbfs': db(rms), 'crest_db': db(peak) - db(rms),
            'full_scale_fraction': float(np.mean(np.abs(x) >= .999)), 'dc_offset': float(np.mean(x)),
            'stereo_correlation': correlation, 'band_energy_fraction': bands, 'bar_rms_dbfs': envelopes,
            'usable_signal': bool(peak >= 1e-5), 'findings': issues,
            'limits': 'RMS is not LUFS; sample peak is not true peak. Spectral ratios do not establish musical quality.'}


def analyze(producer, path, label, bpm, version_id, start_beat=0, beats_per_bar=4, source='imported_wav'):
    producer.store.get(version_id, 'version')
    path = Path(path).resolve()
    with path.open('rb') as source_file:
        if os.fstat(source_file.fileno()).st_size > MAX_WAV_BYTES:
            raise ValueError('WAV preview exceeds 256 MiB size limit')
        data = source_file.read(MAX_WAV_BYTES + 1)
    if len(data) > MAX_WAV_BYTES:
        raise ValueError('WAV preview exceeds 256 MiB size limit')
    samples, rate = read_wav(data)
    metrics = measure(samples, rate, bpm, beats_per_bar)
    # Keep the analyzed bytes: A/B remains reproducible if the source is overwritten.
    sha = hashlib.sha256(data).hexdigest()
    folder = producer.store.root / 'audio'
    folder.mkdir(exist_ok=True)
    retained = folder / (sha + '.wav')
    if retained.exists():
        if retained.read_bytes() != data:
            raise ValueError('Retained audio checksum mismatch; artifact is corrupt')
    else:
        # Publish only complete artifacts; a failed write must not leave a
        # truncated file under a trusted content hash.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=folder, delete=False) as f:
                temporary = Path(f.name)
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, retained)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    body = {'label': label, 'version_id': version_id, 'path': str(retained), 'sha256': sha,
            'bpm': bpm, 'start_beat': start_beat, 'beats_per_bar': beats_per_bar, 'source': source, 'metrics': metrics}
    return dict(body, analysis_id=producer.store.add('analysis', body))


def compare(producer, before_id, after_id):
    a = producer.store.get(before_id, 'analysis')['body']
    b = producer.store.get(after_id, 'analysis')['body']
    for key in ('bpm', 'start_beat', 'beats_per_bar', 'source'):
        if a[key] != b[key]:
            raise ValueError('Comparison requires matching ' + key)
    if a['source'] == 'output_loopback':
        if not a.get('capture', {}).get('clean_capture') or not b.get('capture', {}).get('clean_capture'):
            raise ValueError('Capture continuity must be verified before A/B comparison')
        for key in ('clips', 'device', 'preroll_bars'):
            if a.get('capture', {}).get(key) != b.get('capture', {}).get(key):
                raise ValueError('Loopback comparison requires matching ' + key)
    if not a['metrics']['usable_signal'] or not b['metrics']['usable_signal']:
        raise ValueError('Silent audio cannot support a musical comparison')
    if abs(a['metrics']['duration_seconds'] - b['metrics']['duration_seconds']) > .1:
        raise ValueError('Comparison requires matching preview durations')
    delta = {k: b['metrics'][k] - a['metrics'][k] for k in ('sample_peak_dbfs', 'rms_dbfs', 'crest_db')}
    body = {'before_id': before_id, 'after_id': after_id, 'delta': delta,
            'band_energy_delta': {k: b['metrics']['band_energy_fraction'][k] - v
                                  for k, v in a['metrics']['band_energy_fraction'].items()},
            'after_gain_db_for_rms_matched_audition': -delta['rms_dbfs'],
            'verdict': 'pending_listening', 'next_step': 'Audition A/B at matched loudness; record accepted/rejected feedback. Louder is not automatically better.'}
    return dict(body, comparison_id=producer.store.add('comparison', body))
