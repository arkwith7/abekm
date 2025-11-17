#!/usr/bin/env python3
"""
템플릿 기반 PPT 생성 시스템 테스트 스크립트
"""
import asyncio
import json
from pathlib import Path
import sys
import os

# 백엔드 디렉토리를 Python 경로에 추가
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.services.presentation.enhanced_ppt_generator_service import (
    EnhancedPPTGeneratorService, DeckSpec, SlideSpec
)

async def test_title_extraction():
    """제목 추출 기능 테스트"""
    print("🔍 제목 추출 테스트 시작...")
    
    service = EnhancedPPTGeneratorService()
    
    test_cases = [
        ("발표자료", "기본값"),
        ("# AI 기술 동향 보고서", "AI 기술 동향 보고서"),
        ("**프로젝트 현황 분석**", "프로젝트 현황 분석"),
        ("2024년 사업 계획.pdf", "2024년 사업 계획"),
        ("quarterly_report_Q3.docx", "Quarterly Report Q3"),
        ("마케팅-전략-2024.pptx", "마케팅 전략 2024"),
        ("", "발표자료")
    ]
    
    for input_title, expected in test_cases:
        result = service._extract_clean_title(input_title)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{input_title}' → '{result}' (예상: '{expected}')")
    
    print("제목 추출 테스트 완료!\n")

async def test_content_analysis():
    """컨텐츠 분석 기능 테스트"""
    print("📊 컨텐츠 분석 테스트 시작...")
    
    service = EnhancedPPTGeneratorService()
    
    # 키-값 패턴 테스트
    test_content = """
    다음은 주요 지표입니다:
    • 매출: 1,250억원 (전년 대비 15% 증가)
    • 순이익: 180억원 (전년 대비 25% 증가)
    • 직원수: 1,234명
    • 지점수: 45개
    
    분기별 성과:
    - Q1: 300억원
    - Q2: 350억원  
    - Q3: 300억원
    - Q4: 300억원
    """
    
    kv_blocks = service._extract_keyvalue_blocks(test_content)
    print(f"키-값 블록 감지: {len(kv_blocks)}개")
    for i, block in enumerate(kv_blocks):
        print(f"  블록 {i+1}: {block[:50]}...")
    
    # 차트 후보 감지 테스트
    is_chart = service._is_chart_candidate(test_content, "성과 분석")
    print(f"차트 후보 여부: {'✅' if is_chart else '❌'}")
    
    print("컨텐츠 분석 테스트 완료!\n")

async def test_slide_compression():
    """슬라이드 압축 테스트"""
    print("🗜️ 슬라이드 압축 테스트 시작...")
    
    service = EnhancedPPTGeneratorService()
    
    # 테스트용 DeckSpec 생성
    slides = [
        SlideSpec(title="개요", key_message="프로젝트 개요", bullets=["목표", "범위"]),
        SlideSpec(title="배경", key_message="짧은 내용", bullets=["간단한 내용"]),  # 약한 슬라이드
        SlideSpec(title="현황", key_message="상세한 현황 분석 내용", bullets=[
            "첫 번째 주요 현황", "두 번째 중요한 현황", "세 번째 핵심 사항"
        ]),
        SlideSpec(title="계획", key_message="향후 계획", bullets=["1단계", "2단계", "3단계"]),
        SlideSpec(title="부록", key_message="추가 자료", bullets=["참고자료"]),  # 약한 슬라이드
    ]
    
    original_spec = DeckSpec(topic="테스트 프레젠테이션", slides=slides, max_slides=10)
    
    compressed_spec = service._compress_slides(original_spec, max_slides=4)
    
    print(f"원본 슬라이드 수: {len(original_spec.slides)}")
    print(f"압축 후 슬라이드 수: {len(compressed_spec.slides)}")
    print("압축 후 슬라이드 제목:")
    for i, slide in enumerate(compressed_spec.slides):
        print(f"  {i+1}. {slide.title}")
    
    print("슬라이드 압축 테스트 완료!\n")

async def test_full_pipeline():
    """전체 파이프라인 테스트"""
    print("🚀 전체 파이프라인 테스트 시작...")
    
    service = EnhancedPPTGeneratorService()
    
    test_context = """
    # AI 기술 동향 분석 보고서
    
    ## 1. 개요
    인공지능 기술의 최신 동향을 분석하고 향후 전망을 제시합니다.
    
    ## 2. 현재 AI 기술 현황
    • 자연어 처리: GPT-4, Claude 등 대형 언어 모델 발전
    • 컴퓨터 비전: Stable Diffusion, DALL-E 등 이미지 생성 AI
    • 로보틱스: 자율주행, 산업용 로봇 자동화
    
    ## 3. 시장 규모 및 성장
    • 2023년 AI 시장 규모: 1,500억 달러
    • 2028년 예상 시장 규모: 7,390억 달러
    • 연평균 성장률(CAGR): 37.3%
    
    ## 4. 주요 기업 동향
    • OpenAI: ChatGPT 및 GPT-4 출시로 시장 선도
    • Google: Bard, PaLM 2 등으로 경쟁 
    • Microsoft: Azure AI 서비스 확장
    • 네이버: HyperCLOVA X 개발
    
    ## 5. 향후 전망
    다음 5년간 AI 기술은 다음 분야에서 혁신적 변화를 가져올 것으로 예상:
    - 의료 진단 및 치료
    - 교육 개인화
    - 금융 서비스 자동화
    - 제조업 스마트 팩토리
    """
    
    try:
        # 아웃라인 생성
        deck_spec = await service.generate_enhanced_outline(
            topic="AI 기술 동향 보고서",
            context_text=test_context,
            document_filename="ai_tech_trends_2024.pdf",
            template_style="business",
            include_charts=True
        )
        
        print(f"생성된 슬라이드 수: {len(deck_spec.slides)}")
        print(f"주제: {deck_spec.topic}")
        
        print("\n슬라이드 구성:")
        for i, slide in enumerate(deck_spec.slides):
            print(f"{i+1}. {slide.title}")
            if slide.key_message:
                print(f"   핵심 메시지: {slide.key_message[:50]}...")
            print(f"   불렛 포인트: {len(slide.bullets)}개")
            if slide.diagram and slide.diagram.type != 'none':
                print(f"   다이어그램: {slide.diagram.type}")
        
        # PPT 파일 생성 테스트
        print(f"\n📄 PPT 파일 생성 중...")
        ppt_path = service.build_enhanced_pptx(
            deck_spec, 
            file_basename="test_ai_trends.pptx",
            template_style="business"
        )
        
        if Path(ppt_path).exists():
            print(f"✅ PPT 파일 생성 성공: {ppt_path}")
            file_size = Path(ppt_path).stat().st_size
            print(f"   파일 크기: {file_size:,} bytes")
        else:
            print("❌ PPT 파일 생성 실패")
            
    except Exception as e:
        print(f"❌ 파이프라인 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("전체 파이프라인 테스트 완료!\n")

async def main():
    """메인 테스트 실행"""
    print("🧪 템플릿 기반 PPT 생성 시스템 테스트\n")
    print("=" * 60)
    
    await test_title_extraction()
    await test_content_analysis()
    await test_slide_compression()
    await test_full_pipeline()
    
    print("=" * 60)
    print("🎉 모든 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
