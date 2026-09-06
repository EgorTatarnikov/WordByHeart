from src.storage import digest


def cache_key(text, language, engine_version):
    return digest(
        {"text": text, "language": language, "engine": engine_version, "stress": True, "version": 1}
    )
