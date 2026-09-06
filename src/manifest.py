"""Content-addressed stage state. Generations make --force invalidate descendants."""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from src.models import PipelineStageState
from src.storage import digest, file_hash, write_json

DEPENDENCIES = {
    "preprocess": [],
    "nlp": ["preprocess"],
    "aggregate": ["nlp"],
    "reference": ["aggregate"],
    "postprocess": ["reference"],
    "grammar": ["postprocess"],
    "ipa": ["postprocess"],
    "translate": ["postprocess"],
    "validate": ["grammar", "ipa", "translate"],
    "export": ["validate"],
    "cards": ["export"],
}


def differences(old, new, prefix=""):
    result = []
    for key in sorted(old.keys() | new.keys()):
        name = f"{prefix}.{key}" if prefix else key
        a, b = old.get(key), new.get(key)
        if isinstance(a, dict) and isinstance(b, dict):
            result.extend(differences(a, b, name))
        elif a != b:
            result.append(f"{name}: {a!r} → {b!r}")
    return result


class Manifest:
    def __init__(self, path):
        self.path = path
        self.data = (
            json.loads(path.read_text(encoding="utf-8"))
            if path.exists()
            else {"schema_version": 1, "stages": {}}
        )

    def save(self):
        write_json(self.path, self.data)

    def status(self, stage, configs, fingerprints, outputs):
        record = self.data["stages"].get(stage)
        if not record:
            return "MISSING", "ещё не запускалась"
        if not record["completed"]:
            return "FAILED", record.get("error", "незавершённый запуск")
        for dep in DEPENDENCIES[stage]:
            state, reason = self.status(dep, configs, fingerprints, outputs)
            if state != "OK":
                return "OUTDATED", f"{dep}: {state} ({reason})"
            if record["dependencies"].get(dep) != self.data["stages"][dep]["generation"]:
                return "OUTDATED", f"{dep} пересчитана"
        if record["fingerprint"] != fingerprints[stage]:
            changes = differences(record["config"], configs[stage])
            return "OUTDATED", "; ".join(changes) or "изменился код/инструмент/исходный файл"
        if set(record["outputs"]) != {str(p) for p in outputs[stage]}:
            return "OUTDATED", "изменился набор выходных файлов"
        for name, expected in record["outputs"].items():
            path = Path(name)
            if not path.exists():
                return "OUTDATED", f"отсутствует {path.name}"
            if file_hash(path) != expected:
                return "OUTDATED", f"изменён artifact {path.name}"
        return "OK", ""

    def begin(self, stage, config, fingerprint):
        dependencies = {dep: self.data["stages"][dep]["generation"] for dep in DEPENDENCIES[stage]}
        record = PipelineStageState(False, fingerprint, config, digest(config), {}, uuid4().hex, dependencies)
        self.data["stages"][stage] = asdict(record)
        self.save()

    def complete(self, stage, outputs, metadata=None):
        record = self.data["stages"][stage]
        record.update(
            completed=True,
            outputs={str(p): file_hash(p) for p in outputs},
            completed_at=datetime.now(UTC).isoformat(),
        )
        if metadata:
            record.update(metadata)
        self.save()

    def fail(self, stage, error):
        self.data["stages"][stage].update(completed=False, error=str(error))
        self.save()
