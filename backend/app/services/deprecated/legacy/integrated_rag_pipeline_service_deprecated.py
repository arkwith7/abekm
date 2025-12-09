"""
🚀 통합 RAG 파이프라인 서비스 
============================

문서 업로드 → 전처리 → NLP → 벡터화 → 저장의 완전한 파이프라인
"""

import logging
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import time
from pathlib import Path

# 서비스 imports
from app.services.document.processing.document_preprocessing_service import document_preprocessing_service
from app.services.core.korean_nlp_service import korean_nlp_service
from app.services.document.storage.vector_storage_service import vector_storage_service

logger = logging.getLogger(__name__)

class IntegratedRAGPipelineService:
    """통합 RAG 파이프라인 서비스"""
    
    def __init__(self):
        self.vector_storage = vector_storage_service
    
    async def process_document_for_rag(
        self,
        session: AsyncSession,
        file_path: str,
        file_name: str,
        container_id: str,
        user_emp_no: str,
        file_bss_info_sno: int
    ) -> Dict[str, Any]:
        """
        완전한 RAG 파이프라인 실행
        
        1. 문서 전처리 (텍스트 추출 + 청킹)
        2. 한국어 NLP 분석 (청크별)
        3. 벡터 임베딩 생성
        4. 데이터베이스 저장 (하이브리드 검색용)
        """
        start_time = time.time()
        
        result = {
            "success": False,
            "rag_ready": False,
            "processing_stats": {
                "chunks_created": 0,
                "nlp_processed": 0,
                "vectors_stored": 0,
                "total_processing_time": 0.0
            },
            "pipeline_steps": {
                "preprocessing": {"success": False},
                "nlp_analysis": {"success": False},
                "vector_storage": {"success": False}
            },
            "errors": []
        }
        
        try:
            # 1단계: 문서 전처리 및 청킹
            logger.info(f"📄 1단계: 문서 전처리 시작 - {file_name}")
            preprocessing_result = await document_preprocessing_service.process_document(
                file_path=file_path,
                file_extension=Path(file_path).suffix,
                container_id=container_id,
                user_emp_no=user_emp_no
            )
            
            if not preprocessing_result.get("success"):
                result["errors"].append(f"전처리 실패: {preprocessing_result.get('error')}")
                return result
            
            chunks = preprocessing_result.get("chunks", [])
            result["pipeline_steps"]["preprocessing"] = {
                "success": True,
                "chunks_count": len(chunks)
            }
            result["processing_stats"]["chunks_created"] = len(chunks)
            
            logger.info(f"✅ 전처리 완료: {len(chunks)}개 청크 생성")
            
            # 2단계: 청크별 한국어 NLP 분석
            logger.info(f"🔤 2단계: 한국어 NLP 분석 시작")
            nlp_results = []
            
            for i, chunk in enumerate(chunks):
                try:
                    chunk_nlp = await korean_nlp_service.analyze_chunk_for_search(
                        chunk['content']
                    )
                    
                    if chunk_nlp.get("success"):
                        nlp_results.append(chunk_nlp)
                        result["processing_stats"]["nlp_processed"] += 1
                    else:
                        # 실패한 청크도 기본 구조로 추가
                        nlp_results.append({
                            "success": False,
                            "korean_keywords": [],
                            "named_entities": [],
                            "embedding": None,
                            "error": chunk_nlp.get("error", "분석 실패")
                        })
                        result["errors"].append(f"청크 {i} NLP 분석 실패")
                
                except Exception as e:
                    nlp_results.append({
                        "success": False,
                        "korean_keywords": [],
                        "named_entities": [],
                        "embedding": None,
                        "error": str(e)
                    })
                    result["errors"].append(f"청크 {i} NLP 처리 예외: {str(e)}")
            
            result["pipeline_steps"]["nlp_analysis"] = {
                "success": len(nlp_results) > 0,
                "processed_chunks": len(nlp_results),
                "successful_chunks": result["processing_stats"]["nlp_processed"]
            }
            
            logger.info(f"✅ NLP 분석 완료: {result['processing_stats']['nlp_processed']}/{len(chunks)}개 청크")
            
            # 3단계: 벡터 스토리지에 저장
            logger.info(f"🔮 3단계: 벡터 스토리지 저장 시작")
            storage_result = await self.vector_storage.store_processed_document(
                session=session,
                file_bss_info_sno=file_bss_info_sno,
                container_id=container_id,
                preprocessed_data=preprocessing_result,
                nlp_results=nlp_results
            )
            
            if storage_result.get("success"):
                result["pipeline_steps"]["vector_storage"] = {
                    "success": True,
                    "stored_chunks": storage_result.get("stored_chunks", 0),
                    "stored_vectors": storage_result.get("stored_vectors", 0),
                    "search_records": storage_result.get("search_records", 0)
                }
                result["processing_stats"]["vectors_stored"] = storage_result.get("stored_vectors", 0)
                
                logger.info(f"✅ 벡터 저장 완료: {storage_result.get('stored_vectors', 0)}개 벡터")
            else:
                result["errors"].append(f"벡터 저장 실패: {storage_result.get('error')}")
                logger.error(f"벡터 저장 실패: {storage_result.get('error')}")
            
            # 최종 성공 판단
            successful_steps = sum(1 for step in result["pipeline_steps"].values() if step.get("success"))
            result["success"] = successful_steps >= 2  # 전처리 + NLP 최소 성공
            result["rag_ready"] = successful_steps == 3  # 모든 단계 성공
            
            # 처리 시간 계산
            result["processing_stats"]["total_processing_time"] = time.time() - start_time
            
            if result["rag_ready"]:
                logger.info(f"🎉 RAG 파이프라인 완료: {file_name} - "
                           f"{result['processing_stats']['chunks_created']}개 청크, "
                           f"{result['processing_stats']['vectors_stored']}개 벡터 저장")
            else:
                logger.warning(f"⚠️ RAG 파이프라인 부분 완료: {file_name} - 일부 단계 실패")
            
            return result
            
        except Exception as e:
            result["errors"].append(f"파이프라인 예외: {str(e)}")
            result["processing_stats"]["total_processing_time"] = time.time() - start_time
            logger.error(f"RAG 파이프라인 실패: {file_name} - {str(e)}")
            return result
    
    async def test_pipeline_with_sample(self) -> Dict[str, Any]:
        """샘플 데이터로 파이프라인 테스트"""
        import tempfile
        import os
        
        test_text = """웅진씽크빅 지식관리시스템 테스트 문서
        
이 문서는 RAG 파이프라인 테스트를 위한 샘플입니다.

주요 기능:
1. 문서 전처리 및 청킹
2. 한국어 형태소 분석  
3. 벡터 임베딩 생성
4. 하이브리드 검색 저장

웅진씽크빅은 교육 전문 기업으로 AI 기반 솔루션을 개발하고 있습니다.
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(test_text)
            test_file_path = f.name
        
        try:
            from app.core.database import get_db
            async for session in get_db():
                result = await self.process_document_for_rag(
                    session=session,
                    file_path=test_file_path,
                    file_name="test_document.txt",
                    container_id="test_container",
                    user_emp_no="test_user",
                    file_bss_info_sno=999999  # 테스트용 ID
                )
                break
            
            return result
            
        finally:
            if os.path.exists(test_file_path):
                os.unlink(test_file_path)

# 전역 인스턴스
integrated_rag_pipeline_service = IntegratedRAGPipelineService()
