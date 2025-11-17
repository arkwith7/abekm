"""
검색 성능 모니터링 및 개선 가이드
===================================

## 🚀 자연어 검색 개선 단계별 가이드

### 1단계: 즉시 적용 (완료)
- ✅ 자연어 쿼리 프로세서 추가
- ✅ 다중 키워드 검색 최적화  
- ✅ 검색 의도 파악 시스템

### 2단계: 검색 품질 향상 (권장)

#### A. 임계값 동적 조정
```python
# 사용자 쿼리 복잡도에 따른 임계값 자동 조정
def get_dynamic_threshold(query_analysis):
    if len(query_analysis.main_keywords) >= 3:
        return 0.4  # 복잡한 쿼리는 낮은 임계값
    elif query_analysis.intent == 'find_document':
        return 0.5  # 일반 검색
    else:
        return 0.6  # 단순 키워드
```

#### B. 검색 결과 리랭킹
```python
# 컨텍스트 기반 재정렬
def rerank_results(results, query_analysis):
    for result in results:
        # 도메인 일치도 보너스
        if any(kw in result['content'] for kw in query_analysis.context_keywords):
            result['final_score'] = result['similarity_score'] * 1.2
        
        # 최신성 보너스 (최근 문서 우선)
        file_age_days = get_file_age_days(result['file_path'])
        if file_age_days < 30:
            result['final_score'] *= 1.1
```

#### C. 사용자 피드백 학습
```python
# 검색 결과 클릭률 기반 개선
async def update_search_relevance(query, clicked_results):
    # 클릭된 문서의 키워드를 쿼리와 연관
    # 향후 동일한 키워드 검색 시 우선순위 상승
    pass
```

### 3단계: 고급 기능 (선택)

#### A. 의미적 쿼리 확장
```python
# GPT/Claude를 활용한 쿼리 확장
async def expand_query_with_llm(original_query):
    prompt = f'''
    다음 검색 쿼리를 분석하여 관련 키워드를 추천해주세요:
    "{original_query}"
    
    관련 키워드 (5개 이내):
    '''
    # LLM 호출하여 관련 키워드 생성
```

#### B. 검색 자동완성 개선
```python
# 실제 문서 내용 기반 자동완성
async def get_smart_suggestions(partial_query):
    # 기존 문서에서 빈도 높은 키워드 조합 추천
    # 사용자 검색 히스토리 반영
```

#### C. 개인화 검색
```python
# 사용자별 검색 선호도 학습
async def personalized_search(query, user_profile):
    # 사용자가 자주 클릭하는 문서 유형 우선
    # 부서별 맞춤 검색 결과
```

## 🔧 성능 모니터링 지표

### 검색 품질 KPI
1. **검색 성공률**: 결과가 반환된 쿼리 비율
2. **결과 관련성**: 사용자가 실제로 클릭한 결과 비율
3. **검색 응답 시간**: 평균 검색 처리 시간
4. **재검색률**: 동일 세션에서 쿼리를 수정한 비율

### 모니터링 SQL 쿼리 예시
```sql
-- 검색 성공률 추적
SELECT 
    DATE(created_at) as search_date,
    COUNT(*) as total_searches,
    COUNT(CASE WHEN result_count > 0 THEN 1 END) as successful_searches,
    (COUNT(CASE WHEN result_count > 0 THEN 1 END) * 100.0 / COUNT(*)) as success_rate
FROM search_history 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY search_date DESC;

-- 인기 검색어 분석
SELECT 
    query_text,
    COUNT(*) as search_count,
    AVG(result_count) as avg_results,
    AVG(user_click_count) as avg_clicks
FROM search_history 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY query_text
HAVING COUNT(*) >= 5
ORDER BY search_count DESC
LIMIT 20;
```

## 🎯 즉시 테스트 가능한 쿼리들

### 자연어 검색 테스트 케이스
1. **"제조 현장 로봇 도입 관련 문서 찾아줘"**
   - 기대 결과: 로봇, 제조, 현장, 도입 키워드 포함 문서

2. **"인사평가 정책이 어떻게 바뀌었는지 알려줘"**  
   - 기대 결과: 인사평가, 정책, 변경 관련 문서

3. **"Azure 클라우드 마이그레이션 계획 문서"**
   - 기대 결과: Azure, 클라우드, 마이그레이션 관련 문서

4. **"안전 관리 규정 최신 버전"**
   - 기대 결과: 안전, 관리, 규정 키워드와 최신성 고려

### 성능 개선 확인 방법
```bash
# 검색 응답 시간 측정
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:8000/api/v1/search" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query":"제조 현장 로봇 도입 관련 문서 찾아줘"}'

# 결과 품질 확인
# - 반환된 문서 수
# - 유사도 점수 분포  
# - 검색 처리 시간
```

## 📈 기대 효과

### Before (기존)
- ❌ "제조 현장 로봇 도입 관련 문서 찾아줘" → 검색 실패
- ❌ 정확한 키워드만 인식
- ❌ 자연어 이해 불가

### After (개선 후)  
- ✅ "제조 현장 로봇 도입 관련 문서 찾아줘" → 관련 문서 검색 성공
- ✅ 핵심 키워드 자동 추출: [제조, 현장, 로봇, 도입]
- ✅ 동의어 확장: [manufacturing, 생산, automation, 설치]
- ✅ 검색 의도 파악: find_document
- ✅ 다중 검색 방식 조합으로 정확도 향상

## 🚨 주의사항

1. **성능 모니터링**: 자연어 처리 추가로 검색 시간 증가 가능
2. **메모리 사용량**: 확장 키워드로 인한 메모리 사용 증가
3. **정확도 검증**: 초기에는 기존 키워드 검색과 병행 필요
4. **사용자 피드백**: 검색 결과 품질에 대한 사용자 만족도 조사 필요

## 📞 기술 지원

문제 발생 시 다음 로그 확인:
- `backend/logs/search_service.log`
- `backend/logs/natural_language_processor.log`

검색 디버깅 모드 활성화:
```python
# search_service.py에서 로그 레벨 변경
logger.setLevel(logging.DEBUG)
```
""
