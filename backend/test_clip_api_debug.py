"""Azure CLIP API 상세 디버깅 스크립트

Azure ML 엔드포인트 스키마 및 응답 분석
"""
import asyncio
import httpx
import base64
from PIL import Image
import io
import os
import json
from dotenv import load_dotenv

load_dotenv()

ENDPOINT = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_ENDPOINT")
API_KEY = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_API_KEY")
DEPLOYMENT = os.getenv("AZURE_OPENAI_MULTIMODAL_DEPLOYMENT")

print("="*80)
print("Azure CLIP API 디버깅 정보")
print("="*80)
print(f"Endpoint: {ENDPOINT}")
print(f"Deployment: {DEPLOYMENT}")
print(f"API Key: {'✓ ' + API_KEY[:20] + '...' if API_KEY else '✗ 미설정'}")
print(f"API Key 길이: {len(API_KEY) if API_KEY else 0}")
print("="*80)

async def test_endpoint_metadata():
    """엔드포인트 메타데이터 확인"""
    print("\n[1] 엔드포인트 메타데이터 확인")
    print("-" * 60)
    
    async with httpx.AsyncClient() as client:
        # Swagger/OpenAPI 정보 시도
        swagger_urls = [
            f"{ENDPOINT}/swagger.json",
            f"{ENDPOINT}/openapi.json",
            f"{ENDPOINT}?op=swagger",
        ]
        
        for url in swagger_urls:
            try:
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    print(f"✅ Swagger 발견: {url}")
                    print(json.dumps(response.json(), indent=2)[:500])
                    return
            except Exception:
                pass
        
        print("❌ Swagger/OpenAPI 정보 없음")

async def test_simple_get():
    """간단한 GET 요청"""
    print("\n[2] GET 요청 테스트")
    print("-" * 60)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(ENDPOINT, timeout=10.0)
            print(f"상태 코드: {response.status_code}")
            print(f"응답 헤더: {dict(response.headers)}")
            print(f"응답 본문: {response.text[:200]}")
        except Exception as e:
            print(f"❌ GET 요청 실패: {e}")

async def test_text_minimal():
    """최소 텍스트 요청"""
    print("\n[3] 최소 텍스트 요청 테스트")
    print("-" * 60)
    
    payloads = [
        # 형식 1: Azure ML 표준 형식
        {
            "input_data": {
                "columns": ["text"],
                "data": [["테스트"]]
            }
        },
        # 형식 2: CLIP 특화 형식
        {
            "inputs": {
                "text": ["테스트"]
            }
        },
        # 형식 3: OpenAI 스타일
        {
            "input": "테스트"
        },
        # 형식 4: 배열 직접
        ["테스트"],
        # 형식 5: Batch 형식
        {
            "data": [
                {
                    "text": "테스트"
                }
            ]
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for i, payload in enumerate(payloads, 1):
            print(f"\n형식 {i}: {type(payload).__name__}")
            print(f"Payload: {json.dumps(payload, ensure_ascii=False)[:100]}")
            
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
                
                print(f"✅ 상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅✅ 성공! 응답 타입: {type(result)}")
                    print(f"응답: {json.dumps(result, ensure_ascii=False)[:200]}")
                    return i, payload, result
                else:
                    print(f"응답: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ 예외: {type(e).__name__}: {str(e)[:100]}")
    
    return None, None, None

async def test_image_minimal():
    """최소 이미지 요청"""
    print("\n[4] 최소 이미지 요청 테스트")
    print("-" * 60)
    
    # 작은 테스트 이미지 생성 (10x10)
    img = Image.new('RGB', (10, 10), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_base64 = base64.b64encode(img_bytes.getvalue()).decode('utf-8')
    
    print(f"이미지 크기: 10x10 픽셀")
    print(f"Base64 길이: {len(img_base64)} 문자")
    
    payloads = [
        # 형식 1: Azure ML 표준
        {
            "input_data": {
                "columns": ["image"],
                "data": [[img_base64]]
            }
        },
        # 형식 2: CLIP 특화
        {
            "inputs": {
                "image": [img_base64]
            }
        },
        # 형식 3: Base64 직접
        {
            "image": img_base64
        },
        # 형식 4: 배열
        [img_base64],
        # 형식 5: Batch
        {
            "data": [
                {
                    "image": img_base64
                }
            ]
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for i, payload in enumerate(payloads, 1):
            print(f"\n형식 {i}:")
            print(f"Payload keys: {payload.keys() if isinstance(payload, dict) else 'list'}")
            
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
                
                print(f"✅ 상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅✅ 성공! 응답 타입: {type(result)}")
                    print(f"응답: {str(result)[:200]}")
                    return i, payload, result
                else:
                    print(f"응답: {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ 예외: {type(e).__name__}: {str(e)[:100]}")
    
    return None, None, None

async def test_authentication():
    """인증 방식 테스트"""
    print("\n[5] 인증 방식 테스트")
    print("-" * 60)
    
    payload = {
        "input_data": {
            "columns": ["text"],
            "data": [["테스트"]]
        }
    }
    
    auth_methods = [
        ("Bearer", f"Bearer {API_KEY}"),
        ("직접", API_KEY),
        ("api-key 헤더", None, {"api-key": API_KEY}),
        ("azureml-model-deployment", None, {"azureml-model-deployment": DEPLOYMENT}),
    ]
    
    async with httpx.AsyncClient() as client:
        for name, auth_value, extra_headers in [(a[0], a[1], a[2] if len(a) > 2 else {}) for a in auth_methods]:
            print(f"\n인증 방식: {name}")
            
            headers = {
                "Content-Type": "application/json",
            }
            
            if auth_value:
                headers["Authorization"] = auth_value
            
            if extra_headers:
                headers.update(extra_headers)
            
            try:
                response = await client.post(
                    ENDPOINT,
                    headers=headers,
                    json=payload,
                    timeout=30.0
                )
                
                print(f"상태: {response.status_code}")
                if response.status_code == 200:
                    print(f"✅✅ 성공! 인증 방식: {name}")
                    return name
                else:
                    print(f"응답: {response.text[:100]}")
                    
            except Exception as e:
                print(f"❌ 예외: {str(e)[:100]}")
    
    return None

async def test_content_type():
    """Content-Type 테스트"""
    print("\n[6] Content-Type 테스트")
    print("-" * 60)
    
    payload = {
        "input_data": {
            "columns": ["text"],
            "data": [["테스트"]]
        }
    }
    
    content_types = [
        "application/json",
        "application/json; charset=utf-8",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]
    
    async with httpx.AsyncClient() as client:
        for ct in content_types:
            print(f"\nContent-Type: {ct}")
            
            try:
                response = await client.post(
                    ENDPOINT,
                    headers={
                        "Content-Type": ct,
                        "Authorization": f"Bearer {API_KEY}"
                    },
                    json=payload if "json" in ct else None,
                    data=json.dumps(payload) if "json" not in ct else None,
                    timeout=30.0
                )
                
                print(f"상태: {response.status_code}")
                if response.status_code == 200:
                    print(f"✅✅ 성공! Content-Type: {ct}")
                    return ct
                else:
                    print(f"응답: {response.text[:100]}")
                    
            except Exception as e:
                print(f"❌ 예외: {str(e)[:100]}")
    
    return None

async def main():
    print("\n\n")
    print("="*80)
    print("Azure CLIP API 상세 디버깅 시작")
    print("="*80)
    
    if not ENDPOINT or not API_KEY:
        print("❌ 환경 변수 설정 확인 필요:")
        print(f"   - AZURE_OPENAI_MULTIMODAL_EMBEDDING_ENDPOINT: {'✓' if ENDPOINT else '✗'}")
        print(f"   - AZURE_OPENAI_MULTIMODAL_EMBEDDING_API_KEY: {'✓' if API_KEY else '✗'}")
        return
    
    # 1. 엔드포인트 메타데이터
    await test_endpoint_metadata()
    
    # 2. 간단한 GET
    await test_simple_get()
    
    # 3. 텍스트 요청
    text_format, text_payload, text_result = await test_text_minimal()
    
    # 4. 이미지 요청
    image_format, image_payload, image_result = await test_image_minimal()
    
    # 5. 인증 방식
    auth_method = await test_authentication()
    
    # 6. Content-Type
    content_type = await test_content_type()
    
    # 결과 요약
    print("\n\n")
    print("="*80)
    print("디버깅 결과 요약")
    print("="*80)
    
    if text_format:
        print(f"✅ 텍스트 성공 형식: #{text_format}")
        print(f"   Payload: {json.dumps(text_payload, ensure_ascii=False)[:100]}")
    else:
        print("❌ 텍스트: 모든 형식 실패")
    
    if image_format:
        print(f"✅ 이미지 성공 형식: #{image_format}")
    else:
        print("❌ 이미지: 모든 형식 실패")
    
    if auth_method:
        print(f"✅ 성공 인증 방식: {auth_method}")
    else:
        print("❌ 인증: 모든 방식 실패")
    
    if content_type:
        print(f"✅ 성공 Content-Type: {content_type}")
    
    print("\n" + "="*80)
    print("권장 조치:")
    print("="*80)
    print("1. Azure Portal → Machine Learning Studio → Endpoints 확인")
    print("2. 배포 상태 및 로그 확인")
    print("3. 스코어링 스크립트(score.py) 검토")
    print("4. 모델 입력 스키마 확인")
    print(f"5. 엔드포인트: {ENDPOINT}")

if __name__ == "__main__":
    asyncio.run(main())
