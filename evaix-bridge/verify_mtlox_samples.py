"""Verify downloaded MTLOX PCM files and retain their local provenance."""
import hashlib
import json
import wave
from pathlib import Path

import numpy as np

from MCP_Server.producer.engine import Producer


root = Path('.producer/projects/mental-acid-001')
entries = json.loads((root / 'samples/manifest.json').read_text())
results = []
for entry in entries:
    path = root / 'samples' / entry['name']
    payload = path.read_bytes()
    assert len(payload) == entry['bytes']
    with wave.open(str(path)) as stream:
        channels, width, rate, frames = stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes()
        pcm = stream.readframes(frames)
        assert len(pcm) == frames * channels * width
        assert frames > 0 and width in (2, 3, 4)
        if width == 3:
            b = np.frombuffer(pcm, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
            values = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
            values = (values ^ 0x800000) - 0x800000
        else:
            values = np.frombuffer(pcm, dtype='<i' + str(width))
        peak = float(np.max(np.abs(values.astype(np.float64)))) / 2 ** (width * 8 - 1)
        assert peak > 0, 'Silent file'
    results.append({**entry, 'path': str(path.resolve()), 'sha256': hashlib.sha256(payload).hexdigest(),
                    'channels': channels, 'sample_rate': rate, 'bits': width * 8,
                    'duration_s': frames / rate, 'sample_peak': peak})
(root / 'samples/verified.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
Producer(root).remember('decision', 'Eight MTLOX WAV files downloaded and PCM-verified locally. Paths, source URLs and SHA-256 checksums are in samples/verified.json. Ready for audition; no Live edits made by download.')
print(json.dumps(results, indent=2))
