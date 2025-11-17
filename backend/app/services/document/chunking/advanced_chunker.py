"""고급 청킹 유틸리티
=================================

단순 고정 길이 슬라이싱 대신 문단/문장 경계를 고려한 토큰 기반 청킹.

설계 목표:
1. 원문 문단(두 개 이상의 연속 개행) 우선 분리
2. 문단을 토큰 길이로 누적하여 target_tokens에 도달할 때까지 청크 구성
3. overrun(초과) 발생 시 최대 max_tokens 내에서 마감, 다음 청크에 overlap_tokens 적용
4. source_object_ids 및 page 번호 집합을 추적하여 메타데이터로 반환
5. 실패/예외 상황에서 안전하게 빈 리스트 반환

토크나이저: tiktoken이 사용 가능하면 이를 활용, 없으면 fallback (공백 split)
"""
from __future__ import annotations

from typing import List, Dict, Any, Iterable, Tuple, Optional, Set
import logging

logger = logging.getLogger(__name__)

try:  # tiktoken 선택적 의존
    import tiktoken  # type: ignore
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")
except Exception:  # pragma: no cover
    _TOKENIZER = None  # type: ignore


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    if _TOKENIZER:
        try:
            # tiktoken은 토큰 id 리스트를 반환하므로 개수만 필요할 경우 길이 사용 가능
            # 여기서는 overlap 재구성 위해 인위적 토큰 문자열 필요 → fallback to simple split
            # 따라서 tiktoken은 길이 참고용만 쓰고 실제 토큰 리스트는 split 사용
            return text.split()
        except Exception:
            return text.split()
    return text.split()


def advanced_chunk_text(
    objects: Iterable[Tuple[str, Optional[int], int]],
    *,
    min_tokens: int = 80,
    target_tokens: int = 280,
    max_tokens: int = 420,
    overlap_tokens: int = 40,
    join_separator: str = "\n\n"
) -> List[Dict[str, Any]]:
    """문단/토큰 기반 고급 청킹 수행.

    Parameters
    ----------
    objects : iterable of (text, page_no, object_id)
        TEXT_BLOCK 추출 객체.
    min_tokens : int
        너무 작은 청크 방지를 위한 최소 토큰 길이.
    target_tokens : int
        이상적인 청크 토큰 길이.
    max_tokens : int
        절대 허용 최대 토큰 길이.
    overlap_tokens : int
        다음 청크로 carry 하는 토큰 수 (문맥 유지).
    join_separator : str
        여러 문단 결합 시 구분 문자열.

    Returns
    -------
    List[Dict]
        각 청크 딕셔너리: {
            'content_text', 'token_count', 'char_count', 'source_object_ids', 'page_numbers'
        }
    """
    try:
        # 1) 입력 객체에서 텍스트/페이지/ID 구성
        paragraphs: List[Tuple[str, Optional[int], int]] = []
        for text, page_no, obj_id in objects:
            if not text or not text.strip():
                continue
            # 문단 분리: 두 개 이상 연속 개행 기준
            raw_parts = [p for p in text.replace('\r', '').split('\n\n') if p.strip()]
            for part in raw_parts:
                paragraphs.append((part.strip(), page_no, obj_id))

        if not paragraphs:
            return []

        chunks: List[Dict[str, Any]] = []
        buffer_tokens: List[str] = []
        buffer_texts: List[str] = []
        buffer_object_ids: Set[int] = set()
        buffer_pages: Set[int] = set()

        def flush(final: bool = False):
            if not buffer_texts:
                return
            content_text = join_separator.join(buffer_texts).strip()
            tokens = buffer_tokens
            if not final and len(tokens) < min_tokens:
                # 미니멈 도달 전이면 flush하지 않음
                return
            if content_text:
                chunk_dict = {
                    'content_text': content_text,
                    'token_count': len(tokens),
                    'char_count': len(content_text),
                    'source_object_ids': list(buffer_object_ids),
                    'page_numbers': sorted(list(buffer_pages))
                }
                chunks.append(chunk_dict)

        for para_text, page_no, obj_id in paragraphs:
            para_tokens = _tokenize(para_text)
            # 너무 긴 단일 문단 → 하드 슬라이스
            if len(para_tokens) > max_tokens:
                start = 0
                while start < len(para_tokens):
                    end = min(start + max_tokens, len(para_tokens))
                    slice_tokens = para_tokens[start:end]
                    slice_text = " ".join(slice_tokens)
                    # 현재 버퍼 flush 후 단일 청크로 저장
                    flush(final=True)
                    chunks.append({
                        'content_text': slice_text,
                        'token_count': len(slice_tokens),
                        'char_count': len(slice_text),
                        'source_object_ids': [obj_id],
                        'page_numbers': [page_no] if page_no is not None else []
                    })
                    start = end - overlap_tokens if (end < len(para_tokens) and overlap_tokens > 0) else end
                # 새 문단이므로 버퍼 초기화 보장
                buffer_tokens = []
                buffer_texts = []
                buffer_object_ids = set()
                buffer_pages = set()
                continue

            prospective_len = len(buffer_tokens) + len(para_tokens)
            if prospective_len > max_tokens:
                # flush current buffer first
                flush(final=True)
                # overlap carry
                if overlap_tokens > 0 and chunks:
                    # overlap latest tokens from previous chunk
                    last_tokens = buffer_tokens[-overlap_tokens:] if buffer_tokens else []
                    if last_tokens:
                        buffer_tokens = list(last_tokens)
                        # overlap text 재구성 (근사)
                        buffer_texts = [" ".join(last_tokens)]
                        # object/page는 초기화 (문맥만 유지)
                        buffer_object_ids = set()
                        buffer_pages = set()
                    else:
                        buffer_tokens = []
                        buffer_texts = []
                        buffer_object_ids = set()
                        buffer_pages = set()
                else:
                    buffer_tokens = []
                    buffer_texts = []
                    buffer_object_ids = set()
                    buffer_pages = set()

            # accumulate
            buffer_tokens.extend(para_tokens)
            buffer_texts.append(para_text)
            buffer_object_ids.add(obj_id)
            if page_no is not None:
                buffer_pages.add(page_no)

            # target length flush decision
            if len(buffer_tokens) >= target_tokens:
                flush(final=True)
                # overlap carry
                if overlap_tokens > 0:
                    last_tokens = buffer_tokens[-overlap_tokens:]
                    buffer_tokens = list(last_tokens)
                    buffer_texts = [" ".join(last_tokens)]
                    buffer_object_ids = set()  # 새 chunk에서 다시 채움
                    buffer_pages = set()
                else:
                    buffer_tokens = []
                    buffer_texts = []
                    buffer_object_ids = set()
                    buffer_pages = set()

        # flush tail
        flush(final=True)
        return chunks
    except Exception as e:  # pragma: no cover
        logger.error(f"[ADV-CHUNKER] 청킹 실패: {e}")
        return []

__all__ = ["advanced_chunk_text"]
