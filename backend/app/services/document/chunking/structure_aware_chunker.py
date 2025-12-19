"""
구조화 청킹 유틸리티 (Structure-Aware Chunker)
=============================================

Upstage/Azure Document Intelligence의 구조화된 출력(elements)을 기반으로
계층적 트리 구조(TreeRAG)를 반영하여 청킹을 수행합니다.

기능:
1. 제목(Header) 기반의 계층 구조 인식 및 parent_id 부여
2. 표(Table), 그림(Figure)의 별도 청크화 (Vision-guided)
3. 텍스트의 의미적/구조적 경계 유지 (제목 경계 우선 자르기)
4. 메타데이터(page, type, parent_id 등) 보존

작성일: 2025-12-19
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import uuid
import copy

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

class StructureAwareChunker:
    """
    구조화된 문서 요소(elements)를 기반으로 청킹을 수행하는 클래스
    """
    
    def __init__(
        self, 
        chunk_size: int = 512, 
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
        emit_header_chunks: bool = False,
        include_visual_chunks: bool = False,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.emit_header_chunks = emit_header_chunks
        self.include_visual_chunks = include_visual_chunks

    def chunk_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Upstage/Azure의 elements 리스트를 입력받아 구조화된 청크 리스트를 반환합니다.
        
        Args:
            elements: [{'category': 'heading1', 'content': '...', 'id': 1}, ...]
            
        Returns:
            List of chunk dicts compatible with multimodal_document_service:
              - content_text: str
              - token_count: int
              - page_numbers: List[int]
              - source_object_ids: List[int|str]
              - section: Optional[str]
              - section_title: Optional[str]
              - section_path: Optional[str]
        """
        if not elements:
            return []

        chunks: List[Dict[str, Any]] = []
        
        # 1. 계층 구조 파악을 위한 스택 (level, id, text)
        # level: heading1=1, heading2=2, ... root=0
        header_stack: List[Dict[str, Any]] = [
            {'level': 0, 'id': 'root', 'text': 'root', 'path': []}
        ]
        
        # 텍스트 버퍼 (같은 섹션 내의 문단들을 모아서 청킹)
        text_buffer: List[Dict[str, Any]] = []
        current_section_id = 'root'
        
        for elem in elements:
            category = elem.get('category', '').lower()
            content = (elem.get('content') or elem.get('text') or '').strip()
            # IMPORTANT: keep numeric ids numeric so downstream can store bigint[] source_object_ids
            elem_id = elem.get('id', uuid.uuid4())
            page = elem.get('page')
            
            if not content and category not in ['image', 'figure', 'table', 'chart']:
                continue

            # --- 1. 헤더 처리 (계층 구조 변경) ---
            if category.startswith('heading') or category == 'title':
                # 버퍼에 있는 이전 섹션 텍스트 처리
                if text_buffer:
                    chunks.extend(self._process_text_buffer(text_buffer, header_stack[-1]))
                    text_buffer = []
                
                # 헤더 레벨 파악
                level = 1
                if category == 'title':
                    level = 1
                elif category == 'heading1':
                    level = 2
                elif category == 'heading2':
                    level = 3
                elif category == 'heading3':
                    level = 4
                elif category == 'heading4':
                    level = 5
                else:
                    # heading5 등
                    try:
                        level = int(category.replace('heading', '')) + 1
                    except:
                        level = 6

                # 스택 조정: 현재 레벨보다 깊거나 같은 레벨은 pop
                while len(header_stack) > 1 and header_stack[-1]['level'] >= level:
                    header_stack.pop()
                
                # 현재 헤더를 스택에 push
                parent = header_stack[-1]
                current_path = parent['path'] + [content]
                
                new_header = {
                    'level': level,
                    'id': elem_id,
                    'text': content,
                    'path': current_path
                }
                header_stack.append(new_header)
                current_section_id = elem_id
                
                # 헤더 자체를 독립 청크로 저장할지 여부
                if self.emit_header_chunks:
                    chunks.append(self._make_chunk(
                        content_text=content,
                        page_numbers=[page] if isinstance(page, int) else [],
                        source_object_ids=[elem_id],
                        section=category,
                        section_title=content,
                        section_path=" > ".join(current_path),
                    ))

            # --- 2. 표/그림 처리 (별도 청크) ---
            elif category in ['table', 'figure', 'chart', 'image']:
                if not self.include_visual_chunks:
                    continue
                # 버퍼 처리
                if text_buffer:
                    chunks.extend(self._process_text_buffer(text_buffer, header_stack[-1]))
                    text_buffer = []
                
                parent = header_stack[-1]
                
                section_path = " > ".join(parent.get('path') or [])
                chunks.append(self._make_chunk(
                    content_text=content,
                    page_numbers=[page] if isinstance(page, int) else [],
                    source_object_ids=[elem_id],
                    section=category,
                    section_title=parent.get('text'),
                    section_path=section_path,
                ))

            # --- 3. 일반 텍스트 (문단, 리스트 등) ---
            else:
                # 버퍼에 추가
                text_buffer.append({
                    'content': content,
                    'id': elem_id,
                    'page': page,
                    'category': category
                })

        # 남은 버퍼 처리
        if text_buffer:
            chunks.extend(self._process_text_buffer(text_buffer, header_stack[-1]))

        return chunks

    def _make_chunk(
        self,
        content_text: str,
        page_numbers: List[int],
        source_object_ids: List[Any],
        section: Optional[str],
        section_title: Optional[str],
        section_path: Optional[str],
    ) -> Dict[str, Any]:
        token_count = _count_tokens(content_text)
        source_object_ids = self._coerce_source_object_ids(source_object_ids)
        # 멀티모달 파이프라인 호환 키
        return {
            "content_text": content_text,
            "token_count": token_count,
            "page_numbers": [p for p in page_numbers if isinstance(p, int)],
            "source_object_ids": source_object_ids,
            "section": section,
            "section_title": section_title,
            "section_path": section_path,
        }

    @staticmethod
    def _coerce_source_object_ids(source_ids: List[Any]) -> List[int]:
        """Coerce ids to integers suitable for bigint[] storage.

        - int -> kept
        - str digits -> int
        - everything else -> dropped
        """
        coerced: List[int] = []
        for value in source_ids or []:
            if value is None:
                continue
            if isinstance(value, int):
                coerced.append(value)
                continue
            if isinstance(value, str):
                s = value.strip()
                if s.isdigit():
                    try:
                        coerced.append(int(s))
                    except Exception:
                        continue
        return coerced

    def _process_text_buffer(self, buffer: List[Dict[str, Any]], parent_header: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        텍스트 버퍼를 chunk_size에 맞게 분할하여 청크 리스트 생성
        """
        if not buffer:
            return []
            
        chunks: List[Dict[str, Any]] = []
        current_chunk_text: List[str] = []
        current_chunk_tokens = 0
        current_chunk_pages: List[int] = []
        current_chunk_ids: List[Any] = []
        
        parent_id = parent_header.get('id')
        section_path = " > ".join(parent_header.get('path') or [])
        section_title = parent_header.get('text')
        
        for item in buffer:
            text = item['content']
            tokens = _count_tokens(text)
            
            # 현재 청크에 추가하면 chunk_size를 넘는지 확인
            if current_chunk_tokens + tokens > self.chunk_size and current_chunk_tokens >= self.min_chunk_size:
                # 현재 청크 저장
                full_text = "\n\n".join(current_chunk_text).strip()
                if full_text:
                    chunks.append(self._make_chunk(
                        content_text=full_text,
                        page_numbers=current_chunk_pages,
                        source_object_ids=current_chunk_ids,
                        section="text",
                        section_title=section_title,
                        section_path=section_path,
                    ))

                # 오버랩: 마지막 문단들 중 overlap_tokens 이내를 다음 청크의 초기값으로 유지
                if self.chunk_overlap and current_chunk_text:
                    carry_text: List[str] = []
                    carry_ids: List[Any] = []
                    carry_pages: List[int] = []
                    carry_tokens = 0
                    # 뒤에서부터 누적
                    for back_idx in range(len(current_chunk_text) - 1, -1, -1):
                        seg = current_chunk_text[back_idx]
                        seg_tokens = _count_tokens(seg)
                        if carry_tokens + seg_tokens > self.chunk_overlap and carry_tokens > 0:
                            break
                        carry_text.insert(0, seg)
                        carry_tokens += seg_tokens
                        # ids/pages도 동일 인덱스 기반으로 carry
                        if back_idx < len(current_chunk_ids):
                            carry_ids.insert(0, current_chunk_ids[back_idx])
                        if back_idx < len(current_chunk_pages):
                            carry_pages.insert(0, current_chunk_pages[back_idx])

                    current_chunk_text = carry_text
                    current_chunk_tokens = carry_tokens
                    current_chunk_pages = carry_pages
                    current_chunk_ids = carry_ids
                else:
                    current_chunk_text = []
                    current_chunk_tokens = 0
                    current_chunk_pages = []
                    current_chunk_ids = []
            
            current_chunk_text.append(text)
            current_chunk_tokens += tokens
            if item.get('page') and isinstance(item.get('page'), int):
                current_chunk_pages.append(item['page'])
            current_chunk_ids.append(item.get('id'))
            
        # 마지막 청크 저장
        if current_chunk_text:
            full_text = "\n\n".join(current_chunk_text).strip()
            if full_text:
                chunks.append(self._make_chunk(
                    content_text=full_text,
                    page_numbers=current_chunk_pages,
                    source_object_ids=current_chunk_ids,
                    section="text",
                    section_title=section_title,
                    section_path=section_path,
                ))
            
        return chunks
