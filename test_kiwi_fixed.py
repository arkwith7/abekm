#!/usr/bin/env python3
"""
수정된 Korean NLP Service 테스트
"""

def test_kiwi_stopwords():
    """kiwipiepy.utils.Stopwords 테스트"""
    try:
        from kiwipiepy import Kiwi
        from kiwipiepy.utils import Stopwords
        
        print("✅ kiwipiepy.utils.Stopwords import 성공")
        
        # Stopwords 객체 생성
        stopwords = Stopwords()
        print("✅ Stopwords 객체 생성 성공")
        
        # Kiwi 객체 생성
        kiwi = Kiwi()
        print("✅ Kiwi 객체 생성 성공")
        
        # 불용어를 사용한 토큰화 테스트
        text = "안녕하세요. 웅진 지식관리시스템의 문서를 처리합니다."
        
        # 불용어 없이 토큰화
        tokens_without_stopwords = kiwi.tokenize(text)
        print(f"불용어 제거 전 토큰 수: {len(tokens_without_stopwords)}")
        
        # 불용어 적용하여 토큰화
        tokens_with_stopwords = kiwi.tokenize(text, stopwords=stopwords)
        print(f"불용어 제거 후 토큰 수: {len(tokens_with_stopwords)}")
        
        print("\n불용어 제거 전 토큰:")
        for token in tokens_without_stopwords:
            print(f"  {token.form} ({token.tag})")
            
        print("\n불용어 제거 후 토큰:")
        for token in tokens_with_stopwords:
            print(f"  {token.form} ({token.tag})")
        
        return True
        
    except Exception as e:
        print(f"❌ Stopwords 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pyhwp_again():
    """pyhwp 재테스트"""
    try:
        import pyhwp
        print("✅ pyhwp import 성공")
        print(f"pyhwp 위치: {pyhwp.__file__}")
        return True
    except Exception as e:
        print(f"❌ pyhwp import 실패: {e}")
        return False

if __name__ == "__main__":
    print("=== 수정된 Korean NLP Service 테스트 ===")
    print()
    
    print("1. kiwipiepy Stopwords 테스트:")
    test_kiwi_stopwords()
    print()
    
    print("2. pyhwp 재테스트:")
    test_pyhwp_again()
    print()
    
    print("테스트 완료!")
