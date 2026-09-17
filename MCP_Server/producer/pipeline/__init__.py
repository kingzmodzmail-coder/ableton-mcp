"""The producer pipeline: one named stage per step, resumable, QC-gated.

intake -> align -> build -> mix -> master -> qc -> publish

Stages that only read or measure files run here. ``build``, ``mix`` and
``master`` need a live Ableton bridge, so they raise ``StageNeedsLive`` with
the pre-flight command instead of pretending to work headless.
"""

from .sections import load_section_map, validate_section_map, SectionMapError
from .state import PipelineState, STAGES, StageOrderError
from .stages import (StageNeedsLive, intake, align, qc as qc_stage, publish,
                     estimate_bpm)

__all__ = [
    "load_section_map", "validate_section_map", "SectionMapError",
    "PipelineState", "STAGES", "StageOrderError",
    "StageNeedsLive", "intake", "align", "qc_stage", "publish", "estimate_bpm",
]
