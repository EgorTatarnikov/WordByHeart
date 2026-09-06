import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from src.manifest import DEPENDENCIES
from src.pipeline import Pipeline

logger = logging.getLogger(__name__)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Частотный учебный словарь книги")
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in [*DEPENDENCIES, "run-all", "status"]:
        sub = commands.add_parser(name)
        sub.add_argument("--config", type=Path, default=argparse.SUPPRESS)
        if name in {"preprocess", "run-all", "status"}:
            sub.add_argument("source", nargs="?", type=Path)
        if name != "status":
            sub.add_argument(
                "--force",
                action="store_true",
                help="Пересчитать выбранную стадию (run-all: все); кэш сохраняется",
            )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )
    # HTTP success lines duplicate the translation progress bar.  They remain
    # available with --verbose for network troubleshooting.
    logging.getLogger("httpx").setLevel(logging.DEBUG if args.verbose else logging.WARNING)
    # Load the project/cwd .env first (where eSpeak DLL/data are normally kept),
    # then let a config-local file supply overrides for a specific run.
    load_dotenv()
    load_dotenv(args.config.resolve().parent / ".env")
    try:
        pipeline = Pipeline(args.config, getattr(args, "source", None))
        if args.command == "status":
            for stage, (state, reason) in pipeline.status().items():
                print(f"{stage:12} {state:9} {reason}")
        else:
            pipeline.run(args.command, args.force)
    except Exception as exc:
        if args.verbose:
            logger.exception("Ошибка pipeline")
        else:
            logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
