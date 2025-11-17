# PPT 생성 기능 테스트 가이드

## 📋 현재 시스템 상태

업데이트된 PPT 생성 기능의 주요 개선사항:

### ✅ 완료된 개선사항
1. **템플릿 메타데이터 시스템**
   - 템플릿 구조 분석 및 JSON 저장
   - 슬라이드 레이아웃, 도형 위치, 폰트 정보 추출
   - 현재 등록된 템플릿: 2개 (제품소개서 샘플 + 비즈니스 기본)

2. **스타일 보존 시스템**
   - 템플릿의 원본 폰트 색상 유지 (흰색 텍스트 → 검은색 변경 문제 해결)
   - 폰트 크기, 볼드, 이탤릭 스타일 보존
   - TOC/목차 슬라이드의 스타일 정확성 향상

3. **템플릿 관리 개선**
   - 중복 템플릿 정리 (기존 7개 → 2개 의미있는 템플릿)
   - 품질 등급 시스템 (professional/standard/basic)
   - 동적 템플릿 분석 및 썸네일 생성

## 🧪 테스트 시나리오

### 1. 기본 시스템 상태 확인

```bash
cd /home/admin/wkms-aws/backend && source ../.venv/bin/activate

# 1-1. 템플릿 목록 확인
python -c "
from app.services.presentation.ppt_template_manager import template_manager
templates = template_manager.list_templates()
print(f'등록된 템플릿: {len(templates)}개')
for t in templates:
    print(f'  - {t[\"name\"]} ({t[\"quality_level\"]}, {t[\"slide_count\"]}개 슬라이드)')
"

# 1-2. 메타데이터 상태 확인
ls -la /home/admin/wkms-aws/backend/uploads/templates/metadata/
```

### 2. 템플릿 기반 PPT 생성 테스트

#### 2-1. 프론트엔드 UI 테스트
1. **브라우저에서 접속**: `http://localhost:3000`
2. **로그인** 후 채팅 인터페이스 이용
3. **테스트 쿼리 입력**:
   ```
   제품소개서 PPT를 만들어주세요
   
   1. 제품 개요
   - AI 기반 지식관리 시스템
   - 문서 자동 분류 및 검색
   - 실시간 협업 지원
   
   2. 기술 사양
   - AWS Bedrock 활용
   - PostgreSQL + pgvector
   - React/TypeScript 프론트엔드
   
   3. 주요 기능
   - 자연어 검색
   - 문서 자동 태깅
   - 워크플로우 관리
   ```

4. **PPT 아웃라인 보기** 버튼 클릭
5. **템플릿 선택**: "제품소개서 샘플" 선택
6. **PPT 생성** 후 다운로드하여 확인

#### 2-2. API 직접 테스트

```bash
# 2-2-1. 아웃라인 생성 테스트
curl -X POST "http://localhost:8000/api/v1/chat/presentation/outline" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "user_query": "제품소개서 PPT 만들어주세요",
    "context_text": "AI 기반 지식관리 시스템입니다. 1. 제품 개요 - 자동 문서 분류, 2. 기술 사양 - AWS Bedrock 활용, 3. 주요 기능 - 자연어 검색",
    "template_style": "business",
    "include_charts": true,
    "presentation_type": "general"
  }'

# 2-2-2. 템플릿 목록 조회
curl -X GET "http://localhost:8000/api/v1/chat/presentation/templates" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2-2-3. PPT 빌드 테스트
curl -X POST "http://localhost:8000/api/v1/chat/presentation/build" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "outline": {
      "topic": "제품소개서",
      "max_slides": 5,
      "slides": [
        {
          "title": "제품 개요",
          "key_message": "AI 기반 지식관리 시스템",
          "bullets": ["자동 문서 분류", "실시간 검색", "협업 지원"],
          "layout": "title-and-content"
        }
      ]
    },
    "custom_template_path": "/home/admin/wkms-aws/backend/uploads/templates/clean_제품소개서 샘플.pptx"
  }'
```

### 3. 스타일 보존 테스트

#### 3-1. 흰색 텍스트 보존 테스트
- **목적**: 어두운 배경의 템플릿에서 흰색 텍스트가 검은색으로 변경되지 않는지 확인
- **방법**:
  1. "제품소개서 샘플" 템플릿 사용
  2. 제목과 본문에 텍스트 입력
  3. 생성된 PPT에서 텍스트 색상 확인
- **예상 결과**: 원본 템플릿의 흰색 텍스트 색상 유지

#### 3-2. 목차(TOC) 스타일 테스트
- **목적**: 목차 슬라이드에서 각 항목의 스타일이 올바르게 적용되는지 확인
- **방법**:
  1. 번호가 있는 구조화된 내용으로 PPT 생성
  2. 두 번째 슬라이드(목차)의 스타일 확인
- **예상 결과**: 템플릿의 원본 폰트 색상/크기 유지

### 4. 메타데이터 활용 테스트

```bash
# 4-1. 메타데이터 추출 테스트
python -c "
from app.services.presentation.simple_template_extractor import simple_template_extractor
from pathlib import Path

template_path = '/home/admin/wkms-aws/backend/uploads/templates/제품소개서 샘플.pptx'
metadata = simple_template_extractor.extract_basic_metadata(template_path, '테스트_템플릿')
print(f'슬라이드 수: {metadata[\"total_slides\"]}')
print(f'전체 도형 수: {sum(len(s[\"shapes\"]) for s in metadata[\"slides\"])}')
"

# 4-2. 레이아웃 정보 활용 테스트
python -c "
from app.services.presentation.simple_template_extractor import simple_template_extractor

layout_info = simple_template_extractor.get_slide_layout_info('제품소개서_샘플', 0)
if layout_info:
    print(f'텍스트 플레이스홀더: {len(layout_info.get(\"text_placeholders\", []))}')
    print(f'이미지 플레이스홀더: {len(layout_info.get(\"image_placeholders\", []))}')
    print(f'디자인 요소: {len(layout_info.get(\"design_elements\", []))}')
"
```

### 5. 성능 및 안정성 테스트

#### 5-1. 대용량 내용 처리 테스트
```bash
python -c "
import asyncio
from app.services.presentation.enhanced_ppt_generator_service import enhanced_ppt_generator_service

# 긴 내용으로 테스트
long_content = '''
1. 시스템 개요
AI 기반 지식관리 플랫폼으로 기업의 모든 문서와 지식을 효율적으로 관리합니다.

2. 핵심 기술
- AWS Bedrock을 통한 고성능 AI 추론
- PostgreSQL과 pgvector를 활용한 벡터 검색
- React/TypeScript 기반 현대적 UI/UX

3. 주요 기능
- 자연어 기반 문서 검색
- 자동 문서 분류 및 태깅
- 실시간 협업 워크플로우
- 다국어 지원 (한국어, 영어)

4. 기술 아키텍처
- 마이크로서비스 기반 설계
- Docker 컨테이너 배포
- Redis 캐싱 시스템
- 확장 가능한 클라우드 인프라
''' * 3  # 3배 반복으로 대용량 테스트

async def test():
    result = await enhanced_ppt_generator_service.generate_enhanced_outline(
        '대용량 제품소개서', long_content, 'bedrock'
    )
    print(f'생성된 슬라이드 수: {len(result.slides)}')
    
asyncio.run(test())
"
```

#### 5-2. 다양한 템플릿 스타일 테스트
```bash
python -c "
import asyncio
from app.services.presentation.enhanced_ppt_generator_service import enhanced_ppt_generator_service

test_content = '1. 개요\n- 주요 기능\n- 특징\n2. 상세\n- 구현 방법\n- 결과'

async def test_styles():
    styles = ['business', 'minimal', 'modern', 'playful']
    for style in styles:
        result = await enhanced_ppt_generator_service.generate_enhanced_outline(
            f'{style} 스타일 테스트', test_content, 'bedrock', template_style=style
        )
        print(f'{style}: {len(result.slides)}개 슬라이드')
        
asyncio.run(test_styles())
"
```

## 🔍 검증 포인트

### 1. 템플릿 적용 검증
- [ ] 템플릿 목록 정상 로드 (2개 템플릿)
- [ ] 메타데이터 JSON 파일 존재 확인
- [ ] 템플릿 기반 PPT 생성 성공

### 2. 스타일 보존 검증
- [ ] 원본 템플릿의 흰색 텍스트 유지
- [ ] 폰트 크기 및 스타일 보존
- [ ] 목차 슬라이드 스타일 정확성

### 3. 기능성 검증
- [ ] 구조화된 내용의 슬라이드 분할
- [ ] 목차 자동 생성
- [ ] 차트/테이블 데이터 처리
- [ ] 다양한 레이아웃 적용

### 4. 성능 검증
- [ ] 대용량 내용 처리 (5초 이내)
- [ ] 메모리 사용량 안정성
- [ ] 동시 요청 처리 능력

## 🐛 알려진 문제 및 해결책

### 1. 메타데이터 추출 실패
- **현상**: `No module named 'pptx.shapes.table'` 오류
- **영향**: 동적 템플릿 분석 실패하지만 기본 분석으로 폴백
- **해결책**: 현재 simple_template_extractor로 우회 중

### 2. 템플릿 파일 경로
- **현상**: backend/uploads/templates 경로 사용
- **확인**: 실제 파일 존재 여부 체크 필요
- **해결책**: 자동 경로 탐지 및 폴백 로직 구현됨

## 📊 테스트 결과 예시

```
✅ 시스템 상태: 정상
📋 등록된 템플릿: 2개
  - 제품소개서 샘플 (professional, 9개 슬라이드)
  - 비즈니스 기본 (professional, 9개 슬라이드)
📄 메타데이터: 43.1KB (제품소개서_샘플_metadata.json)
🎯 스타일 보존: 정상 작동
📐 레이아웃 정보: 활용 가능
```

## 🚀 다음 단계

### Step 3: UI 개선 (예정)
- PresentationOutlineModal에서 템플릿 미리보기
- 슬라이드별 레이아웃 선택 기능
- 메타데이터 기반 편집 힌트

### Step 4: 지능형 템플릿 적용 (예정)
- 내용 유형별 자동 레이아웃 선택
- 차트/테이블 감지 및 최적 배치
- 템플릿 추천 시스템

---

**업데이트 일시**: 2025-08-22
**테스트 환경**: Docker + FastAPI + React
**주요 개선**: 스타일 보존 + 메타데이터 시스템
