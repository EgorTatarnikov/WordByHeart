import gzip
import json
import logging
import subprocess
import sys

import pytest

from scripts import setup
from src.translation.download import install
from src.translation.health import dictionary_is_healthy


def test_corrupt_dictionary_rebuilt_from_cached_archive(tmp_path):
    directory = tmp_path / 'kaikki'
    directory.mkdir()
    target = directory / 'dictionary.sqlite'
    target.write_bytes(b'broken database')
    (directory / 'SOURCES.json').write_text(json.dumps({'editions': ['ru']}))
    with gzip.open(directory / 'ru-extract.jsonl.gz', 'wt', encoding='utf-8') as stream:
        stream.write(json.dumps({'lang_code': 'en', 'word': 'house', 'pos': 'noun',
                                 'translations': [{'lang_code': 'ru', 'word': 'дом'}]}))
    assert not dictionary_is_healthy(target, full=True)
    assert install(tmp_path) == target
    assert dictionary_is_healthy(target, full=True)


def test_output_visible_and_logged(tmp_path, monkeypatch, capsys, caplog):
    monkeypatch.setattr(setup, 'ROOT', tmp_path)
    with caplog.at_level(logging.INFO):
        result = setup.command([sys.executable, '-u', '-c', "print('download-progress')"])
    assert result.returncode == 0
    assert 'download-progress' in capsys.readouterr().out
    assert 'download-progress' in caplog.text
    setup.command([sys.executable, '-c', "print('hidden-check')"], capture=True)
    assert 'hidden-check' not in capsys.readouterr().out


def test_pip_timeout_does_not_stop_dependency_install(monkeypatch, capsys):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        if '--upgrade' in args:
            raise subprocess.TimeoutExpired(args, 180)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(setup.metadata, 'version', lambda name: '24.0')
    monkeypatch.setattr(setup.metadata, 'distributions', lambda **kwargs: [])
    monkeypatch.setattr(setup, 'requirements_satisfied', lambda project: False)
    monkeypatch.setattr(setup, 'imports_work', lambda: True)
    monkeypatch.setattr(setup, 'python', run)
    setup.install_dependencies()
    assert any('-e' in args and '--use-feature=truststore' in args for args in calls)
    assert 'pip 24.0' in capsys.readouterr().out


def test_old_pip_uses_truststore_for_model(monkeypatch):
    calls = []
    checks = iter([False, True])
    monkeypatch.setattr(setup, 'model_works', lambda model: next(checks))
    monkeypatch.setattr(setup, 'configured_models', lambda language: ['en_core_web_trf'])
    monkeypatch.setattr(setup.metadata, 'version', lambda name: '24.0')
    def run(*args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(setup, 'python', run)
    setup.install_models()
    assert '--use-feature=truststore' in calls[0]


def test_command_timeout_stops_process(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, 'ROOT', tmp_path)
    with pytest.raises(subprocess.TimeoutExpired):
        setup.command([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=0.3)
