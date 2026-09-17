import copy
import wave

import numpy as np
import pytest

from MCP_Server.producer import Producer
from MCP_Server.producer.audio import analyze, compare, measure
from MCP_Server.producer.engine import digest


def snapshot():
    return {'schema': 'ableton_mcp_snapshot_v2', 'include_notes': True, 'include_params': True,
            'session': {'tempo': 126., 'signature_numerator': 4, 'signature_denominator': 4,
                        'is_playing': False, 'current_song_time': 0},
            'tracks': [{'index': 0, 'name': '303', 'is_midi_track': True, 'arm': False,
                        'devices': [{'name': 'Drift', 'class_name': 'Drift', 'parameters': [
                            {'index': 0, 'name': 'Cutoff', 'value': .5, 'min': 0., 'max': 1., 'is_enabled': True}]}],
                        'arrangement_clips': [], 'clip_slots': [
                            {'index': 0, 'has_clip': True, 'clip': {'name': 'Acid', 'is_midi_clip': True,
                             'length': 32., 'notes': [{'pitch': 36, 'start_time': 0., 'duration': .25,
                                                      'velocity': 100., 'mute': False, 'note_id': 10}], 'note_count': 1}},
                            {'index': 1, 'has_clip': False, 'clip': None}]}]}


class FakeBridge:
    def __init__(self):
        self.state = snapshot()
        self.sent = []
        self.fail = None

    def send_command(self, command, params=None):
        params = params or {}
        self.sent.append(command)
        if command == self.fail:
            self.fail = None
            raise TimeoutError('injected timeout')
        if command == 'get_session_snapshot': return copy.deepcopy(self.state)
        if command == 'set_tempo': self.state['session']['tempo'] = params['tempo']
        elif command == 'set_device_parameter':
            self.state['tracks'][0]['devices'][0]['parameters'][0]['value'] = params['value']
        else:
            slot = self.state['tracks'][params['track_index']]['clip_slots'][params['clip_index']]
            if command == 'clear_notes_from_clip': slot['clip']['notes'] = []; slot['clip']['note_count'] = 0
            elif command == 'add_notes_to_clip':
                slot['clip']['notes'] += copy.deepcopy(params['notes'])
                slot['clip']['note_count'] = len(slot['clip']['notes'])
            elif command == 'create_clip':
                slot['has_clip'] = True
                slot['clip'] = {'name': '', 'is_midi_clip': True, 'length': params['length'], 'notes': [], 'note_count': 0}
            elif command == 'set_clip_name': slot['clip']['name'] = params['name']
            elif command == 'delete_clip': slot['clip'] = None; slot['has_clip'] = False
            else: raise AssertionError(command)
        return {}


@pytest.fixture
def producer(tmp_path):
    return Producer(tmp_path, FakeBridge())


def param(value=.65):
    return {'tool': 'set_device_parameter', 'track_index': 0, 'device_index': 0, 'parameter_index': 0, 'value': value}


def test_old_unresolved_journal_blocks_new_edits(producer):
    old = producer.store.add('run', {'status': 'needs_recovery'})
    for _ in range(201):
        producer.store.add('run', {'status': 'undone'})
    plan = producer.prepare('filter', [param()])
    with pytest.raises(ValueError, match=old):
        producer.apply(plan['plan_id'])
    assert 'set_device_parameter' not in producer.bridge.sent


def test_store_closes_connections_and_rolls_back(producer):
    import sqlite3
    with producer.store.connect() as db:
        db.execute('SELECT 1')
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with producer.store.connect() as db:
            db.execute("INSERT INTO settings VALUES ('rollback-test', '{}')")
            raise RuntimeError('abort')
    assert producer.store.setting('rollback-test') is None


def test_capture_refuses_arrangement_recording_before_transport(producer):
    from MCP_Server.producer.capture import capture
    producer.bridge.state['session']['record_mode'] = True
    with pytest.raises(ValueError, match='recording'):
        capture(producer, [{'track_index': 0, 'clip_index': 0}], 'preview')
    assert producer.bridge.sent == ['get_session_snapshot']


def test_audio_analysis_retains_exact_measured_bytes(producer, tmp_path, monkeypatch):
    from MCP_Server.producer import audio
    from pathlib import Path
    path = tmp_path / 'preview.wav'
    with wave.open(str(path), 'wb') as f:
        f.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        f.writeframes(np.full(4800, 1000, dtype='<i2').tobytes())
    original = path.read_bytes()
    real_measure = audio.measure
    def changed_source(*args, **kwargs):
        path.write_bytes(b'replaced during analysis')
        return real_measure(*args, **kwargs)
    monkeypatch.setattr(audio, 'measure', changed_source)
    result = audio.analyze(producer, path, 'test', 126, producer.sync()['version_id'])
    assert Path(result['path']).read_bytes() == original


def test_persistent_memory_and_separate_profile(producer):
    producer.store.setting('profile', {'key': 'G#m'})
    producer.remember('taste', 'Restrained percussion')
    producer.sync()
    reopened = Producer(producer.store.root, producer.bridge)
    assert reopened.context()['profile'] == {'key': 'G#m'}
    assert reopened.context()['memory'][0]['body']['category'] == 'taste'
    assert reopened.context()['version']['snapshot']['tracks'][0]['name'] == '303'


def test_stale_plan_rejected_without_writes(producer):
    plan = producer.prepare('filter', [param()])
    producer.bridge.state['tracks'][0]['name'] = 'Different song'
    with pytest.raises(ValueError, match='changed'):
        producer.apply(plan['plan_id'])
    assert 'set_device_parameter' not in producer.bridge.sent


def test_apply_once_and_undo(producer):
    original = digest(producer.bridge.state)
    plan = producer.prepare('filter', [param()])
    producer.bridge.state['session']['current_song_time'] = 22
    run = producer.apply(plan['plan_id'])
    assert producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] == .65
    with pytest.raises(ValueError, match='already attempted'): producer.apply(plan['plan_id'])
    assert producer.undo(run['run_id'])['status'] == 'undone'
    assert digest(producer.bridge.state) == original


def test_apply_preserves_external_change_between_steps(producer, monkeypatch):
    plan = producer.prepare('two steps', [{'tool': 'set_tempo', 'tempo': 130}, param()])
    original_send = producer.bridge.send_command

    def send(command, params=None):
        result = original_send(command, params)
        if command == 'set_tempo':
            producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] = .9
        return result

    monkeypatch.setattr(producer.bridge, 'send_command', send)
    with pytest.raises(RuntimeError, match='changed during execution'):
        producer.apply(plan['plan_id'])
    assert 'set_device_parameter' not in producer.bridge.sent
    run = producer.store.list('run')[0]
    assert run['body']['status'] == 'needs_recovery'
    assert producer.recover(run['id'])['status'] == 'recovered'
    assert producer.bridge.state['session']['tempo'] == 126
    assert producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] == .9


@pytest.mark.parametrize('operation', ['undo', 'recover'])
def test_restoration_preserves_change_between_steps(producer, monkeypatch, operation):
    plan = producer.prepare('two steps', [{'tool': 'set_tempo', 'tempo': 130}, param()])
    run = producer.apply(plan['plan_id'])
    if operation == 'recover':
        body = producer.store.get(run['run_id'], 'run')['body']
        body['status'] = 'needs_recovery'
        producer.store.update(run['run_id'], body)
    original_send = producer.bridge.send_command

    def send(command, params=None):
        result = original_send(command, params)
        if command == 'set_device_parameter':
            producer.bridge.state['session']['tempo'] = 145
        return result

    monkeypatch.setattr(producer.bridge, 'send_command', send)
    producer.bridge.sent.clear()
    with pytest.raises(ValueError, match='changed during'):
        getattr(producer, operation)(run['run_id'])
    assert 'set_tempo' not in producer.bridge.sent
    assert producer.bridge.state['session']['tempo'] == 145
    assert producer.store.get(run['run_id'], 'run')['body']['status'] == 'needs_recovery'


def test_undo_blocks_other_unresolved_journal(producer):
    run = producer.apply(producer.prepare('filter', [param()])['plan_id'])
    unresolved = producer.store.add('run', {'status': 'needs_recovery'})
    producer.bridge.sent.clear()
    with pytest.raises(ValueError, match=unresolved):
        producer.undo(run['run_id'])
    assert producer.bridge.sent == []


def test_undo_preserves_later_user_edits(producer):
    run = producer.apply(producer.prepare('filter', [param()])['plan_id'])
    producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] = .9
    with pytest.raises(ValueError, match='overwrite'): producer.undo(run['run_id'])


def test_new_clip_is_reversible(producer):
    before = digest(producer.bridge.state)
    notes = [{'pitch': 44, 'start_time': 1, 'duration': .5, 'velocity': 90},
             {'pitch': 32, 'start_time': 0, 'duration': .75, 'velocity': 110}]
    action = {'tool': 'create_midi_clip', 'track_index': 0, 'clip_index': 1, 'length': 32, 'name': 'New', 'notes': notes}
    run = producer.apply(producer.prepare('new phrase', [action])['plan_id'])
    assert producer.bridge.state['tracks'][0]['clip_slots'][1]['clip']['note_count'] == 2
    producer.undo(run['run_id'])
    assert digest(producer.bridge.state) == before


def test_replace_notes_is_reversible(producer):
    before = digest(producer.bridge.state)
    action = {'tool': 'replace_midi_notes', 'track_index': 0, 'clip_index': 0,
              'notes': [{'pitch': 40, 'start_time': 1, 'duration': .5, 'velocity': 90}]}
    run = producer.apply(producer.prepare('variation', [action])['plan_id'])
    producer.undo(run['run_id'])
    assert digest(producer.bridge.state) == before


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 2, True])
def test_parameter_validation(producer, value):
    with pytest.raises(ValueError): producer.prepare('bad', [param(value)])


def test_automation_and_duplicate_targets_rejected(producer):
    with pytest.raises(ValueError, match='One edit'): producer.prepare('bad', [param(), param(.7)])
    producer.bridge.state['tracks'][0]['devices'][0]['automated_parameters'] = ['Cutoff']
    with pytest.raises(ValueError, match='automated'): producer.prepare('bad', [param()])


def test_extended_note_properties_not_destroyed(producer):
    producer.bridge.state['tracks'][0]['clip_slots'][0]['clip']['notes'][0]['probability'] = .5
    with pytest.raises(ValueError, match='Expressive'):
        producer.prepare('bad', [{'tool': 'replace_midi_notes', 'track_index': 0, 'clip_index': 0, 'notes': []}])


def test_timeout_journal_and_recovery(producer):
    plan = producer.prepare('filter', [param()])
    producer.bridge.fail = 'set_device_parameter'
    with pytest.raises(RuntimeError, match='journal retained'): producer.apply(plan['plan_id'])
    record = producer.store.list('run')[0]
    assert record['body']['status'] == 'needs_recovery'
    assert record['body']['steps'][0]['inverse']['value'] == .5
    fresh = producer.prepare('filter', [param()])
    with pytest.raises(ValueError, match='Unresolved'): producer.apply(fresh['plan_id'])
    assert producer.recover(record['id'])['status'] == 'recovered'
    assert producer.apply(fresh['plan_id'])['status'] == 'applied'


def test_silence_and_sine_measurements():
    silence = measure(np.zeros((48000, 2)), 48000, 120)
    assert not silence['usable_signal']
    t = np.arange(48000) / 48000
    tone = .5 * np.sin(2 * np.pi * 60 * t)
    result = measure(np.column_stack([tone, tone]), 48000, 120)
    assert result['sample_peak_dbfs'] == pytest.approx(-6.0206, abs=.01)
    assert result['rms_dbfs'] == pytest.approx(-9.0309, abs=.01)
    assert result['band_energy_fraction']['sub_30_80'] > .99
    assert result['stereo_correlation'] == pytest.approx(1)


def test_phase_inversion_is_not_mistaken_for_silence():
    tone = .2 * np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000)
    result = measure(np.column_stack([tone, -tone]), 48000, 120)
    assert result['usable_signal']
    assert result['stereo_correlation'] == pytest.approx(-1)
    assert result['findings']


def test_audio_retained_comparison_and_feedback(producer, tmp_path):
    version = producer.sync()['version_id']
    path = tmp_path / 'preview.wav'
    analyses = []
    for gain in (.2, .4):
        values = np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000) * gain
        with wave.open(str(path), 'wb') as f:
            f.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
            f.writeframes((values * 32767).astype('<i2').tobytes())
        analyses.append(analyze(producer, path, 'test', 126, version))
    result = compare(producer, analyses[0]['analysis_id'], analyses[1]['analysis_id'])
    assert result['delta']['rms_dbfs'] == pytest.approx(6.02, abs=.01)
    assert result['verdict'] == 'pending_listening'
    assert analyses[0]['path'] != analyses[1]['path']
    producer.remember('rejected', 'Louder but too harsh', result['comparison_id'])
    changed = producer.store.get(analyses[1]['analysis_id'])['body']; changed['bpm'] = 130
    producer.store.update(analyses[1]['analysis_id'], changed)
    with pytest.raises(ValueError, match='matching bpm'): compare(producer, analyses[0]['analysis_id'], analyses[1]['analysis_id'])


def test_partial_note_write_is_journaled_not_retried(producer):
    action = {'tool': 'replace_midi_notes', 'track_index': 0, 'clip_index': 0,
              'notes': [{'pitch': 40, 'start_time': 1, 'duration': .5, 'velocity': 90}]}
    original = copy.deepcopy(producer.bridge.state)
    plan = producer.prepare('variation', [action])
    producer.bridge.fail = 'add_notes_to_clip'
    with pytest.raises(RuntimeError): producer.apply(plan['plan_id'])
    record = producer.store.list('run')[0]
    assert producer.bridge.sent.count('add_notes_to_clip') == 1
    with pytest.raises(ValueError, match='Partial/conflicting'): producer.recover(record['id'])
    # A manual repair from the saved snapshot permits reconciliation.
    producer.bridge.state = original
    assert producer.recover(record['id'])['status'] == 'recovered'


def test_recovery_after_write_succeeded_but_response_lost(producer):
    plan = producer.prepare('filter', [param()])
    producer.bridge.fail = 'set_device_parameter'
    with pytest.raises(RuntimeError): producer.apply(plan['plan_id'])
    # Simulate Live having received the timed-out edit after all.
    producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] = .65
    record = producer.store.list('run')[0]
    assert producer.recover(record['id'])['status'] == 'recovered'
    assert producer.bridge.state['tracks'][0]['devices'][0]['parameters'][0]['value'] == .5


def test_cycle_refuses_silent_baseline(producer, monkeypatch):
    from MCP_Server.producer import capture as module
    plan = producer.prepare('filter', [param()])
    monkeypatch.setattr(module, 'capture', lambda *a, **k: {'metrics': {'usable_signal': False}})
    with pytest.raises(ValueError, match='silent'):
        module.cycle(producer, plan['plan_id'], [{'track_index': 0, 'clip_index': 0}])
    assert 'set_device_parameter' not in producer.bridge.sent


def test_cycle_returns_undo_id_when_after_audio_fails(producer, monkeypatch):
    from MCP_Server.producer import capture as module
    plan = producer.prepare('filter', [param()])
    calls = []
    def capture(*a, **k):
        calls.append(1)
        if len(calls) > 1: raise RuntimeError('device lost')
        return {'metrics': {'usable_signal': True}, 'analysis_id': 'baseline', 'capture': {'clean_capture': True}}
    monkeypatch.setattr(module, 'capture', capture)
    result = module.cycle(producer, plan['plan_id'], [{'track_index': 0, 'clip_index': 0}])
    assert result['status'] == 'after_capture_failed'
    assert producer.undo(result['run_id'])['status'] == 'undone'


def test_mcp_tools_registered():
    from MCP_Server import server
    names = {tool.name for tool in server.mcp._tool_manager.list_tools()}
    assert {'producer_prepare', 'producer_cycle', 'producer_context', 'producer_recover'} <= names


def test_capture_does_not_interrupt_playback(producer):
    from MCP_Server.producer.capture import capture
    producer.bridge.state['session']['is_playing'] = True
    with pytest.raises(ValueError, match='Stop Live'):
        capture(producer, [{'track_index': 0, 'clip_index': 0}], 'test')
    assert producer.bridge.sent == ['get_session_snapshot']


def test_capture_refuses_armed_and_duplicate_tracks(producer):
    from MCP_Server.producer.capture import capture
    producer.bridge.state['tracks'][0]['arm'] = True
    with pytest.raises(ValueError, match='Disarm'):
        capture(producer, [{'track_index': 0, 'clip_index': 0}], 'test')
    producer.bridge.state['tracks'][0]['arm'] = False
    with pytest.raises(ValueError, match='one clip per track'):
        capture(producer, [{'track_index': 0, 'clip_index': 0}] * 2, 'test')


def test_cycle_refuses_discontinuous_baseline(producer, monkeypatch):
    from MCP_Server.producer import capture as module
    plan = producer.prepare('filter', [param()])
    monkeypatch.setattr(module, 'capture', lambda *a, **k: {
        'metrics': {'usable_signal': True}, 'capture': {'clean_capture': False}})
    with pytest.raises(ValueError, match='discontinuous'):
        module.cycle(producer, plan['plan_id'], [{'track_index': 0, 'clip_index': 0}])
    assert 'set_device_parameter' not in producer.bridge.sent


def test_compare_rejects_unverified_loopback_continuity(producer):
    a = {'bpm': 126, 'start_beat': 0, 'beats_per_bar': 4, 'source': 'output_loopback',
         'capture': {'clean_capture': False}}
    first = producer.store.add('analysis', a)
    second = producer.store.add('analysis', a)
    with pytest.raises(ValueError, match='continuity'): compare(producer, first, second)


def test_extra_fields_cannot_bypass_duplicate_target_guard(producer):
    actions = [{'tool': 'set_tempo', 'tempo': 130}, {'tool': 'set_tempo', 'tempo': 135, 'track_index': 0}]
    with pytest.raises(ValueError, match='unexpected fields'):
        producer.prepare('duplicate tempo', actions)
    assert 'set_tempo' not in producer.bridge.sent


def test_cycle_requires_positive_capture_integrity(producer, monkeypatch):
    from MCP_Server.producer import capture as module
    plan = producer.prepare('filter', [param()])
    monkeypatch.setattr(module, 'capture', lambda *a, **k: {'metrics': {'usable_signal': True}})
    with pytest.raises(ValueError, match='discontinuous'):
        module.cycle(producer, plan['plan_id'], [{'track_index': 0, 'clip_index': 0}])
    assert 'set_device_parameter' not in producer.bridge.sent


@pytest.mark.parametrize('rate', [0, -1, float('nan'), float('inf'), 192001])
def test_audio_measure_rejects_invalid_rates(rate):
    with pytest.raises(ValueError, match='sample rate'):
        measure(np.zeros((10, 2)), rate, 126)


def test_audio_rejects_corrupted_retained_artifact(producer, tmp_path):
    from pathlib import Path
    path = tmp_path / 'input.wav'
    with wave.open(str(path), 'wb') as f:
        f.setparams((1, 2, 48000, 0, 'NONE', 'not compressed'))
        f.writeframes(np.full(4800, 1000, dtype='<i2').tobytes())
    version = producer.sync()['version_id']
    first = analyze(producer, path, 'first', 126, version)
    Path(first['path']).write_bytes(b'partial write')
    with pytest.raises(ValueError, match='checksum mismatch'):
        analyze(producer, path, 'second', 126, version)


def test_audio_size_limit_checked_before_loading(producer, tmp_path, monkeypatch):
    from MCP_Server.producer import audio
    path = tmp_path / 'too-big.wav'
    path.write_bytes(b'x' * 65)
    monkeypatch.setattr(audio, 'MAX_WAV_BYTES', 64)
    with pytest.raises(ValueError, match='size limit'):
        analyze(producer, path, 'test', 126, producer.sync()['version_id'])
