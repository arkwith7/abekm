"""섹션 인식 청킹 유틸리티
=================================

학술 논문을 위한 섹션 구조 기반 청킹:
1. 섹션 경계를 존중하여 청킹 (섹션 내용이 여러 청크로 분할되지 않도록)
2. References 이후 콘텐츠 제외 (저자 사진, acknowledgments 등)
3. 섹션 타입에 따른 차별화된 청킹 전략:
   - Abstract/Introduction/Conclusion: 전체를 하나의 청크로
   - Methods/Results/Discussion: 서브섹션 단위 또는 토큰 기반 분할
4. 각 청크에 섹션 메타데이터 포함 (검색 시 컨텍스트 제공)
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)

try:
    import tiktoken
    _TOKENIZER = tiktoken.get_encoding("cl100k_base")
except Exception:
    _TOKENIZER = None


def _count_tokens(text: str) -> int:
    """텍스트의 토큰 수 계산"""
    if not text:
        return 0
    if _TOKENIZER:
        try:
            return len(_TOKENIZER.encode(text))
        except Exception:
            return len(text.split())
    return len(text.split())


def should_exclude_section(section_type: str, section_title: str) -> bool:
    """
    섹션을 청킹에서 제외해야 하는지 판단
    
    Args:
        section_type: 표준 섹션 타입 (references, acknowledgments 등)
        section_title: 섹션 원본 제목
    
    Returns:
        True if 제외해야 함, False otherwise
    """
    # References 이후 섹션 제외
    exclude_types = {
        'references',
        'bibliography', 
        'acknowledgments',
        'acknowledgements',
        'appendix'
    }
    
    if section_type in exclude_types:
        return True
    
    # 제목 기반 추가 필터링
    title_lower = section_title.lower()
    exclude_keywords = [
        'about the author',
        'author',
        'contributor',
        'biography',
        'photo',
        'funding',
        'conflict of interest',
        'ethical approval'
    ]
    
    for keyword in exclude_keywords:
        if keyword in title_lower:
            return True
    
    return False


def chunk_by_sections(
    sections: List[Dict[str, Any]],
    full_text: str,
    *,
    min_tokens: int = 80,
    target_tokens: int = 280,
    max_tokens: int = 420,
    overlap_tokens: int = 40,
) -> List[Dict[str, Any]]:
    """
    섹션 구조를 고려한 청킹
    
    Args:
        sections: AdaptiveSectionDetector.detect_sections()의 결과
        full_text: 전체 텍스트 (markdown 또는 plain text)
        min_tokens: 최소 토큰 수
        target_tokens: 목표 토큰 수
        max_tokens: 최대 토큰 수
        overlap_tokens: 청크 간 오버랩 토큰 수
    
    Returns:
        청크 리스트: [{
            'content_text': str,
            'token_count': int,
            'char_count': int,
            'section_type': str,
            'section_title': str,
            'section_level': int,
            'chunk_index': int,  # 섹션 내 청크 순서
            'page_numbers': Set[int],
        }]
    """
    if not sections:
        logger.warning("[SECTION-CHUNK] 섹션 정보가 없어 기본 청킹으로 폴백")
        return _fallback_chunk(full_text, min_tokens, target_tokens, max_tokens)
    
    chunks = []
    references_reached = False
    
    logger.info(f"[SECTION-CHUNK] {len(sections)}개 섹션 기반 청킹 시작")
    
    for section in sections:
        section_type = section.get('type', 'other')
        section_title = section.get('original_title', 'Unknown')
        section_level = section.get('level', 1)
        start_pos = section.get('start_pos', 0)
        end_pos = section.get('end_pos', len(full_text))
        page_start = section.get('page_start', 1)
        page_end = section.get('page_end', page_start)
        
        # References 도달 시 이후 섹션 모두 제외
        if section_type == 'references':
            references_reached = True
            logger.info(f"[SECTION-CHUNK] ✂️ References 섹션 도달, 이후 콘텐츠 제외: '{section_title}'")
            break
        
        # 제외 대상 섹션 체크
        if should_exclude_section(section_type, section_title):
            logger.info(f"[SECTION-CHUNK] ⏭️ 섹션 제외: '{section_title}' (type={section_type})")
            continue
        
        # 섹션 텍스트 추출
        section_text = full_text[start_pos:end_pos].strip()
        if not section_text:
            logger.debug(f"[SECTION-CHUNK] ⚠️ 빈 섹션: '{section_title}'")
            continue
        
        section_token_count = _count_tokens(section_text)
        
        # 섹션 타입에 따른 청킹 전략
        if section_type in ['abstract', 'introduction', 'conclusion']:
            # 짧은 섹션: 전체를 하나의 청크로
            if section_token_count <= max_tokens:
                chunks.append({
                    'content_text': section_text,
                    'token_count': section_token_count,
                    'char_count': len(section_text),
                    'section_type': section_type,
                    'section_title': section_title,
                    'section_level': section_level,
                    'chunk_index': 0,
                    'total_chunks': 1,
                    'page_numbers': set(range(page_start, page_end + 1)),
                    'chunking_strategy': 'single_section'
                })
                logger.info(
                    f"[SECTION-CHUNK] ✅ '{section_title}' → 단일 청크 "
                    f"({section_token_count} tokens)"
                )
            else:
                # 너무 긴 경우 토큰 기반 분할
                section_chunks = _split_section_by_tokens(
                    section_text,
                    section_type,
                    section_title,
                    section_level,
                    page_start,
                    page_end,
                    target_tokens,
                    max_tokens,
                    overlap_tokens
                )
                chunks.extend(section_chunks)
                logger.info(
                    f"[SECTION-CHUNK] ✅ '{section_title}' → {len(section_chunks)}개 청크 "
                    f"(토큰 기반 분할, {section_token_count} tokens)"
                )
        
        elif section_type in ['methods', 'results', 'discussion']:
            # 중간 길이 섹션: 서브섹션 확인 후 처리
            subsections = section.get('subsections', [])
            
            if subsections and len(subsections) > 1:
                # 서브섹션이 있으면 서브섹션 단위로 청킹
                logger.info(
                    f"[SECTION-CHUNK] 🔍 '{section_title}' → {len(subsections)}개 서브섹션 기반 청킹"
                )
                # TODO: 서브섹션 기반 청킹 구현
                # 현재는 토큰 기반으로 폴백
                section_chunks = _split_section_by_tokens(
                    section_text,
                    section_type,
                    section_title,
                    section_level,
                    page_start,
                    page_end,
                    target_tokens,
                    max_tokens,
                    overlap_tokens
                )
                chunks.extend(section_chunks)
            else:
                # 서브섹션 없으면 토큰 기반 분할
                section_chunks = _split_section_by_tokens(
                    section_text,
                    section_type,
                    section_title,
                    section_level,
                    page_start,
                    page_end,
                    target_tokens,
                    max_tokens,
                    overlap_tokens
                )
                chunks.extend(section_chunks)
                logger.info(
                    f"[SECTION-CHUNK] ✅ '{section_title}' → {len(section_chunks)}개 청크 "
                    f"({section_token_count} tokens)"
                )
        
        else:
            # 기타 섹션: 토큰 기반 분할
            section_chunks = _split_section_by_tokens(
                section_text,
                section_type,
                section_title,
                section_level,
                page_start,
                page_end,
                target_tokens,
                max_tokens,
                overlap_tokens
            )
            chunks.extend(section_chunks)
            logger.info(
                f"[SECTION-CHUNK] ✅ '{section_title}' (type={section_type}) → "
                f"{len(section_chunks)}개 청크 ({section_token_count} tokens)"
            )
    
    logger.info(
        f"[SECTION-CHUNK] 🎉 청킹 완료: 총 {len(chunks)}개 청크 생성 "
        f"(References 이후 제외: {references_reached})"
    )
    
    return chunks


def _split_section_by_tokens(
    section_text: str,
    section_type: str,
    section_title: str,
    section_level: int,
    page_start: int,
    page_end: int,
    target_tokens: int,
    max_tokens: int,
    overlap_tokens: int
) -> List[Dict[str, Any]]:
    """
    섹션을 토큰 기반으로 분할
    
    문단 경계를 존중하면서 target_tokens에 가깝게 분할
    """
    # 문단 단위로 분리
    paragraphs = [p.strip() for p in section_text.split('\n\n') if p.strip()]
    
    if not paragraphs:
        return []
    
    chunks = []
    current_buffer = []
    current_token_count = 0
    chunk_index = 0
    
    for para in paragraphs:
        para_tokens = _count_tokens(para)
        
        # 현재 버퍼가 비어있으면 무조건 추가
        if not current_buffer:
            current_buffer.append(para)
            current_token_count = para_tokens
            continue
        
        # 추가했을 때 max_tokens를 초과하면 현재 청크 플러시
        if current_token_count + para_tokens > max_tokens:
            # 현재 버퍼를 청크로 저장
            chunk_text = '\n\n'.join(current_buffer)
            chunks.append({
                'content_text': chunk_text,
                'token_count': current_token_count,
                'char_count': len(chunk_text),
                'section_type': section_type,
                'section_title': section_title,
                'section_level': section_level,
                'chunk_index': chunk_index,
                'page_numbers': set(range(page_start, page_end + 1)),
                'chunking_strategy': 'token_based'
            })
            chunk_index += 1
            
            # 오버랩 처리 (마지막 문단 일부 포함)
            if overlap_tokens > 0 and current_buffer:
                last_para = current_buffer[-1]
                last_para_tokens = _count_tokens(last_para)
                if last_para_tokens <= overlap_tokens:
                    current_buffer = [last_para, para]
                    current_token_count = last_para_tokens + para_tokens
                else:
                    current_buffer = [para]
                    current_token_count = para_tokens
            else:
                current_buffer = [para]
                current_token_count = para_tokens
        
        # target_tokens에 가까우면 추가
        elif current_token_count + para_tokens >= target_tokens:
            current_buffer.append(para)
            chunk_text = '\n\n'.join(current_buffer)
            current_token_count += para_tokens
            
            chunks.append({
                'content_text': chunk_text,
                'token_count': current_token_count,
                'char_count': len(chunk_text),
                'section_type': section_type,
                'section_title': section_title,
                'section_level': section_level,
                'chunk_index': chunk_index,
                'page_numbers': set(range(page_start, page_end + 1)),
                'chunking_strategy': 'token_based'
            })
            chunk_index += 1
            current_buffer = []
            current_token_count = 0
        
        else:
            # 아직 target에 도달하지 않았으면 계속 추가
            current_buffer.append(para)
            current_token_count += para_tokens
    
    # 남은 버퍼 처리
    if current_buffer:
        chunk_text = '\n\n'.join(current_buffer)
        chunks.append({
            'content_text': chunk_text,
            'token_count': current_token_count,
            'char_count': len(chunk_text),
            'section_type': section_type,
            'section_title': section_title,
            'section_level': section_level,
            'chunk_index': chunk_index,
            'page_numbers': set(range(page_start, page_end + 1)),
            'chunking_strategy': 'token_based'
        })
    
    # total_chunks 메타데이터 추가
    for chunk in chunks:
        chunk['total_chunks'] = len(chunks)
    
    return chunks


def _fallback_chunk(
    text: str,
    min_tokens: int,
    target_tokens: int,
    max_tokens: int
) -> List[Dict[str, Any]]:
    """섹션 정보가 없을 때 기본 토큰 기반 청킹"""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if not paragraphs:
        return []
    
    chunks = []
    current_buffer = []
    current_token_count = 0
    
    for para in paragraphs:
        para_tokens = _count_tokens(para)
        
        if not current_buffer:
            current_buffer.append(para)
            current_token_count = para_tokens
            continue
        
        if current_token_count + para_tokens > max_tokens:
            chunk_text = '\n\n'.join(current_buffer)
            chunks.append({
                'content_text': chunk_text,
                'token_count': current_token_count,
                'char_count': len(chunk_text),
                'section_type': 'unknown',
                'section_title': 'Unknown',
                'chunk_index': len(chunks),
                'chunking_strategy': 'fallback'
            })
            current_buffer = [para]
            current_token_count = para_tokens
        elif current_token_count + para_tokens >= target_tokens:
            current_buffer.append(para)
            chunk_text = '\n\n'.join(current_buffer)
            current_token_count += para_tokens
            chunks.append({
                'content_text': chunk_text,
                'token_count': current_token_count,
                'char_count': len(chunk_text),
                'section_type': 'unknown',
                'section_title': 'Unknown',
                'chunk_index': len(chunks),
                'chunking_strategy': 'fallback'
            })
            current_buffer = []
            current_token_count = 0
        else:
            current_buffer.append(para)
            current_token_count += para_tokens
    
    if current_buffer:
        chunk_text = '\n\n'.join(current_buffer)
        chunks.append({
            'content_text': chunk_text,
            'token_count': current_token_count,
            'char_count': len(chunk_text),
            'section_type': 'unknown',
            'section_title': 'Unknown',
            'chunk_index': len(chunks),
            'chunking_strategy': 'fallback'
        })
    
    return chunks


def filter_objects_before_references(
    sections: List[Dict[str, Any]],
    objects: List[Any]
) -> Tuple[List[Any], Optional[int]]:
    """
    References 섹션 이전의 객체들만 필터링
    
    Args:
        sections: 섹션 정보 리스트
        objects: 추출된 객체 리스트 (테이블, 이미지 등)
    
    Returns:
        (filtered_objects, references_page): 필터링된 객체 리스트와 References 시작 페이지
    """
    # References 섹션 찾기
    references_section = None
    for section in sections:
        if section.get('type') == 'references':
            references_section = section
            break
    
    if not references_section:
        logger.info("[SECTION-FILTER] References 섹션을 찾지 못함, 모든 객체 포함")
        return objects, None
    
    references_page = references_section.get('page_start')
    references_pos = references_section.get('start_pos', float('inf'))
    
    # 🆕 page_start가 1이면서 start_pos가 큰 경우 (즉, 문서 후반부) 의심스러움
    # References는 보통 문서 끝에 있으므로 page=1은 잘못된 감지일 가능성 높음
    suspected_invalid_page = (references_page == 1 and references_pos > 30000)
    
    # page_start가 없거나 잘못된 경우 None 사용 (bbox 기반 추정에 의존)
    if not references_page or references_page <= 0 or references_page == float('inf') or suspected_invalid_page:
        if suspected_invalid_page:
            logger.warning(
                f"[SECTION-FILTER] References 섹션 page_start=1 의심스러움 (pos={references_pos} > 30000), "
                f"필터링 비활성화 (bbox 기반 추정 필요)"
            )
        references_page = None
        logger.info(
            f"[SECTION-FILTER] References 섹션 발견 (page_start 미설정, 필터링 건너뜀), pos={references_pos}"
        )
    else:
        logger.info(
            f"[SECTION-FILTER] References 섹션 시작: page={references_page}, pos={references_pos}"
        )
    
    # 페이지 번호 또는 위치 기반으로 필터링
    filtered = []
    excluded_count = 0
    
    for obj in objects:
        obj_page = getattr(obj, 'page_no', None) or getattr(obj, 'page', None)
        obj_type = getattr(obj, 'object_type', 'unknown')
        
        # references_page가 None이면 필터링하지 않고 모두 포함
        if references_page is None:
            filtered.append(obj)
            continue
        
        # 페이지 기반 필터링
        if obj_page and obj_page < references_page:
            filtered.append(obj)
        elif obj_page and obj_page >= references_page:
            excluded_count += 1
            logger.debug(
                f"[SECTION-FILTER] 제외: {obj_type} (page={obj_page}, "
                f"references_page={references_page})"
            )
        else:
            # 페이지 정보 없으면 포함 (안전한 선택)
            filtered.append(obj)
    
    logger.info(
        f"[SECTION-FILTER] 필터링 완료: {len(filtered)}개 포함, {excluded_count}개 제외"
    )
    
    return filtered, references_page
