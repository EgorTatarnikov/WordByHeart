import re
import unicodedata


def normalize(text: str, config) -> str:
    text = unicodedata.normalize("NFC", text.lstrip("\ufeff")).replace("\r\n", "\n").replace("\r", "\n")
    if config.strip_gutenberg:
        text = re.sub(
            r"\A.*?^\*\*\* START OF (?:THE|THIS) PROJECT GUTENBERG.*?$",
            "",
            text,
            flags=re.DOTALL | re.MULTILINE | re.IGNORECASE,
        )
        text = re.sub(
            r"^\*\*\* END OF (?:THE|THIS) PROJECT GUTENBERG.*\Z",
            "",
            text,
            flags=re.DOTALL | re.MULTILINE | re.IGNORECASE,
        )
    lines = []
    for line in text.split("\n"):
        line = re.sub(r"[^\S\n]+", " ", line).strip()
        if config.remove_page_numbers and re.fullmatch(r"\d+", line):
            continue
        if line in config.remove_lines:
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip() + "\n"
