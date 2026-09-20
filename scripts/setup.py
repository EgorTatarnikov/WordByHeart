"""Idempotent setup using the venv interpreter. Run through INSTALL.bat."""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import sysconfig
import tomllib
import urllib.request
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ESPEAK_URL = "https://github.com/espeak-ng/espeak-ng/releases/download/1.52.0/espeak-ng.msi"
IMPORTS = [
    "tkinter",
    "customtkinter",
    "spacy",
    "phonemizer",
    "pandas",
    "pyarrow",
    "openpyxl",
    "docx",
    "wordfreq",
    "openai",
    "httpx",
    "yaml",
    "pydantic",
    "dotenv",
    "filelock",
]
logger = logging.getLogger(__name__)


def official_download_environment():
    # Ignore ambient pip mirrors, extra indexes, local wheels and config files.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PIP_")}
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_INDEX_URL"] = "https://pypi.org/simple"
    env["PIP_TIMEOUT"] = "90"
    env["PIP_RESUME_RETRIES"] = "10"
    env["PIP_LOG"] = str(ROOT / "logs" / "pip.log")
    env["PYTHONUTF8"] = "1"
    return env


def command(args, timeout=1800, capture=False):
    result = subprocess.run(
        args,
        cwd=ROOT,
        env=official_download_environment(),
        timeout=timeout,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.stdout:
        logger.info("%s", result.stdout)
        if not capture:
            print(result.stdout, flush=True)
    return result


def python(*args, **kwargs):
    return command([sys.executable, *args], **kwargs)


def require(result, message):
    if result.returncode:
        raise RuntimeError(message)


def requirements_satisfied(project, get_version=metadata.version):
    # pip is installed by venv; use its bundled parser before project deps exist.
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.specifiers import SpecifierSet

    if not SpecifierSet(project["requires-python"]).contains(".".join(map(str, sys.version_info[:3]))):
        return False
    for value in project["dependencies"]:
        req = Requirement(value)
        if req.marker and not req.marker.evaluate():
            continue
        try:
            if get_version(req.name) not in req.specifier:
                return False
        except metadata.PackageNotFoundError:
            return False
    return True


def imports_work():
    return python("-c", "; ".join(f"import {name}" for name in IMPORTS), capture=True).returncode == 0


def install_dependencies():
    import re

    # Do not import pip internals before upgrading them in a subprocess.
    pip_version = tuple(map(int, re.match(r"(\d+)\.(\d+)", metadata.version("pip")).groups()))
    # pip 25.2 enables resuming large model downloads after a network interruption.
    if pip_version < (25, 2):
        require(
            python("-m", "pip", "install", "--upgrade", "pip>=25.2", "--index-url", "https://pypi.org/simple"),
            "Не удалось обновить pip.",
        )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    try:
        installed = next(
            dist
            for dist in metadata.distributions(path=[sysconfig.get_path("purelib")])
            if dist.metadata["Name"].lower().replace("_", "-") == project["name"]
        )
        direct = json.loads(installed.read_text("direct_url.json") or "{}")
        editable_here = direct.get("url", "").rstrip("/") == ROOT.as_uri().rstrip("/")
    except (metadata.PackageNotFoundError, StopIteration):
        editable_here = False
    healthy = requirements_satisfied(project) and imports_work()
    if healthy and editable_here and python("-m", "pip", "check", capture=True).returncode == 0:
        print("Библиотеки уже установлены.", flush=True)
        return
    require(
        python("-m", "pip", "install", "-e", ".", "--index-url", "https://pypi.org/simple"),
        "Не удалось установить зависимости. Проверьте подключение к PyPI и свободное место.",
    )
    if not imports_work():
        print("Восстановление повреждённых библиотек...", flush=True)
        require(
            python(
                "-m",
                "pip",
                "install",
                "--force-reinstall",
                "-e",
                ".",
                "--index-url",
                "https://pypi.org/simple",
            ),
            "Не удалось восстановить библиотеки. Подробности: logs/setup.log.",
        )
        if not imports_work():
            raise RuntimeError("Не проходят проверки импортов. Подробности: logs/setup.log.")
    require(python("-m", "pip", "check", capture=True), "Обнаружен конфликт зависимостей: logs/setup.log.")


def configured_models(language="en"):
    from src.config import load_config

    return [load_config(ROOT / "config" / f"demo_{language}.yaml").nlp.model]


def model_works(model):
    return (
        python(
            "-c",
            "import spacy,sys; nlp=spacy.load(sys.argv[1]); assert len(nlp('Hello. Casa.'))",
            model,
            timeout=600,
            capture=True,
        ).returncode
        == 0
    )


def install_models(language="en"):
    for model in configured_models(language):
        if model_works(model):
            print(f"{model}: готово.", flush=True)
            continue
        print(f"Установка/восстановление {model}...", flush=True)
        try:
            metadata.version(model)
            flags = ["--force-reinstall"]
        except metadata.PackageNotFoundError:
            flags = []
        require(
            python("-m", "spacy", "download", model, *flags, timeout=3600),
            f"Не удалось установить {model}. Проверьте доступ к github.com/explosion/spacy-models.",
        )
        if not model_works(model):
            raise RuntimeError(f"Модель {model} не загружается. Подробности: logs/setup.log.")


def download_espeak(target):
    request = urllib.request.Request(ESPEAK_URL, headers={"User-Agent": "WordByHeart-Setup"})
    part = target.with_suffix(".part")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as stream:
            if not response.url.startswith("https://"):
                raise RuntimeError("Загрузка eSpeak перенаправлена на небезопасный URL.")
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)


def espeak_works():
    return (
        python(
            "-c",
            "from src.pronunciation.discovery import check_espeak; check_espeak()",
            timeout=60,
            capture=True,
        ).returncode
        == 0
    )


def install_espeak():
    if espeak_works():
        print("eSpeak NG: реальная транскрипция English и Español проверена.", flush=True)
        return
    if os.name != "nt":
        raise RuntimeError(
            "Установите системный eSpeak NG; автоматическая установка предназначена для Windows."
        )
    downloads = ROOT / ".local" / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    archive = downloads / "espeak-ng-1.52.0.msi"
    print("Загрузка официального eSpeak NG 1.52.0...", flush=True)
    download_espeak(archive)
    target = ROOT / ".local" / "espeak"
    target.mkdir(parents=True, exist_ok=True)
    # Administrative extraction copies files locally without registering a system installation.
    result = command(
        [
            "msiexec.exe",
            "/a",
            str(archive),
            "/qn",
            f"TARGETDIR={target}",
            "/L*v",
            str(ROOT / "logs" / "espeak-install.log"),
        ],
        timeout=300,
        capture=True,
    )
    if result.returncode not in (0, 3010) or not espeak_works():
        raise RuntimeError(
            "Не удалось распаковать/запустить eSpeak NG автоматически. Откройте "
            ".local/downloads/espeak-ng-1.52.0.msi для стандартной установки "
            "(Windows может запросить права администратора), затем повторите INSTALL.bat."
        )
    (target / "SOURCE.json").write_text(
        json.dumps(
            {
                "url": ESPEAK_URL,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                "license": "https://github.com/espeak-ng/espeak-ng/blob/1.52.0/COPYING",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def install_kaikki(language="en"):
    from src.translation.download import main

    if main(["--language", language]):
        raise RuntimeError("Не удалось установить Kaikki. Проверьте интернет и повторите INSTALL.bat.")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Проверки без скачивания и установки")
    parser.add_argument("--language", choices=("en", "es"), default="en")
    args = parser.parse_args(argv)
    (ROOT / "logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=ROOT / "logs" / "setup.log",
        level=logging.INFO,
        encoding="utf-8",
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        if args.check:
            if not imports_work():
                raise RuntimeError("Не готовы Python-зависимости.")
            for model in configured_models(args.language):
                if not model_works(model):
                    raise RuntimeError(f"Не готова модель {model}.")
            if not espeak_works():
                raise RuntimeError("Не готов eSpeak NG.")
            from src.languages.installation import language_is_installed

            if not language_is_installed(ROOT, args.language):
                raise RuntimeError(f"Не установлены ресурсы языка: {args.language}.")
        else:
            if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
                raise RuntimeError("Используйте INSTALL.bat: установка должна выполняться внутри .venv.")
            for number, label, action in (
                (3, "Проверка библиотек", install_dependencies),
                (4, "Проверка NLP-модели", lambda: install_models(args.language)),
                (5, "Проверка eSpeak NG", install_espeak),
                (6, "Установка словарей Kaikki", lambda: install_kaikki(args.language)),
            ):
                print(f"[{number}/7] {label}...", flush=True)
                action()
        from scripts.assets import check_assets

        check_assets(ROOT)
        print("[7/7] Проверка интерфейса...", flush=True)
        require(
            python(
                "-c",
                "import customtkinter as c; r=c.CTk(); r.withdraw(); r.update(); r.destroy()",
                timeout=30,
                capture=True,
            ),
            "Не удалось открыть GUI. Проверьте Tcl/Tk.",
        )
        return 0
    except Exception as exc:
        logger.exception("Setup failed")
        print(f"Ошибка: {exc}", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
