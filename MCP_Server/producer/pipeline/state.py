"""Resumable pipeline state: one JSON file per build, written after each stage.

A dropped bridge or a 180-second shell limit should cost one stage, not a
whole build, so every stage records what it produced and the next run picks
up from there.
"""
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

STAGES = ("intake", "align", "build", "mix", "master", "qc", "publish")
TERMINAL_OK = "completed"
STATUSES = ("pending", "running", TERMINAL_OK, "failed", "needs_live")


class StageOrderError(RuntimeError):
    """A stage was run before the stage it depends on completed."""


def slugify(name):
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    if not slug:
        raise ValueError("Build name has no usable characters")
    return slug[:64]


def _now():
    return datetime.now(timezone.utc).isoformat()


class PipelineState:
    """Stage status for one build, persisted under <project>/pipeline/."""

    def __init__(self, root, build):
        self.build = str(build)
        self.slug = slugify(build)
        self.root = Path(root).resolve()
        self.path = self.root / "pipeline" / (self.slug + ".json")
        self.data = self._read()

    def _read(self):
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("stages", {}).keys() - set(STAGES):
                raise ValueError("State file has unknown stages: %s" % self.path)
            return data
        return {"build": self.build, "slug": self.slug, "created": _now(),
                "updated": _now(), "stages": {}}

    def _write(self):
        self.data["updated"] = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic: a killed shell must not leave a half-written state file.
        handle = tempfile.NamedTemporaryFile("w", dir=self.path.parent,
                                             delete=False, encoding="utf-8")
        try:
            json.dump(self.data, handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(handle.name, self.path)
        finally:
            Path(handle.name).unlink(missing_ok=True)
        return self.path

    def status(self, stage):
        return self.data["stages"].get(stage, {}).get("status", "pending")

    def record(self, stage, status, artifacts=None, detail=""):
        if stage not in STAGES:
            raise ValueError("Unknown stage: %r" % stage)
        if status not in STATUSES:
            raise ValueError("Unknown status: %r" % status)
        self.data["stages"][stage] = {
            "status": status,
            "updated": _now(),
            "artifacts": artifacts or {},
            "detail": detail,
        }
        self._write()
        return self.data["stages"][stage]

    def artifacts(self, stage):
        return dict(self.data["stages"].get(stage, {}).get("artifacts", {}))

    def require(self, stage):
        """Raise unless every earlier stage completed. Keeps builds honest."""
        if stage not in STAGES:
            raise ValueError("Unknown stage: %r" % stage)
        for earlier in STAGES[:STAGES.index(stage)]:
            if self.status(earlier) != TERMINAL_OK:
                raise StageOrderError(
                    "Stage %r cannot run: %r is %s. Run it first, or re-run with "
                    "--force if you know it is done." % (stage, earlier, self.status(earlier)))
        return True

    def next_stage(self):
        """The first stage that has not completed, or None when the build is done."""
        for stage in STAGES:
            if self.status(stage) != TERMINAL_OK:
                return stage
        return None

    def summary(self):
        return {
            "build": self.build,
            "state_file": str(self.path),
            "next_stage": self.next_stage(),
            "complete": self.next_stage() is None,
            "stages": {stage: self.status(stage) for stage in STAGES},
            "published": self.status("publish") == TERMINAL_OK,
        }
