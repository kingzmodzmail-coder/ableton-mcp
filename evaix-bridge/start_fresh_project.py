"""Initialize a verified empty Live Set; refuse existing musical content."""
import json
from pathlib import Path

from ableton_cmd import send_command
from MCP_Server.producer.engine import Producer


def main():
    root = Path('.producer/projects/mental-acid-001')
    root.mkdir(parents=True, exist_ok=True)
    journal = root / 'setup-journal.jsonl'
    if journal.exists():
        raise RuntimeError('Setup already started; inspect the journal before resuming')
    before = send_command('get_session_snapshot')
    tracks = before['tracks']
    if before['session']['is_playing'] or len(tracks) != 4:
        raise RuntimeError('Expected stopped four-track default Live Set')
    if any(t['devices'] or t['arrangement_clips'] or any(c['has_clip'] for c in t['clip_slots']) for t in tracks):
        raise RuntimeError('Set contains devices or musical content')
    if [t['is_midi_track'] for t in tracks] != [True, True, False, False]:
        raise RuntimeError('Unexpected default track layout')
    (root / 'before-setup.json').write_text(json.dumps(before, indent=2), encoding='utf-8')

    def command(name, params):
        with journal.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'command': name, 'params': params, 'status': 'pending'}) + '\n')
        result = send_command(name, params)
        with journal.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'command': name, 'status': 'completed', 'result': result}) + '\n')
        return result

    names = ['Kick', 'Acid 303', 'Atmospheres', 'FX', 'Bass', 'Percussion', 'Reference']
    for index, name in enumerate(names[:4]):
        command('set_track_name', {'track_index': index, 'name': name})
    for index, name in enumerate(names[4:], 4):
        command('create_audio_track' if name == 'Reference' else 'create_midi_track', {'index': -1})
        command('set_track_name', {'track_index': index, 'name': name})
    command('set_tempo', {'tempo': 162})
    after = send_command('get_session_snapshot')
    if [t['name'] for t in after['tracks']] != names or after['session']['tempo'] != 162:
        raise RuntimeError('Setup readback mismatch; inspect journal')
    (root / 'after-setup.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
    producer = Producer(root)
    producer.store.setting('profile', {
        'name': 'Mental Acid 001', 'tempo': 162, 'tempo_source': 'previous session starting assumption',
        'genre': 'mental / tribal / acid tekno', 'working_bars': 8,
        'preferences': ['dominant kick', 'sparse percussion', 'dark highs'],
        'status': 'empty project scaffold; instruments and patterns pending',
    })
    producer.remember('decision', 'Fresh Live Set initialized separately from Aftertekno. Build and evaluate eight bars at a time. No instruments or clips loaded yet.')
    producer.sync('new-project-scaffold')
    print(json.dumps({'project_memory': str(root.resolve()), 'tempo': 162, 'tracks': names, 'live_set_saved': False}))


if __name__ == '__main__':
    main()
