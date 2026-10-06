"""Approximate Russian reading of Spanish eSpeak NG IPA."""

VOWELS = {"a", "e", "i", "o", "u", "ə", "ɛ", "ɔ"}
SOUNDS = {
    "a": "а", "e": "э", "i": "и", "o": "о", "u": "у",
    "ə": "э", "ɛ": "э", "ɔ": "о",
    "b": "б", "β": "б", "d": "д", "ð": "д", "f": "ф",
    "ɡ": "г", "g": "г", "ɣ": "г", "k": "к", "l": "л", "ʎ": "ль",
    "m": "м", "n": "н", "ɲ": "нь", "ŋ": "н", "p": "п",
    "r": "р", "ɾ": "р", "s": "с", "z": "з", "t": "т",
    "θ": "с", "x": "х", "χ": "х", "h": "х", "ʝ": "й", "j": "й",
    "w": "у", "ɪ": "й", "ʊ": "у", "v": "в", "ʃ": "ш", "ʒ": "ж", "ʔ": "",
    "tʃ": "ч", "dʒ": "дж", "ts": "ц",
}
MULTI_SOUNDS = tuple(sorted((s for s in SOUNDS if len(s) > 1), key=len, reverse=True))
IGNORE_MARKS = {"ˌ", "ː", "ˑ", "̃", "̯", "͡", "͜", ".", "‿"}
PUNCTUATION = set(" ,;:!?¡¿()[]«»\"'-–—…")


def _next_sound(ipa, position):
    while position < len(ipa) and ipa[position] in IGNORE_MARKS | {"ˈ"}:
        position += 1
    for sound in MULTI_SOUNDS:
        if ipa.startswith(sound, position):
            return sound
    return ipa[position] if position < len(ipa) else None


def ipa_to_russian(ipa):
    """Return (approximate Cyrillic, note); unknown IPA yields a dash."""
    result, unknown = [], set()
    stress_pending = False
    glide_mode = None
    position = 0
    while position < len(ipa):
        char = ipa[position]
        if char == "ˈ":
            stress_pending = True
            position += 1
            continue
        if char in IGNORE_MARKS:
            position += 1
            continue
        if char.isspace():
            result.append(char)
            stress_pending = False
            glide_mode = None
            position += 1
            continue
        if char in PUNCTUATION:
            result.append(char)
            position += 1
            continue
        sound = next((s for s in MULTI_SOUNDS if ipa.startswith(s, position)), char)
        if sound not in SOUNDS:
            unknown.add(sound)
            position += len(sound)
            continue
        russian = SOUNDS[sound]
        next_unit = _next_sound(ipa, position + len(sound))
        if sound == "j" and next_unit in VOWELS and result:
            previous = result[-1]
            if previous == "й":
                russian = ""
                glide_mode = "after_y"
            elif previous and previous[-1].lower() in "бвгджзклмнпрстфхцчшщ":
                russian = "ьй"
                glide_mode = "soft"
        elif sound in VOWELS and glide_mode:
            replacements = (
                {"а": "я", "э": "е", "и": "и", "о": "о", "у": "ю"}
                if glide_mode == "soft" else {"а": "я", "э": "е"}
            )
            russian = replacements.get(russian, russian)
            glide_mode = None
        if sound == "l" and (next_unit is None or next_unit.isspace() or next_unit in PUNCTUATION):
            russian = "ль"
        if sound in VOWELS and stress_pending:
            russian = russian.upper()
            stress_pending = False
        result.append(russian)
        position += len(sound)
    if unknown:
        return "—", "Неизвестные символы МФА: " + ", ".join(sorted(unknown))
    return "".join(result), ""


def formatted_cyrillic(ipa):
    """Use the same slash convention as the IPA export; missing IPA stays empty."""
    if not ipa or ipa == "-":
        return ""
    russian, _ = ipa_to_russian(ipa)
    return russian if russian == "—" else f"/{russian}/"
