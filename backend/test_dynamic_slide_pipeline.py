"""
동적 슬라이드 관리 파이프라인 테스트

사용자 질의: "자동차 산업의 특허분석 방법론에 대해 가이드 문서를 PPT로 작성하려고 합니다. 작성해 주세요"
"""

import asyncio
import json
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

# 로그 설정
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")


async def test_dynamic_slide_pipeline():
    """동적 슬라이드 파이프라인 전체 테스트"""
    
    print("=" * 80)
    print("🧪 동적 슬라이드 관리 파이프라인 테스트")
    print("=" * 80)
    
    # 1. 필요한 모듈 임포트
    print("\n📦 Step 1: 모듈 임포트...")
    try:
        from app.agents.presentation.unified_presentation_agent import UnifiedPresentationAgent
        from app.tools.presentation.ai_direct_mapping_tool import AIDirectMappingTool
        from app.services.presentation.dynamic_slide_manager import DynamicSlideManager
        from app.services.presentation.ppt_template_manager import template_manager
        print("  ✅ 모듈 임포트 성공")
    except Exception as e:
        print(f"  ❌ 모듈 임포트 실패: {e}")
        return
    
    # 2. 사용자 질의 (🆕 v3.8: 슬라이드 수 요청 포함)
    user_query = "자동차 산업의 특허분석 특징을 슬라이드 5장의 PPT로 작성하려고 합니다. 작성해 주세요"
    print(f"\n📝 Step 2: 사용자 질의")
    print(f"  \"{user_query}\"")
    
    # 3. 템플릿 찾기
    print("\n📄 Step 3: 템플릿 검색...")
    template_id = None
    template_path = None
    user_id = "8"  # 테스트 사용자
    
    # 직접 템플릿 경로 지정
    backend_root = Path(__file__).parent
    template_path = str(backend_root / "uploads" / "templates" / "users" / "8" / "제품소개서 샘플.pptx")
    template_id = "제품소개서_샘플"
    
    import os
    if os.path.exists(template_path):
        print(f"  ✅ 템플릿 발견: {template_id}")
        print(f"     경로: {template_path}")
    else:
        print(f"  ❌ 템플릿 파일 없음: {template_path}")
        return
    
    # 4. 템플릿 메타데이터 로드
    print("\n📊 Step 4: 템플릿 메타데이터 로드...")
    try:
        from app.services.presentation.user_template_manager import user_template_manager
        from app.services.presentation.ppt_template_manager import template_manager
        
        # template_id 정규화
        normalized_id = template_id.lower().replace(' ', '_').replace('.pptx', '')
        
        # 사용자 템플릿 메타데이터 시도
        metadata = user_template_manager.get_template_metadata(user_id, normalized_id)
        
        if not metadata:
            # 시스템 템플릿 메타데이터 시도
            metadata = template_manager.get_template_metadata(normalized_id)
        
        if not metadata:
            # template_analyzer_tool 사용
            from app.tools.presentation.template_analyzer_tool import template_analyzer_tool
            analysis_result = await template_analyzer_tool._arun(
                template_id=template_id,
                user_id=int(user_id) if user_id else None
            )
            if analysis_result.get('success'):
                metadata = analysis_result.get('template_metadata', {})
                # slides 추출
                if not metadata.get('slides') and analysis_result.get('slides_info'):
                    metadata['slides'] = analysis_result.get('slides_info', [])
        
        if not metadata:
            print("  ❌ 메타데이터 로드 실패")
            return
        
        slides = metadata.get('slides', [])
        print(f"  ✅ 템플릿 분석 완료: {len(slides)}개 슬라이드")
        
        for i, slide in enumerate(slides[:5]):  # 처음 5개만 출력
            role = slide.get('role', 'unknown')
            elem_count = len(slide.get('elements', []))
            print(f"     슬라이드 {i+1}: role={role}, elements={elem_count}")
        if len(slides) > 5:
            print(f"     ... 외 {len(slides)-5}개")
            
    except Exception as e:
        print(f"  ❌ 템플릿 분석 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. DynamicSlideManager 테스트
    print("\n📐 Step 5: DynamicSlideManager 테스트...")
    try:
        dsm = DynamicSlideManager(metadata)  # 메타데이터 딕셔너리 전달
        
        # 슬라이드 타입별 정보 출력
        content_slides = dsm.get_content_slide_indices()
        toc_idx = dsm.get_toc_slide_index()
        
        print(f"  ✅ 슬라이드 분류 완료:")
        print(f"     TOC 슬라이드: {toc_idx}")
        print(f"     콘텐츠 슬라이드: {content_slides}")
        print(f"     슬라이드 타입: {dsm.slide_types}")
                
    except Exception as e:
        print(f"  ❌ DynamicSlideManager 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 6. AI 매핑 생성 (AIDirectMappingTool)
    print("\n🤖 Step 6: AI 매핑 생성...")
    try:
        ai_mapping_tool = AIDirectMappingTool()
        
        # AI 매핑 실행
        result = await ai_mapping_tool._arun(
            user_query=user_query,
            template_metadata=metadata,
            additional_context="한국어로 작성해주세요. 자동차 산업 특허분석에 초점을 맞춰주세요."
        )
        
        if result.get('success'):
            mappings = result.get('mappings', [])
            slide_replacements = result.get('slide_replacements', [])
            content_plan = result.get('content_plan', {})
            dynamic_slides = result.get('dynamic_slides', {})
            
            print(f"  ✅ AI 매핑 생성 완료:")
            print(f"     - 매핑 수: {len(mappings)}")
            print(f"     - 슬라이드 대체: {len(slide_replacements)}")
            print(f"     - content_plan: {json.dumps(content_plan, ensure_ascii=False, indent=2)[:200]}...")
            print(f"     - dynamic_slides: {json.dumps(dynamic_slides, ensure_ascii=False)}")
            
            # 매핑 샘플 출력
            print("\n     📋 매핑 샘플 (처음 5개):")
            for m in mappings[:5]:
                slide_idx = m.get('slideIndex', 0)
                elem_id = m.get('elementId', '')
                text = m.get('generatedText', '')[:50]
                is_enabled = m.get('isEnabled', True)
                print(f"        슬라이드 {slide_idx+1}: {elem_id} → \"{text}...\" (enabled={is_enabled})")
            
        else:
            print(f"  ❌ AI 매핑 실패: {result.get('error')}")
            return result
            
    except Exception as e:
        print(f"  ❌ AI 매핑 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 7. PPT 빌드
    print("\n🔨 Step 7: PPT 빌드...")
    try:
        from app.services.presentation.ai_ppt_builder import build_ppt_from_ai_mappings
        
        # 동적 슬라이드 연산 준비
        dynamic_slide_ops = None
        if dynamic_slides and dynamic_slides.get('mode') != 'fixed':
            if dynamic_slides.get('mode') == 'expand':
                dynamic_slide_ops = {
                    'mode': 'expand',
                    'add_slides': dynamic_slides.get('add_slides', [])
                }
            elif dynamic_slides.get('mode') == 'reduce':
                dynamic_slide_ops = {
                    'mode': 'reduce',
                    'remove_slides': dynamic_slides.get('remove_slides', [])
                }
        
        output_filename = "자동차_특허분석_5장_테스트.pptx"
        
        build_result = build_ppt_from_ai_mappings(
            template_path=template_path,
            mappings=mappings,
            output_filename=output_filename,
            presentation_title="자동차 산업 특허분석 방법론 가이드",
            slide_replacements=slide_replacements,
            dynamic_slide_ops=dynamic_slide_ops,
        )
        
        if build_result.get('success'):
            print(f"  ✅ PPT 빌드 성공!")
            print(f"     - 파일 경로: {build_result.get('file_path')}")
            print(f"     - 적용된 매핑: {build_result.get('applied_count')}")
            print(f"     - 실패한 매핑: {build_result.get('failed_count')}")
            
            stats = build_result.get('stats', {})
            print(f"     - 통계: {json.dumps(stats, ensure_ascii=False)}")
            
            if build_result.get('dynamic_slides_applied'):
                print(f"     - 동적 슬라이드 모드: {build_result.get('dynamic_slides_mode')}")
        else:
            print(f"  ❌ PPT 빌드 실패: {build_result.get('error')}")
            
    except Exception as e:
        print(f"  ❌ PPT 빌드 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 8. 결과 요약
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)
    print(f"  사용자 질의: {user_query}")
    print(f"  템플릿: {template_id}")
    print(f"  AI 매핑: {len(mappings)}개 생성")
    print(f"  동적 슬라이드: {dynamic_slides.get('mode', 'fixed')}")
    print(f"  PPT 생성: {'성공' if build_result.get('success') else '실패'}")
    if build_result.get('success'):
        print(f"  출력 파일: {build_result.get('file_path')}")
    print("=" * 80)
    
    return {
        'success': True,
        'mappings_count': len(mappings),
        'content_plan': content_plan,
        'dynamic_slides': dynamic_slides,
        'build_result': build_result
    }


if __name__ == "__main__":
    result = asyncio.run(test_dynamic_slide_pipeline())
    
    if result and result.get('success'):
        print("\n✅ 테스트 완료!")
    else:
        print("\n❌ 테스트 실패!")
