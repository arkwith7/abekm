# 웅진 WKMS 초기 데이터 설정 가이드

## 통합 완료된 마스터 스크립트

새로 생성된 **`init_woongjin_master.py`**가 최종 통합본입니다.

### 기본 실행 (기존 데이터 유지)
```bash
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python init_woongjin_master.py
```

### 완전 초기화 후 재설정 (기존 데이터 삭제)
```bash
cd /home/admin/wkms-aws/backend
source ../.venv/bin/activate
python init_woongjin_master.py --reset
```

## 제거 권장 파일들

이제 다음 파일들은 **중복되므로 제거 권장**:
- `complete_initial_data.py` (567라인)
- `init_database.py` (1160라인)  
- `init_database_backup.py` (181라인)

## 설정 완료 후 제공되는 로그인 계정

### 🔐 시스템 관리자
- Username: `admin`
- Password: `admin123!`
- 권한: 전체 시스템 관리

### 👥 부서별 관리자
- **인사팀장**: `hr.manager` / `hr123!`
- **기획팀장**: `planning` / `planning123!`
- **클라우드팀장**: `cloud` / `cloud123!`
- **MS서비스팀장**: `ms.service` / `ms123!`
- **인프라팀장**: `infra` / `infra123!`
- **Biz운영팀장**: `biz.ops` / `biz123!`

### 👤 팀별 담당자  
- **채용담당**: `recruit` / `recruit123!`
- **교육담당**: `training` / `training123!`

## 생성되는 조직구조

```
🏢 웅진
├── 📁 CEO직속
│   ├── 📁 인사전략팀
│   │   ├── 📁 채용팀
│   │   └── 📁 교육팀
│   └── 📁 기획팀
├── 📁 클라우드사업본부
│   ├── 📁 클라우드서비스팀
│   └── 📁 MS서비스팀
└── 📁 CTI사업본부
    ├── 📁 인프라컨설팅팀
    └── 📁 Biz운영1팀
```

## 포함되는 기능

✅ **SAP HR 정보** (9명의 직원 데이터)
✅ **사용자 계정** (9개 계정)
✅ **지식 컨테이너** (12개 조직 구조)
✅ **지식 카테고리** (4개 카테고리)
✅ **사용자 역할** (4단계 권한)
✅ **권한 할당** (RBAC 시스템)
✅ **샘플 문서** (3개 문서)

## 다음 단계

1. **API 서버 실행**
   ```bash
   cd /home/admin/wkms-aws/backend
   source ../.venv/bin/activate
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **API 문서 확인**: http://localhost:8000/docs

3. **프론트엔드 연동 테스트**

4. **파일 업로드 및 벡터 검색 테스트**
