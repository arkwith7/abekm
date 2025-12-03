# Archived Presentation Services

이 디렉토리에는 현재 사용되지 않는 레거시 프레젠테이션 서비스들이 보관되어 있습니다.

## 아카이브된 파일 목록

### 1. `quick_html_presentation_service.py`
- **기능**: DeckSpec으로부터 HTML 기반 슬라이드 덱 생성
- **아카이브 사유**: 사용되지 않음 (grep 검색 결과 0건)
- **대체**: PPTX 기반 생성만 사용 중

### 2. `enhanced_ppt_generator_service.py`
- **기능**: 고급 PPT 생성 서비스 (DeckSpec 기반)
- **아카이브 사유**: `app.agents.tools.presentation_tools.py`에서만 사용되며, 해당 파일도 사용되지 않음
- **대체**: `quick_ppt_generator_service.py`, `templated_ppt_generator_service.py` 사용

### 3. `pptx_template_analyzer.py`
- **기능**: PPTX 템플릿 구조 분석
- **아카이브 사유**: `dynamic_template_manager.py`에서만 사용되며, 해당 매니저도 archived tool에서만 참조됨
- **대체**: `ppt_template_manager.py` 사용

### 4. `template_metadata_extractor.py`
- **기능**: 템플릿 메타데이터 추출
- **아카이브 사유**: 사용되지 않음 (grep 검색 결과 0건)
- **대체**: `ppt_template_manager.py`의 내장 메타데이터 처리

## 현재 활성 서비스

### Core Services (활성)
- `quick_ppt_generator_service.py` - Quick PPT 생성 (API 및 도구에서 사용)
- `templated_ppt_generator_service.py` - Template PPT 생성 (API 및 도구에서 사용)
- `ppt_template_manager.py` - 템플릿 관리 (전체 시스템에서 사용)
- `ppt_models.py` - 데이터 모델 (전체 시스템에서 사용)

### Supporting Services (활성)
- `thumbnail_generator.py` - 썸네일 생성 (API에서 사용)
- `template_migration_service.py` - 템플릿 마이그레이션 (API에서 사용)
- `template_debugger.py` - 템플릿 디버깅 (API에서 사용)
- `template_content_cleaner.py` - 템플릿 콘텐츠 정리 (ppt_template_manager에서 사용)
- `enhanced_object_processor.py` - PPT 객체 처리 (archived assembly_tools에서 사용)

### Partially Active (아카이브 고려 대상)
- `dynamic_template_manager.py` - archived tool에서만 사용됨
- `product_template_manager.py` - archived tool에서만 사용됨

## 복원 방법

아카이브된 서비스가 필요한 경우:

1. **파일 이동**:
```bash
cd /home/admin/Dev/abekm/backend/app/services/presentation
mv archived/<service_name>.py .
```

2. **Import 경로 업데이트**:
```python
# Before
from app.services.presentation.archived.<service_name> import ...

# After
from app.services.presentation.<service_name> import ...
```

3. **의존성 확인**: 아카이브된 다른 파일들과의 의존성 확인 필요

## 참고사항

- 아카이브된 서비스들은 하위 호환성을 위해 유지되고 있습니다
- 완전 삭제 전 최소 6개월 유지 권장
- 프로덕션 환경에서 사용되지 않는 것이 확인되었습니다
