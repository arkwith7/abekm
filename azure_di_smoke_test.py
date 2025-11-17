#!/usr/bin/env python3
"""
Azure Document Intelligence 통합 스모크 테스트
===========================================

Azure Document Intelligence와 pdfplumber 간의 PDF 추출 성능 및 기능을 비교 테스트합니다.
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.core.config import settings
from app.services.document.extraction.text_extractor_service import TextExtractorService
from app.services.document.extraction.azure_document_intelligence_service import (
    azure_document_intelligence_service,
    DocumentIntelligenceResult
)


class AzureDIComparisonTest:
    """Azure DI vs pdfplumber 비교 테스트"""
    
    def __init__(self):
        self.extractor = TextExtractorService()
        self.results = []
    
    async def run_comparison_test(self, pdf_path: str) -> Dict[str, Any]:
        """PDF 파일에 대해 Azure DI와 pdfplumber 비교 테스트"""
        
        print(f"\n{'='*60}")
        print(f"PDF 비교 테스트: {Path(pdf_path).name}")
        print(f"{'='*60}")
        
        if not Path(pdf_path).exists():
            print(f"❌ 파일을 찾을 수 없습니다: {pdf_path}")
            return {}
        
        # 파일 정보
        file_size = Path(pdf_path).stat().st_size
        print(f"📄 파일 크기: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
        
        comparison_result = {
            'file_path': pdf_path,
            'file_size_bytes': file_size,
            'azure_di_result': None,
            'pdfplumber_result': None,
            'comparison': {}
        }
        
        # 1. Azure Document Intelligence 테스트
        print(f"\n🔍 Azure Document Intelligence 테스트...")
        azure_di_result = await self._test_azure_di(pdf_path)
        comparison_result['azure_di_result'] = azure_di_result
        
        # 2. pdfplumber 테스트 
        print(f"\n📚 pdfplumber 테스트...")
        pdfplumber_result = await self._test_pdfplumber(pdf_path)
        comparison_result['pdfplumber_result'] = pdfplumber_result
        
        # 3. 비교 분석
        print(f"\n📊 결과 비교...")
        comparison = self._compare_results(azure_di_result, pdfplumber_result)
        comparison_result['comparison'] = comparison
        
        # 4. 요약 출력
        self._print_comparison_summary(comparison)
        
        return comparison_result
    
    async def _test_azure_di(self, pdf_path: str) -> Dict[str, Any]:
        """Azure Document Intelligence 테스트"""
        
        if not azure_document_intelligence_service.is_available():
            print("❌ Azure Document Intelligence 서비스를 사용할 수 없습니다")
            print(f"   - 엔드포인트: {settings.azure_document_intelligence_endpoint}")
            print(f"   - 플래그 활성화: {settings.use_azure_document_intelligence_pdf}")
            return {
                'success': False,
                'error': 'Service unavailable',
                'available': False
            }
        
        print(f"✅ Azure DI 서비스 사용 가능")
        print(f"   - 엔드포인트: {settings.azure_document_intelligence_endpoint}")
        print(f"   - 모델: {settings.azure_document_intelligence_layout_model}")
        
        start_time = time.time()
        try:
            di_result = await azure_document_intelligence_service.analyze_pdf(pdf_path)
            processing_time = time.time() - start_time
            
            if di_result.success:
                print(f"✅ Azure DI 분석 성공 ({processing_time:.2f}초)")
                print(f"   - 텍스트 길이: {len(di_result.text):,} 문자")
                print(f"   - 페이지 수: {len(di_result.pages)}")
                print(f"   - 표 수: {len(di_result.tables)}")
                print(f"   - 그림 수: {len(di_result.figures)}")
                
                return {
                    'success': True,
                    'available': True,
                    'processing_time': processing_time,
                    'text_length': len(di_result.text),
                    'page_count': len(di_result.pages),
                    'table_count': len(di_result.tables),
                    'figure_count': len(di_result.figures),
                    'extraction_method': di_result.extraction_method,
                    'metadata': di_result.metadata,
                    'text_preview': di_result.text[:200] + "..." if len(di_result.text) > 200 else di_result.text
                }
            else:
                print(f"❌ Azure DI 분석 실패: {di_result.error}")
                return {
                    'success': False,
                    'available': True,
                    'error': di_result.error,
                    'processing_time': processing_time,
                    'extraction_method': di_result.extraction_method
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ Azure DI 예외 발생: {e}")
            return {
                'success': False,
                'available': True,
                'error': str(e),
                'processing_time': processing_time
            }
    
    async def _test_pdfplumber(self, pdf_path: str) -> Dict[str, Any]:
        """pdfplumber 테스트"""
        
        start_time = time.time()
        try:
            # 기존 설정 백업
            original_di_setting = settings.use_azure_document_intelligence_pdf
            
            # DI 비활성화하여 pdfplumber만 사용
            settings.use_azure_document_intelligence_pdf = False
            
            result = await self.extractor._extract_pdf_with_pdfplumber(pdf_path, {
                'text': '',
                'metadata': {},
                'success': True,
                'error': None
            })
            
            # 설정 복원
            settings.use_azure_document_intelligence_pdf = original_di_setting
            
            processing_time = time.time() - start_time
            
            if result['success']:
                pages_count = result['metadata'].get('page_count', 0)
                total_tables = result['metadata'].get('total_tables', 0)
                total_images = result['metadata'].get('total_images', 0)
                
                print(f"✅ pdfplumber 추출 성공 ({processing_time:.2f}초)")
                print(f"   - 텍스트 길이: {len(result['text']):,} 문자")
                print(f"   - 페이지 수: {pages_count}")
                print(f"   - 표 수: {total_tables}")
                print(f"   - 이미지 수: {total_images}")
                
                return {
                    'success': True,
                    'processing_time': processing_time,
                    'text_length': len(result['text']),
                    'page_count': pages_count,
                    'table_count': total_tables,
                    'image_count': total_images,
                    'extraction_method': result['metadata'].get('extraction_method', 'pdfplumber'),
                    'text_preview': result['text'][:200] + "..." if len(result['text']) > 200 else result['text']
                }
            else:
                print(f"❌ pdfplumber 추출 실패: {result.get('error', 'Unknown error')}")
                return {
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'processing_time': processing_time
                }
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ pdfplumber 예외 발생: {e}")
            return {
                'success': False,
                'error': str(e),
                'processing_time': processing_time
            }
    
    def _compare_results(self, azure_result: Dict, pdfplumber_result: Dict) -> Dict[str, Any]:
        """두 결과 비교 분석"""
        
        comparison = {
            'both_success': azure_result.get('success', False) and pdfplumber_result.get('success', False),
            'azure_success': azure_result.get('success', False),
            'pdfplumber_success': pdfplumber_result.get('success', False),
            'performance': {},
            'content': {},
            'features': {}
        }
        
        # 성능 비교
        if azure_result.get('processing_time') and pdfplumber_result.get('processing_time'):
            azure_time = azure_result['processing_time']
            pdfplumber_time = pdfplumber_result['processing_time']
            
            comparison['performance'] = {
                'azure_di_time': azure_time,
                'pdfplumber_time': pdfplumber_time,
                'time_difference': azure_time - pdfplumber_time,
                'azure_faster': azure_time < pdfplumber_time,
                'speedup_ratio': pdfplumber_time / azure_time if azure_time > 0 else 0
            }
        
        # 콘텐츠 비교
        if comparison['both_success']:
            azure_text_len = azure_result.get('text_length', 0)
            pdfplumber_text_len = pdfplumber_result.get('text_length', 0)
            
            comparison['content'] = {
                'azure_text_length': azure_text_len,
                'pdfplumber_text_length': pdfplumber_text_len,
                'text_length_difference': azure_text_len - pdfplumber_text_len,
                'azure_extracted_more': azure_text_len > pdfplumber_text_len
            }
        
        # 기능 비교
        comparison['features'] = {
            'azure_di_features': {
                'structured_tables': azure_result.get('table_count', 0) > 0,
                'figure_detection': azure_result.get('figure_count', 0) > 0,
                'confidence_scores': 'confidence' in str(azure_result.get('metadata', {})),
                'bounding_boxes': 'bbox' in str(azure_result.get('metadata', {}))
            },
            'pdfplumber_features': {
                'basic_tables': pdfplumber_result.get('table_count', 0) > 0,
                'image_locations': pdfplumber_result.get('image_count', 0) > 0
            }
        }
        
        return comparison
    
    def _print_comparison_summary(self, comparison: Dict[str, Any]):
        """비교 결과 요약 출력"""
        
        print(f"\n📋 비교 결과 요약")
        print(f"─" * 40)
        
        # 성공 여부
        if comparison['both_success']:
            print("✅ 두 방식 모두 성공")
        elif comparison['azure_success']:
            print("✅ Azure DI만 성공, pdfplumber 실패")
        elif comparison['pdfplumber_success']:
            print("✅ pdfplumber만 성공, Azure DI 실패")
        else:
            print("❌ 두 방식 모두 실패")
        
        # 성능 비교
        if 'performance' in comparison and comparison['performance']:
            perf = comparison['performance']
            azure_time = perf['azure_di_time']
            pdfplumber_time = perf['pdfplumber_time']
            
            print(f"\n⚡ 성능:")
            print(f"   Azure DI: {azure_time:.2f}초")
            print(f"   pdfplumber: {pdfplumber_time:.2f}초")
            
            if perf['azure_faster']:
                speedup = perf['speedup_ratio']
                print(f"   🏆 Azure DI가 {speedup:.1f}배 빠름")
            else:
                slowdown = 1 / perf['speedup_ratio'] if perf['speedup_ratio'] > 0 else 0
                print(f"   🏆 pdfplumber가 {slowdown:.1f}배 빠름")
        
        # 콘텐츠 비교
        if 'content' in comparison and comparison['content']:
            content = comparison['content']
            print(f"\n📝 텍스트 추출:")
            print(f"   Azure DI: {content['azure_text_length']:,} 문자")
            print(f"   pdfplumber: {content['pdfplumber_text_length']:,} 문자")
            
            if content['azure_extracted_more']:
                diff = content['text_length_difference']
                print(f"   🏆 Azure DI가 {diff:,} 문자 더 추출")
            else:
                diff = -content['text_length_difference']
                print(f"   🏆 pdfplumber가 {diff:,} 문자 더 추출")
        
        # 기능 비교
        if 'features' in comparison:
            features = comparison['features']
            print(f"\n🔧 고급 기능:")
            
            azure_features = features['azure_di_features']
            print(f"   Azure DI:")
            print(f"     - 구조화된 표: {'✅' if azure_features['structured_tables'] else '❌'}")
            print(f"     - 그림 탐지: {'✅' if azure_features['figure_detection'] else '❌'}")
            print(f"     - 신뢰도 점수: {'✅' if azure_features['confidence_scores'] else '❌'}")
            print(f"     - 경계 상자: {'✅' if azure_features['bounding_boxes'] else '❌'}")
            
            pdfplumber_features = features['pdfplumber_features']
            print(f"   pdfplumber:")
            print(f"     - 기본 표 추출: {'✅' if pdfplumber_features['basic_tables'] else '❌'}")
            print(f"     - 이미지 위치: {'✅' if pdfplumber_features['image_locations'] else '❌'}")


async def main():
    """메인 테스트 실행"""
    
    print("🚀 Azure Document Intelligence 통합 스모크 테스트")
    print("=" * 60)
    
    # 환경 설정 확인
    print(f"📋 환경 설정:")
    print(f"   - DI 엔드포인트: {settings.azure_document_intelligence_endpoint}")
    print(f"   - DI 사용 활성화: {settings.use_azure_document_intelligence_pdf}")
    print(f"   - DI 최대 페이지: {settings.azure_document_intelligence_max_pages}")
    print(f"   - DI 기본 모델: {settings.azure_document_intelligence_default_model}")
    
    # 테스트할 PDF 파일들 찾기
    test_files = []
    for pattern in ["test_*.pdf", "*.pdf"]:
        test_files.extend(Path(".").glob(pattern))
    
    if not test_files:
        print(f"\n❌ 테스트할 PDF 파일을 찾을 수 없습니다.")
        print(f"   현재 디렉토리에 test_*.pdf 또는 *.pdf 파일을 놓고 다시 실행하세요.")
        return
    
    print(f"\n📁 발견된 테스트 파일: {len(test_files)}개")
    for file in test_files:
        size_mb = file.stat().st_size / 1024 / 1024
        print(f"   - {file.name} ({size_mb:.1f} MB)")
    
    # 비교 테스트 실행
    tester = AzureDIComparisonTest()
    all_results = []
    
    for pdf_file in test_files[:3]:  # 최대 3개 파일만 테스트
        try:
            result = await tester.run_comparison_test(str(pdf_file))
            if result:
                all_results.append(result)
        except KeyboardInterrupt:
            print(f"\n⚠️ 사용자에 의해 중단되었습니다.")
            break
        except Exception as e:
            print(f"\n❌ 테스트 중 오류 발생: {e}")
            continue
    
    # 전체 결과 요약
    if all_results:
        print(f"\n" + "=" * 60)
        print(f"📊 전체 테스트 결과 요약")
        print(f"=" * 60)
        
        successful_azure = sum(1 for r in all_results if r.get('azure_di_result', {}).get('success', False))
        successful_pdfplumber = sum(1 for r in all_results if r.get('pdfplumber_result', {}).get('success', False))
        
        print(f"📈 성공률:")
        print(f"   - Azure DI: {successful_azure}/{len(all_results)} ({successful_azure/len(all_results)*100:.1f}%)")
        print(f"   - pdfplumber: {successful_pdfplumber}/{len(all_results)} ({successful_pdfplumber/len(all_results)*100:.1f}%)")
        
        # 평균 처리 시간
        azure_times = [r['azure_di_result']['processing_time'] for r in all_results 
                      if r.get('azure_di_result', {}).get('processing_time')]
        pdfplumber_times = [r['pdfplumber_result']['processing_time'] for r in all_results 
                           if r.get('pdfplumber_result', {}).get('processing_time')]
        
        if azure_times and pdfplumber_times:
            avg_azure = sum(azure_times) / len(azure_times)
            avg_pdfplumber = sum(pdfplumber_times) / len(pdfplumber_times)
            
            print(f"\n⚡ 평균 처리 시간:")
            print(f"   - Azure DI: {avg_azure:.2f}초")
            print(f"   - pdfplumber: {avg_pdfplumber:.2f}초")
            
            if avg_azure < avg_pdfplumber:
                print(f"   🏆 Azure DI가 평균 {avg_pdfplumber/avg_azure:.1f}배 빠름")
            else:
                print(f"   🏆 pdfplumber가 평균 {avg_azure/avg_pdfplumber:.1f}배 빠름")
        
        # 결과를 JSON으로 저장
        results_file = Path("azure_di_comparison_results.json")
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n💾 상세 결과가 {results_file}에 저장되었습니다.")
    
    print(f"\n✅ 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())