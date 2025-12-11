import logging
import re
from typing import List, Dict, Any, Set, Optional, Tuple

logger = logging.getLogger(__name__)


class QualityGuard:
    """
    PPT 생성 품질을 검증하는 에이전트 (Critic).
    
    주요 기능:
    1. 완결성 검증 (Completeness): 목차(TOC)와 본문 슬라이드 일치 여부 확인
    2. 데이터 정체 감지 (Data Stagnation): 템플릿 원본 데이터/플레이스홀더 잔존 확인
    3. 도메인 적합성 (Domain Relevance): 주제와 무관한 텍스트 확인
    
    v3.6: 테이블/다이어그램 원본 데이터 감지 강화
    """
    
    # 흔한 템플릿 도메인 키워드 (주제와 무관한 데이터 감지용)
    TEMPLATE_DOMAIN_KEYWORDS = {
        # 의료/헬스케어 관련 (확장)
        'medical': [
            '인슐린', '혈당', 'cgm', 'emr', 'fhir', '의료', '병원', '환자', '처방', '진료',
            '펌프', '펌웨어', 'ieee', 'sdc', '프로파일', '전자의무기록', '당뇨',
            '혈압', '심박', '산소포화도', '투여', '주입', '카테터', 'hl7',
        ],
        # 스마트폰/앱 관련  
        'mobile': ['모바일 앱', '앱 다운로드', 'ios', 'android', '스마트폰'],
        # 전자제품 사양 (단독 사용 시에만 감지)
        'specs': ['mah', 'usb-c', '블루투스', 'bluetooth', 'nfc'],
        # 일반 플레이스홀더
        'placeholder': ['lorem ipsum', 'sample text', '샘플 텍스트', 'placeholder'],
    }
    
    # 테이블 데이터에서 템플릿 원본 데이터를 나타내는 패턴
    TABLE_TEMPLATE_PATTERNS = [
        r'\d+\s*[xX×]\s*\d+\s*[xX×]\s*\d+\s*mm',  # 크기: 78x48x18mm
        r'\d+\s*g\b',                              # 무게: 78g
        r'\d+\s*u\b',                              # 용량: 200U
        r'ipx\d+',                                 # 방수: IPX8
        r'usb-?c',                                 # USB-C
        r'ota\s*\(',                               # OTA(서명 검증)
        r'인슐린\s*저장',                          # 인슐린 저장 용량
        r'방수\s*등급',                            # 방수 등급
        r'배터리\s*수명',                          # 배터리 수명
    ]
    
    def check_completeness(self, mappings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        목차(TOC) 항목이 실제 슬라이드로 생성되었는지 검증합니다.
        
        Args:
            mappings: AI가 생성한 매핑 리스트
            
        Returns:
            {
                "is_complete": bool,
                "missing_items": List[str],  # 누락된 목차 항목
                "toc_items": List[str],      # 감지된 목차 항목
                "slide_titles": List[str]    # 감지된 슬라이드 제목
            }
        """
        toc_items = []
        slide_titles = set()
        
        # 1. 매핑 데이터 분석
        for m in mappings:
            role = m.get('elementRole', '')
            text = m.get('generatedText', '') or m.get('newContent', '')
            
            if not text or not isinstance(text, str):
                continue
                
            # 목차 항목 수집
            if role == 'toc_item':
                # "01. 분석 개요" -> "분석 개요" 정규화
                clean_text = self._normalize_text(text)
                if clean_text:
                    toc_items.append(clean_text)
            
            # 슬라이드 제목 수집 (main_title, slide_title)
            elif role in ['main_title', 'slide_title', 'title']:
                clean_text = self._normalize_text(text)
                if clean_text:
                    slide_titles.add(clean_text)
                    
        # 2. 누락 항목 검사
        missing_items = []
        for item in toc_items:
            # 목차 항목이 슬라이드 제목 집합에 포함되어 있는지 확인
            # 완전 일치 또는 부분 일치 허용 (예: "분석 개요" in "1. 분석 개요")
            is_found = False
            for title in slide_titles:
                if item in title or title in item:
                    is_found = True
                    break
            
            if not is_found:
                missing_items.append(item)
                
        is_complete = len(missing_items) == 0
        
        if not is_complete:
            logger.warning(f"🚨 [QualityGuard] 슬라이드 누락 감지: {missing_items}")
        else:
            logger.info(f"✅ [QualityGuard] 완결성 검증 통과 (목차 {len(toc_items)}개 일치)")
            
        return {
            "is_complete": is_complete,
            "missing_items": missing_items,
            "toc_items": toc_items,
            "slide_titles": list(slide_titles)
        }

    def _normalize_text(self, text: str) -> str:
        """텍스트 정규화 (번호, 공백 제거)"""
        import re
        # 1. 숫자+점 제거 ("01. 개요" -> " 개요")
        text = re.sub(r'^\d+[\.\)]\s*', '', text)
        # 2. 앞뒤 공백 제거
        return text.strip()

    def check_data_stagnation(
        self, 
        mappings: List[Dict[str, Any]],
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        템플릿의 기본 데이터나 플레이스홀더가 그대로 남아있는지 검사합니다.
        
        v3.6 개선:
        - 테이블/다이어그램 요소의 템플릿 원본 데이터 감지 강화
        - 도메인 불일치 키워드 감지 (의료 템플릿의 데이터가 자동차 주제에 남아있는 경우)
        - 🆕 isEnabled=False인 요소도 검사 (미매핑으로 원본 유지된 경우)
        
        Args:
            mappings: AI가 생성한 매핑 리스트
            user_query: 사용자 요청 (도메인 컨텍스트 추출용)
            
        Returns:
            {
                "is_clean": bool,
                "stagnant_items": List[Dict],  # 문제가 되는 매핑 항목들
                "domain_mismatch_items": List[Dict]  # 도메인 불일치 항목들
            }
        """
        stagnant_items = []
        domain_mismatch_items = []
        
        # 사용자 쿼리에서 주제 키워드 추출
        query_keywords = self._extract_query_keywords(user_query) if user_query else set()
        
        # 템플릿 흔한 플레이스홀더 패턴 (영어/한글)
        placeholders = [
            "Click to add title", "Click to add text", "Lorem ipsum", 
            "Text placeholder", "Chart Title", "Series 1", "Category 1",
            "제목을 입력하세요", "텍스트를 입력하세요", "차트 제목"
        ]
        
        for m in mappings:
            gen_text = str(m.get('generatedText', '') or '').strip()
            orig_text = str(m.get('originalText', '') or '').strip()
            elem_id = m.get('elementId', '')
            role = m.get('elementRole', 'unknown')
            object_type = m.get('objectType', 'textbox')
            is_enabled = m.get('isEnabled', True)
            
            # 🆕 v3.6: isEnabled=False인 경우 (미매핑으로 원본 유지)
            # 이 경우 originalText에 템플릿 원본이 있고, 그게 그대로 유지될 것
            if not is_enabled and orig_text:
                has_issue = False
                
                # 테이블 패턴 검사 (먼저 실행 - 더 구체적)
                if object_type == 'table' or elem_id.startswith('table-'):
                    for pattern in self.TABLE_TEMPLATE_PATTERNS:
                        if re.search(pattern, orig_text.lower()):
                            stagnant_items.append({
                                "reason": "unmapped_table_template_data",
                                "elementId": elem_id,
                                "elementRole": role,
                                "objectType": object_type,
                                "pattern": pattern,
                                "text": orig_text[:80],
                                "is_enabled": False
                            })
                            has_issue = True
                            break
                
                # 원본 텍스트가 사용자 쿼리와 도메인 불일치인지 검사
                if not has_issue and query_keywords:
                    mismatch = self._check_domain_mismatch(orig_text, query_keywords)
                    if mismatch:
                        domain_mismatch_items.append({
                            "reason": "unmapped_domain_mismatch",
                            "elementId": elem_id,
                            "elementRole": role,
                            "objectType": object_type,
                            "detected_domain": mismatch['domain'],
                            "keywords_found": mismatch['keywords'],
                            "text": orig_text[:80],
                            "is_enabled": False
                        })
                        
                continue  # isEnabled=False면 이후 검사 스킵
            
            if not gen_text:
                continue

            # 1. 원본 텍스트와 100% 일치하는 경우
            if orig_text and gen_text == orig_text:
                # 숫자로만 된건 무시 (페이지 번호 등)
                if gen_text.isdigit():
                    continue
                # 짧은 단어 무시 (단, 테이블/다이어그램 제외)
                if len(gen_text) < 4 and object_type not in ['table', 'shape']:
                    continue
                    
                stagnant_items.append({
                    "reason": "same_as_template",
                    "elementId": elem_id,
                    "elementRole": role,
                    "objectType": object_type,
                    "text": gen_text[:50]
                })
                continue
            
            # 2. 플레이스홀더 텍스트가 포함된 경우
            for ph in placeholders:
                if ph.lower() in gen_text.lower():
                    stagnant_items.append({
                        "reason": "contains_placeholder",
                        "elementId": elem_id,
                        "elementRole": role,
                        "placeholder": ph
                    })
                    break
            
            # 3. 🆕 테이블 원본 데이터 패턴 검사
            if object_type == 'table' or elem_id.startswith('table-'):
                for pattern in self.TABLE_TEMPLATE_PATTERNS:
                    if re.search(pattern, gen_text.lower()):
                        stagnant_items.append({
                            "reason": "table_template_data",
                            "elementId": elem_id,
                            "elementRole": role,
                            "pattern": pattern,
                            "text": gen_text[:50]
                        })
                        break
            
            # 4. 🆕 도메인 불일치 키워드 감지
            if query_keywords:
                mismatch = self._check_domain_mismatch(gen_text, query_keywords)
                if mismatch:
                    domain_mismatch_items.append({
                        "reason": "domain_mismatch",
                        "elementId": elem_id,
                        "elementRole": role,
                        "detected_domain": mismatch['domain'],
                        "keywords_found": mismatch['keywords'],
                        "text": gen_text[:50]
                    })
                    
        is_clean = len(stagnant_items) == 0 and len(domain_mismatch_items) == 0
        
        if not is_clean:
            logger.warning(f"🚨 [QualityGuard] 데이터 정체(Stagnation) 감지: {len(stagnant_items)}건, 도메인 불일치: {len(domain_mismatch_items)}건")
            
        return {
            "is_clean": is_clean,
            "stagnant_items": stagnant_items,
            "domain_mismatch_items": domain_mismatch_items
        }
    
    def _extract_query_keywords(self, query: str) -> Set[str]:
        """사용자 쿼리에서 주제 키워드 추출"""
        if not query:
            return set()
        
        # 한국어 명사 추출 (간단한 패턴 매칭)
        # 복잡한 형태소 분석 대신 주요 키워드만 추출
        keywords = set()
        
        # 2음절 이상 한글 단어 추출
        korean_words = re.findall(r'[가-힣]{2,}', query)
        keywords.update(korean_words)
        
        # 영문 단어 추출 (3자 이상)
        english_words = re.findall(r'[a-zA-Z]{3,}', query.lower())
        keywords.update(english_words)
        
        return keywords
    
    def _check_domain_mismatch(
        self, 
        text: str, 
        query_keywords: Set[str]
    ) -> Optional[Dict[str, Any]]:
        """
        텍스트가 사용자 쿼리 도메인과 불일치하는지 검사
        
        예: 사용자가 "자동차 특허분석"을 요청했는데 
            텍스트에 "인슐린", "EMR", "FHIR" 등 의료 키워드가 있으면 불일치
        """
        text_lower = text.lower()
        
        # 각 템플릿 도메인별로 키워드 검사
        for domain, keywords in self.TEMPLATE_DOMAIN_KEYWORDS.items():
            found_keywords = []
            for kw in keywords:
                if kw.lower() in text_lower:
                    # 사용자 쿼리에 해당 키워드가 있으면 정상
                    if kw.lower() in {q.lower() for q in query_keywords}:
                        continue
                    found_keywords.append(kw)
            
            if found_keywords:
                return {
                    "domain": domain,
                    "keywords": found_keywords
                }
        
        return None
    
    def get_stagnant_element_ids(
        self, 
        stagnation_result: Dict[str, Any]
    ) -> List[str]:
        """
        데이터 정체 검사 결과에서 문제가 있는 elementId 목록 추출
        (재생성 대상 식별용)
        """
        element_ids = []
        
        for item in stagnation_result.get('stagnant_items', []):
            elem_id = item.get('elementId')
            if elem_id:
                element_ids.append(elem_id)
        
        for item in stagnation_result.get('domain_mismatch_items', []):
            elem_id = item.get('elementId')
            if elem_id and elem_id not in element_ids:
                element_ids.append(elem_id)
        
        return element_ids
