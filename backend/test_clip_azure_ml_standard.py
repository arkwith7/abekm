"""Azure ML 공식 예제 기반 CLIP API 테스트

Azure ML 문서의 표준 형식을 사용한 정확한 테스트
"""
import urllib.request
import json
import base64
import os
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_MULTIMODAL_EMBEDDING_API_KEY")

print("="*80)
print("Azure ML 공식 형식 CLIP API 테스트")
print("="*80)
print(f"URL: {url}")
print(f"API Key: {'✓ ' + api_key[:20] + '...' if api_key else '✗ 미설정'}")
print("="*80)

if not api_key:
    raise Exception("A key should be provided to invoke the endpoint")

def test_request(data, test_name="테스트"):
    """표준 요청 함수"""
    print(f"\n{'='*60}")
    print(f"{test_name}")
    print(f"{'='*60}")
    print(f"Request Data: {json.dumps(data, ensure_ascii=False)[:200]}...")
    
    body = str.encode(json.dumps(data))
    
    # Azure ML 표준 헤더 (Accept 헤더 추가)
    headers = {
        'Content-Type': 'application/json', 
        'Accept': 'application/json',
        'Authorization': ('Bearer ' + api_key)
    }
    
    req = urllib.request.Request(url, body, headers)
    
    try:
        response = urllib.request.urlopen(req)
        result = response.read()
        result_json = json.loads(result.decode('utf-8'))
        
        print(f"✅✅ 성공!")
        print(f"응답 타입: {type(result_json)}")
        print(f"응답 내용: {json.dumps(result_json, ensure_ascii=False)[:300]}")
        
        # 임베딩 차원 확인
        if isinstance(result_json, list):
            if len(result_json) > 0:
                if isinstance(result_json[0], list):
                    print(f"임베딩 차원: {len(result_json[0])}d")
                else:
                    print(f"임베딩 차원: {len(result_json)}d")
        elif isinstance(result_json, dict):
            if 'output' in result_json:
                print(f"임베딩 차원: {len(result_json['output'][0]) if result_json['output'] else 'N/A'}")
        
        return True, result_json
        
    except urllib.error.HTTPError as error:
        print(f"❌ 실패 - 상태 코드: {error.code}")
        print(f"\n헤더 정보:")
        print(error.info())
        print(f"\n에러 상세:")
        error_detail = error.read().decode("utf8", 'ignore')
        print(error_detail)
        
        return False, None

# 테스트 1: 빈 데이터 (스키마 확인용)
print("\n\n[테스트 1] 빈 데이터 - 스키마 오류 메시지 확인")
test_request({}, "빈 데이터")

# 테스트 2: 텍스트 임베딩 - 다양한 형식
print("\n\n[테스트 2] 텍스트 임베딩 - 다양한 형식")

text_formats = [
    # 형식 1: Azure ML 표준 (columns + data)
    {
        "input_data": {
            "columns": ["text"],
            "data": [["파란색 자동차"]]
        }
    },
    # 형식 2: index 추가
    {
        "input_data": {
            "columns": ["text"],
            "index": [0],
            "data": [["파란색 자동차"]]
        }
    },
    # 형식 3: 배열 형식
    {
        "input_data": {
            "columns": ["text"],
            "data": ["파란색 자동차"]
        }
    },
    # 형식 4: 단일 문자열
    {
        "input_data": {
            "text": "파란색 자동차"
        }
    },
    # 형식 5: inputs 키
    {
        "inputs": {
            "text": "파란색 자동차"
        }
    },
]

successful_text_format = None
for i, data in enumerate(text_formats, 1):
    success, result = test_request(data, f"텍스트 형식 {i}")
    if success:
        successful_text_format = (i, data, result)
        break

# 테스트 3: 이미지 임베딩 - 다양한 형식
print("\n\n[테스트 3] 이미지 임베딩 - 다양한 형식")

# 작은 테스트 이미지 생성
img = Image.new('RGB', (100, 100), color='blue')
img_bytes_io = io.BytesIO()
img.save(img_bytes_io, format='PNG')
img_base64 = base64.b64encode(img_bytes_io.getvalue()).decode('utf-8')

print(f"이미지 Base64 길이: {len(img_base64)}")

image_formats = [
    # 형식 1: Azure ML 표준
    {
        "input_data": {
            "columns": ["image"],
            "data": [[img_base64]]
        }
    },
    # 형식 2: index 추가
    {
        "input_data": {
            "columns": ["image"],
            "index": [0],
            "data": [[img_base64]]
        }
    },
    # 형식 3: 배열 형식
    {
        "input_data": {
            "columns": ["image"],
            "data": [img_base64]
        }
    },
    # 형식 4: 단일 이미지
    {
        "input_data": {
            "image": img_base64
        }
    },
    # 형식 5: inputs 키
    {
        "inputs": {
            "image": img_base64
        }
    },
]

successful_image_format = None
for i, data in enumerate(image_formats, 1):
    success, result = test_request(data, f"이미지 형식 {i}")
    if success:
        successful_image_format = (i, data, result)
        break

# 테스트 4: 멀티모달 (텍스트 + 이미지 동시)
print("\n\n[테스트 4] 멀티모달 (텍스트 + 이미지)")

multimodal_formats = [
    # 형식 1: 두 개의 columns
    {
        "input_data": {
            "columns": ["text", "image"],
            "data": [["파란색 자동차", img_base64]]
        }
    },
    # 형식 2: 별도 필드
    {
        "input_data": {
            "text": "파란색 자동차",
            "image": img_base64
        }
    },
]

successful_multimodal_format = None
for i, data in enumerate(multimodal_formats, 1):
    success, result = test_request(data, f"멀티모달 형식 {i}")
    if success:
        successful_multimodal_format = (i, data, result)
        break

# 결과 요약
print("\n\n")
print("="*80)
print("테스트 결과 요약")
print("="*80)

if successful_text_format:
    print(f"✅ 텍스트 성공 형식: #{successful_text_format[0]}")
    print(f"   데이터: {json.dumps(successful_text_format[1], ensure_ascii=False)[:150]}")
else:
    print("❌ 텍스트: 모든 형식 실패")

if successful_image_format:
    print(f"✅ 이미지 성공 형식: #{successful_image_format[0]}")
    print(f"   데이터 구조: {list(successful_image_format[1].keys())}")
else:
    print("❌ 이미지: 모든 형식 실패")

if successful_multimodal_format:
    print(f"✅ 멀티모달 성공 형식: #{successful_multimodal_format[0]}")
else:
    print("❌ 멀티모달: 모든 형식 실패")

print("\n" + "="*80)
print("권장 조치")
print("="*80)

if not (successful_text_format or successful_image_format):
    print("⚠️ Azure ML 엔드포인트에 문제가 있습니다.")
    print("\n다음을 확인하세요:")
    print("1. Azure Portal → Machine Learning Studio")
    print("2. Endpoints → 'openai-clip-image-text-embed-11'")
    print("3. Deployment logs 및 Details 탭 확인")
    print("4. 스코어링 스크립트 (score.py) 검토")
    print("\n가능한 원인:")
    print("- 모델 배포 실패")
    print("- 스코어링 스크립트 오류")
    print("- 입력 스키마 불일치")
    print("- 모델 파일 손상")
    print("\n대안:")
    print("- 로컬 CLIP 모델 사용 (Hugging Face)")
    print("- OpenAI CLIP API 사용")
    print("- Azure Computer Vision API 사용")
else:
    print("✅ 성공한 형식을 image_embedding_service.py에 적용하세요!")
