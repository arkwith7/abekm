"""
📄 WKMS 문서 서비스
===================

🎯 목적: 문서 CRUD 및 파일 시스템 관리를 담당하는 핵심 서비스

🔗 관계도:
```
v1/documents.py (API Layer)
    ↓ 호출
document_service.py (Business Logic)
    ↓ 데이터 접근
TbFileBssInfo, TbFileDtlInfo (Data Layer)
    ↓ 저장
PostgreSQL Database
```

📋 주요 기능:
- create_document_fro            # 🔄 2단계: 새로운 통합 RAG 파이프라인 실행
            try:
                logger.info(f"🔄 [DOC-SERVICE-DEBUG] 2단계 RAG 파이프라인 시작")pload(): 업로드된 파일의 문서 생성
- delete_document_by_id(): 문서 소프트 삭제
- get_document(): 문서 조회
- list_documents(): 문서 목록 조회

🔄 확장 계획:
- 문서 버전 관리
- 자동 백업 및 복원
- 문서 통계 분석
"""

import os
from pathlib import Path
import aiofiles
import logging
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

logger = logging.getLogger(__name__)
from app.models import TbFileBssInfo, TbFileDtlInfo
from app.schemas.chat import DocumentCreate, DocumentResponse
from app.services.core.embedding_service import EmbeddingService
from app.services.core.korean_nlp_service import KoreanNLPService
from app.services.document.storage.vector_embedding_service import VectorEmbeddingService
from app.services.auth.notification_service import NotificationService
from app.core.config import settings

try:
    from app.utils.storage_paths import classify_key_scheme as _classify_key_scheme
except Exception:
    _classify_key_scheme = lambda k: 'unknown'

class DocumentService:
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        try:
            self.embedding_service = EmbeddingService()
            self.korean_nlp_service = KoreanNLPService()
            self.vector_embedding_service = VectorEmbeddingService()
            self.notification_service = NotificationService()
        except Exception as e:
            logger.warning(f"DocumentService 초기화 중 일부 서비스 실패 (계속 진행): {e}")
            # 필수가 아닌 서비스들이므로 실패해도 계속 진행
            self.embedding_service = None
            self.korean_nlp_service = None
            self.vector_embedding_service = None
            self.notification_service = None
    
    async def create_document(self, document_data: DocumentCreate) -> DocumentResponse:
        """
        새 문서 생성 - tb_file_bss_info 테이블 사용
        """
        try:
            # 파일 기본 정보 생성
            file_bss_info = TbFileBssInfo(
                file_lgc_nm=document_data.title,
                file_psl_nm=document_data.file_path.split('/')[-1] if document_data.file_path else document_data.title,
                file_extsn=document_data.file_path.split('.')[-1] if '.' in document_data.file_path else 'txt',
                path=document_data.file_path,
                korean_metadata=document_data.metadata or {},
                drcy_sno=1,  # 기본 디렉토리
                created_by="system",
                last_modified_by="system"
            )
            
            self.db.add(file_bss_info)
            await self.db.flush()  # ID 생성을 위해 flush
            
            # 파일 상세 정보 생성
            file_dtl_info = TbFileDtlInfo(
                file_bss_info_sno=file_bss_info.file_bss_info_sno,
                content_text=document_data.content,
                document_title=document_data.title,
                metadata_json=document_data.metadata or {}
            )
            
            self.db.add(file_dtl_info)
            await self.db.commit()
            await self.db.refresh(file_bss_info)
            
            return DocumentResponse(
                id=str(file_bss_info.file_bss_info_sno),
                title=file_bss_info.file_lgc_nm,
                content=document_data.content,
                file_path=file_bss_info.path,
                metadata=file_bss_info.korean_metadata,
                created_at=file_bss_info.created_date,
                updated_at=file_bss_info.last_modified_date
            )
            
        except Exception as e:
            await self.db.rollback()
            raise e
    
    async def upload_and_process_file(self, file: UploadFile) -> DocumentResponse:
        """
        파일 업로드 및 처리
        """
        try:
            # 업로드 디렉토리 생성
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            # 파일 저장
            file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # 파일 내용 읽기 (텍스트 파일인 경우)
            file_content = ""
            if file.filename.endswith(('.txt', '.md', '.py', '.js', '.html', '.css')):
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    file_content = await f.read()
            else:
                # 바이너리 파일의 경우 파일명과 기본 정보만 저장
                file_content = f"파일명: {file.filename}\n파일 크기: {len(content)} bytes"
            
            # 문서 생성
            document_data = DocumentCreate(
                title=file.filename,
                content=file_content,
                file_path=file_path,
                metadata={
                    "original_filename": file.filename,
                    "file_size": len(content),
                    "content_type": file.content_type
                }
            )
            
            return await self.create_document(document_data)
            
        except Exception as e:
            # 업로드 실패 시 파일 삭제
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
            raise e
    
    async def get_document(self, document_id: str) -> Optional[DocumentResponse]:
        """
        문서 조회 - tb_file_bss_info 테이블 사용
        """
        try:
            stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == int(document_id))
            result = await self.db.execute(stmt)
            file_info = result.scalar_one_or_none()
            
            if not file_info:
                return None
            
            return DocumentResponse(
                id=str(file_info.file_bss_info_sno),
                title=file_info.file_lgc_nm,
                content="",  # 상세 내용은 별도 조회 필요
                file_path=file_info.path,
                metadata=file_info.korean_metadata or {},
                created_at=file_info.created_date,
                updated_at=file_info.last_modified_date
            )
            
        except Exception as e:
            logger.error(f"Error getting document: {e}")
            return None
    
    async def list_documents(self, skip: int = 0, limit: int = 100) -> List[DocumentResponse]:
        """
        문서 목록 조회 - tb_file_bss_info 테이블 사용
        """
        try:
            stmt = (select(TbFileBssInfo)
                   .where(TbFileBssInfo.del_yn == 'N')
                   .offset(skip)
                   .limit(limit)
                   .order_by(TbFileBssInfo.created_date.desc()))
            result = await self.db.execute(stmt)
            file_infos = result.scalars().all()
            
            return [
                DocumentResponse(
                    id=str(file_info.file_bss_info_sno),
                    title=file_info.file_lgc_nm,
                    content="",  # 목록에서는 내용 제외
                    file_path=file_info.path,
                    metadata=file_info.korean_metadata or {},
                    created_at=file_info.created_date,
                    updated_at=file_info.last_modified_date
                ) for file_info in file_infos
            ]
            
        except Exception as e:
            logger.error(f"Error listing documents: {e}")
            return []

    async def create_document_basic_info(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        file_extension: str,
        user_emp_no: str,
        container_id: str,
        session: AsyncSession,
        processing_status: str = 'pending',
        document_type: str = 'general',  # ✅ 추가
        processing_options: Optional[dict] = None  # ✅ 추가
    ) -> dict:
        """
        문서 기본 정보만 DB에 저장 (RAG 파이프라인 제외)
        비동기 백그라운드 처리를 위한 경량 버전
        
        Args:
            file_path: DB에 저장할 파일 경로
            file_name: 파일명
            file_size: 파일 크기
            file_extension: 파일 확장자
            user_emp_no: 사용자 사번
            container_id: 컨테이너 ID
            session: DB 세션
            processing_status: 처리 상태 (기본: 'pending')
            document_type: 문서 유형 (기본: 'general')
            processing_options: 문서 유형별 처리 옵션
        
        Returns:
            dict: {success, document_id, file_hash}
        """
        logger.info(f"📊 [DOC-SERVICE] 문서 기본 정보 저장: {file_name} (유형: {document_type})")
        
        if processing_options is None:
            processing_options = {}
        
        try:
            import hashlib
            
            # 간단한 해시 생성 (파일명 기반)
            file_hash = hashlib.md5(file_name.encode('utf-8')).hexdigest()
            
            # 파일 상세 정보 생성
            file_dtl_info = TbFileDtlInfo(
                sj=file_name,
                cn="",
                file_sz=file_size,
                authr=user_emp_no,
                created_by=user_emp_no,
                last_modified_by=user_emp_no
            )
            
            session.add(file_dtl_info)
            await session.flush()
            
            # 파일 기본 정보 생성
            file_bss_info = TbFileBssInfo(
                drcy_sno=1,
                file_dtl_info_sno=file_dtl_info.file_dtl_info_sno,
                file_lgc_nm=file_name,
                file_psl_nm=file_name,
                file_extsn=file_extension.lstrip('.'),
                path=file_path,
                knowledge_container_id=container_id,
                owner_emp_no=user_emp_no,
                created_by=user_emp_no,
                last_modified_by=user_emp_no,
                korean_metadata={"file_hash": file_hash, "file_size": file_size},
                processing_status=processing_status,
                processing_started_at=None,
                processing_completed_at=None,
                processing_error=None,
                document_type=document_type,  # ✅ 추가
                processing_options=processing_options  # ✅ 추가
            )
            
            session.add(file_bss_info)
            await session.flush()
            await session.commit()
            
            document_id = file_bss_info.file_bss_info_sno
            
            logger.info(f"✅ [DOC-SERVICE] 문서 기본 정보 저장 완료: doc_id={document_id}")
            
            return {
                "success": True,
                "document_id": document_id,
                "file_hash": file_hash
            }
            
        except Exception as e:
            logger.error(f"❌ [DOC-SERVICE] 문서 기본 정보 저장 실패: {e}")
            await session.rollback()
            return {
                "success": False,
                "error": str(e)
            }

    async def create_document_from_upload(
        self,
        file_path: str,  # DB에 저장할 경로 (S3 키 또는 로컬 경로)
        file_name: str,
        file_size: int,
        file_extension: str,
        user_emp_no: str,
        container_id: str,
        session: AsyncSession,
        local_source_path: Optional[str] = None,  # 해시 계산 등에 사용할 로컬 임시 파일 경로
        use_multimodal: bool = True,  # 멀티모달 파이프라인 사용 여부
        document_type: str = 'general',  # ✅ 추가
        processing_options: Optional[dict] = None  # ✅ 추가
    ) -> dict:
        """업로드된 파일로부터 문서 생성 + RAG 파이프라인 (멀티모달 지원)"""
        
        if processing_options is None:
            processing_options = {}
        
        logger.info(f"🚀 [DOC-SERVICE-DEBUG] 문서 생성 시작: {file_name} (유형: {document_type})")
        logger.info(f"🔎 [DOC-SERVICE-DEBUG] 경로 스킴 감지: {file_path} -> {_classify_key_scheme(file_path)}")
        logger.info(f"🎨 [DOC-SERVICE-DEBUG] 멀티모달 파이프라인: {'활성화' if use_multimodal else '비활성화'}")
        
        try:
            import hashlib
            import tempfile
            from app.core.config import settings as app_settings
            
            # 파일 해시 생성 (로컬 경로 우선, 없으면 S3에서 임시 다운로드)
            file_hash = None
            hash_path = None
            try:
                # 1) 명시적으로 전달된 로컬 소스 경로 사용
                if local_source_path and os.path.exists(local_source_path):
                    hash_path = local_source_path
                # 2) DB 경로가 로컬 경로로 존재하는 경우
                elif file_path and os.path.exists(file_path):
                    hash_path = file_path
                # 3) S3 모드이고 file_path가 S3 키로 보이는 경우: 임시 다운로드
                else:
                    storage_backend = getattr(app_settings, 'storage_backend', 'local')
                    looks_like_s3_key = bool(file_path) and not os.path.isabs(file_path) and '/' in file_path
                    if storage_backend == 's3' and looks_like_s3_key:
                        try:
                            from app.services.core.aws_service import S3Service
                            s3 = S3Service()
                            tmp_fd, tmp_path = tempfile.mkstemp(prefix='hash_', suffix=Path(file_path).suffix or '')
                            os.close(tmp_fd)
                            await s3.download_file(object_key=file_path, local_path=tmp_path)
                            hash_path = tmp_path
                        except Exception as _:
                            hash_path = None
                
                if hash_path and os.path.exists(hash_path):
                    with open(hash_path, 'rb') as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                else:
                    # 마지막 수단: 파일명 기반 해시
                    file_hash = hashlib.md5(file_name.encode('utf-8')).hexdigest()
            finally:
                # 임시 다운로드 파일 정리
                if 'tmp_path' in locals():
                    try:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    except Exception:
                        pass
            
            # 파일 상세 정보 생성
            file_dtl_info = TbFileDtlInfo(
                sj=file_name,
                cn="",
                file_sz=file_size,
                authr=user_emp_no,
                created_by=user_emp_no,
                last_modified_by=user_emp_no
            )
            
            session.add(file_dtl_info)
            await session.flush()
            
            # 파일 기본 정보 생성 (DB path는 입력받은 file_path 그대로 사용)
            file_bss_info = TbFileBssInfo(
                drcy_sno=1,
                file_dtl_info_sno=file_dtl_info.file_dtl_info_sno,
                file_lgc_nm=file_name,
                file_psl_nm=file_name,
                file_extsn=file_extension.lstrip('.'),
                path=file_path,
                knowledge_container_id=container_id,
                owner_emp_no=user_emp_no,
                created_by=user_emp_no,
                last_modified_by=user_emp_no,
                korean_metadata={"file_hash": file_hash, "file_size": file_size},
                document_type=document_type,  # ✅ 추가
                processing_options=processing_options  # ✅ 추가
            )
            
            session.add(file_bss_info)
            await session.flush()
            await session.commit()
            
            logger.info(f"✅ [DOC-SERVICE-DEBUG] 문서 생성 성공: 문서 ID {file_bss_info.file_bss_info_sno}")
            
            # ==========================================
            # RAG 파이프라인 실행 (멀티모달 vs 기존) - 실패 시 롤백
            # ==========================================
            multimodal_stats = None  # 초기화
            try:
                if use_multimodal:
                    # 🎨 멀티모달 파이프라인 실행
                    logger.info(f"🎨 [DOC-SERVICE-DEBUG] 멀티모달 파이프라인 시작")
                    from app.services.document.multimodal_document_service import multimodal_document_service

                    effective_provider = settings.get_current_llm_provider()

                    multimodal_result = await multimodal_document_service.process_document_multimodal(
                        file_path=local_source_path or file_path,
                        file_bss_info_sno=int(getattr(file_bss_info, 'file_bss_info_sno')),
                        container_id=container_id,
                        user_emp_no=user_emp_no,
                        session=session,
                        provider=effective_provider,
                        model_profile="default"
                    )
                    
                    if multimodal_result.get("success", False):
                        logger.info(f"✅ [DOC-SERVICE-DEBUG] 멀티모달 파이프라인 성공")
                        logger.info(f"   📊 추출: {multimodal_result.get('objects_count')}개 객체")
                        logger.info(f"   📦 청킹: {multimodal_result.get('chunks_count')}개 청크")
                        logger.info(f"   🔢 임베딩: {multimodal_result.get('embeddings_count')}개 벡터")
                    else:
                        error_msg = multimodal_result.get('error', '알 수 없는 오류')
                        logger.error(f"❌ [DOC-SERVICE-DEBUG] 멀티모달 파이프라인 실패: {error_msg}")
                        # 🚨 파이프라인 실패를 치명적 오류로 처리
                        await session.rollback()
                        return {
                            "success": False,
                            "error": f"멀티모달 처리 실패: {error_msg}"
                        }
                    
                    # 결과를 반환 객체에 포함시키기 위해 전체 스코프에 저장
                    stats_dict = multimodal_result.get("stats", {}) or {}
                    multimodal_stats = {
                        "enabled": True,
                        "success": multimodal_result.get("success", False),
                        "error": multimodal_result.get("error"),
                        "objects_count": multimodal_result.get("objects_count"),
                        "chunks_count": multimodal_result.get("chunks_count"),
                        "embeddings_count": multimodal_result.get("embeddings_count"),
                        "vector_dimension": stats_dict.get("vector_dimension"),
                        "elapsed_seconds": stats_dict.get("elapsed_seconds"),
                        "tables": stats_dict.get("tables", 0),
                        "images": stats_dict.get("images", 0),
                        "figures": stats_dict.get("figures", 0),
                    }
                        
                else:
                    # 📋 기존 파이프라인 실행
                    logger.info(f"📋 [DOC-SERVICE-DEBUG] 기존 RAG 파이프라인 시작")
                    from app.services.document.pipeline.integrated_document_pipeline_service import integrated_pipeline_service
                    
                    rag_result = await integrated_pipeline_service.process_document_for_rag(
                        file_path=local_source_path or file_path,
                        file_name=file_name,
                        container_id=container_id,
                        user_emp_no=user_emp_no,
                        file_bss_info_sno=int(getattr(file_bss_info, 'file_bss_info_sno'))
                    )
                    
                    if rag_result.get("success", False):
                        logger.info(f"✅ [DOC-SERVICE-DEBUG] 기존 RAG 파이프라인 성공")
                    else:
                        error_msg = rag_result.get('error', '알 수 없는 오류')
                        logger.error(f"❌ [DOC-SERVICE-DEBUG] 기존 RAG 파이프라인 실패: {error_msg}")
                        # 🚨 파이프라인 실패를 치명적 오류로 처리
                        await session.rollback()
                        return {
                            "success": False,
                            "error": f"RAG 처리 실패: {error_msg}"
                        }
                    
            except Exception as e:
                logger.error(f"💥 [DOC-SERVICE-DEBUG] RAG 파이프라인 예외: {str(e)}")
                # 🚨 예외를 치명적 오류로 처리
                await session.rollback()
                return {
                    "success": False,
                    "error": f"RAG 처리 중 예외 발생: {str(e)}"
                }
            
            return {
                "success": True,
                "document_id": file_bss_info.file_bss_info_sno,
                "detail_id": file_dtl_info.file_dtl_info_sno,
                "file_hash": file_hash,
                "message": "문서 업로드 처리 완료",
                "multimodal": multimodal_stats if use_multimodal else None
            }
            
        except Exception as e:
            await session.rollback()
            logger.error(f"💥 [DOC-SERVICE-DEBUG] 문서 생성 실패: {str(e)}")
            return {
                "success": False,
                "error": f"문서 생성 실패: {str(e)}"
            }
    
    async def delete_document_by_id(
        self,
        document_id: int,
        user_emp_no: str,
        session: AsyncSession
    ) -> dict:
        """
        문서 삭제 (소프트 삭제)
        """
        try:
            stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == document_id)
            result = await session.execute(stmt)
            file_info = result.scalar_one_or_none()
            
            if not file_info:
                return {
                    "success": False,
                    "error": "문서를 찾을 수 없습니다."
                }
            
            # 삭제 대상 경로 스킴 로깅 (raw 스킴 적용 여부 확인용)
            try:
                file_path_val_preview = getattr(file_info, 'path', '') or ''
                logger.info(f"🔎 [DOC-SERVICE-DEBUG] 삭제 대상 경로 스킴: {file_path_val_preview} -> {_classify_key_scheme(file_path_val_preview)}")
            except Exception:
                pass

            # 🔐 권한 확인 (통일된 permission_service 사용)
            owner_emp_no = getattr(file_info, 'owner_emp_no', None)
            creator_emp_no = getattr(file_info, 'created_by', None)
            container_id = getattr(file_info, 'knowledge_container_id', None)
            
            if container_id:
                from app.services.auth.permission_service import permission_service
                can_delete, permission_message = await permission_service.check_delete_permission(
                    user_emp_no=user_emp_no,
                    container_id=container_id,
                    owner_emp_no=owner_emp_no,
                    created_by=creator_emp_no
                )
                if not can_delete:
                    logger.warning(
                        f"문서 삭제 권한 없음 - 사용자: {user_emp_no}, 문서: {document_id}, 메시지: {permission_message}"
                    )
                    return {
                        "success": False,
                        "error": f"문서 삭제 권한이 없습니다: {permission_message}"
                    }
            else:
                # 컨테이너 정보가 없는 경우 소유자/생성자만 삭제 가능
                if (owner_emp_no or creator_emp_no) and user_emp_no not in {owner_emp_no, creator_emp_no}:
                    return {
                        "success": False,
                        "error": "문서 삭제 권한이 없습니다."
                    }
            # 1. 메인 파일 정보 소프트 삭제 (선 커밋, 후 클린업 전략)
            setattr(file_info, 'del_yn', 'Y')
            setattr(file_info, 'last_modified_by', user_emp_no)
            
            # 2. 파일 상세 정보 소프트 삭제
            if getattr(file_info, 'file_dtl_info_sno', None):
                stmt_dtl = (update(TbFileDtlInfo)
                           .where(TbFileDtlInfo.file_dtl_info_sno == file_info.file_dtl_info_sno)
                           .values(del_yn='Y', last_modified_by=user_emp_no))
                await session.execute(stmt_dtl)
            
            await session.commit()
            
            # 3. 물리적 파일/오브젝트 삭제 (옵션)
            file_path_val = getattr(file_info, 'path', '') or ''
            try:
                from app.core.config import settings as app_settings
                storage_backend = getattr(app_settings, 'storage_backend', 'local')
            except Exception:
                storage_backend = 'local'

            if storage_backend == 's3' and file_path_val and ('/' in file_path_val) and not os.path.isabs(file_path_val):
                # S3 키로 판단 -> 오브젝트 삭제
                try:
                    from app.services.core.aws_service import S3Service
                    s3 = S3Service()
                    await s3.delete_file(file_path_val)
                    logger.info(f"S3 오브젝트 삭제 완료: {file_path_val}")
                except Exception as e:
                    logger.warning(f"S3 오브젝트 삭제 실패: {e}")
            elif storage_backend == 'azure_blob' and file_path_val and ('/' in file_path_val) and not os.path.isabs(file_path_val):
                try:
                    from app.services.core.azure_blob_service import get_azure_blob_service
                    azure = get_azure_blob_service()
                    # 기본 용도는 raw, prefix에 따라 재설정
                    purpose = 'raw'
                    blob_path = file_path_val
                    if file_path_val.startswith(('raw/', 'intermediate/', 'derived/')):
                        maybe_purpose, _, remainder = file_path_val.partition('/')
                        if maybe_purpose and remainder:
                            purpose = maybe_purpose
                            blob_path = remainder
                    if azure.delete_blob(blob_path, purpose=purpose):
                        logger.info(f"Azure Blob 삭제 완료: {purpose}/{blob_path}")
                    else:
                        logger.warning(f"Azure Blob 삭제 불가 또는 미존재: {purpose}/{blob_path}")
                except Exception as e:
                    logger.warning(f"Azure Blob 삭제 실패: {e}")
            else:
                # 로컬 파일 삭제
                if file_path_val and os.path.exists(file_path_val):
                    try:
                        os.remove(file_path_val)
                        logger.info(f"물리적 파일 삭제 완료: {file_path_val}")
                    except Exception as e:
                        logger.warning(f"물리적 파일 삭제 실패: {e}")

            # 4. PDF 캐시 삭제
            try:
                cache_dir = Path("backend/uploads/pdf_cache")
                patterns = [f"{document_id}_*.pdf"]
                for pattern in patterns:
                    for p in cache_dir.glob(pattern):
                        try:
                            p.unlink()
                            logger.info(f"PDF 캐시 삭제: {p}")
                        except Exception as e:
                            logger.warning(f"PDF 캐시 삭제 실패: {e}")
            except Exception:
                pass

            # 5. 연관 데이터 정리 (벡터 청크 / 검색 인덱스) - 메인 커밋 이후 분리 트랜잭션/연결로 수행
            try:
                cleanup_ok = await self._cleanup_vector_and_index_artifacts_standalone(
                    document_id=document_id,
                    user_emp_no=user_emp_no,
                )
                if not cleanup_ok:
                    logger.warning(
                        "연관 데이터 정리 실패 - 문서 ID: %s (향후 배치 정리 필요)",
                        document_id
                    )
            except Exception as e:
                # 클린업 실패는 치명적이지 않으므로 경고만 남김
                logger.warning(
                    "연관 데이터 정리 중 예외 - 문서 ID: %s, 오류: %s (향후 배치 정리)",
                    document_id,
                    e
                )
            
            logger.info(f"문서 삭제 완료 - ID: {document_id}, 사용자: {user_emp_no}")
            
            # 🔢 컨테이너의 document_count 업데이트
            if container_id:
                try:
                    from app.services.auth.container_service import ContainerService
                    container_svc = ContainerService(session)
                    updated_count = await container_svc.update_container_document_count(container_id)
                    logger.info(f"📊 컨테이너 문서 개수 업데이트: {container_id} -> {updated_count}개")
                except Exception as count_error:
                    logger.warning(f"⚠️ 컨테이너 문서 개수 업데이트 실패 (무시): {count_error}")
            
            return {
                "success": True,
                "message": "문서가 성공적으로 삭제되었습니다."
            }
            
        except Exception as e:
            await session.rollback()
            logger.exception(f"문서 삭제 처리 중 예외 발생 - 문서 ID: {document_id}, 사용자: {user_emp_no}")
            return {
                "success": False,
                "error": f"문서 삭제 실패: {str(e)}"
            }

    async def _cleanup_vector_and_index_artifacts(
        self,
        document_id: int,
        user_emp_no: str,
        session: AsyncSession  # 메인 세션을 받아서 사용
    ) -> bool:
        """
        Delete or soft-delete vector/search artifacts using the provided session.
        메인 세션을 공유하여 connection 충돌 방지
        """
        try:
            from app.models import VsDocContentsChunks
            from app.models.document.unified_search_models import TbDocumentSearchIndex
            
            # 벡터 청크 소프트 삭제
            stmt_chunks = (update(VsDocContentsChunks)
                          .where(VsDocContentsChunks.file_bss_info_sno == document_id)
                          .values(del_yn='Y', last_modified_by=user_emp_no))
            await session.execute(stmt_chunks)

            # 검색 인덱스 삭제
            stmt_search = delete(TbDocumentSearchIndex).where(
                TbDocumentSearchIndex.file_bss_info_sno == document_id
            )
            await session.execute(stmt_search)
            
            logger.info(f"✅ [CLEANUP-DEBUG] 문서 연관 데이터 정리 성공: doc_id={document_id}")
            return True
            
        except Exception as cleanup_error:
            logger.error(
                "❌ [CLEANUP-DEBUG] 문서 연관 데이터 정리 실패: doc_id=%s, 오류=%s",
                document_id,
                cleanup_error
            )
            return False

    async def _cleanup_vector_and_index_artifacts_standalone(
        self,
        document_id: int,
        user_emp_no: str,
    ) -> bool:
        """
        별도의 짧은-lived 세션을 사용하여 연관 데이터 정리를 수행.
        - 메인 삭제 커밋 이후 호출
        - 자체 트랜잭션과 커밋/롤백 처리
        - 일시적인 연결 문제에 대비하여 소규모 재시도
        """
        from asyncio import sleep
        from app.core.database import get_async_session_local
        from app.models import VsDocContentsChunks
        from app.models.document.unified_search_models import TbDocumentSearchIndex
        
        max_attempts = 3
        delay = 2.0  # 0.5 → 2.0 (초기 대기 시간 증가)
        
        for attempt in range(1, max_attempts + 1):
            try:
                # 매번 새로운 connection factory 생성
                async_session_factory = get_async_session_local()
                async with async_session_factory() as cleanup_session:
                    try:
                        # EXPLICIT transaction control
                        async with cleanup_session.begin():
                            stmt_chunks = (update(VsDocContentsChunks)
                                           .where(VsDocContentsChunks.file_bss_info_sno == document_id)
                                           .values(del_yn='Y', last_modified_by=user_emp_no))
                            await cleanup_session.execute(stmt_chunks)

                            stmt_search = delete(TbDocumentSearchIndex).where(
                                TbDocumentSearchIndex.file_bss_info_sno == document_id
                            )
                            await cleanup_session.execute(stmt_search)
                        
                        # begin() context 종료 시 자동 commit
                        logger.info(f"✅ [CLEANUP-DEBUG] (standalone) 문서 연관 데이터 정리 성공: doc_id={document_id}")
                        return True
                        
                    except Exception as inner_e:
                        # begin() context는 자동 rollback하지만 명시적 로깅
                        logger.warning(
                            "[CLEANUP-DEBUG] (standalone) 시도 %s/%s 실패 - doc_id=%s: %s",
                            attempt, max_attempts, document_id, inner_e
                        )
                        raise  # 외부 except로 전파
                        
            except Exception as e:
                if attempt < max_attempts:
                    logger.info(f"🔄 [CLEANUP-DEBUG] {delay}초 대기 후 재시도...")
                    await sleep(delay)
                    delay = min(delay * 2.5, 10.0)  # 2초 → 5초 → 10초
                else:
                    logger.error(
                        "❌ [CLEANUP-DEBUG] (standalone) 최종 실패 - doc_id=%s, 오류=%s",
                        document_id, e
                    )
                    return False
        
        return False


# 싱글톤 인스턴스
document_service = DocumentService(None)  # 세션은 사용시 전달
