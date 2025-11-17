"""
📄 통합 문서 처리 파이프라인 서비스
==================================

업로드된 문서를 RAG용 벡터스토어까지 완전 처리하는 통합 서비스

파이프라인:
1. 문서 전처리 (텍스트 추출 + 청킹)
2. 한국어 NLP 분석 (형태소 + 임베딩) 
3. 벡터스토어 저장 (메타데이터 + 임베딩)
"""

import asyncio
import logging
import os
import json
import uuid
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import tiktoken

from app.core.config import settings
try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except Exception:  # pragma: no cover
    get_azure_blob_service = None  # type: ignore
try:
    from app.utils.storage_paths import (
        build_derived_chunk_key,
        build_derived_chunks_manifest_key,
    )
except Exception:  # pragma: no cover
    build_derived_chunk_key = None  # type: ignore
    build_derived_chunks_manifest_key = None  # type: ignore

# 서비스 imports
from app.services.document.processing.document_preprocessing_service import document_preprocessing_service
from app.services.core.korean_nlp_service import korean_nlp_service

# 데이터베이스 imports
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models import TbDocumentSearchIndex
from app.models import VsDocContentsChunks

logger = logging.getLogger(__name__)

class IntegratedDocumentPipelineService:
    """통합 문서 처리 파이프라인 서비스"""
    
    def __init__(self):
        self.max_retries = 3
        self.batch_size = 10  # 청크 배치 처리 크기
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    async def process_document_for_rag(
        self,
        file_path: str,
        file_name: str,
        container_id: str,
        user_emp_no: str,
        file_bss_info_sno: int
    ) -> Dict[str, Any]:
        """
        RAG용 문서 완전 처리 파이프라인
        
        Args:
            file_path: 업로드된 파일 경로
            file_name: 원본 파일명
            container_id: 지식 컨테이너 ID
            user_emp_no: 업로드 사용자 사번
            file_bss_info_sno: 파일 기본 정보 일련번호
            
        Returns:
            처리 결과 딕셔너리
        """
        pipeline_result = {
            "success": False,
            "file_info": {
                "file_path": file_path,
                "file_name": file_name,
                "container_id": container_id,
                "user_emp_no": user_emp_no,
                "file_bss_info_sno": file_bss_info_sno
            },
            "stage_results": {
                "preprocessing": {},
                "nlp_analysis": {},
                "vector_storage": {}
            },
            "rag_ready": False,
            "processing_stats": {}
        }
        
        try:
            start_time = datetime.now()
            logger.info(f"🚀 [PIPELINE-DEBUG] RAG 파이프라인 시작")
            logger.info(f"   📄 파일: {file_name}")
            logger.info(f"   📁 경로: {file_path}")
            logger.info(f"   🔧 컨테이너: {container_id}")
            logger.info(f"   👤 사용자: {user_emp_no}")
            logger.info(f"   🆔 DB ID: {file_bss_info_sno}")
            
            # 🔄 1단계: 문서 전처리 (텍스트 추출 + 청킹)
            logger.info(f"💾 [PIPELINE-DEBUG] 1단계 시작: 문서 전처리")
            preprocessing_result = await document_preprocessing_service.process_document(
                file_path=file_path,
                file_extension=Path(file_path).suffix,
                container_id=container_id,
                user_emp_no=user_emp_no
            )
            
            pipeline_result["stage_results"]["preprocessing"] = preprocessing_result
            
            if not preprocessing_result.get("success"):
                pipeline_result["error"] = f"전처리 단계 실패: {preprocessing_result.get('error')}"
                logger.error(f"❌ [PIPELINE-DEBUG] 1단계 실패: {preprocessing_result.get('error')}")
                return pipeline_result
            
            chunks = preprocessing_result["chunks"]
            logger.info(f"✅ [PIPELINE-DEBUG] 전처리 완료: {len(chunks)}개 청크 생성")
            logger.info(f"   📝 추출된 텍스트 길이: {len(preprocessing_result.get('extracted_text', ''))}")
            
            if len(chunks) == 0:
                logger.error(f"❌ [PIPELINE-DEBUG] 청크가 생성되지 않음")
                pipeline_result["error"] = "청크 생성 실패"
                return pipeline_result
            
            # 🔄 2단계: 한국어 NLP 분석 + 임베딩
            logger.info(f"🧠 [PIPELINE-DEBUG] 2단계 시작: NLP 분석 - {len(chunks)}개 청크")
            analyzed_chunks = []
            
            # 전처리에서 생성된 메타데이터 재사용
            preprocessing_metadata = preprocessing_result.get('metadata', [])
            
            for i, chunk_text in enumerate(chunks):
                logger.info(f"   📝 [PIPELINE-DEBUG] 청크 {i+1}/{len(chunks)} 분석 중...")
                logger.info(f"   📄 청크 내용 길이: {len(chunk_text)}")
                
                chunk_analysis = await korean_nlp_service.analyze_chunk_for_search(
                    chunk_text
                )
                
                # 전처리 메타데이터에서 토큰 수 재사용 (중복 계산 방지)
                existing_meta = preprocessing_metadata[i] if i < len(preprocessing_metadata) else {}
                token_count = existing_meta.get('token_count', len(chunk_text.split()))
                
                if chunk_analysis.get("success"):
                    # 원본 청크 데이터와 NLP 분석 결과 병합
                    enriched_chunk = {
                        "content": chunk_text,  # 청크 텍스트
                        "chunk_index": i,
                        "char_count": len(chunk_text),
                        "token_count": token_count,  # ✅ 중복 계산 제거
                        "korean_keywords": chunk_analysis.get("korean_keywords", []),
                        "pos_tags": chunk_analysis.get("pos_tags", []),
                        "named_entities": chunk_analysis.get("named_entities", []),
                        "embedding": chunk_analysis.get("embedding"),
                        "success": True
                    }
                    analyzed_chunks.append(enriched_chunk)
                    logger.info(f"   ✅ 청크 {i+1} NLP 성공: {len(enriched_chunk.get('korean_keywords', []))}개 키워드")
                else:
                    logger.warning(f"   ⚠️ [PIPELINE-DEBUG] 청크 {i+1} NLP 분석 실패: {chunk_analysis.get('error')}")
                    # 실패해도 기본 청크는 유지
                    analyzed_chunks.append({
                        "content": chunk_text,
                        "chunk_index": i,
                        "char_count": len(chunk_text),
                        "token_count": len(self.tokenizer.encode(chunk_text)) if hasattr(self, 'tokenizer') else len(chunk_text.split()),
                        "korean_keywords": [],
                        "pos_tags": [],
                        "named_entities": [],
                        "embedding": None,
                        "success": False,
                        "error": chunk_analysis.get('error')
                    })
            
            pipeline_result["stage_results"]["nlp_analysis"] = {
                "success": True,
                "processed_chunks": len(analyzed_chunks),
                "successful_chunks": len([c for c in analyzed_chunks if c.get("success")]),
                "failed_chunks": len([c for c in analyzed_chunks if not c.get("success")])
            }
            
            successful_chunks = len([c for c in analyzed_chunks if c.get("success")])
            failed_chunks = len([c for c in analyzed_chunks if not c.get("success")])
            logger.info(f"✅ [PIPELINE-DEBUG] 2단계 NLP 완료: {successful_chunks}개 성공, {failed_chunks}개 실패")
            
            # 🔄 2.5단계: (옵션) 파생 산출물 Blob 저장 (청크/매니페스트)
            try:
                if settings.storage_backend == 'azure_blob' and get_azure_blob_service and build_derived_chunk_key:
                    azure = get_azure_blob_service()
                    manifest = []
                    for ch_idx, ch_obj in enumerate(analyzed_chunks):
                        chunk_key = build_derived_chunk_key(container_id, file_bss_info_sno, ch_idx)
                        payload = {
                            'chunk_index': ch_idx,
                            'char_count': ch_obj.get('char_count'),
                            'token_count': ch_obj.get('token_count'),
                            'has_embedding': ch_obj.get('embedding') is not None,
                            'korean_keywords': ch_obj.get('korean_keywords'),
                        }
                        azure.upload_bytes(json.dumps(payload, ensure_ascii=False).encode('utf-8'), chunk_key, purpose='derived')
                        manifest.append({'key': chunk_key, 'size': len(ch_obj.get('content',''))})
                    if build_derived_chunks_manifest_key:
                        m_key = build_derived_chunks_manifest_key(container_id, file_bss_info_sno)
                        azure.upload_bytes(json.dumps({'chunks': manifest}, ensure_ascii=False).encode('utf-8'), m_key, purpose='derived')
                    logger.info(f"🗂️ [PIPELINE-DEBUG] 파생 청크 {len(analyzed_chunks)}개 Blob 저장 완료")
            except Exception as derived_err:
                logger.warning(f"[PIPELINE-DEBUG] 파생 산출물 Blob 저장 실패 (무시): {derived_err}")

            # 🔄 3단계: 벡터스토어 저장
            logger.info(f"📦 [PIPELINE-DEBUG] 3단계 시작: 벡터스토어 저장")
            storage_result = await self._store_document_and_chunks(
                file_bss_info_sno=file_bss_info_sno,
                container_id=container_id,
                user_emp_no=user_emp_no,
                file_name=file_name,
                preprocessing_result=preprocessing_result,
                analyzed_chunks=analyzed_chunks
            )
            
            pipeline_result["stage_results"]["vector_storage"] = storage_result
            
            logger.info(f"🔄 [PIPELINE-DEBUG] 벡터스토어 결과: success={storage_result.get('success', False)}")
            if storage_result.get("success"):
                logger.info(f"   📦 저장된 청크 수: {storage_result.get('chunks_stored', 0)}")
                pipeline_result["success"] = True
                pipeline_result["rag_ready"] = True
                logger.info(f"✅ [PIPELINE-DEBUG] 벡터스토어 저장 완료")
            else:
                logger.error(f"❌ [PIPELINE-DEBUG] 벡터스토어 저장 실패: {storage_result.get('error')}")
                pipeline_result["error"] = f"벡터스토어 저장 실패: {storage_result.get('error')}"
                return pipeline_result
            
            # 📊 처리 통계 생성
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            pipeline_result["processing_stats"] = {
                "total_processing_time": processing_time,
                "chunks_created": len(chunks),
                "chunks_with_embeddings": len([c for c in analyzed_chunks if c.get("embedding")]),
                "total_keywords": sum(len(c.get("korean_keywords", [])) for c in analyzed_chunks),
                "avg_chunk_size": sum(c.get("char_count", 0) for c in analyzed_chunks) // len(analyzed_chunks) if analyzed_chunks else 0,
                "vector_dimension": len(analyzed_chunks[0].get("embedding", [])) if analyzed_chunks and analyzed_chunks[0].get("embedding") else 0
            }
            
            logger.info(f"🎯 [PIPELINE-DEBUG] 파이프라인 완료: {processing_time:.2f}초")
            logger.info(f"   📊 통계: 청크 {len(chunks)}개, 임베딩 {len([c for c in analyzed_chunks if c.get('embedding')])}개")
            logger.info(f"   ✅ RAG 준비 완료!")
            return pipeline_result
            
        except Exception as e:
            logger.error(f"💥 [PIPELINE-DEBUG] 파이프라인 예외 발생: {e}")
            logger.error(f"   📄 파일: {file_name}")
            logger.error(f"   🆔 DB ID: {file_bss_info_sno}")
            import traceback
            logger.error(f"   🔍 상세 오류: {traceback.format_exc()}")
            pipeline_result["error"] = str(e)
            return pipeline_result
    
    async def _store_document_and_chunks(
        self,
        file_bss_info_sno: int,
        container_id: str,
        user_emp_no: str,
        file_name: str,
        preprocessing_result: Dict[str, Any],
        analyzed_chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """기존 스키마를 사용하여 벡터 문서 및 청크를 데이터베이스에 저장"""
        try:
            logger.info("🗄️ [STORE-DEBUG] 벡터스토어 저장 시작 (기존 스키마 사용)")
            logger.info(f"   📝 파일 ID: {file_bss_info_sno}")
            logger.info(f"   📦 저장할 청크 수: {len(analyzed_chunks)}")

            async for session in get_db():
                successful_chunks = 0
                vs_doc_records: List[TbDocumentSearchIndex] = []
                chunk_records: List[VsDocContentsChunks] = []

                # 1. 검색 인덱스 저장
                logger.info("🗄️ [STORE-DEBUG] 1단계: 키워드/전문 검색 인덱스 저장")
                for chunk_data in analyzed_chunks:
                    content = chunk_data.get("content", "")
                    if not content:
                        logger.warning(f"청크 {chunk_data.get('chunk_index', 'unknown')}에 content 없음")
                        continue
                    container_id_to_use = container_id or 'DEFAULT_CONTAINER'
                    if not container_id:
                        logger.warning(f"🚨 [STORE-DEBUG] 컨테이너 ID 누락 -> DEFAULT_CONTAINER 사용 (파일 ID: {file_bss_info_sno})")
                    try:
                        search_record = TbDocumentSearchIndex(
                            file_bss_info_sno=file_bss_info_sno,
                            knowledge_container_id=container_id_to_use,
                            document_title=file_name,
                            full_content=content,
                            content_summary=content[:1000],
                            keywords=chunk_data.get("korean_keywords", []),
                            proper_nouns=chunk_data.get("named_entities", []),
                            document_type=Path(file_name).suffix.upper().replace('.', ''),
                            content_length=len(content),
                            language_code='ko'
                        )
                        session.add(search_record)
                        vs_doc_records.append(search_record)
                        logger.debug(f"   🔖 인덱스 레코드 추가 chunk={chunk_data.get('chunk_index')}")
                    except Exception as e:
                        logger.warning(f"🗄️ [STORE-DEBUG] 인덱스 저장 실패 chunk={chunk_data.get('chunk_index')}: {e}")
                        continue

                # 2. 벡터/청크 저장
                logger.info("🗄️ [STORE-DEBUG] 2단계: 벡터/청크 저장")
                expected_dimension = settings.get_current_embedding_dimension()
                for chunk_data in analyzed_chunks:
                    content = chunk_data.get("content", "")
                    if not content:
                        continue
                    container_id_to_use = container_id or 'DEFAULT_CONTAINER'
                    chunk_embedding = chunk_data.get("embedding")
                    try:
                        if chunk_embedding:
                            chunk_embedding = settings.apply_smart_dimension_reduction(chunk_embedding, expected_dimension)
                            if len(chunk_embedding) != expected_dimension:
                                if len(chunk_embedding) < expected_dimension:
                                    chunk_embedding = chunk_embedding + [0.0] * (expected_dimension - len(chunk_embedding))
                                else:
                                    chunk_embedding = chunk_embedding[:expected_dimension]
                        else:
                            chunk_embedding = [0.0] * expected_dimension

                        metadata_payload = json.dumps({
                            "chunk_index": chunk_data.get("chunk_index", 0),
                            "token_count": chunk_data.get("token_count", 0),
                            "char_count": chunk_data.get("char_count", 0),
                            "korean_keywords": chunk_data.get("korean_keywords", []),
                            "named_entities": chunk_data.get("named_entities", []),
                            "pos_tags": chunk_data.get("pos_tags", []),  # ✅ 품사 태그 저장
                            "file_name": file_name,
                            "container_id": container_id
                        })
                        chunk_record = VsDocContentsChunks(
                            file_bss_info_sno=file_bss_info_sno,
                            chunk_index=chunk_data.get("chunk_index", 0),
                            chunk_text=content,
                            chunk_size=chunk_data.get("char_count", len(content)),
                            chunk_embedding=chunk_embedding,
                            page_number=chunk_data.get("page_number"),
                            section_title=chunk_data.get("section_title"),
                            knowledge_container_id=container_id_to_use,
                            metadata_json=metadata_payload,
                            created_by=user_emp_no,
                            last_modified_by=user_emp_no
                        )
                        session.add(chunk_record)
                        chunk_records.append(chunk_record)
                        successful_chunks += 1
                        logger.debug(f"   💾 벡터 청크 저장 chunk={chunk_data.get('chunk_index')}")
                    except Exception as e:
                        logger.warning(f"🗄️ [STORE-DEBUG] 벡터/청크 저장 실패 chunk={chunk_data.get('chunk_index')}: {e}")
                        continue

                # 3. 커밋
                logger.info("🗄️ [STORE-DEBUG] 3단계: 트랜잭션 커밋")
                logger.info(f"   📊 vs_doc_contents_index: {len(vs_doc_records)}개 레코드")
                logger.info(f"   📊 vs_doc_contents_chunks: {len(chunk_records)}개 레코드")
                await session.commit()
                logger.info("✅ [STORE-DEBUG] 벡터스토어 저장 완료!")
                return {
                    "success": True,
                    "file_bss_info_sno": file_bss_info_sno,
                    "vector_records_stored": len(vs_doc_records),
                    "chunk_records_stored": len(chunk_records),
                    "total_chunks": len(analyzed_chunks),
                    "storage_info": {
                        "vector_table": "vs_doc_contents_index",
                        "chunk_table": "vs_doc_contents_chunks",
                        "vector_dimension": len(analyzed_chunks[0].get("embedding", [])) if analyzed_chunks and analyzed_chunks[0].get("embedding") else 0,
                        "has_korean_analysis": any(c.get("korean_keywords") for c in analyzed_chunks),
                        "has_embeddings": any(c.get("embedding") for c in analyzed_chunks)
                    }
                }
        except Exception as e:
            logger.error(f"💥 [STORE-DEBUG] 벡터스토어 저장 실패: {e}")
            import traceback
            logger.error(f"   🔍 상세 오류: {traceback.format_exc()}")
            return {"success": False, "error": str(e)}

        # 이 위치에 도달하면 세션 루프에서 return 되지 않은 비정상 흐름
        logger.error("💥 [STORE-DEBUG] 비정상 흐름: 세션 루프에서 반환되지 않음")
        return {"success": False, "error": "Unexpected control flow in _store_document_and_chunks"}

        # NOTE: 정상적으로는 위에서 이미 반환됨.

# 전역 인스턴스
integrated_pipeline_service = IntegratedDocumentPipelineService()
