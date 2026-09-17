import copy
import hashlib
import json
import math
from contextlib import contextmanager

from .bridge import Bridge
from .store import Store


VOLATILE = {'is_playing', 'is_recording', 'current_song_time', 'note_id', 'value_string'}


def stable(value):
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [stable(v) for v in value]
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        return round(float(value), 6)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(stable(value), sort_keys=True, allow_nan=False).encode()).hexdigest()


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Number outside permitted range [%s, %s]' % (low, high))
    return value


def indexed(items, index):
    if type(index) is not int or not 0 <= index < len(items):
        raise ValueError('Invalid index: %r' % index)
    return items[index]


class Producer:
    def __init__(self, root, bridge=None):
        self.store = Store(root)
        self.bridge = bridge or Bridge()

    @contextmanager
    def lock(self):
        # A SQLite write lock coordinates separate CLI and MCP processes.
        # Separate database: journal writes must remain possible during execution.
        import sqlite3
        lock = sqlite3.connect(self.store.root / 'execution.sqlite3', timeout=1)
        try:
            lock.execute('CREATE TABLE IF NOT EXISTS mutex (id INTEGER)')
            lock.execute('BEGIN IMMEDIATE')
            yield
        finally:
            lock.rollback()
            lock.close()

    def snapshot(self):
        result = self.bridge.send_command('get_session_snapshot', {'include_notes': True, 'include_params': True})
        if result.get('schema') != 'ableton_mcp_snapshot_v2' or not result.get('include_notes') or not result.get('include_params'):
            schema = result.get('schema') or result.get('snapshot_schema') or 'unknown'
            raise ValueError(
                'Complete v2 snapshot required; received %s. '
                'The active bridge does not provide the producer snapshot contract. '
                'Check bridge capabilities and implementation before replacing scripts.' % schema
            )
        return result

    def sync(self, label='checkpoint'):
        snapshot = self.snapshot()
        identity = self.store.add('version', {'label': label, 'snapshot': snapshot, 'hash': digest(snapshot)})
        self.store.setting('current_version', identity)
        return {'version_id': identity, 'tempo': snapshot['session']['tempo'],
                'tracks': [{'index': t['index'], 'name': t['name']} for t in snapshot['tracks']]}

    def context(self):
        version = self.store.setting('current_version')
        return {'profile': self.store.setting('profile') or {},
                'version': self.store.get(version)['body'] if version else None,
                'memory': self.store.list('memory'), 'plans': self.store.list('plan', 5),
                'runs': self.store.list('run', 5), 'analyses': self.store.list('analysis', 5)}

    def remember(self, category, text, related_id=None):
        if category not in {'taste', 'song', 'decision', 'problem', 'todo', 'accepted', 'rejected'} or not text.strip():
            raise ValueError('Use taste/song/decision/problem/todo/accepted/rejected and nonempty text')
        if related_id:
            self.store.get(related_id)
        return self.store.add('memory', {'category': category, 'text': text, 'related_id': related_id})

    def target(self, snapshot, action):
        kind = action['tool']
        if kind == 'set_tempo':
            return {'tempo': snapshot['session']['tempo']}
        track = indexed(snapshot['tracks'], action.get('track_index'))
        identity = {'track_index': track['index'], 'track_name': track['name'],
                    'devices': [(d['name'], d['class_name']) for d in track['devices']]}
        if kind == 'set_device_parameter':
            device = indexed(track['devices'], action.get('device_index'))
            parameter = indexed(device['parameters'], action.get('parameter_index'))
            return dict(identity, parameter=parameter, automated=device.get('automated_parameters', []))
        if kind in {'replace_midi_notes', 'create_midi_clip'}:
            slot = indexed(track['clip_slots'], action.get('clip_index'))
            return dict(identity, slot=slot)
        raise ValueError('Unsupported reversible tool: ' + kind)

    def notes(self, notes, length):
        if not isinstance(notes, list) or len(notes) > 8192:
            raise ValueError('Expected at most 8192 notes')
        output = []
        for n in notes:
            pitch = number(n.get('pitch'), 0, 127)
            if int(pitch) != pitch:
                raise ValueError('Pitch must be an integer')
            start = number(n.get('start_time'), 0, length)
            duration = number(n.get('duration'), 0.001, length)
            if start + duration > length + 1e-6:
                raise ValueError('Note extends beyond clip')
            if type(n.get('mute', False)) is not bool:
                raise ValueError('mute must be boolean')
            output.append({'pitch': int(pitch), 'start_time': float(start), 'duration': float(duration),
                           'velocity': float(number(n.get('velocity', 100), 1, 127)), 'mute': n.get('mute', False)})
        return sorted(output, key=lambda n: (n['start_time'], n['pitch'], n['duration'], n['velocity'], n['mute']))

    def prepare(self, goal, actions, start_beat=0, bars=8):
        if not goal.strip() or not isinstance(actions, list) or not 1 <= len(actions) <= 32:
            raise ValueError('Provide a goal and 1–32 actions')
        if type(bars) is not int or not 1 <= bars <= 8:
            raise ValueError('Work in sections of 1–8 bars')
        number(start_beat, 0, 1000000)
        snapshot = self.snapshot()
        beats_per_bar = snapshot['session']['signature_numerator'] * 4 / snapshot['session']['signature_denominator']
        prepared, targets = [], set()
        for original in actions:
            fields = {
                'set_tempo': {'tool', 'tempo'},
                'set_device_parameter': {'tool', 'track_index', 'device_index', 'parameter_index', 'value'},
                'replace_midi_notes': {'tool', 'track_index', 'clip_index', 'notes'},
                'create_midi_clip': {'tool', 'track_index', 'clip_index', 'length', 'name', 'notes'},
            }
            if not isinstance(original, dict) or original.get('tool') not in fields:
                raise ValueError('Unsupported reversible action')
            if set(original) != fields[original['tool']]:
                raise ValueError('Action has missing or unexpected fields')
            a = copy.deepcopy(original)
            target = self.target(snapshot, a)
            key = (a['tool'] if a['tool'] == 'set_tempo' else 'slot' if 'clip_index' in a else 'param',
                   a.get('track_index'), a.get('clip_index'), a.get('device_index'), a.get('parameter_index'))
            if key in targets:
                raise ValueError('One edit per target per plan')
            targets.add(key)
            if a['tool'] == 'set_tempo':
                number(a.get('tempo'), 20, 300)
                inverse = {'tool': 'set_tempo', 'tempo': target['tempo']}
            elif a['tool'] == 'set_device_parameter':
                p = target['parameter']
                if not p.get('is_enabled', True) or p['name'] in target['automated'] or p.get('automation_state', 0) != 0:
                    raise ValueError('Parameter disabled or automated; choose a manual control')
                value = number(a.get('value'), p['min'], p['max'])
                if p.get('is_quantized') and value != int(value):
                    raise ValueError('Quantized parameters require integer values')
                inverse = dict(a, value=p['value'])
            else:
                clip = target['slot'].get('clip')
                if a['tool'] == 'create_midi_clip':
                    if clip or not snapshot['tracks'][a['track_index']]['is_midi_track']:
                        raise ValueError('An empty MIDI clip slot is required')
                    length = number(a.get('length'), .25, bars * beats_per_bar)
                    if not isinstance(a.get('name'), str) or not a['name'].strip():
                        raise ValueError('New clips require a name')
                    inverse = {'tool': 'delete_clip', 'track_index': a['track_index'], 'clip_index': a['clip_index']}
                else:
                    if not clip or not clip.get('is_midi_clip'):
                        raise ValueError('Existing MIDI clip required')
                    length = clip['length']
                    if length > bars * beats_per_bar:
                        raise ValueError('Select a MIDI clip no longer than the work section')
                    # The installed bridge writes five-field notes. Do not silently erase expression.
                    for n in clip['notes']:
                        if n.get('probability', 1) != 1 or n.get('velocity_deviation', 0) != 0 or n.get('release_velocity', 0) != 0:
                            raise ValueError('Expressive/probabilistic notes require a richer bridge writer')
                    inverse = dict(a, notes=self.notes(clip['notes'], length))
                a['notes'] = self.notes(a.get('notes'), length)
            prepared.append({'action': a, 'before': target, 'inverse': inverse})
        version = self.store.add('version', {'label': 'before: ' + goal, 'snapshot': snapshot, 'hash': digest(snapshot)})
        plan = {'goal': goal, 'version_id': version, 'snapshot_hash': digest(snapshot),
                'start_beat': start_beat, 'bars': bars, 'beats_per_bar': beats_per_bar,
                'actions': prepared, 'status': 'prepared'}
        identity = self.store.add('plan', plan)
        return dict(plan, plan_id=identity)

    def execute(self, action):
        a = dict(action)
        kind = a.pop('tool')
        if kind in {'replace_midi_notes', 'create_midi_clip'}:
            location = {k: a[k] for k in ('track_index', 'clip_index')}
            if kind == 'create_midi_clip':
                self.bridge.send_command('create_clip', dict(location, length=a['length']))
                self.bridge.send_command('set_clip_name', dict(location, name=a['name']))
            else:
                self.bridge.send_command('clear_notes_from_clip', location)
            if a['notes']:
                self.bridge.send_command('add_notes_to_clip', dict(location, notes=a['notes']))
        else:
            allowed = {'set_tempo': ('tempo',), 'set_device_parameter': ('track_index', 'device_index', 'parameter_index', 'value'),
                       'delete_clip': ('track_index', 'clip_index')}
            self.bridge.send_command(kind, {k: a[k] for k in allowed[kind]})

    def verify(self, snapshot, action):
        target = self.target(snapshot, action)
        if action['tool'] == 'set_tempo':
            matched = abs(target['tempo'] - action['tempo']) < 1e-4
        elif action['tool'] == 'set_device_parameter':
            matched = abs(target['parameter']['value'] - action['value']) < 1e-4
        else:
            clip = target['slot']['clip']
            matched = bool(clip) and digest(self.notes(clip['notes'], clip['length'])) == digest(action['notes'])
            if action['tool'] == 'create_midi_clip':
                matched = matched and clip['name'] == action['name'] and clip['length'] == action['length']
        if not matched:
            raise ValueError('Live readback did not match the planned edit')
        return target

    def apply(self, plan_id):
        with self.lock():
            # An ambiguous prior write must be examined before more automation.
            unresolved = self.store.unresolved_run()
            if unresolved:
                raise ValueError('Unresolved run: ' + unresolved)
            plan = self.store.get(plan_id, 'plan')['body']
            if plan['status'] != 'prepared':
                raise ValueError('Plan already attempted; prepare a fresh plan')
            before = self.snapshot()
            if digest(before) != plan['snapshot_hash']:
                raise ValueError('Live changed since planning; sync and prepare again')
            run = {'plan_id': plan_id, 'status': 'executing', 'steps': []}
            run_id = self.store.add('run', run)
            plan['status'] = 'attempted'
            self.store.update(plan_id, plan)
            try:
                # One full snapshot per step instead of two. `before` was read
                # a moment ago and already digest-matched the plan, so step 0
                # reuses it; afterwards the post-execute read that verifies
                # step N is also the pre-check for step N+1. Only a local
                # SQLite write separates them, so re-reading Live in between
                # bought no freshness the next per-step check does not give.
                current = before
                for step in plan['actions']:
                    if digest(self.target(current, step['action'])) != digest(step['before']):
                        raise ValueError('Target changed during execution; remaining edits stopped')
                    entry = dict(step, status='attempting')
                    run['steps'].append(entry)
                    self.store.update(run_id, run)  # durable before the first write
                    self.execute(step['action'])
                    current = self.snapshot()
                    entry['after'] = self.verify(current, step['action'])
                    entry['status'] = 'verified'
                    self.store.update(run_id, run)
                run['status'] = 'applied'
                run['version_id'] = self.sync(plan['goal'])['version_id']
            except Exception as error:
                run['status'] = 'needs_recovery'
                run['error'] = str(error)
                self.store.update(run_id, run)
                raise RuntimeError('Edit interrupted; journal retained at run ' + run_id + ': ' + str(error)) from error
            self.store.update(run_id, run)
            return dict(run, run_id=run_id)

    def undo(self, run_id):
        with self.lock():
            unresolved = self.store.unresolved_run()
            if unresolved:
                raise ValueError('Unresolved run: ' + unresolved)
            run = self.store.get(run_id, 'run')['body']
            if run['status'] != 'applied':
                raise ValueError('Automatic undo requires a fully verified applied run; inspect interrupted journals manually')
            current = self.snapshot()
            for step in run['steps']:
                if digest(self.target(current, step['action'])) != digest(step['after']):
                    raise ValueError('Edited target changed since this run; undo would overwrite newer work')
            run['status'] = 'undoing'
            self.store.update(run_id, run)
            try:
                for step in reversed(run['steps']):
                    if digest(self.target(self.snapshot(), step['action'])) != digest(step['after']):
                        raise ValueError('Target changed during undo; remaining edits stopped')
                    self.execute(step['inverse'])
                    target = self.target(self.snapshot(), step['action'])
                    if digest(target) != digest(step['before']):
                        raise ValueError('Undo verification failed')
                    step['status'] = 'undone'
                    self.store.update(run_id, run)
                run['status'] = 'undone'
                run['undo_version_id'] = self.sync('undo ' + run_id)['version_id']
            except Exception as error:
                run['status'] = 'needs_recovery'
                run['error'] = str(error)
                self.store.update(run_id, run)
                raise
            self.store.update(run_id, run)
            return run

    def recover(self, run_id):
        """Reconcile an interrupted run, restoring only provably owned states.

        If a write partially cleared a clip, manual inspection is required;
        repairing it to its saved before state lets this method close the run.
        """
        with self.lock():
            run = self.store.get(run_id, 'run')['body']
            if run['status'] not in {'executing', 'needs_recovery', 'undoing'}:
                raise ValueError('Run is not interrupted')
            current = self.snapshot()
            states = []
            for step in run['steps']:
                target = self.target(current, step['action'])
                if digest(target) == digest(step['before']):
                    states.append('before')
                else:
                    try:
                        expected = self.verify(current, step['action'])
                        if step.get('after') and digest(expected) != digest(step['after']):
                            raise ValueError('Target identity changed')
                        # Verify names/devices separately for a timed-out write without an after image.
                        for key in ('track_name', 'devices'):
                            if key in target and digest(target[key]) != digest(step['before'][key]):
                                raise ValueError('Target identity changed')
                        if step['action']['tool'] == 'set_device_parameter':
                            previous = dict(step['before']['parameter'])
                            actual = dict(target['parameter'])
                            previous.pop('value'); actual.pop('value')
                            if digest(previous) != digest(actual):
                                raise ValueError('Parameter identity changed')
                        elif step['action']['tool'] == 'replace_midi_notes':
                            previous = dict(step['before']['slot']['clip'])
                            actual = dict(target['slot']['clip'])
                            for key in ('notes', 'note_count'):
                                previous.pop(key, None); actual.pop(key, None)
                            if digest(previous) != digest(actual):
                                raise ValueError('Clip identity changed')
                    except Exception as error:
                        raise ValueError('Partial/conflicting target; inspect saved before/inverse in run ' + run_id) from error
                    states.append('after')
            try:
                for step, state in reversed(list(zip(run['steps'], states))):
                    if digest(self.target(self.snapshot(), step['action'])) != digest(self.target(current, step['action'])):
                        raise ValueError('Target changed during recovery; remaining edits stopped')
                    if state == 'after':
                        self.execute(step['inverse'])
                    if digest(self.target(self.snapshot(), step['action'])) != digest(step['before']):
                        raise ValueError('Recovery verification failed')
                    step['status'] = 'restored'
                    self.store.update(run_id, run)
                run['status'] = 'recovered'
                run['recovery_version_id'] = self.sync('recovery ' + run_id)['version_id']
                self.store.update(run_id, run)
                return run
            except Exception as error:
                run['status'] = 'needs_recovery'
                run['error'] = str(error)
                self.store.update(run_id, run)
                raise
