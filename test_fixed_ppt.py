#!/usr/bin/env python3
"""
수정된 PPT 생성기로 새로운 PPT 생성 및 테스트
"""

import sys
import os
from pathlib import Path

# 프로젝트 경로 설정
project_root = Path("/home/admin/wkms-aws")
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

def test_fixed_ppt_generation():
    """수정된 PPT 생성기 테스트"""
    try:
        from backend.app.services.presentation.quick_ppt_generator_service import QuickPPTGeneratorService
        
        # 서비스 초기화
        generator = QuickPPTGeneratorService()
        
        # 테스트용 간단한 프롬프트
        test_content = """
        # 인슐린 펌프 개선 사항 소개
        
        ## 주요 개선 기능
        
        ### 정밀한 투약 시스템
        🔑 **메시지**: 0.05 unit 단위로 미세 조절이 가능합니다.
        
        🔹 고정밀 마이크로펌프 탑재
        🔸 AI 기반 투약량 예측 알고리즘
        💎 실시간 피드백 루프 구현
        
        ### 스마트 모니터링
        🔑 **메시지**: 24시간 연속 혈당 모니터링이 가능합니다.
        
        항목 1: 실시간 혈당 트렌드 분석
        항목 2: 이상 상황 자동 감지 및 알림
        항목 3: 클라우드 기반 데이터 백업
        항목 4: 가족/의료진 원격 모니터링 지원
        
        ### 사용자 편의성
        🔑 **메시지**: 직관적인 인터페이스로 누구나 쉽게 사용할 수 있습니다.
        
        🔹 터치스크린 기반 간편 조작
        🔸 음성 가이드 지원
        💎 방수 설계로 일상 활동 제약 없음
        
        ### 감사합니다
        """
        
        # PPT 생성
        print("🚀 수정된 PPT 생성기로 테스트 PPT 생성 중...")
        
        # 1. 구조화된 내용을 파싱하여 DeckSpec 생성
        deck_spec = generator.generate_fixed_outline(
            topic="인슐린 펌프 개선 사항 소개",
            context_text=test_content,
            max_slides=6
        )
        
        # 2. DeckSpec을 PPT 파일로 빌드
        file_path = generator.build_quick_pptx(deck_spec, "test_fixed_insulin_pump")
        
        print(f"✅ PPT 생성 완료: {file_path}")
        return file_path
        
    except Exception as e:
        print(f"❌ PPT 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_fixed_ppt_generation()
    if result:
        print(f"\n📁 생성된 파일: {result}")
        print("🔍 이제 중복 문제가 해결되었는지 분석해보겠습니다...")
    else:
        print("\n❌ 테스트 실패")
