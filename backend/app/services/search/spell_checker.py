"""간단한 영어 스펠링 보정 유틸리티."""

from typing import Dict, Tuple
import re
import logging
from functools import lru_cache

from spellchecker import SpellChecker

logger = logging.getLogger(__name__)

_english_word_pattern = re.compile(r"[A-Za-z]{3,}")


@lru_cache(maxsize=1)
def _get_spellchecker() -> SpellChecker:
    """
    SpellChecker 인스턴스를 lazy하게 생성.
    distance=1로 설정하여 과도한 교정 방지.
    """
    return SpellChecker(distance=1)


def apply_spell_correction(text: str) -> Tuple[str, Dict[str, str]]:
    """
    입력 텍스트 내 영어 단어에 대해 간단한 스펠링 교정을 수행한다.

    Args:
        text: 정규화된 사용자의 검색어

    Returns:
        (교정된 텍스트, {원본단어: 교정단어})
    """
    if not text:
        return text, {}

    spell = _get_spellchecker()
    corrections: Dict[str, str] = {}

    def repl(match: re.Match[str]) -> str:
        word = match.group(0)
        lower = word.lower()

        # 이미 사전에 있는 단어는 그대로 둔다.
        if lower in spell:
            return word

        suggestion = spell.correction(lower)
        # 오타만 교정 (제안이 없거나 동일하면 원본 유지)
        if not suggestion or suggestion == lower:
            return word

        corrections[word] = suggestion

        if word.isupper():
            return suggestion.upper()
        if word[0].isupper():
            return suggestion.capitalize()
        return suggestion

    corrected_text = _english_word_pattern.sub(repl, text)

    if corrections:
        logger.info("📝 영어 스펠링 교정 적용: %s", corrections)

    return corrected_text, corrections

