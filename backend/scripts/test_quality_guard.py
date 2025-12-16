import logging
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tools.presentation.quality_guard_tool import QualityGuard

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_completeness_check():
    guard = QualityGuard()
    
    print("🧪 테스트 1: 정상 케이스 (모든 목차 항목이 슬라이드로 존재)")
    mappings_success = [
        {"elementRole": "toc_item", "generatedText": "01. 분석 개요"},
        {"elementRole": "toc_item", "generatedText": "02. 분석 방법"},
        {"elementRole": "slide_title", "generatedText": "분석 개요"},
        {"elementRole": "slide_title", "generatedText": "분석 방법 및 절차"}, # 부분 일치 테스트
    ]
    result = guard.check_completeness(mappings_success)
    print(f"결과: {result['is_complete']} (Missing: {result['missing_items']})")
    assert result['is_complete'] == True
    print("✅ 통과\n")

    print("🧪 테스트 2: 누락 케이스 (활용 방안 슬라이드 없음)")
    mappings_fail = [
        {"elementRole": "toc_item", "generatedText": "01. 분석 개요"},
        {"elementRole": "toc_item", "generatedText": "02. 활용 방안"},
        {"elementRole": "slide_title", "generatedText": "분석 개요"},
        # 활용 방안 슬라이드 없음
    ]
    result = guard.check_completeness(mappings_fail)
    print(f"결과: {result['is_complete']} (Missing: {result['missing_items']})")
    assert result['is_complete'] == False
    assert "활용 방안" in result['missing_items']
    print("✅ 통과\n")

def test_stagnation_check():
    guard = QualityGuard()
    
    print("🧪 테스트 3: 정상 케이스 (데이터 정체 없음)")
    mappings_clean = [
        {"generatedText": "Actual Content", "originalText": "Click to add text"}
    ]
    result = guard.check_data_stagnation(mappings_clean)
    print(f"결과: {result['is_clean']} (Stagnant: {len(result['stagnant_items'])})")
    assert result['is_clean'] == True
    print("✅ 통과\n")
    
    print("🧪 테스트 4: 정체 케이스 (원본과 동일)")
    mappings_stagnant1 = [
        {"generatedText": "Click to add text", "originalText": "Click to add text"}
    ]
    result1 = guard.check_data_stagnation(mappings_stagnant1)
    print(f"결과: {result1['is_clean']} (Stagnant: {len(result1['stagnant_items'])})")
    assert result1['is_clean'] == False
    print("✅ 통과\n")

    print("🧪 테스트 5: 정체 케이스 (Placeholder 포함)")
    mappings_stagnant2 = [
        {"generatedText": "Some content with Lorem Ipsum inside", "originalText": "Empty"}
    ]
    result2 = guard.check_data_stagnation(mappings_stagnant2)
    print(f"결과: {result2['is_clean']} (Stagnant: {len(result2['stagnant_items'])})")
    assert result2['is_clean'] == False
    print("✅ 통과\n")

if __name__ == "__main__":
    test_completeness_check()
    test_stagnation_check()
