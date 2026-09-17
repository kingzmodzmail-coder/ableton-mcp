import argparse
import json
import os
from pathlib import Path

from .engine import Producer


def main():
    parser = argparse.ArgumentParser(description='Local AI producer project brain')
    parser.add_argument('--project', default=os.getenv('ABLETON_PRODUCER_HOME', '.producer'))
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('sync'); p.add_argument('--label', default='checkpoint')
    commands.add_parser('context')
    p = commands.add_parser('profile'); p.add_argument('file')
    p = commands.add_parser('remember'); p.add_argument('category'); p.add_argument('text'); p.add_argument('--related-id')
    p = commands.add_parser('prepare'); p.add_argument('file', help='JSON goal/actions/start_beat/bars')
    for name in ('apply', 'undo', 'recover'):
        p = commands.add_parser(name); p.add_argument('id')
    p = commands.add_parser('analyze')
    p.add_argument('path'); p.add_argument('--label', required=True); p.add_argument('--bpm', type=float, required=True)
    p.add_argument('--version', required=True); p.add_argument('--start-beat', type=float, default=0)
    p.add_argument('--beats-per-bar', type=float, default=4)
    p = commands.add_parser('compare'); p.add_argument('before'); p.add_argument('after')
    for name in ('capture', 'cycle'):
        p = commands.add_parser(name); p.add_argument('clips_file'); p.add_argument('--device')
        if name == 'capture':
            p.add_argument('--label', required=True); p.add_argument('--bars', type=int, default=8)
        else:
            p.add_argument('--plan', required=True)
    commands.add_parser('devices')

    # Mix ear, QC gate, reference profiles, pre-flight and pipeline stages
    p = commands.add_parser('ear', help='measure a WAV (no Live needed)')
    p.add_argument('path'); p.add_argument('--bpm', type=float, required=True)
    p.add_argument('--bars-per-section', type=int, default=8)
    p = commands.add_parser('qc', help='run the QC gate on a render')
    p.add_argument('path'); p.add_argument('--bpm', type=float, required=True)
    p.add_argument('--profile', default=''); p.add_argument('--allow-unmeasured', action='store_true')
    p = commands.add_parser('refprofile', help='build target ranges from reference renders')
    p.add_argument('paths', nargs='+'); p.add_argument('--bpm', type=float, required=True)
    p.add_argument('--name', required=True); p.add_argument('--save-to', default='')
    p = commands.add_parser('preflight', help='check bridge, Live, snapshot and disk')
    p.add_argument('--min-free-gb', type=float, default=20.0)
    p = commands.add_parser('sections', help='validate a YAML/JSON section map')
    p.add_argument('file')
    p = commands.add_parser('pipeline', help='pipeline stages for one build')
    stages = p.add_subparsers(dest='stage', required=True)
    stages.add_parser('status').add_argument('build')
    q = stages.add_parser('intake'); q.add_argument('build'); q.add_argument('inbox')
    q = stages.add_parser('align'); q.add_argument('build'); q.add_argument('--bpm', type=float)
    q = stages.add_parser('qc'); q.add_argument('build'); q.add_argument('path')
    q.add_argument('--bpm', type=float, required=True); q.add_argument('--profile', default='')
    q = stages.add_parser('publish'); q.add_argument('build'); q.add_argument('--title', required=True)
    q.add_argument('--bpm', type=float, required=True); q.add_argument('--key', default='')
    q.add_argument('--link', default='')
    args = parser.parse_args()
    producer = Producer(args.project)
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if args.command == 'sync': result = producer.sync(args.label)
        elif args.command == 'context': result = producer.context()
        elif args.command == 'profile': result = producer.store.setting('profile', read(args.file))
        elif args.command == 'remember': result = {'memory_id': producer.remember(args.category, args.text, args.related_id)}
        elif args.command == 'prepare': result = producer.prepare(**read(args.file))
        elif args.command == 'apply': result = producer.apply(args.id)
        elif args.command == 'undo': result = producer.undo(args.id)
        elif args.command == 'recover': result = producer.recover(args.id)
        elif args.command == 'analyze':
            from .audio import analyze
            result = analyze(producer, args.path, args.label, args.bpm, args.version, args.start_beat, args.beats_per_bar)
        elif args.command == 'compare':
            from .audio import compare
            result = compare(producer, args.before, args.after)
        elif args.command == 'ear':
            from .ear import scan_file
            result = scan_file(args.path, args.bpm, bars_per_section=args.bars_per_section)
        elif args.command == 'qc':
            from .ear import check, load_profile, scan_file
            profile = load_profile(args.profile) if args.profile else None
            metrics = scan_file(args.path, args.bpm)
            result = {'metrics': metrics,
                      'qc': check(metrics, profile, allow_unmeasured=args.allow_unmeasured)}
        elif args.command == 'refprofile':
            from .ear import build_profile, save_profile, scan_file
            result = build_profile([scan_file(path, args.bpm) for path in args.paths], args.name)
            if args.save_to:
                result['saved_to'] = save_profile(result, args.save_to)
        elif args.command == 'preflight':
            from .preflight import run as preflight
            result = preflight(project=args.project, min_free_gb=args.min_free_gb)
        elif args.command == 'sections':
            from .pipeline import load_section_map
            result = load_section_map(args.file)
        elif args.command == 'pipeline':
            from .pipeline import PipelineState, align, intake, publish, qc_stage
            state = PipelineState(args.project, args.build)
            if args.stage == 'status':
                result = state.summary()
            elif args.stage == 'intake':
                result = intake(args.inbox, state)
            elif args.stage == 'align':
                state.require('align')
                manifest = read(state.artifacts('intake')['manifest'])
                result = align(manifest, args.bpm, state)
            elif args.stage == 'qc':
                from .ear import load_profile
                profile = load_profile(args.profile) if args.profile else None
                result = qc_stage(args.path, args.bpm, profile, state)
            else:
                state.require('publish')
                result = publish(read(state.artifacts('qc')['report']),
                                 args.title, args.bpm, args.key, args.link, state)
        elif args.command == 'devices':
            import soundcard as sc
            result = [{'id': s.id, 'name': s.name} for s in sc.all_speakers()]
        else:
            from .capture import capture, cycle
            if args.command == 'capture': result = capture(producer, read(args.clips_file), args.label, args.bars, args.device)
            else: result = cycle(producer, args.plan, read(args.clips_file), args.device)
        print(json.dumps(result, indent=2, allow_nan=False))
    except Exception as error:
        parser.exit(1, json.dumps({'error': str(error)}) + '\n')


if __name__ == '__main__':
    main()
