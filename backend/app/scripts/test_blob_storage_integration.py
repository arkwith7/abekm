#!/usr/bin/env python3
"""
Blob Storage 통합 테스트

역할:
- Azure Blob Storage 연결 테스트
- 문서 처리                        try:
                            self.azure_blob.client.create_container(container_name)
                            logger.info(f"✅ 컴테이너 생성 성공: {container_name}")프라인에서 생성되는 파일들이 Blob에 저장되는지 확인
- raw, intermediate, derived 컨테이너별 저장 상태 점검
- 추출된 텍스트, 이미지, 표 등의 저장 상태 검증
"""
import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# 경로 설정
sys.path.append('/home/wjadmin/Dev/InsightBridge/backend')

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_async_session_local
from app.core.config import settings
from app.services.core.azure_blob_service import get_azure_blob_service, AzureBlobService
from app.services.document.multimodal_document_service import multimodal_document_service
from app.services.document.storage.file_storage_service import FileStorageService

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlobStorageIntegrationTester:
    def __init__(self):
        """Blob Storage 통합 테스터 초기화"""
        self.azure_blob: Optional[AzureBlobService] = None
        self.file_storage: Optional[FileStorageService] = None
        
    async def initialize(self):
        """서비스 초기화"""
        try:
            # Azure Blob Service 초기화
            if settings.storage_backend == 'azure_blob':
                self.azure_blob = get_azure_blob_service()
                logger.info(f"✅ Azure Blob Service 초기화 성공 - Account: {self.azure_blob.account_name}")
            else:
                logger.warning(f"⚠️ 현재 스토리지 백엔드: {settings.storage_backend} (azure_blob가 아님)")
                
            # File Storage Service 초기화
            self.file_storage = FileStorageService()
            logger.info("✅ File Storage Service 초기화 성공")
            
        except Exception as e:
            logger.error(f"❌ 초기화 실패: {e}")
            raise

    async def test_blob_connectivity(self) -> bool:
        """Blob Storage 연결 테스트"""
        logger.info("🔗 Azure Blob Storage 연결 테스트 시작...")
        
        if not self.azure_blob:
            logger.warning("⚠️ Azure Blob Service가 초기화되지 않음")
            return False
            
        try:
            # 컨테이너 목록 조회
            containers = []
            for container in self.azure_blob.client.list_containers():
                containers.append(container.name)
                
            logger.info(f"✅ 연결 성공 - 발견된 컨테이너: {containers}")
            
            # 필수 컨테이너 확인
            required_containers = [
                settings.azure_blob_container_raw,
                settings.azure_blob_container_intermediate, 
                settings.azure_blob_container_derived
            ]
            
            missing_containers = [c for c in required_containers if c not in containers]
            if missing_containers:
                logger.warning(f"⚠️ 누락된 컨테이너: {missing_containers}")
                
                # 자동 생성 옵션이 있으면 생성 시도
                if settings.azure_blob_enable_auto_container:
                    for container_name in missing_containers:
                        try:
                            self.azure_blob.client.create_container(container_name)
                            logger.info(f"✅ 컨테이너 생성 성공: {container_name}")
                        except Exception as e:
                            logger.error(f"❌ 컨테이너 생성 실패 {container_name}: {e}")
                            
            return True
            
        except Exception as e:
            logger.error(f"❌ Blob Storage 연결 실패: {e}")
            return False

    async def list_blob_contents(self, container_name: str, prefix: str = "", max_results: int = 10) -> List[Dict[str, Any]]:
        """Blob 컨테이너 내용 조회"""
        if not self.azure_blob:
            return []
            
        try:
            container_client = self.azure_blob.client.get_container_client(container_name)
            blobs = []
            
            for blob in container_client.list_blobs(name_starts_with=prefix):
                blob_info = {
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified,
                    'content_type': getattr(blob, 'content_type', None),
                    'metadata': getattr(blob, 'metadata', {})
                }
                blobs.append(blob_info)
                
                if len(blobs) >= max_results:
                    break
                    
            return blobs
            
        except Exception as e:
            logger.error(f"❌ Blob 목록 조회 실패 - {container_name}: {e}")
            return []

    async def test_file_upload_and_processing(self) -> Dict[str, Any]:
        """파일 업로드 및 처리 후 Blob 저장 상태 테스트"""
        logger.info("📁 파일 업로드 및 처리 테스트 시작...")
        
        # 테스트용 샘플 파일 생성
        test_content = """
        블롭 스토리지 테스트 문서
        
        이 문서는 Azure Blob Storage에 올바르게 저장되는지 테스트하기 위한 샘플 문서입니다.
        
        주요 기능:
        1. 텍스트 추출
        2. 메타데이터 저장
        3. 중간 결과물 저장
        4. 최종 결과물 저장
        
        테스트 시간: {test_time}
        """.format(test_time=datetime.now())
        
        # 임시 파일 생성
        test_file_path = "/tmp/blob_test_document.txt"
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
            
        try:
            # DB에서 테스트할 파일 정보 가져오기 (정확한 컬럼명 사용)
            from sqlalchemy import text
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                result = await session.execute(
                    text("SELECT file_bss_info_sno, file_lgc_nm, file_psl_nm FROM tb_file_bss_info WHERE del_yn = 'N' LIMIT 1")
                )
                file_row = result.fetchone()
                
                if not file_row:
                    logger.error("❌ 테스트할 파일을 찾을 수 없습니다")
                    return {"success": False, "error": "No test file found"}
                
                file_id = file_row[0]
                file_logical_name = file_row[1] 
                file_physical_name = file_row[2]
                
                logger.info(f"📄 테스트 파일: ID={file_id}, 이름={file_logical_name}")
                
                # 처리 전 Blob 상태 확인
                before_state = await self.get_blob_storage_state()
                logger.info(f"📊 처리 전 Blob 상태: {before_state}")
                
                # 멀티모달 파이프라인 실행
                logger.info("🎨 멀티모달 파이프라인 실행...")
                result = await multimodal_document_service.process_document_multimodal(
                    file_path=test_file_path,
                    file_bss_info_sno=file_id,
                    container_id="test-container",
                    user_emp_no="test-user",
                    session=session
                )
                
                if result.get("success"):
                    logger.info(f"✅ 파이프라인 성공: {result}")
                    
                    # 처리 후 Blob 상태 확인
                    after_state = await self.get_blob_storage_state()
                    logger.info(f"📊 처리 후 Blob 상태: {after_state}")
                    
                    # 상태 비교
                    blob_changes = self.compare_blob_states(before_state, after_state)
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "file_name": file_logical_name,
                        "pipeline_result": result,
                        "blob_before": before_state,
                        "blob_after": after_state,
                        "blob_changes": blob_changes
                    }
                else:
                    logger.error(f"❌ 파이프라인 실패: {result}")
                    return {"success": False, "pipeline_result": result}
                    
        except Exception as e:
            logger.error(f"❌ 파일 처리 테스트 실패: {e}")
            return {"success": False, "error": str(e)}
        
        finally:
            # 임시 파일 정리
            if os.path.exists(test_file_path):
                os.remove(test_file_path)

    async def get_blob_storage_state(self) -> Dict[str, Any]:
        """현재 Blob Storage 상태 조회"""
        state = {
            "raw": {"count": 0, "total_size": 0, "files": []},
            "intermediate": {"count": 0, "total_size": 0, "files": []},
            "derived": {"count": 0, "total_size": 0, "files": []}
        }
        
        if not self.azure_blob:
            return state
            
        try:
            # Raw 컨테이너
            raw_blobs = await self.list_blob_contents(settings.azure_blob_container_raw, max_results=50)
            state["raw"]["count"] = len(raw_blobs)
            state["raw"]["total_size"] = sum(blob.get("size", 0) for blob in raw_blobs)
            state["raw"]["files"] = [blob["name"] for blob in raw_blobs]
            
            # Intermediate 컨테이너
            intermediate_blobs = await self.list_blob_contents(settings.azure_blob_container_intermediate, max_results=50)
            state["intermediate"]["count"] = len(intermediate_blobs)
            state["intermediate"]["total_size"] = sum(blob.get("size", 0) for blob in intermediate_blobs)  
            state["intermediate"]["files"] = [blob["name"] for blob in intermediate_blobs]
            
            # Derived 컨테이너
            derived_blobs = await self.list_blob_contents(settings.azure_blob_container_derived, max_results=50)
            state["derived"]["count"] = len(derived_blobs)
            state["derived"]["total_size"] = sum(blob.get("size", 0) for blob in derived_blobs)
            state["derived"]["files"] = [blob["name"] for blob in derived_blobs]
            
        except Exception as e:
            logger.error(f"❌ Blob 상태 조회 실패: {e}")
            
        return state

    def compare_blob_states(self, before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
        """Blob 상태 변화 비교"""
        changes = {}
        
        for container in ["raw", "intermediate", "derived"]:
            before_count = before.get(container, {}).get("count", 0)
            after_count = after.get(container, {}).get("count", 0)
            before_size = before.get(container, {}).get("total_size", 0)
            after_size = after.get(container, {}).get("total_size", 0)
            
            before_files = set(before.get(container, {}).get("files", []))
            after_files = set(after.get(container, {}).get("files", []))
            new_files = after_files - before_files
            
            changes[container] = {
                "count_change": after_count - before_count,
                "size_change": after_size - before_size,
                "new_files": list(new_files)
            }
            
        return changes

    async def test_specific_file_extraction_results(self, file_id: int) -> Dict[str, Any]:
        """특정 파일의 추출 결과물들이 Blob에 저장되었는지 확인"""
        logger.info(f"🔍 파일 {file_id}의 추출 결과물 Blob 저장 상태 확인...")
        
        try:
            from sqlalchemy import text
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                # 추출 세션 정보 조회
                result = await session.execute(
                    text("""
                    SELECT es.extraction_session_id, es.file_bss_info_sno, es.status,
                           COUNT(eo.extraction_object_id) as object_count
                    FROM extraction_session es
                    LEFT JOIN extraction_object eo ON es.extraction_session_id = eo.extraction_session_id
                    WHERE es.file_bss_info_sno = :file_id
                    GROUP BY es.extraction_session_id, es.file_bss_info_sno, es.status
                    ORDER BY es.extraction_session_id DESC
                    LIMIT 1
                    """),
                    {"file_id": file_id}
                )
                session_row = result.fetchone()
                
                if not session_row:
                    return {"success": False, "error": "추출 세션을 찾을 수 없음"}
                
                extraction_session_id = session_row[0]
                object_count = session_row[3]
                
                logger.info(f"📊 추출 세션 {extraction_session_id}: {object_count}개 객체")
                
                # 추출된 객체들 조회
                objects_result = await session.execute(
                    text("""
                    SELECT object_type, content_length, metadata, storage_path
                    FROM extraction_object 
                    WHERE extraction_session_id = :session_id
                    """),
                    {"session_id": extraction_session_id}
                )
                objects = objects_result.fetchall()
                
                # Blob 저장 상태 확인
                blob_status = {}
                for obj in objects:
                    obj_type = obj[0]
                    storage_path = obj[3]
                    
                    if storage_path:
                        # Blob에서 파일 존재 확인
                        exists = await self.check_blob_exists(storage_path)
                        blob_status[f"{obj_type}_{storage_path}"] = {
                            "exists": exists,
                            "storage_path": storage_path
                        }
                
                return {
                    "success": True,
                    "extraction_session_id": extraction_session_id,
                    "object_count": object_count,
                    "objects": [
                        {
                            "type": obj[0],
                            "content_length": obj[1], 
                            "metadata": obj[2],
                            "storage_path": obj[3]
                        } for obj in objects
                    ],
                    "blob_status": blob_status
                }
                
        except Exception as e:
            logger.error(f"❌ 추출 결과물 확인 실패: {e}")
            return {"success": False, "error": str(e)}

    async def check_blob_exists(self, blob_path: str) -> bool:
        """특정 Blob 파일이 존재하는지 확인"""
        if not self.azure_blob or not blob_path:
            return False
            
        try:
            # 경로에서 컨테이너와 blob 이름 분리
            parts = blob_path.strip('/').split('/', 1)
            if len(parts) != 2:
                return False
                
            container_name, blob_name = parts
            blob_client = self.azure_blob.client.get_blob_client(
                container=container_name, 
                blob=blob_name
            )
            
            # 존재 여부 확인
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"❌ Blob 존재 확인 실패 {blob_path}: {e}")
            return False

    async def generate_blob_report(self) -> Dict[str, Any]:
        """종합적인 Blob Storage 상태 리포트 생성"""
        logger.info("📋 Blob Storage 종합 리포트 생성...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "storage_backend": settings.storage_backend,
            "connectivity": False,
            "containers": {},
            "summary": {}
        }
        
        # 연결 테스트
        report["connectivity"] = await self.test_blob_connectivity()
        if not report["connectivity"]:
            return report
            
        # 각 컨테이너별 상세 정보
        containers = [
            ("raw", settings.azure_blob_container_raw),
            ("intermediate", settings.azure_blob_container_intermediate), 
            ("derived", settings.azure_blob_container_derived)
        ]
        
        total_files = 0
        total_size = 0
        
        for container_type, container_name in containers:
            blobs = await self.list_blob_contents(container_name, max_results=100)
            container_size = sum(blob.get("size", 0) for blob in blobs)
            
            report["containers"][container_type] = {
                "name": container_name,
                "file_count": len(blobs),
                "total_size": container_size,
                "size_mb": round(container_size / 1024 / 1024, 2),
                "recent_files": [
                    {
                        "name": blob["name"],
                        "size": blob["size"],
                        "last_modified": blob["last_modified"].isoformat() if blob["last_modified"] else None
                    }
                    for blob in sorted(blobs, key=lambda x: x.get("last_modified", datetime.min), reverse=True)[:5]
                ]
            }
            
            total_files += len(blobs)
            total_size += container_size
            
        report["summary"] = {
            "total_files": total_files,
            "total_size": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2)
        }
        
        return report

async def main():
    """메인 테스트 실행"""
    logger.info("🚀 Azure Blob Storage 통합 테스트 시작")
    
    tester = BlobStorageIntegrationTester()
    
    try:
        # 초기화
        await tester.initialize()
        
        # 1. 연결 테스트
        logger.info("\n" + "="*50)
        logger.info("1️⃣ Blob Storage 연결 테스트")
        logger.info("="*50)
        connectivity = await tester.test_blob_connectivity()
        
        if not connectivity:
            logger.error("❌ Blob Storage 연결 실패 - 테스트 중단")
            return
            
        # 2. 현재 상태 확인
        logger.info("\n" + "="*50) 
        logger.info("2️⃣ 현재 Blob Storage 상태 확인")
        logger.info("="*50)
        current_state = await tester.get_blob_storage_state()
        logger.info(f"📊 현재 상태:")
        for container, info in current_state.items():
            logger.info(f"  {container}: {info['count']}개 파일, {info.get('total_size', 0):,}바이트")
            
        # 3. 파일 처리 및 저장 테스트
        logger.info("\n" + "="*50)
        logger.info("3️⃣ 파일 처리 및 Blob 저장 테스트")
        logger.info("="*50)
        processing_result = await tester.test_file_upload_and_processing()
        
        if processing_result.get("success"):
            logger.info("✅ 파일 처리 및 저장 테스트 성공")
            changes = processing_result.get("blob_changes", {})
            for container, change in changes.items():
                if change["count_change"] > 0:
                    logger.info(f"  📁 {container}: +{change['count_change']}개 파일, +{change['size_change']:,}바이트")
                    if change["new_files"]:
                        logger.info(f"    새 파일: {change['new_files'][:3]}")
        else:
            logger.error(f"❌ 파일 처리 테스트 실패: {processing_result.get('error', 'Unknown error')}")
            
        # 4. 종합 리포트
        logger.info("\n" + "="*50)
        logger.info("4️⃣ 종합 리포트 생성")
        logger.info("="*50)
        report = await tester.generate_blob_report()
        
        logger.info("📋 === Azure Blob Storage 통합 테스트 리포트 ===")
        logger.info(f"🕐 테스트 시간: {report['timestamp']}")
        logger.info(f"🔗 연결 상태: {'✅ 성공' if report['connectivity'] else '❌ 실패'}")
        logger.info(f"📊 전체 통계: {report['summary']['total_files']}개 파일, {report['summary']['total_size_mb']}MB")
        
        for container_type, container_info in report["containers"].items():
            logger.info(f"📁 {container_type} ({container_info['name']}): "
                       f"{container_info['file_count']}개 파일, {container_info['size_mb']}MB")
            
        logger.info("\n🎉 Blob Storage 통합 테스트 완료!")
        
    except Exception as e:
        logger.error(f"❌ 테스트 실행 중 오류: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())