"""Azure CLIP API 테스트 스크립트 - 디버깅용

Azure ML 스코어링 엔드포인트의 정확한 요청 형식 확인
"""
import asyncio
import httpx
import base64
from PIL import Image
import io
import os
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_ENDPOINT")
API_KEY = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_API_KEY")

async def test_text_request_format():
    """텍스트 요청 형식 테스트"""
    
    test_formats = [
        # 형식 1: input_data with columns and data
        {
            "input_data": {
                "columns": ["text"],
                "data": [["파란색 자동차"]]
            }
        },
        # 형식 2: input_data with index
        {
            "input_data": {
                "columns": ["text"],
                "index": [0],
                "data": [["파란색 자동차"]]
            }
        },
        # 형식 3: 직접 데이터
        {
            "data": [["파란색 자동차"]]
        },
        # 형식 4: 텍스트 배열
        {
            "text": ["파란색 자동차"]
        },
        # 형식 5: 입력 필드
        {
            "input": "파란색 자동차"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for i, payload in enumerate(test_formats, 1):
            print(f"\n{'='*60}")
            print(f"텍스트 형식 {i} 테스트:")
            print(f"Payload: {payload}")
            print(f"{'='*60}")
            
            try:
                response = await client.post(
                    ENDPOINT,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}"
                    },
                    json=payload,
                    timeout=30.0
                )
                
                print(f"✅ 상태 코드: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 성공! 응답: {result}")
                    return i, payload, result
                else:
                    print(f"❌ 오류: {response.text}")
                    
            except Exception as e:
                print(f"❌ 예외 발생: {str(e)}")
    
    return None, None, None

async def test_image_request_format():
    """이미지 요청 형식 테스트"""
    
    # 테스트 이미지 생성
    img = Image.new('RGB', (100, 100), color='blue')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    
    test_formats = [
        # 형식 1: input_data with columns and data
        {
            "input_data": {
                "columns": ["image"],
                "data": [[img_base64]]
            }
        },
        # 형식 2: input_data with index
        {
            "input_data": {
                "columns": ["image"],
                "index": [0],
                "data": [[img_base64]]
            }
        },
        # 형식 3: 직접 데이터
        {
            "data": [[img_base64]]
        },
        # 형식 4: 이미지 배열
        {
            "image": [img_base64]
        },
        # 형식 5: 입력 필드
        {
            "input": img_base64
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for i, payload in enumerate(test_formats, 1):
            print(f"\n{'='*60}")
            print(f"이미지 형식 {i} 테스트:")
            print(f"Payload keys: {list(payload.keys())}")
            print(f"{'='*60}")
            
            try:
                response = await client.post(
                    ENDPOINT,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}"
                    },
                    json=payload,
                    timeout=30.0
                )
                
                print(f"✅ 상태 코드: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 성공! 응답 타입: {type(result)}")
                    if isinstance(result, list):
                        print(f"   응답 길이: {len(result)}")
                        if result and isinstance(result[0], list):
                            print(f"   임베딩 차원: {len(result[0])}")
                    return i, payload, result
                else:
                    print(f"❌ 오류: {response.text}")
                    
            except Exception as e:
                print(f"❌ 예외 발생: {str(e)}")
    
    return None, None, None

async def main():
    print("="*80)
    print("Azure CLIP API 요청 형식 디버깅")
    print("="*80)
    print(f"Endpoint: {ENDPOINT}")
    print(f"API Key: {'✓ 설정됨' if API_KEY else '✗ 미설정'}")
    
    # 텍스트 요청 테스트
    print("\n\n" + "="*80)
    print("📝 텍스트 임베딩 요청 형식 테스트")
    print("="*80)
    text_format, text_payload, text_result = await test_text_request_format()
    
    # 이미지 요청 테스트
    print("\n\n" + "="*80)
    print("🖼️ 이미지 임베딩 요청 형식 테스트")
    print("="*80)
    image_format, image_payload, image_result = await test_image_request_format()
    
    # 결과 요약
    print("\n\n" + "="*80)
    print("📊 테스트 결과 요약")
    print("="*80)
    
    if text_format:
        print(f"✅ 텍스트 성공 형식: #{text_format}")
        print(f"   Payload: {text_payload}")
    else:
        print("❌ 텍스트: 모든 형식 실패")
    
    if image_format:
        print(f"✅ 이미지 성공 형식: #{image_format}")
        print(f"   Payload keys: {list(image_payload.keys())}")
    else:
        print("❌ 이미지: 모든 형식 실패")

if __name__ == "__main__":
    asyncio.run(main())
