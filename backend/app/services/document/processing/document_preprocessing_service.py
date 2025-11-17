"""
📄 문서 전처리 서비스
===================

문서 업로드 후 의미 기반 청킹까지의 전처리 담당
1. 텍스트 추출 (PDF, DOCX, etc.)
2. 텍스트 정제 및 구조화
3. 의미 기반 스마트 청킹
4. 청크 메타데이터 생성
"""

import re
import hashlib
import logging
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
import tiktoken

from app.services.document.extraction.text_extractor_service import text_extractor_service
from app.core.config import settings
try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except Exception:  # pragma: no cover
    get_azure_blob_service = None  # type: ignore
try:
    from app.utils.storage_paths import (
        build_intermediate_page_key,
        build_intermediate_extraction_summary_key,
    )
except Exception:  # pragma: no cover
    build_intermediate_page_key = None  # type: ignore
    build_intermediate_extraction_summary_key = None  # type: ignore

logger = logging.getLogger(__name__)

class DocumentPreprocessingService:
    """문서 전처리 서비스 - 업로드부터 청킹까지"""
    
    def __init__(self):
        # AWS Bedrock Titan Embeddings V2 토큰 제한에 맞춘 설정
        self.max_tokens_per_chunk = 6000  # 안전 마진 포함 (8192 제한)
        self.min_tokens_per_chunk = 200  # 최소 청크 크기 (토큰) - 의미있는 맥락 보장
        self.target_tokens_per_chunk = 3000  # 목표 청크 크기 - 균형 잡힌 크기
        self.overlap_tokens = 300  # 겹침 토큰 수 (약 10%)
        self.tokenizer = tiktoken.get_encoding("cl100k_base")  # 정확한 토큰 계산
        
        # kss (Korean Sentence Splitter) 초기화
        try:
            import kss
            self.kss = kss
            self.use_kss = True
            logger.info("한국어 문장 분할기 (kss) 로드 성공")
        except ImportError:
            self.kss = None
            self.use_kss = False
            logger.warning("kss 라이브러리 없음 - 폴백 문장 분할 사용")
        
        logger.info(f"문서 전처리 서비스 초기화 - 최대: {self.max_tokens_per_chunk}, 목표: {self.target_tokens_per_chunk}, 최소: {self.min_tokens_per_chunk}, 겹침: {self.overlap_tokens}")
    
    async def preprocess_document(
        self,
        file_path: str,
        file_extension: str,
        container_id: str,
        user_emp_no: str
    ) -> Dict[str, Any]:
        """
        단계 1) 문서 전처리만 수행 (텍스트 추출 + 정제)

        반환:
          { success, extracted_text, cleaned_text, extraction_metadata }
        """
        try:
            logger.info(f"[PREPROCESS] 텍스트 추출 시작: {file_path}")
            extraction_result = await text_extractor_service.extract_text_from_file(file_path)
            if not extraction_result.get('success'):
                return {
                    'success': False,
                    'error': f"텍스트 추출 실패: {extraction_result.get('error')}"
                }

            raw_text = extraction_result.get('text', '')
            cleaned_text = self._clean_text(raw_text)

            return {
                'success': True,
                'extracted_text': raw_text,
                'cleaned_text': cleaned_text,
                'extraction_metadata': extraction_result.get('metadata', {})
            }
        except Exception as e:
            logger.error(f"[PREPROCESS] 전처리 중 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def chunk_text(
        self,
        cleaned_text: str,
        *,
        file_path: Optional[str] = None,
        container_id: Optional[str] = None,
        user_emp_no: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        단계 2) 청킹만 수행

        매개변수로 받은 정제 텍스트를 토큰 한도 기반으로 스마트 청킹합니다.
        파일/컨테이너 정보가 주어지면 메타데이터를 함께 생성합니다.
        """
        try:
            if not cleaned_text or not cleaned_text.strip():
                return {'success': False, 'error': '청킹할 텍스트가 없습니다.'}

            chunks = self._smart_chunk_text(cleaned_text)

            chunk_metadata: List[Dict[str, Any]] = []
            for i, chunk in enumerate(chunks):
                if file_path and container_id and user_emp_no:
                    meta = self._create_chunk_metadata(
                        chunk=chunk,
                        chunk_index=i,
                        total_chunks=len(chunks),
                        file_path=file_path,
                        container_id=container_id,
                        user_emp_no=user_emp_no
                    )
                    chunk_metadata.append(meta)

            return {
                'success': True,
                'chunks': chunks,
                'metadata': chunk_metadata,
                'total_chunks': len(chunks),
                'total_tokens': sum(len(self.tokenizer.encode(c)) for c in chunks)
            }
        except Exception as e:
            logger.error(f"[CHUNK] 청킹 중 오류: {e}")
            return {'success': False, 'error': str(e)}

    async def process_document(
        self, 
        file_path: str, 
        file_extension: str,
        container_id: str,
        user_emp_no: str
    ) -> Dict[str, Any]:
        """
        문서 전처리 메인 파이프라인 (호환 유지)
        - 1) 전처리만 수행
        - 2) 청킹만 수행
        """
        try:
            logger.info(f"문서 전처리 시작: {file_path}")

            # 1) 전처리만 수행
            pre = await self.preprocess_document(
                file_path=file_path,
                file_extension=file_extension,
                container_id=container_id,
                user_emp_no=user_emp_no
            )
            if not pre.get('success'):
                return pre

            cleaned_text = pre.get('cleaned_text', '')
            if not cleaned_text or len(cleaned_text.strip()) < 10:
                logger.warning(f"추출/정제된 텍스트가 너무 짧음: {len(cleaned_text)} 문자")
                return {
                    'success': False,
                    'error': '추출된 텍스트가 너무 짧습니다',
                    'extracted_text': pre.get('extracted_text', '')
                }

            # 2) 청킹만 수행
            ch = self.chunk_text(
                cleaned_text,
                file_path=file_path,
                container_id=container_id,
                user_emp_no=user_emp_no
            )
            if not ch.get('success'):
                return ch

            logger.info(f"문서 전처리 완료: {ch.get('total_chunks', 0)}개 청크 생성")
            # 기존 반환 구조 + extracted_text 포함
            result_payload = {
                'success': True,
                'chunks': ch.get('chunks', []),
                'metadata': ch.get('metadata', []),
                'total_chunks': ch.get('total_chunks', 0),
                'total_tokens': ch.get('total_tokens', 0),
                'extracted_text': pre.get('extracted_text', ''),
                'extraction_metadata': pre.get('extraction_metadata', {})
            }

            # Azure Blob intermediate 저장 (옵션)
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and build_intermediate_page_key:
                    azure = get_azure_blob_service()
                    # file_bss_info_sno는 아직 모를 수 있으므로 0 placeholder (추후 dual-write 연결 후 교체 가능)
                    file_id_placeholder = result_payload['extraction_metadata'].get('file_id') or 0
                    
                    # 1. 전체 텍스트를 단일 파일로 저장
                    full_text_key = f"{container_id}/{file_id_placeholder}/full_text.txt"
                    full_text_bytes = result_payload['extracted_text'].encode('utf-8')
                    azure.upload_bytes(full_text_bytes, full_text_key, purpose='intermediate')
                    logger.info(f"[BLOB] 전체 텍스트 저장: {full_text_key} ({len(full_text_bytes)} bytes)")
                    
                    # 2. 페이지/슬라이드/시트 정보가 extraction_metadata 안에 구조화 되어 있다면 페이지별 저장
                    pages = result_payload['extraction_metadata'].get('pages') or []
                    slides = result_payload['extraction_metadata'].get('slides') or []
                    sheets = result_payload['extraction_metadata'].get('sheets') or []
                    
                    # PDF 페이지별 저장
                    for page in pages:
                        pno = page.get('page_no') or page.get('page_number') or 0
                        key = build_intermediate_page_key(container_id, file_id_placeholder, int(pno))
                        azure.upload_bytes(json.dumps(page, ensure_ascii=False).encode('utf-8'), key, purpose='intermediate')
                    
                    # PPTX 슬라이드별 저장
                    for slide in slides:
                        sno = slide.get('slide_no') or 0
                        key = f"{container_id}/{file_id_placeholder}/slide_{sno}.json"
                        azure.upload_bytes(json.dumps(slide, ensure_ascii=False).encode('utf-8'), key, purpose='intermediate')
                    
                    # XLSX 시트별 저장
                    for sheet in sheets:
                        sheet_no = sheet.get('sheet_no') or 0
                        sheet_name = sheet.get('sheet_name', f'sheet_{sheet_no}')
                        key = f"{container_id}/{file_id_placeholder}/sheet_{sheet_no}_{sheet_name}.json"
                        azure.upload_bytes(json.dumps(sheet, ensure_ascii=False).encode('utf-8'), key, purpose='intermediate')
                    
                    # 3. 요약 정보 저장
                    if build_intermediate_extraction_summary_key:
                        summary_key = build_intermediate_extraction_summary_key(container_id, file_id_placeholder)
                        summary_doc = {
                            'page_count': len(pages),
                            'slide_count': len(slides),
                            'sheet_count': len(sheets),
                            'container_id': container_id,
                            'original_file': Path(file_path).name,
                            'total_chars': len(result_payload['extracted_text']),
                            'extraction_method': result_payload['extraction_metadata'].get('extraction_method', 'unknown')
                        }
                        azure.upload_bytes(json.dumps(summary_doc, ensure_ascii=False).encode('utf-8'), summary_key, purpose='intermediate')
                    
                    logger.info(f"[BLOB] 중간 산출물 저장 완료 - 페이지:{len(pages)}, 슬라이드:{len(slides)}, 시트:{len(sheets)}")
            except Exception as e_blob:
                logger.warning(f"[PREPROCESS] Intermediate Blob 업로드 실패 (무시): {e_blob}")

            return result_payload
            
        except Exception as e:
            logger.error(f"문서 전처리 중 오류: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _clean_text(self, text: str) -> str:
        """텍스트 정제 및 정규화"""
        if not text:
            return ""
        
        # 기본 정제
        cleaned = text.strip()
        
        # 연속된 공백 제거
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 특수 문자 정리
        cleaned = re.sub(r'[^\w\s\.,!?;:()\[\]{}"\'-]', ' ', cleaned)
        
        # 문단 구분 정리
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def _split_into_paragraphs(self, text: str) -> List[Dict[str, Any]]:
        """텍스트를 단락으로 분할 (구조 인식 포함)"""
        if not text or not text.strip():
            return []
        
        # 제목/번호 패턴 정의
        heading_patterns = [
            r'^\s*(\d+\.|\d+\))',  # 1., 1), 2., 2) 등
            r'^\s*([\uac00-\ud7a3]\.|[\uac00-\ud7a3]\))',  # 가., 가), 나., 나) 등
            r'^\s*([IVX]+\.|[IVX]+\))',  # I., I), II., II) 등 (로마 숫자)
            r'^\s*(제\s*\d+\s*[장절항관])',  # 제1장, 제2절, 제3항 등
            r'^\s*(■|●|•|\*|\-)',  # 불릿 기호
            r'^\s*([\[\(]\d+[\]\)])',  # [1], (1) 등
        ]
        
        # 연속된 줄바꿈(\n\n)으로 단락 분할
        raw_paragraphs = re.split(r'\n\s*\n', text)
        
        structured_paragraphs = []
        for para in raw_paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # 제목/번호 패턴 확인
            is_heading = False
            heading_type = None
            
            for i, pattern in enumerate(heading_patterns):
                if re.match(pattern, para, re.MULTILINE):
                    is_heading = True
                    heading_type = ['numbered', 'alphabetic', 'roman', 'chapter', 'bullet', 'bracketed'][i]
                    break
            
            # 짧은 텍스트 + 마침표로 끝나면 제목으로 간주
            if not is_heading and len(para) < 100 and (para.endswith(':') or para.endswith('으로') or para.endswith('는')):
                is_heading = True
                heading_type = 'inferred'
            
            structured_paragraphs.append({
                'text': para,
                'is_heading': is_heading,
                'heading_type': heading_type,
                'char_count': len(para),
                'token_count': len(self.tokenizer.encode(para))
            })
        
        logger.info(f"단락 분할 완료: {len(structured_paragraphs)}개 (제목: {sum(1 for p in structured_paragraphs if p['is_heading'])}개)")
        return structured_paragraphs
    
    def _smart_chunk_text(self, text: str) -> List[str]:
        """개선된 스마트 청킹 - 단락 우선, 겹침, 최소/최대 크기, 한국어 분할 지원"""
        if not text:
            return []
        
        # 전체 토큰 수 계산
        total_tokens = len(self.tokenizer.encode(text))
        logger.info(f"전체 텍스트 토큰 수: {total_tokens}")
        
        # 최소 크기 이하면 그대로 반환
        if total_tokens <= self.min_tokens_per_chunk:
            logger.warning(f"텍스트가 최소 크기 이하: {total_tokens} < {self.min_tokens_per_chunk}")
            return [text]
        
        # 목표 크기 이하면 그대로 반환
        if total_tokens <= self.target_tokens_per_chunk:
            return [text]
        
        # 1단계: 단락으로 분할 (구조 인식)
        paragraphs = self._split_into_paragraphs(text)
        
        if not paragraphs:
            # 단락 분할 실패 시 문장 단위로 폴백
            return self._chunk_by_sentences(text)
        
        # 2단계: 단락 기반 청킹
        chunks = []
        current_chunk = ""
        current_tokens = 0
        current_paragraphs = []  # 현재 청크에 포함된 단락들
        
        for i, para_info in enumerate(paragraphs):
            para_text = para_info['text']
            para_tokens = para_info['token_count']
            is_heading = para_info['is_heading']
            
            # 단락이 목표 크기보다 크면 문장 단위로 분할
            if para_tokens > self.target_tokens_per_chunk:
                # 현재 청크 저장
                if current_chunk.strip() and current_tokens >= self.min_tokens_per_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_tokens = 0
                    current_paragraphs = []
                
                # 큰 단락을 문장 단위로 분할
                para_chunks = self._split_paragraph_to_chunks(para_text)
                chunks.extend(para_chunks)
                continue
            
            # 제목이 나타났고 현재 청크가 있으면 새 청크 시작
            if is_heading and current_chunk.strip() and current_tokens >= self.min_tokens_per_chunk:
                chunks.append(current_chunk.strip())
                # 겹침 처리
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = overlap_text + "\n\n" + para_text if overlap_text else para_text
                current_tokens = len(self.tokenizer.encode(current_chunk))
                current_paragraphs = [para_info]
                continue
            
            # 단락 추가 시 목표 크기 초과 확인
            if current_tokens + para_tokens > self.target_tokens_per_chunk:
                # 현재 청크가 최소 크기 이상이면 저장
                if current_tokens >= self.min_tokens_per_chunk and current_chunk.strip():
                    chunks.append(current_chunk.strip())
                    
                    # 겹침 처리
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + "\n\n" + para_text if overlap_text else para_text
                    current_tokens = len(self.tokenizer.encode(current_chunk))
                    current_paragraphs = [para_info]
                else:
                    # 최소 크기 미만이면 계속 추가
                    current_chunk += "\n\n" + para_text if current_chunk else para_text
                    current_tokens += para_tokens
                    current_paragraphs.append(para_info)
            else:
                # 단락 추가
                current_chunk += "\n\n" + para_text if current_chunk else para_text
                current_tokens += para_tokens
                current_paragraphs.append(para_info)
        
        # 마지막 청크 처리
        if current_chunk.strip():
            chunk_tokens = len(self.tokenizer.encode(current_chunk))
            if chunk_tokens >= self.min_tokens_per_chunk:
                chunks.append(current_chunk.strip())
            elif chunks:  # 마지막 청크가 너무 작으면 이전 청크에 병합
                chunks[-1] = chunks[-1] + "\n\n" + current_chunk.strip()
                logger.info(f"마지막 작은 청크를 이전 청크에 병합 ({chunk_tokens} 토큰)")
            else:
                chunks.append(current_chunk.strip())  # 유일한 청크면 그대로 저장
        
        # 청크 검증 및 초과 크기 처리
        validated_chunks = []
        for i, chunk in enumerate(chunks):
            chunk_tokens = len(self.tokenizer.encode(chunk))
            
            if chunk_tokens > self.max_tokens_per_chunk:
                logger.warning(f"청크 {i}가 최대 제한 초과: {chunk_tokens} > {self.max_tokens_per_chunk} - 분할")
                # 문장 경계를 고려한 분할 시도
                sub_chunks = self._split_large_chunk(chunk)
                validated_chunks.extend(sub_chunks)
            else:
                validated_chunks.append(chunk)
        
        avg_tokens = sum(len(self.tokenizer.encode(c)) for c in validated_chunks) // len(validated_chunks) if validated_chunks else 0
        logger.info(f"단락 기반 청킹 완료: {len(validated_chunks)}개 청크 (평균 {avg_tokens} 토큰)")
        return validated_chunks
    
    def _split_paragraph_to_chunks(self, paragraph: str) -> List[str]:
        """큰 단락을 문장 단위로 분할하여 청크 생성"""
        sentences = self._split_into_sentences(paragraph)
        
        if not sentences:
            return [paragraph]
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))
            
            if current_tokens + sentence_tokens > self.target_tokens_per_chunk:
                if current_chunk.strip() and current_tokens >= self.min_tokens_per_chunk:
                    chunks.append(current_chunk.strip())
                    # 겹침 처리
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                    current_tokens = len(self.tokenizer.encode(current_chunk))
                else:
                    current_chunk += " " + sentence if current_chunk else sentence
                    current_tokens += sentence_tokens
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [paragraph]
    
    def _chunk_by_sentences(self, text: str) -> List[str]:
        """문장 기반 청킹 (단락 분할 실패 시 폴백)"""
        sentences = self._split_into_sentences(text)
        
        if not sentences:
            return [text]
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))
            
            if current_tokens + sentence_tokens > self.target_tokens_per_chunk:
                if current_chunk.strip() and current_tokens >= self.min_tokens_per_chunk:
                    chunks.append(current_chunk.strip())
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                    current_tokens = len(self.tokenizer.encode(current_chunk))
                else:
                    current_chunk += " " + sentence if current_chunk else sentence
                    current_tokens += sentence_tokens
            else:
                current_chunk += " " + sentence if current_chunk else sentence
                current_tokens += sentence_tokens
        
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks if chunks else [text]
    
    def _get_overlap_text(self, chunk: str) -> str:
        """청크의 마지막 부분에서 겹침용 텍스트 추출"""
        tokens = self.tokenizer.encode(chunk)
        if len(tokens) <= self.overlap_tokens:
            return chunk  # 청크가 겹침 크기보다 작으면 전체 반환
        
        overlap_start = len(tokens) - self.overlap_tokens
        overlap_tokens_list = tokens[overlap_start:]
        overlap_text = self.tokenizer.decode(overlap_tokens_list)
        return overlap_text.strip()
    
    def _split_large_chunk(self, chunk: str) -> List[str]:
        """큰 청크를 문장 경계를 고려하여 분할"""
        # 먼저 문장 단위로 분할 시도
        sentences = self._split_into_sentences(chunk)
        
        if len(sentences) <= 1:
            # 문장이 하나뿐이면 강제 토큰 분할
            return self._force_split_chunk(chunk)
        
        # 문장을 묶어서 청크 생성
        sub_chunks = []
        current_sub = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = len(self.tokenizer.encode(sentence))
            
            if current_tokens + sentence_tokens > self.max_tokens_per_chunk:
                if current_sub.strip():
                    sub_chunks.append(current_sub.strip())
                current_sub = sentence
                current_tokens = sentence_tokens
            else:
                current_sub += " " + sentence if current_sub else sentence
                current_tokens += sentence_tokens
        
        if current_sub.strip():
            sub_chunks.append(current_sub.strip())
        
        return sub_chunks if sub_chunks else self._force_split_chunk(chunk)
    
    def _force_split_chunk(self, chunk: str) -> List[str]:
        """토큰 제한을 초과한 청크를 강제로 분할"""
        tokens = self.tokenizer.encode(chunk)
        sub_chunks = []
        
        for i in range(0, len(tokens), self.max_tokens_per_chunk):
            sub_tokens = tokens[i:i + self.max_tokens_per_chunk]
            sub_text = self.tokenizer.decode(sub_tokens)
            if sub_text.strip():
                sub_chunks.append(sub_text.strip())
        
        return sub_chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """개선된 텍스트 문장 분할 - kss 우선, 폴백 패턴 사용"""
        if not text or not text.strip():
            return []
        
        # kss 라이브러리 사용 (한국어 최적화)
        if self.use_kss and self.kss:
            try:
                sentences = self.kss.split_sentences(text)
                if sentences:
                    # 빈 문장 제거 및 정리
                    sentences = [s.strip() for s in sentences if s.strip()]
                    if sentences:
                        return sentences
            except Exception as e:
                logger.warning(f"kss 문장 분할 실패, 폴백 사용: {e}")
        
        # 폴백: 개선된 정규식 패턴
        # 한국어 종결어미 고려
        korean_endings = r'(다|요|까|네|지|야|어|아|죠|ㅂ니다|습니다|ㅂ니까|습니까)\.'
        # 영어 문장 끝 (약어 제외)
        english_endings = r'(?<![A-Z])[.!?]+(?=\s+[A-Z가-힣])'
        # 중일 문장 끝
        cjk_endings = r'[。！？]+'
        
        # 통합 패턴
        pattern = f'{korean_endings}|{english_endings}|{cjk_endings}'
        
        sentences = []
        parts = re.split(f'({pattern})', text)
        
        # 구분자를 포함하여 문장 재구성
        current_sentence = ""
        for i, part in enumerate(parts):
            if not part or not part.strip():
                continue
            current_sentence += part
            # 구분자인 경우 문장 완성
            if re.match(pattern, part):
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # 마지막 문장 추가
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # 패턴 매칭 실패 시 줄바꿈 기준 분할
        if not sentences:
            sentences = [s.strip() for s in text.split('\n') if s.strip()]
        
        # 최종 안전 장치: 문장이 없으면 전체 텍스트 반환
        if not sentences:
            sentences = [text.strip()]
        
        return sentences
    
    def _create_chunk_metadata(
        self, 
        chunk: str, 
        chunk_index: int, 
        total_chunks: int,
        file_path: str,
        container_id: str,
        user_emp_no: str
    ) -> Dict[str, Any]:
        """청크 메타데이터 생성"""
        chunk_tokens = len(self.tokenizer.encode(chunk))
        chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
        
        return {
            'chunk_index': chunk_index,
            'chunk_type': self._determine_chunk_type(chunk),
            'token_count': chunk_tokens,
            'char_count': len(chunk),
            'content_hash': chunk_hash,
            'korean_keywords': self._extract_korean_keywords(chunk),
            'container_id': container_id,
            'file_name': Path(file_path).name,
            'created_by': user_emp_no
        }
    
    def _determine_chunk_type(self, chunk: str) -> str:
        """청크 유형 판별"""
        if len(chunk) < 100:
            return "title"
        elif re.search(r'^[0-9]+\.', chunk):
            return "section_header"
        elif re.search(r'[그림|표|Figure|Table]', chunk):
            return "figure_caption"
        else:
            return "content"
    
    def _extract_korean_keywords(self, chunk: str) -> List[str]:
        """한국어 키워드 추출 (간단한 버전)"""
        # 한글 단어 추출
        korean_words = re.findall(r'[가-힣]+', chunk)
        
        # 빈도수 기반 키워드 선택
        word_freq = {}
        for word in korean_words:
            if len(word) >= 2:  # 2글자 이상만
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 상위 5개 키워드 선택
        keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        return [word for word, freq in keywords]

# 전역 인스턴스
document_preprocessing_service = DocumentPreprocessingService()
