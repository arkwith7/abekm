# 📈 업로드 성능 개선 가이드 (실전 적용)

**작성일**: 2025-10-14  
**대상 파일**: 27페이지 PDF (12MB, 80K자)  
**현재 소요 시간**: 98초 → **목표: 3초 이내**

---

## 🔴 현재 문제점

### 처리 시간 분석

- **총 소요**: 98.21초
- **Azure DI 분석**: 75초 (76%) ← 가장 큰 병목
- **임베딩 생성**: 21초 (21%) ← 두 번째 병목
- **기타**: 2초 (2%)

### 사용자 경험 문제

❌ **98초 동안 브라우저가 멈춰있음**  
❌ 업로드 진행 상황을 알 수 없음  
❌ 실패 시 처음부터 다시 시도

---

## ✅ 해결책: 비동기 처리 (즉시 적용 가능)

### 개선 후 흐름

```
[현재] 동기식 처리
클라이언트 → 업로드 → DI(75초) → 임베딩(21초) → 응답
                      ↓
                98초 대기... 😰

[개선] 비동기 처리
클라이언트 → 업로드 → 즉시 응답 (2초) ✅
                    ↓
              백그라운드 처리 (사용자는 다른 작업 가능)
                - DI 분석
                - 임베딩 생성
                - 상태: processing → completed
```

---

## 🚀 구현 방법 (3단계)

### Step 1: 문서 상태 관리 추가

#### 1-1. DB 스키마 업데이트

```sql
-- tb_file_bss_info 테이블에 컬럼 추가
ALTER TABLE tb_file_bss_info 
ADD COLUMN processing_status VARCHAR(20) DEFAULT 'pending',
ADD COLUMN processing_error TEXT,
ADD COLUMN processing_started_at TIMESTAMP,
ADD COLUMN processing_completed_at TIMESTAMP;

-- 인덱스 추가 (상태별 조회 성능 향상)
CREATE INDEX idx_file_processing_status ON tb_file_bss_info(processing_status);
```

**상태값:**
- `pending`: 업로드 완료, 처리 대기
- `processing`: 처리 중
- `completed`: 처리 완료
- `failed`: 처리 실패

#### 1-2. 모델 업데이트

```python
# backend/app/models/document/file_models.py

class TbFileBssInfo(Base):
    # ... 기존 컬럼 ...
    
    # 비동기 처리 상태 관리
    processing_status = Column(String(20), default='pending')
    processing_error = Column(Text, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
```

---

### Step 2: 백그라운드 작업 큐 설정

#### 2-1. Celery 설치 및 설정

```bash
# 필요한 패키지 설치
pip install celery redis
```

#### 2-2. Celery 앱 설정

```python
# backend/app/core/celery_app.py (새 파일)

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "wkms",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/0"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Seoul',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1시간 제한
)
```

#### 2-3. 환경변수 추가

```bash
# .env 파일
REDIS_HOST=localhost
REDIS_PORT=6379
```

---

### Step 3: 비동기 처리 태스크 구현

#### 3-1. Celery 태스크 생성

```python
# backend/app/tasks/document_tasks.py (새 파일)

from celery import Task
from app.core.celery_app import celery_app
from app.core.database import get_async_session_local
from app.models import TbFileBssInfo
from app.services.document.multimodal_document_service import multimodal_document_service
from sqlalchemy import select, update
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """상태 업데이트를 자동으로 처리하는 커스텀 Task"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """작업 실패 시 상태 업데이트"""
        document_id = args[0] if args else kwargs.get('document_id')
        if document_id:
            self.update_status(document_id, 'failed', str(exc))
    
    def update_status(self, document_id, status, error=None):
        """문서 처리 상태 업데이트 (동기)"""
        import asyncio
        asyncio.run(self._update_status_async(document_id, status, error))
    
    async def _update_status_async(self, document_id, status, error):
        async_session_factory = get_async_session_local()
        async with async_session_factory() as session:
            update_data = {'processing_status': status}
            if error:
                update_data['processing_error'] = error
            if status == 'processing':
                update_data['processing_started_at'] = datetime.now()
            elif status in ('completed', 'failed'):
                update_data['processing_completed_at'] = datetime.now()
            
            stmt = (
                update(TbFileBssInfo)
                .where(TbFileBssInfo.file_bss_info_sno == document_id)
                .values(**update_data)
            )
            await session.execute(stmt)
            await session.commit()


@celery_app.task(bind=True, base=CallbackTask, name='process_document_async')
def process_document_async(self, document_id: int, file_path: str, container_id: str, user_emp_no: str):
    """
    문서 비동기 처리 (DI 분석 + 임베딩)
    
    Args:
        document_id: 문서 ID
        file_path: 파일 경로
        container_id: 컨테이너 ID
        user_emp_no: 사용자 사번
    """
    import asyncio
    
    logger.info(f"🔄 [ASYNC-TASK] 문서 처리 시작: ID={document_id}")
    
    # 상태를 processing으로 변경
    self.update_status(document_id, 'processing')
    
    try:
        # 비동기 함수 실행
        result = asyncio.run(
            _process_document_multimodal(document_id, file_path, container_id, user_emp_no)
        )
        
        if result.get('success'):
            self.update_status(document_id, 'completed')
            logger.info(f"✅ [ASYNC-TASK] 문서 처리 완료: ID={document_id}")
            return {
                'success': True,
                'document_id': document_id,
                'chunks_count': result.get('chunks_count', 0),
                'embeddings_count': result.get('embeddings_count', 0)
            }
        else:
            error_msg = result.get('error', '알 수 없는 오류')
            self.update_status(document_id, 'failed', error_msg)
            logger.error(f"❌ [ASYNC-TASK] 문서 처리 실패: ID={document_id}, {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except Exception as e:
        error_msg = str(e)
        self.update_status(document_id, 'failed', error_msg)
        logger.error(f"💥 [ASYNC-TASK] 문서 처리 예외: ID={document_id}, {error_msg}")
        raise


async def _process_document_multimodal(document_id: int, file_path: str, container_id: str, user_emp_no: str):
    """멀티모달 파이프라인 실행"""
    async_session_factory = get_async_session_local()
    async with async_session_factory() as session:
        result = await multimodal_document_service.process_document_multimodal(
            file_path=file_path,
            file_bss_info_sno=document_id,
            container_id=container_id,
            user_emp_no=user_emp_no,
            session=session,
            provider="azure",
            model_profile="default"
        )
        return result
```

---

### Step 4: 업로드 엔드포인트 수정

```python
# backend/app/api/v1/documents.py

from app.tasks.document_tasks import process_document_async

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    container_id: Optional[str] = Form(...),
    use_multimodal: bool = Form(True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    문서 업로드 (비동기 처리)
    
    1. 파일 업로드 및 기본 정보 저장 (2초)
    2. 백그라운드에서 DI 분석 + 임베딩 처리 (90초+)
    3. 즉시 응답 반환
    """
    upload_start_time = datetime.now()
    
    try:
        # ... 권한 확인, 파일 검증 (기존 코드 유지) ...
        
        # 파일 저장 (로컬 + Azure Blob)
        saved_file_path = await _save_upload_file(file)
        
        # Azure Blob 업로드
        # ... (기존 코드 유지) ...
        
        # ✅ DB에 기본 정보만 저장 (RAG 파이프라인 제외)
        file_bss_info = TbFileBssInfo(
            drcy_sno=1,
            file_dtl_info_sno=file_dtl_info.file_dtl_info_sno,
            file_lgc_nm=file_name,
            file_psl_nm=file_name,
            file_extsn=file_extension.lstrip('.'),
            path=db_file_path,
            knowledge_container_id=container_id,
            owner_emp_no=user_emp_no,
            created_by=user_emp_no,
            last_modified_by=user_emp_no,
            processing_status='pending',  # 🆕 처리 대기 상태
            korean_metadata={"file_hash": file_hash, "file_size": file_size}
        )
        
        session.add(file_bss_info)
        await session.flush()
        await session.commit()
        
        document_id = file_bss_info.file_bss_info_sno
        
        logger.info(f"✅ [UPLOAD] 문서 기본 정보 저장 완료: ID={document_id}")
        
        # 🚀 백그라운드 작업 등록
        if use_multimodal:
            task = process_document_async.delay(
                document_id=document_id,
                file_path=saved_file_path,
                container_id=container_id,
                user_emp_no=str(user.emp_no)
            )
            logger.info(f"🔄 [UPLOAD] 백그라운드 작업 등록: task_id={task.id}, doc_id={document_id}")
        
        processing_time = (datetime.now() - upload_start_time).total_seconds()
        
        # 📤 즉시 응답 반환 (2-3초 이내)
        response = DocumentUploadResponse(
            success=True,
            message="문서가 업로드되었습니다. 백그라운드에서 처리 중입니다.",
            document_id=document_id,
            file_info={
                "original_name": safe_filename,
                "file_size": file_size,
                "file_type": file_extension,
                "upload_time": upload_start_time.isoformat(),
                "saved_path": db_file_path,
            },
            processing_stats={
                "upload_time": processing_time,
                "status": "processing",  # 🆕 처리 상태
                "message": "백그라운드에서 문서를 분석하고 있습니다."
            }
        )
        
        # 로컬 임시 파일 정리
        if (s3_object_key or azure_blob_object_key) and os.path.exists(saved_file_path):
            os.remove(saved_file_path)
        
        logger.info(f"📤 [UPLOAD] 즉시 응답 반환: doc_id={document_id}, 소요={processing_time:.2f}초")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [UPLOAD] 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### Step 5: 상태 조회 엔드포인트 추가

```python
# backend/app/api/v1/documents.py

@router.get("/{document_id}/status", summary="문서 처리 상태 조회")
async def get_document_status(
    document_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    """
    문서 처리 상태 조회
    
    Returns:
        - status: pending | processing | completed | failed
        - progress: 진행률 (0-100)
        - error: 오류 메시지 (실패 시)
    """
    stmt = select(TbFileBssInfo).where(TbFileBssInfo.file_bss_info_sno == document_id)
    result = await session.execute(stmt)
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    
    status = getattr(doc, 'processing_status', 'unknown')
    
    # 진행률 계산
    progress = 0
    if status == 'pending':
        progress = 0
    elif status == 'processing':
        # 처리 시작 후 경과 시간 기반 추정
        started = getattr(doc, 'processing_started_at', None)
        if started:
            elapsed = (datetime.now() - started).total_seconds()
            progress = min(int((elapsed / 100) * 100), 95)  # 최대 95%
        else:
            progress = 10
    elif status == 'completed':
        progress = 100
    elif status == 'failed':
        progress = 0
    
    return {
        "document_id": document_id,
        "status": status,
        "progress": progress,
        "error": getattr(doc, 'processing_error', None),
        "started_at": getattr(doc, 'processing_started_at', None),
        "completed_at": getattr(doc, 'processing_completed_at', None)
    }
```

---

## 🖥️ 프론트엔드 연동

### 폴링 방식 (간단)

```javascript
// 파일 업로드
async function uploadFile(file, containerId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('container_id', containerId);
  
  // 1. 업로드 (2-3초)
  const response = await fetch('/api/v1/documents/upload', {
    method: 'POST',
    body: formData
  });
  
  const result = await response.json();
  const documentId = result.document_id;
  
  // 2. 상태 폴링 (3초마다)
  const checkStatus = setInterval(async () => {
    const statusRes = await fetch(`/api/v1/documents/${documentId}/status`);
    const status = await statusRes.json();
    
    console.log(`처리 진행률: ${status.progress}%`);
    
    if (status.status === 'completed') {
      clearInterval(checkStatus);
      alert('문서 처리 완료!');
      refreshDocumentList();
    } else if (status.status === 'failed') {
      clearInterval(checkStatus);
      alert(`처리 실패: ${status.error}`);
    }
  }, 3000);
}
```

---

## 🏃 실행 방법

### 1. Redis 설치 및 실행

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:latest
```

### 2. Celery Worker 실행

```bash
# 터미널 1: Celery Worker
cd backend
celery -A app.core.celery_app worker --loglevel=info

# 터미널 2: FastAPI 서버
uvicorn app.main:app --reload
```

### 3. Celery Flower (모니터링 - 선택)

```bash
pip install flower
celery -A app.core.celery_app flower --port=5555

# 브라우저에서 http://localhost:5555 접속
```

---

## 📊 개선 효과

### Before (동기 처리)

- ❌ 업로드 대기: **98초**
- ❌ 브라우저 멈춤
- ❌ 진행 상황 불명확

### After (비동기 처리)

- ✅ 업로드 응답: **2-3초**
- ✅ 사용자는 즉시 다른 작업 가능
- ✅ 상태 조회로 진행 상황 확인
- ✅ 실패 시 재시도 쉬움

---

## 🔧 추가 최적화 (선택사항)

### 1. 임베딩 배치 처리

현재 48개 청크를 순차 처리하는 대신 배치로 처리:

```python
# 순차 (현재): 48 * 0.43초 = 20.76초
# 배치 (개선): 3 batch * 2초 = 6초

# 배치 크기 16개로 설정
for i in range(0, len(chunks), 16):
    batch = chunks[i:i+16]
    embeddings = await nlp_service.generate_embeddings_batch(batch)
```

### 2. WebSocket 실시간 진행률

폴링 대신 WebSocket으로 실시간 진행 상황 전송:

```python
# backend/app/api/v1/websocket.py
@router.websocket("/ws/document/{document_id}")
async def document_progress_websocket(websocket: WebSocket, document_id: int):
    await websocket.accept()
    
    while True:
        status = await get_document_status(document_id)
        await websocket.send_json(status)
        
        if status['status'] in ('completed', 'failed'):
            break
        
        await asyncio.sleep(2)
```

---

## ✅ 체크리스트

배포 전 확인사항:

- [ ] Redis 서버 실행 중
- [ ] Celery Worker 실행 중
- [ ] DB 스키마 업데이트 완료
- [ ] 환경변수 설정 (REDIS_HOST, REDIS_PORT)
- [ ] 프론트엔드 폴링 로직 구현
- [ ] 에러 처리 및 로깅 확인
- [ ] 테스트 업로드 완료

---

## 📝 다음 단계

1. **즉시**: 비동기 처리 구현 (위 가이드 따라하기)
2. **1주일 후**: 임베딩 배치 처리 최적화
3. **2주일 후**: WebSocket 실시간 진행률 구현
4. **1개월 후**: Azure DI 대신 경량 OCR 고려 (Tesseract + PyMuPDF)

---

**작성자**: AI Assistant  
**버전**: 1.0  
**최종 수정**: 2025-10-14
