from src.storage import digest

from . import prompts


def cache_key(entry, config, language="es"):
    return digest(
        {
            "entry": entry,
            "provider": config.provider,
            "model": config.model,
            "prompt_version": config.prompt_version,
            "system_prompt": prompts.EN_SYSTEM_PROMPT if language == "en" else prompts.SYSTEM_PROMPT,
            "source_language": language,
            "lemma_version": prompts.LEMMA_PROMPT_VERSION,
            "form_version": prompts.FORM_PROMPT_VERSION,
        }
    )
