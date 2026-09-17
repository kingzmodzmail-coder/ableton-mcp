"""Tool registration uses the existing chat model as the producer/critic."""
import os
from pathlib import Path

from .engine import Producer


def register(mcp, connection):
    def engine():
        root = os.getenv('ABLETON_PRODUCER_HOME', str(Path.home() / '.ableton-producer'))
        return Producer(root, connection())

    @mcp.tool()
    def producer_sync(label: str = 'checkpoint') -> dict:
        """Persist complete Live state locally. Start each task by syncing.
        Snapshots are project memory, not saved Ableton .als files.
        """
        return engine().sync(label)

    @mcp.tool()
    def producer_context() -> dict:
        """Read song state, taste, feedback, plans and pending recovery journals.
        Use the conversation model for musical judgment. Never treat memory
        categories or measured loudness as automatic permission to change style.
        """
        return engine().context()

    @mcp.tool()
    def producer_set_profile(profile: dict) -> dict:
        """Persist project metadata: name, key, genre, references, target duration.
        Store enduring taste separately using producer_remember(category='taste').
        """
        return engine().store.setting('profile', profile)

    @mcp.tool()
    def producer_remember(category: str, text: str, related_id: str = '') -> dict:
        """Remember taste/song/decision/problem/todo/accepted/rejected feedback.
        Link feedback to a run or comparison so later changes respect verdicts.
        """
        return {'memory_id': engine().remember(category, text, related_id or None)}

    @mcp.tool()
    def producer_prepare(goal: str, actions: list[dict], start_beat: float = 0, bars: int = 8) -> dict:
        """Prepare a verified, reversible work section of at most eight bars.
        Actions: {tool:set_tempo,tempo}; {tool:set_device_parameter,track_index,
        device_index,parameter_index,value}; {tool:replace_midi_notes,track_index,
        clip_index,notes}; {tool:create_midi_clip,track_index,clip_index,length,name,notes}.
        Notes use pitch,start_time,duration,velocity,mute in beats. Indices are
        zero-based. Read state first. One operation per target. Tempo and device
        edits affect the song/track globally; start_beat is context, not automation.
        Existing expressive notes and automated parameters are rejected.
        """
        return engine().prepare(goal, actions, start_beat, bars)

    @mcp.tool()
    def producer_apply(plan_id: str) -> dict:
        """Apply a prepared plan once, journal inverse edits, verify each write.
        Stale plans are rejected. A timeout may mean the edit happened: inspect
        needs_recovery runs instead of blindly retrying. No audio judgment here.
        """
        return engine().apply(plan_id)

    @mcp.tool()
    def producer_undo(run_id: str) -> dict:
        """Restore a verified run's targets, only if no later target edits conflict.
        This is scoped undo for supported producer actions, not full-set restore.
        """
        return engine().undo(run_id)

    @mcp.tool()
    def producer_recover(run_id: str) -> dict:
        """Reconcile an interrupted run and restore provable before/after states.
        Partial or conflicting targets remain blocked for inspection, with
        original values and inverse edits retained in the run journal.
        """
        return engine().recover(run_id)

    @mcp.tool()
    def producer_analyze(path: str, label: str, bpm: float, version_id: str,
                         start_beat: float = 0, beats_per_bar: float = 4) -> dict:
        """Analyze and retain a local PCM WAV tied to a version and section.
        Measures RMS, sample peaks, crest, spectrum, stereo correlation and bar
        energy. Does not claim LUFS/true peak, genre recognition, or that it listened.
        """
        from .audio import analyze
        return analyze(engine(), path, label, bpm, version_id, start_beat, beats_per_bar)

    @mcp.tool()
    def producer_compare(before_id: str, after_id: str) -> dict:
        """Compare matching previews and provide gain for RMS-matched listening.
        Musical verdict stays pending until the critic/user actually auditions.
        """
        from .audio import compare
        return compare(engine(), before_id, after_id)

    @mcp.tool()
    def producer_audio_devices() -> list[dict]:
        """List output device names/IDs available for realtime loopback audition."""
        import soundcard as sc
        return [{'name': s.name, 'id': s.id} for s in sc.all_speakers()]

    @mcp.tool()
    def producer_capture(clips: list[dict], label: str, bars: int = 8, device: str = '') -> dict:
        """Capture selected Session clips via OS output loopback (requires audio extra).
        clips=[{track_index:0,clip_index:6},...]. Live must be stopped, selected
        tracks disarmed. Records 1–8 bars after two bars preroll. Restores stopped
        transport/playhead and previous launched slots, not playback phase.
        Select Live's actual output device. OS loopback also contains other apps.
        This is a realtime loop audition, not sample-accurate offline rendering.
        """
        from .capture import capture
        return capture(engine(), clips, label, bars, device or None)

    @mcp.tool()
    def producer_cycle(plan_id: str, clips: list[dict], device: str = '') -> dict:
        """Capture A, apply verified edits, capture B, compare, await musical verdict.
        Use existing Session clips and fixed tempo. If B capture fails, the edit
        remains applied and its run ID is returned for retry or undo. Read the
        result, audition, remember feedback, then plan the next bounded section.
        """
        from .capture import cycle
        return cycle(engine(), plan_id, clips, device or None)

    # ── Mix ear, QC gate and pre-flight ──────────────────────────────────────
    # These measure files on disk; none of them touch Live.

    @mcp.tool()
    def ear_scan(path: str, bpm: float, bars_per_section: int = 8) -> dict:
        """Measure a local PCM WAV: true peak, LUFS (when pyloudnorm is
        installed), crest, band energy, low-end mono compatibility, stereo
        width, section energy and kick/bass sub overlap. Measurement only —
        it has not listened, and a good number is not a good track.
        """
        from .ear import scan_file
        return scan_file(path, bpm, bars_per_section=bars_per_section)

    @mcp.tool()
    def ear_kick_bass(path: str, bpm: float) -> dict:
        """Check who owns 30–120 Hz. Compares sub energy under each kick with
        the gaps between kicks; between_to_kick_db near 0 means another element
        holds the sub. Assumes a kick on every beat.
        """
        from .audio import read_wav
        from .ear import kick_bass_overlap
        samples, rate = read_wav(path)
        return kick_bass_overlap(samples, rate, bpm)

    @mcp.tool()
    def ear_qc(path: str, bpm: float, profile_path: str = '',
               allow_unmeasured: bool = False) -> dict:
        """Run the QC gate on a render: hard rules (true-peak ceiling, low-end
        mono, sub ownership) plus a reference profile when given. A pass means
        'worth auditioning', not 'finished'. Never set allow_unmeasured to make
        a failing render pass.
        """
        from .ear import check, load_profile, scan_file
        profile = load_profile(profile_path) if profile_path else None
        measurements = scan_file(path, bpm)
        return {"metrics": measurements,
                "qc": check(measurements, profile, allow_unmeasured=allow_unmeasured)}

    @mcp.tool()
    def ear_build_reference_profile(paths: list[str], bpm: float, name: str,
                                    save_to: str = '') -> dict:
        """Build target ranges from approved reference renders (for Suno
        material, only after the approval gate). The profile describes those
        references; it is not a quality threshold.
        """
        from .ear import build_profile, save_profile, scan_file
        scans = [scan_file(path, bpm) for path in paths]
        profile = build_profile(scans, name)
        if save_to:
            profile['saved_to'] = save_profile(profile, save_to)
        return profile

    @mcp.tool()
    def producer_preflight(project: str = '.producer', min_free_gb: float = 20.0) -> dict:
        """Read-only check before a build: bridge reachable, script version as
        expected, full v2 snapshot contract, exactly one Live instance, disk
        headroom. Returns failures instead of starting a build that will be lost.
        """
        from .preflight import run
        return run(project=project, min_free_gb=min_free_gb)

    @mcp.tool()
    def pipeline_status(build: str, project: str = '.producer') -> dict:
        """Stage status for one build (intake → align → build → mix → master →
        qc → publish) and which stage runs next, so an interrupted build resumes
        instead of restarting.
        """
        from .pipeline import PipelineState
        return PipelineState(project, build).summary()
