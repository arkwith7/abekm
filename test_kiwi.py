#!/usr/bin/env python3
"""
kiwipiepy 0.21.0 버전의 정확한 사용법 테스트
"""

def test_kiwi_import():
    """kiwipiepy import 및 기본 기능 테스트"""
    try:
        from kiwipiepy import Kiwi
        print("✅ Kiwi import 성공")
        
        # Kiwi 객체 생성
        kiwi = Kiwi()
        print("✅ Kiwi 객체 생성 성공")
        
        # tokenize 메서드의 시그니처 확인
        import inspect
        sig = inspect.signature(kiwi.tokenize)
        print(f"tokenize 메서드 시그니처: {sig}")
        
        # 간단한 텍스트로 테스트
        text = "안녕하세요. 웅진 지식관리시스템입니다."
        tokens = kiwi.tokenize(text)
        
        print(f"테스트 텍스트: {text}")
        print(f"토큰 개수: {len(tokens)}")
        print("토큰 정보:")
        for i, token in enumerate(tokens[:5]):  # 처음 5개만 출력
            print(f"  {i+1}. {token.form} ({token.tag})")
        
        return True
        
    except Exception as e:
        print(f"❌ Kiwi 테스트 실패: {e}")
        return False

def test_pyhwp_import():
    """pyhwp import 테스트"""
    try:
        import pyhwp
        print("✅ pyhwp import 성공")
        return True
    except Exception as e:
        print(f"❌ pyhwp import 실패: {e}")
        return False

def test_other_libraries():
    """다른 라이브러리들 테스트"""
    libraries = [
        'tiktoken',
        'sentence_transformers',
        'boto3'
    ]
    
    for lib in libraries:
        try:
            __import__(lib)
            print(f"✅ {lib} import 성공")
        except Exception as e:
            print(f"❌ {lib} import 실패: {e}")

if __name__ == "__main__":
    print("=== 한국어 처리 라이브러리 테스트 ===")
    print()
    
    print("1. Kiwi 테스트:")
    test_kiwi_import()
    print()
    
    print("2. pyhwp 테스트:")
    test_pyhwp_import()
    print()
    
    print("3. 기타 라이브러리 테스트:")
    test_other_libraries()
    print()
    
    print("테스트 완료!")
