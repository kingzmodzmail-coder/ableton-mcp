"""Bounded output-loopback audition of explicitly selected Session clips.

This captures the selected OS output, not Live's offline export. Two bars of
preroll let clip launches settle. It is not sample-accurate render alignment.
"""
import multiprocessing as mp
import uuid
import wave
import warnings

from .audio import analyze, compare
from .engine import digest, indexed, number


def _record(pipe, path, seconds, preroll, device):
    try:
        import numpy as np
        import soundcard as sc
        speaker = sc.get_speaker(device) if device else sc.default_speaker()
        microphone = sc.get_microphone(speaker.id, include_loopback=True)
        if not microphone.isloopback:
            raise ValueError('Selected device is not an output loopback')
        rate = 48000
        with microphone.recorder(samplerate=rate, channels=2, blocksize=1024) as recorder:
            pipe.send({'ready': True, 'device': speaker.name})
            if not pipe.poll(20) or pipe.recv() != 'go':
                raise TimeoutError('No playback start signal')
            with warnings.catch_warnings(record=True) as warmup_warnings:
                warnings.simplefilter('always')
                recorder.record(numframes=round(preroll * rate))
            with warnings.catch_warnings(record=True) as measured_warnings:
                warnings.simplefilter('always')
                samples = recorder.record(numframes=round(seconds * rate))
        # Retain PCM32; overrange is separately recorded before conversion.
        if samples.shape != (round(seconds * rate), 2) or not np.isfinite(samples).all():
            raise ValueError('Recorder returned incomplete or non-finite audio')
        overrange = float(np.mean(np.abs(samples) > 1))
        pcm = (np.clip(samples.astype(np.float64), -1, 1 - 2 ** -31) * (2 ** 31)).astype('<i4')
        with wave.open(str(path), 'wb') as wav:
            wav.setparams((2, 4, rate, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm.tobytes())
        pipe.send({'ok': True, 'device': speaker.name, 'overrange_fraction': overrange,
                   'warmup_warnings': [str(w.message) for w in warmup_warnings],
                   'measured_warnings': [str(w.message) for w in measured_warnings]})
    except Exception as error:
        pipe.send({'error': str(error)})
    finally:
        pipe.close()


def capture(producer, clips, label, bars=8, device=None):
    """Audition selected Session slots; transport must be stopped.

    Restores previously launched slots and stopped transport/playhead. Does not
    restore their playback phase or affect Arrangement content.
    """
    with producer.lock():
        before = producer.snapshot()
        session = before['session']
        if session['is_playing']:
            raise ValueError('Stop Live before a bounded preview')
        if session.get('loop'):
            raise ValueError('Disable Arrangement looping before a Session preview')
        if session.get('record_mode') or any(t.get('arm') for t in before['tracks']):
            raise ValueError('Disarm all tracks and disable Arrangement recording before capture')
        if any(s['clip'].get('is_recording') for t in before['tracks'] for s in t['clip_slots'] if s.get('clip')):
            raise ValueError('Stop recording before capture')
        if not isinstance(clips, list) or not clips or len(clips) > 32:
            raise ValueError('Provide explicit track_index/clip_index selections')
        if type(bars) is not int or not 1 <= bars <= 8:
            raise ValueError('Preview length must be 1–8 bars')
        selected = []
        for location in clips:
            track = indexed(before['tracks'], location.get('track_index'))
            slot = indexed(track['clip_slots'], location.get('clip_index'))
            if not slot.get('clip'):
                raise ValueError('Preview slot is empty')
            if track.get('arm') or any(s.get('clip', {}).get('is_recording') for s in track['clip_slots'] if s.get('clip')):
                raise ValueError('Disarm preview tracks and stop recording before capture')
            selected.append({'track_index': track['index'], 'clip_index': slot['index']})
        if len({x['track_index'] for x in selected}) != len(selected):
            raise ValueError('Select only one clip per track')
        active = [{'track_index': t['index'], 'clip_index': s['index']}
                  for t in before['tracks'] for s in t['clip_slots']
                  if s.get('clip') and s['clip'].get('is_playing')]
        bpm = number(session['tempo'], 20, 300)
        meter = session['signature_numerator'] * 4 / session['signature_denominator']
        seconds, preroll = bars * meter * 60 / bpm, 2 * meter * 60 / bpm
        if seconds + preroll > 60:
            raise ValueError('Preview plus preroll must fit within 60 seconds; reduce bars')
        # Move beyond existing Arrangement clips so unselected Arrangement audio
        # cannot bleed into this Session audition.
        audition_time = max((c['end_time'] for t in before['tracks'] for c in t['arrangement_clips']), default=0) + 32
        version = producer.store.add('version', {'label': label, 'snapshot': before, 'hash': digest(before)})
        folder = producer.store.root / 'audio'
        folder.mkdir(exist_ok=True)
        path = folder / (uuid.uuid4().hex + '.wav')
        ctx = mp.get_context('spawn')
        parent, child = ctx.Pipe()
        process = ctx.Process(target=_record, args=(child, str(path), seconds, preroll, device), daemon=True)
        process.start()
        child.close()
        started = False
        restored = []
        try:
            if not parent.poll(15):
                raise TimeoutError('Audio device did not open within 15 seconds')
            response = parent.recv()
            if not response.get('ready'):
                raise RuntimeError(response.get('error', 'Recorder failed'))
            started = True
            for location in active:
                producer.bridge.send_command('stop_clip', location)
            producer.bridge.send_command('set_current_song_time', {'time': audition_time})
            # Clip fires can start transport. Recorder is already open.
            for location in selected:
                producer.bridge.send_command('fire_clip', location)
            producer.bridge.send_command('start_playback')
            parent.send('go')
            if not parent.poll(seconds + preroll + 10):
                raise TimeoutError('Audio capture timed out')
            response = parent.recv()
            if not response.get('ok'):
                raise RuntimeError(response.get('error', 'Audio capture failed'))
        finally:
            if started:
                # Every restoration operation is attempted even if one fails.
                operations = [('stop_playback', {})]
                operations += [('stop_clip', location) for location in selected]
                operations += [('fire_clip', location) for location in active]
                operations += [('stop_playback', {}), ('set_current_song_time', {'time': session['current_song_time']})]
                for command, params in operations:
                    try:
                        producer.bridge.send_command(command, params)
                    except Exception as error:
                        restored.append(str(error))
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            parent.close()
            if restored:
                producer.store.add('memory', {'category': 'problem', 'text': 'Preview transport restoration failed', 'errors': restored})
                raise RuntimeError('Capture finished but transport restoration failed: ' + '; '.join(restored))
        result = analyze(producer, path, label, bpm, version, 0, meter, 'output_loopback')
        result['capture'] = {'clips': selected, 'device': response['device'], 'preroll_bars': 2,
                             'overrange_fraction': response['overrange_fraction'],
                             'warmup_warnings': response['warmup_warnings'],
                             'measured_warnings': response['measured_warnings'],
                             'clean_capture': not response['measured_warnings'],
                             'alignment': 'steady-state loop audition, not sample-accurate export'}
        stored = dict(result)
        stored.pop('analysis_id')
        producer.store.update(result['analysis_id'], stored)
        return result


def cycle(producer, plan_id, clips, device=None):
    plan = producer.store.get(plan_id, 'plan')['body']
    if any(s['action']['tool'] == 'set_tempo' for s in plan['actions']):
        raise ValueError('Tempo-changing plans cannot use same-tempo A/B')
    selected = {(c['track_index'], c['clip_index']) for c in clips}
    selected_tracks = {t for t, _ in selected}
    for step in plan['actions']:
        a = step['action']
        if a['tool'] == 'create_midi_clip':
            raise ValueError('Create clips first, then compare edits to existing clips')
        if a.get('track_index') not in selected_tracks or ('clip_index' in a and (a['track_index'], a['clip_index']) not in selected):
            raise ValueError('Every edit must affect the selected audition clips')
    if digest(producer.snapshot()) != plan['snapshot_hash']:
        raise ValueError('Plan is stale; prepare again')
    before = capture(producer, clips, 'A: ' + plan['goal'], plan['bars'], device)
    if not before['metrics']['usable_signal'] or not before.get('capture', {}).get('clean_capture', False):
        raise ValueError('Baseline is silent or discontinuous; edit was not applied')
    run = producer.apply(plan_id)
    try:
        after = capture(producer, clips, 'B: ' + plan['goal'], plan['bars'], device)
        comparison = compare(producer, before['analysis_id'], after['analysis_id'])
    except Exception as error:
        return {'status': 'after_capture_failed', 'run_id': run['run_id'], 'before_id': before['analysis_id'],
                'error': str(error), 'next_step': 'Retry capture or undo the applied run; edit remains applied.'}
    result = {'status': 'awaiting_listening', 'run_id': run['run_id'], 'comparison': comparison}
    producer.store.add('cycle', result)
    return result
