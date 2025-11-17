#!/usr/bin/env python3
"""
📊 문서 추출 품질 테스트 스크립트
====================================

목적: 실제 텍스트, 표, 그림이 제대로 추출되는지 확인
- Blob Storage에 저장된 추출 결과 내용 분석
- 실제 파일로 멀티모달 파이프라인 테스트
- 추출된 객체들의 상세 내용 검토
"""

import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import get_async_session_local
from app.services.document.multimodal_document_service import multimodal_document_service

# Azure Blob Storage 서비스
try:
    from app.services.core.azure_blob_service import get_azure_blob_service
except ImportError:
    get_azure_blob_service = None

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExtractionQualityTester:
    """추출 품질 테스터"""
    
    def __init__(self):
        self.azure_blob = None
        
    async def initialize(self):
        """서비스 초기화"""
        if settings.storage_backend == 'azure_blob' and get_azure_blob_service:
            self.azure_blob = get_azure_blob_service()
            logger.info(f"✅ Azure Blob Service 초기화: {self.azure_blob.account_name}")
        else:
            logger.error("❌ Azure Blob Storage가 설정되지 않음")
            
    async def analyze_stored_extraction_results(self) -> Dict[str, Any]:
        """저장된 추출 결과 분석"""
        if not self.azure_blob:
            return {"error": "Azure Blob Service not available"}
            
        logger.info("🔍 저장된 추출 결과 분석 시작...")
        
        # Intermediate 컨테이너에서 추출 결과 찾기
        try:
            intermediate_blobs = await self.list_blob_contents('intermediate', prefix='multimodal/')
            logger.info(f"📁 발견된 중간 결과: {len(intermediate_blobs)}개")
            
            analysis_results = []
            
            for blob in intermediate_blobs:
                blob_name = blob['name']
                logger.info(f"📄 분석 중: {blob_name}")
                
                # 추출 메타데이터 분석
                if 'extraction_metadata.json' in blob_name:
                    content = await self.download_blob_content('intermediate', blob_name)
                    if content:
                        metadata = json.loads(content)
                        analysis_results.append({
                            'type': 'extraction_metadata',
                            'file': blob_name,
                            'content': metadata,
                            'summary': {
                                'objects_count': metadata.get('extracted_objects_count', 0),
                                'pages_detected': metadata.get('pages_detected', 0),
                                'provider': metadata.get('provider', 'unknown')
                            }
                        })
                        
                # 전체 텍스트 분석
                elif 'extraction_full_text.txt' in blob_name:
                    content = await self.download_blob_content('intermediate', blob_name)
                    if content:
                        analysis_results.append({
                            'type': 'full_text',
                            'file': blob_name,
                            'content': content[:500] + "..." if len(content) > 500 else content,
                            'summary': {
                                'char_count': len(content),
                                'line_count': len(content.split('\n')),
                                'has_korean': '한' in content or 'ㄱ' <= max(content, default='') <= '힣'
                            }
                        })
                        
                # 객체별 상세 분석
                elif '/objects/' in blob_name:
                    content = await self.download_blob_content('intermediate', blob_name)
                    if content:
                        if blob_name.endswith('.txt'):
                            # 텍스트 블록
                            analysis_results.append({
                                'type': 'text_object',
                                'file': blob_name,
                                'content': content[:200] + "..." if len(content) > 200 else content,
                                'summary': {
                                    'char_count': len(content),
                                    'object_type': 'TEXT_BLOCK'
                                }
                            })
                        elif blob_name.endswith('.json'):
                            # 표 또는 이미지 객체
                            obj_data = json.loads(content)
                            analysis_results.append({
                                'type': 'structured_object',
                                'file': blob_name,
                                'content': obj_data,
                                'summary': {
                                    'object_type': obj_data.get('object_type', 'unknown'),
                                    'page_no': obj_data.get('page_no'),
                                    'has_bbox': bool(obj_data.get('bbox')),
                                    'has_structure': bool(obj_data.get('structure_json'))
                                }
                            })
            
            return {
                'success': True,
                'total_files': len(intermediate_blobs),
                'analysis_results': analysis_results,
                'summary': self._generate_extraction_summary(analysis_results)
            }
            
        except Exception as e:
            logger.error(f"❌ 분석 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def test_with_real_document(self, file_path: str) -> Dict[str, Any]:
        """실제 문서로 추출 테스트"""
        if not os.path.exists(file_path):
            return {'success': False, 'error': f'파일을 찾을 수 없음: {file_path}'}
            
        logger.info(f"📄 실제 문서 테스트: {file_path}")
        
        try:
            # 가상의 file_bss_info_sno 사용 (테스트용)
            test_file_id = 9999
            
            # DB 세션 생성 (테스트용)
            from app.core.database import get_async_session_local
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                result = await multimodal_document_service.process_document_multimodal(
                    file_path=file_path,
                    file_bss_info_sno=test_file_id,
                    container_id="TEST_CONTAINER",
                    user_emp_no="test_user",
                    session=session,
                    provider="azure",
                    model_profile="default"
                )
            
            logger.info(f"✅ 처리 완료: {result.get('success', False)}")
            
            if result.get('success'):
                # 저장된 결과 분석
                analysis = await self.analyze_extraction_for_file(test_file_id)
                result['detailed_analysis'] = analysis
                
            return result
            
        except Exception as e:
            logger.error(f"❌ 문서 처리 실패: {e}")
            return {'success': False, 'error': str(e)}
    
    async def analyze_extraction_for_file(self, file_id: int) -> Dict[str, Any]:
        """특정 파일의 추출 결과 분석"""
        if not self.azure_blob:
            return {'error': 'Azure Blob not available'}
            
        prefix = f"multimodal/{file_id}/"
        
        # Intermediate 결과 분석
        intermediate_analysis = await self._analyze_container_for_prefix('intermediate', prefix)
        # Derived 결과 분석  
        derived_analysis = await self._analyze_container_for_prefix('derived', prefix)
        
        return {
            'file_id': file_id,
            'intermediate': intermediate_analysis,
            'derived': derived_analysis,
            'extraction_quality': self._assess_extraction_quality(intermediate_analysis, derived_analysis)
        }
    
    async def _analyze_container_for_prefix(self, container_type: str, prefix: str) -> Dict[str, Any]:
        """특정 컨테이너와 prefix에서 결과 분석"""
        container_name = getattr(settings, f'azure_blob_container_{container_type}')
        blobs = await self.list_blob_contents(container_type, prefix=prefix)
        
        analysis = {
            'file_count': len(blobs),
            'files': []
        }
        
        for blob in blobs:
            content = await self.download_blob_content(container_type, blob['name'])
            file_analysis = {
                'name': blob['name'],
                'size': blob['size']
            }
            
            if content:
                if blob['name'].endswith('.json'):
                    try:
                        data = json.loads(content)
                        file_analysis['type'] = 'json'
                        file_analysis['keys'] = list(data.keys()) if isinstance(data, dict) else None
                        file_analysis['sample'] = str(data)[:200] + "..." if len(str(data)) > 200 else str(data)
                    except:
                        file_analysis['type'] = 'invalid_json'
                elif blob['name'].endswith('.txt'):
                    file_analysis['type'] = 'text'
                    file_analysis['char_count'] = len(content)
                    file_analysis['sample'] = content[:200] + "..." if len(content) > 200 else content
                    
            analysis['files'].append(file_analysis)
            
        return analysis
    
    def _assess_extraction_quality(self, intermediate: Dict, derived: Dict) -> Dict[str, Any]:
        """추출 품질 평가"""
        quality = {
            'text_extraction': False,
            'structured_objects': False,
            'chunking': False,
            'embedding': False,
            'overall_score': 0
        }
        
        # 텍스트 추출 확인
        for file in intermediate.get('files', []):
            if 'full_text' in file['name'] and file.get('char_count', 0) > 0:
                quality['text_extraction'] = True
                quality['overall_score'] += 25
                break
                
        # 구조화된 객체 확인
        for file in intermediate.get('files', []):
            if '/objects/' in file['name']:
                quality['structured_objects'] = True
                quality['overall_score'] += 25
                break
                
        # 청킹 확인
        for file in derived.get('files', []):
            if 'chunking_metadata' in file['name']:
                quality['chunking'] = True
                quality['overall_score'] += 25
                break
                
        # 임베딩 확인
        for file in derived.get('files', []):
            if 'embedding_metadata' in file['name']:
                quality['embedding'] = True
                quality['overall_score'] += 25
                break
        
        return quality
    
    def _generate_extraction_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """추출 결과 요약 생성"""
        summary = {
            'total_objects': 0,
            'text_objects': 0,
            'table_objects': 0,
            'image_objects': 0,
            'total_chars': 0,
            'has_korean_text': False
        }
        
        for result in results:
            if result['type'] == 'structured_object':
                summary['total_objects'] += 1
                obj_type = result['summary'].get('object_type', '')
                if obj_type == 'TABLE':
                    summary['table_objects'] += 1
                elif obj_type == 'IMAGE':
                    summary['image_objects'] += 1
            elif result['type'] == 'text_object':
                summary['text_objects'] += 1
                summary['total_chars'] += result['summary'].get('char_count', 0)
            elif result['type'] == 'full_text':
                summary['total_chars'] += result['summary'].get('char_count', 0)
                summary['has_korean_text'] = result['summary'].get('has_korean', False)
                
        return summary
    
    async def list_blob_contents(self, container_type: str, prefix: str = "", max_results: int = 50) -> List[Dict[str, Any]]:
        """Blob 컨테이너 내용 조회"""
        if not self.azure_blob:
            return []
            
        container_name = getattr(settings, f'azure_blob_container_{container_type}')
        
        try:
            blobs = []
            # Azure Blob Service의 실제 API 사용
            blobs_iter = self.azure_blob.list_blobs(container_name, prefix=prefix)
            
            for blob_info in blobs_iter[:max_results]:
                if len(blobs) >= max_results:
                    break
                    
                blobs.append({
                    'name': blob_info.get('name', ''),
                    'size': blob_info.get('size', 0),
                    'last_modified': blob_info.get('last_modified'),
                    'content_type': blob_info.get('content_type', 'unknown')
                })
                
            return blobs
            
        except Exception as e:
            logger.error(f"❌ Blob 목록 조회 실패 ({container_name}): {e}")
            return []
    
    async def download_blob_content(self, container_type: str, blob_name: str) -> Optional[str]:
        """Blob 내용 다운로드"""
        if not self.azure_blob:
            return None
            
        container_name = getattr(settings, f'azure_blob_container_{container_type}')
        
        try:
            # Azure Blob Service를 통해 직접 다운로드
            content_bytes = self.azure_blob.download_blob(container_name, blob_name)
            
            # 텍스트로 디코딩 시도
            try:
                return content.decode('utf-8')
            except UnicodeDecodeError:
                return content.decode('utf-8', errors='ignore')
                
        except Exception as e:
            logger.error(f"❌ Blob 다운로드 실패 ({blob_name}): {e}")
            return None

async def main():
    """메인 테스트 실행"""
    logger.info("🔍 문서 추출 품질 테스트 시작")
    
    tester = ExtractionQualityTester()
    await tester.initialize()
    
    print("\n" + "="*60)
    print("📊 1단계: 기존 저장된 추출 결과 분석")
    print("="*60)
    
    stored_analysis = await tester.analyze_stored_extraction_results()
    
    if stored_analysis.get('success'):
        summary = stored_analysis.get('summary', {})
        print(f"✅ 분석 완료:")
        print(f"  📄 총 추출된 객체: {summary.get('total_objects', 0)}개")
        print(f"  📝 텍스트 객체: {summary.get('text_objects', 0)}개")
        print(f"  📊 표 객체: {summary.get('table_objects', 0)}개")
        print(f"  🖼️ 이미지 객체: {summary.get('image_objects', 0)}개")
        print(f"  💬 총 텍스트 길이: {summary.get('total_chars', 0):,}자")
        print(f"  🇰🇷 한국어 포함: {'✅' if summary.get('has_korean_text') else '❌'}")
        
        # 상세 결과 출력
        print(f"\n📋 상세 분석 결과:")
        for result in stored_analysis.get('analysis_results', [])[:5]:  # 처음 5개만
            print(f"  📁 {result['type']}: {result['file']}")
            if result['type'] == 'full_text':
                sample = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
                print(f"     내용 샘플: {sample}")
            elif result['type'] == 'structured_object':
                print(f"     객체 타입: {result['summary'].get('object_type')}")
                print(f"     페이지: {result['summary'].get('page_no')}")
                
    else:
        print(f"❌ 분석 실패: {stored_analysis.get('error')}")
    
    print("\n" + "="*60)
    print("📄 2단계: 실제 문서로 추출 테스트 제안")
    print("="*60)
    
    # 테스트 가능한 문서 파일 찾기
    test_documents = [
        "/tmp/test_document.docx",
        "/tmp/test_document.pdf", 
        "/tmp/test_document.pptx",
        "/home/wjadmin/Dev/InsightBridge/test_template.pdf"
    ]
    
    available_docs = [doc for doc in test_documents if os.path.exists(doc)]
    
    if available_docs:
        print(f"📁 테스트 가능한 문서:")
        for doc in available_docs:
            print(f"  - {doc}")
        print(f"\n💡 실제 문서 테스트를 원하시면 다음 명령어 실행:")
        print(f"   python app/scripts/test_extraction_quality.py --test-file {available_docs[0]}")
    else:
        print(f"📁 테스트용 문서를 업로드하고 다음 명령어로 테스트하세요:")
        print(f"   python app/scripts/test_extraction_quality.py --test-file /path/to/document.pdf")
    
    print(f"\n🎉 추출 품질 분석 완료!")

if __name__ == "__main__":
    import sys
    
    if "--test-file" in sys.argv:
        file_index = sys.argv.index("--test-file") + 1
        if file_index < len(sys.argv):
            test_file = sys.argv[file_index]
            
            async def test_file():
                tester = ExtractionQualityTester()
                await tester.initialize()
                result = await tester.test_with_real_document(test_file)
                print(f"\n📄 파일 테스트 결과: {test_file}")
                print(f"성공: {'✅' if result.get('success') else '❌'}")
                if result.get('success'):
                    stats = result.get('stats', {})
                    print(f"추출 시간: {stats.get('elapsed_seconds', 0):.2f}초")
                    print(f"청크 수: {result.get('chunks_count', 0)}개")
                    print(f"임베딩 수: {result.get('embeddings_count', 0)}개")
                else:
                    print(f"오류: {result.get('error')}")
                    
            asyncio.run(test_file())
        else:
            print("❌ --test-file 옵션에 파일 경로가 필요합니다")
    else:
        asyncio.run(main())