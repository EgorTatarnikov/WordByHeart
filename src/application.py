"""The same entry point is used by the CLI and the GUI worker."""

from src.pipeline import Pipeline
from src.runtime import prepare_environment


def run_pipeline(config_path, source=None, stage="run-all", force=False, on_progress=None):
    prepare_environment()
    pipeline = Pipeline(config_path, source)
    pipeline.run(stage, force, on_progress=on_progress)
    return pipeline
