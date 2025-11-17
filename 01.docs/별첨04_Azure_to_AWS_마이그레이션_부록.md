# 별첨04. Azure → AWS 클라우드 네이티브 마이그레이션 부록

본 부록은 01.system_overview_design.md에서 1~11장(현행 운영 관점) 이외의 마이그레이션/이관/설치/운영 상세를 체계적으로 재편성한 참고 자료입니다. 핵심 주제는 “이전 Azure 기반 지식관리시스템을 AWS 기반 클라우드 네이티브 지향 구조로 마이그레이션”입니다.

## A. Executive Summary

- 목표: 벤더 종속 최소화, 비용 효율, 한국어 품질 유지/향상, 운영 단순화
- 범위: 검색/RAG, 문서 처리, 인증/권한, 배포/모니터링, 데이터 이관
- 성과: pgvector 기반 하이브리드 검색, 다중 AI 공급자, 오픈소스 우선 문서 처리, JWT+SAP 권한, 컨테이너 기반 배포
- 품질 게이트: Recall@K, 답변 신뢰도, 응답시간 p95, Failover율, 비용 점유율

## B. Before/After 아키텍처 개요

- Legacy(Azure): Functions + AI Search + Azure OpenAI + Blob + MySQL + AD
- Target(AWS/OSS): FastAPI(Container) + PostgreSQL/pgvector + Bedrock(멀티) + S3/Local + JWT+SAP + Redis
- 다이어그램 및 상호 연동은 본문 2장 아키텍처를 기준으로 함

## C. 서비스 매핑 요약

- Azure Functions → FastAPI(Container)
- Azure AI Search → PostgreSQL + pgvector(1024차원)
- Azure OpenAI → 다중 공급자(우선 Bedrock) + 1536→1024 차원 축소
- Blob → S3/Local, Azure AD → JWT + SAP RFC
- 설치/운영 상세는 본 부록 H, I 참조

## D. 데이터/검색 이관

- AI Search 인덱스 → pgvector: content/main 이중 벡터, IVFFlat 인덱스, 한국어 FTS
- 하이브리드 검색 재현: 코사인 유사도 + 키워드, 리랭킹 및 캐시
- 품질 관리: Recall@K, CTR, Answer Relevance 배치 측정

## E. AI 공급자 전략

- 환경변수 기반 실시간 전환, 자동 Failover, Circuit Breaker
- 임베딩 차원 표준화(1024), 1536/3072→1024 스마트 축소, 손실 <10% 목표

## F. 문서 처리 전환

- Doc Intelligence → LibreOffice/오픈소스 + Textract(스캔/이미지)
- HWP/HWPX 처리 경로, 캐시 및 폰트/로케일 요구사항 정리

## G. 인증/권한/감사

- Azure AD → JWT + SAP RFC, RBAC/감사 로그 동등 수준 유지
- 컨테이너 스코프 필터와 세션/검색 단계 이중 적용

## H. 배포/운영 변경점

- Functions → 컨테이너(Compose→K8s 확장 경로)
- 구조화 로그, Prometheus/Grafana, Slack/Webhook 경보

---

아래부터는 원 문서 하단에 존재하던 상세 가이드를 부록으로 이관한 내용입니다. 필요 시 섹션 링크로 건너뛰어 활용하세요.

### H-1. Debian 12 필수 패키지 및 LibreOffice 설치

```bash
sudo apt-get update
sudo apt-get install -y libreoffice libreoffice-java-common \
  libreoffice-writer libreoffice-calc libreoffice-impress \
  default-jre fonts-liberation
```

설치 확인
```bash
which libreoffice
which soffice
libreoffice --version
```

### H-2. 한국어 폰트/로케일

```bash
sudo apt-get install -y locales \
  fonts-nanum fonts-nanum-coding fonts-nanum-extra \
  fonts-baekmuk fonts-unfonts-core fonts-unfonts-extra
sudo sed -i '/ko_KR.UTF-8/s/^# //g' /etc/locale.gen
sudo locale-gen
sudo update-locale LANG=ko_KR.UTF-8
sudo fc-cache -f -v
```

환경변수 예시(Python 서비스):
```python
env.update({
  'LANG': 'ko_KR.UTF-8',
  'LC_ALL': 'ko_KR.UTF-8',
  'FONTCONFIG_FILE': '/etc/fonts/fonts.conf',
  'FONTCONFIG_PATH': '/etc/fonts/conf.d',
})
```

### H-3. Office 변환 서비스 스펙

지원 확장자 예시:
```python
supported_extensions = {
  '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.odt', '.ods', '.odp', '.rtf'
}
```
리소스 기준: 메모리 512MB+, 임시디스크 1GB+, 동시변환 8, 타임아웃 60s, 변경시각 캐시 무효화

### H-4. Docker 예시(한국어/LibreOffice)

```dockerfile
FROM python:3.11-slim-bookworm
RUN apt-get update && apt-get install -y \
  libreoffice libreoffice-java-common libreoffice-writer \
  libreoffice-calc libreoffice-impress default-jre \
  fonts-nanum fonts-nanum-coding fonts-unfonts-core locales \
  && sed -i '/ko_KR.UTF-8/s/^# //g' /etc/locale.gen \
  && locale-gen && fc-cache -f -v \
  && apt-get clean && rm -rf /var/lib/apt/lists/*
ENV LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8 \
  FONTCONFIG_FILE=/etc/fonts/fonts.conf \
  FONTCONFIG_PATH=/etc/fonts/conf.d
RUN mkdir -p /app/cache/pdf_conversions && chmod 755 /app/cache/pdf_conversions
```

### H-5. 파일 뷰어 문제 해결 체크리스트

- 폰트 누락 → fonts-nanum 재설치, fc-cache
- 로케일 누락 → ko_KR.UTF-8 생성, LANG/LC_ALL 적용
- 권한 문제 → 변환 캐시 디렉토리 권한/소유자 점검
- 메모리 부족 → 스왑 생성(1GB 권장)
- Java 오류 → default-jre 재설치

### H-6. 수동 변환 테스트

```bash
cd /home/admin/wkms-aws/backend/uploads
libreoffice --headless --convert-to pdf --outdir /tmp sample.docx
ls -la /tmp/*.pdf
```

---

## I. 마이그레이션 매핑/전략 세부

### I-1. 매핑 테이블(요약)

- Functions → FastAPI/uvicorn (공통 API)
- AI Search → PostgreSQL + pgvector 0.5.0+
- Azure OpenAI → Bedrock/Azure/OpenAI 다중 공급자, 실시간 전환
- Blob → S3/Local, MySQL → PostgreSQL, AD → JWT+SAP

### I-2. 동적 다중 공급자 매핑

- LLM: Bedrock Claude ↔ Azure GPT-4o-mini ↔ OpenAI GPT-4o (Env 전환)
- 임베딩: Titan V2(1024) ↔ ada-002(1536→1024) ↔ (3-large 3072→1024)
- 벡터 스토어: pgvector(1024) 표준화

### I-3. 한국어 처리 통합 전략

- tiktoken 토큰화, kiwipiepy 형태소, Bedrock 고급 분석 보완

---

## J. 통합 DB/검색 설계 발췌

- tb_search_documents: content/main 이중 벡터, 한국어 FTS 인덱스, 패싯 인덱스
- 하이브리드 검색 쿼리/리랭킹/필터 요지

## K. API/처리 파이프라인 발췌

- 문서 업로드/대용량 처리 전략, 채팅/검색 RAG 처리 흐름 요지

## L. 보안/운영

- JWT/권한 스코프, 감사 로그, CORS/RateLimit, 관측성/경보

## M. 품질/비용

- KPI 표, 모니터링 수집 구조, 회귀 방지 루프, 비용 최적화 요지

---

본 부록은 운영 변화에 따라 적시에 업데이트되며, 본문(1~11장)의 현행 설명과 상충 시 본문을 우선합니다.
