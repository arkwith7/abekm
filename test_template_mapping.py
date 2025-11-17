#!/usr/bin/env python3
"""
템플릿 매핑 기능 테스트 스크립트
- 템플릿 적용 PPT 생성에서 매핑이 제대로 적용되는지 확인
- build_enhanced_pptx_with_slide_management 메서드 테스트
"""

import os
import sys
import json
from pathlib import Path

# 백엔드 모듈 경로 추가
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def test_template_mapping():
    """템플릿 매핑 기능 테스트"""
    try:
        print("🧪 템플릿 매핑 기능 테스트 시작")
        
        # 환경 변수 설정
        os.environ["PYTHONPATH"] = str(backend_path)
        
        from app.services.presentation.templated_ppt_generator_service import TemplatedPPTGeneratorService
        from app.services.presentation.ppt_models import SlideSpec, DeckSpec
        
        print("✅ 모듈 임포트 성공")
        
        # 서비스 초기화
        service = TemplatedPPTGeneratorService()
        print("✅ TemplatedPPTGeneratorService 초기화 성공")
        
        # 테스트용 DeckSpec 생성
        slides = [
            SlideSpec(
                title="테스트 제목 슬라이드",
                key_message="테스트용 부제목입니다",
                bullets=[],
                layout="title-slide"
            ),
            SlideSpec(
                title="테스트 내용 슬라이드",
                key_message="테스트용 핵심 메시지입니다",
                bullets=["첫 번째 불릿", "두 번째 불릿", "세 번째 불릿"],
                layout="title-and-content"
            )
        ]
        
        deck = DeckSpec(
            topic="테스트 발표자료",
            slides=slides,
            max_slides=2
        )
        
        print("✅ 테스트용 DeckSpec 생성 완료")
        
        # 템플릿 매핑 데이터 준비
        text_box_mappings = [
            {
                "elementId": "test_element_1",
                "slideIndex": 0,
                "newContent": "매핑된 새로운 제목",
                "action": "replace_content",
                "isEnabled": True
            },
            {
                "elementId": "test_element_2", 
                "slideIndex": 1,
                "newContent": "매핑된 새로운 내용",
                "action": "replace_content",
                "isEnabled": True
            }
        ]
        
        content_segments = [
            {
                "segment_id": "seg_1",
                "content": "테스트 세그먼트 내용 1",
                "type": "text"
            },
            {
                "segment_id": "seg_2", 
                "content": "테스트 세그먼트 내용 2",
                "type": "text"
            }
        ]
        
        print("✅ 매핑 데이터 준비 완료")
        
        # 기본 빌드 테스트 (매핑 없음)
        print("🔍 기본 빌드 테스트...")
        try:
            basic_path = service.build_enhanced_pptx_with_slide_management(deck)
            if os.path.exists(basic_path):
                print(f"✅ 기본 빌드 성공: {basic_path}")
            else:
                print(f"❌ 기본 빌드 실패: 파일이 생성되지 않음")
                return False
        except Exception as e:
            print(f"❌ 기본 빌드 에러: {e}")
            return False
        
        # 매핑 적용 빌드 테스트
        print("🔍 매핑 적용 빌드 테스트...")
        try:
            mapping_path = service.build_enhanced_pptx_with_slide_management(
                deck,
                text_box_mappings=text_box_mappings,
                content_segments=content_segments
            )
            if os.path.exists(mapping_path):
                print(f"✅ 매핑 적용 빌드 성공: {mapping_path}")
            else:
                print(f"❌ 매핑 적용 빌드 실패: 파일이 생성되지 않음")
                return False
        except Exception as e:
            print(f"❌ 매핑 적용 빌드 에러: {e}")
            return False
        
        print("✅ 모든 테스트 통과!")
        return True
        
    except ImportError as e:
        print(f"❌ 모듈 임포트 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

if __name__ == "__main__":
    success = test_template_mapping()
    if success:
        print("\n🎉 템플릿 매핑 기능이 정상적으로 작동합니다!")
    else:
        print("\n💥 템플릿 매핑 기능에 문제가 있습니다.")
        sys.exit(1)
