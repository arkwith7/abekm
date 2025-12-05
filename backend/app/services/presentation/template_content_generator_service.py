from typing import List, Dict, Any, Optional
import json
from loguru import logger
from app.services.core.ai_service import ai_service
from app.services.presentation.ppt_template_manager import template_manager


class TemplateContentGeneratorService:
    """
    템플릿 구조를 기반으로 맞춤형 콘텐츠를 생성하는 서비스.
    (Template-First Approach with Agentic AI)
    
    핵심 개선:
    1. RAG 검색을 통한 관련 문서 컨텍스트 수집
    2. 채팅 히스토리 활용
    3. 도구 기반 컨텍스트 빌딩
    """

    async def generate_content_for_template(
        self,
        template_id: str,
        user_query: str,
        context: str = "",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        container_ids: Optional[List[str]] = None,
        use_rag: bool = True
    ) -> Dict[str, Any]:
        """
        템플릿의 메타데이터를 분석하여, 해당 구조에 딱 맞는 콘텐츠를 생성합니다.
        
        Agentic AI 파이프라인:
        1. RAG 검색으로 관련 문서 컨텍스트 수집
        2. 채팅 히스토리에서 추가 컨텍스트 추출
        3. 템플릿 구조 분석
        4. LLM을 통한 콘텐츠 생성
        """
        # 1. 템플릿 메타데이터 로드
        metadata = await self._load_template_metadata(template_id, user_id)
        if not metadata:
            raise ValueError(f"Template not found: {template_id}")

        slides = metadata.get("slides", [])
        template_name = metadata.get("name", template_id)
        
        logger.info(f"📊 PPT 콘텐츠 생성 시작: template={template_name}, slides={len(slides)}, use_rag={use_rag}")
        
        # 2. Agentic AI: 컨텍스트 수집 (RAG + 채팅 히스토리)
        enriched_context = await self._build_enriched_context(
            user_query=user_query,
            base_context=context,
            session_id=session_id,
            container_ids=container_ids,
            use_rag=use_rag
        )
        
        logger.info(f"📚 컨텍스트 수집 완료: base={len(context)}, enriched={len(enriched_context)}")
        
        # 3. 프롬프트 구성 (Few-shot with full template JSON)
        system_prompt = self._build_system_prompt(slides)
        user_prompt = self._build_user_prompt(slides, user_query, enriched_context)

        # 4. LLM 호출
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.info(f"📤 LLM 호출: system_prompt={len(system_prompt)}자, user_prompt={len(user_prompt)}자")
        
        result = await ai_service.chat_completion(
            messages=messages,
            provider=None,  # Use default provider from settings (bedrock)
            temperature=0.7,
            max_tokens=8192
        )
        response = result.get("response", "")
        
        logger.info(f"📥 LLM 응답: provider={result.get('provider')}, length={len(response)}자")

        # 5. 응답 파싱 및 검증
        content_data = self._parse_llm_response(response)
        return self._post_process_content(content_data, slides)

    async def _load_template_metadata(self, template_id: str, user_id: Optional[str]) -> Optional[Dict]:
        """템플릿 메타데이터 로드 (시스템 + 사용자 템플릿)"""
        metadata = template_manager.get_template_metadata(template_id)
        
        if not metadata:
            try:
                from app.services.presentation.user_template_manager import user_template_manager
                
                if user_id:
                    metadata = user_template_manager.get_template_metadata(user_id, template_id)
                
                if not metadata:
                    owner_id = user_template_manager.find_template_owner(template_id)
                    if owner_id:
                        metadata = user_template_manager.get_template_metadata(owner_id, template_id)
            except Exception as e:
                logger.warning(f"User template lookup failed: {e}")
        
        return metadata

    async def _build_enriched_context(
        self,
        user_query: str,
        base_context: str,
        session_id: Optional[str],
        container_ids: Optional[List[str]],
        use_rag: bool
    ) -> str:
        """
        Agentic AI: RAG 검색 및 채팅 히스토리를 통한 컨텍스트 강화
        """
        context_parts = []
        
        # 1. 기본 컨텍스트 (채팅창에서 전달된 내용)
        if base_context and base_context.strip():
            context_parts.append(f"## 사용자 제공 컨텍스트\n{base_context}")
        
        # 2. RAG 검색으로 관련 문서 컨텍스트 수집
        if use_rag:
            try:
                rag_context = await self._perform_rag_search(user_query, container_ids)
                if rag_context:
                    context_parts.append(f"## RAG 검색 결과 (관련 문서)\n{rag_context}")
            except Exception as e:
                logger.warning(f"RAG 검색 실패 (계속 진행): {e}")
        
        # 3. 채팅 히스토리에서 추가 컨텍스트 추출
        if session_id:
            try:
                chat_context = await self._extract_chat_context(session_id)
                if chat_context:
                    context_parts.append(f"## 이전 대화 컨텍스트\n{chat_context}")
            except Exception as e:
                logger.warning(f"채팅 컨텍스트 추출 실패 (계속 진행): {e}")
        
        return "\n\n".join(context_parts) if context_parts else ""

    async def _perform_rag_search(self, query: str, container_ids: Optional[List[str]]) -> str:
        """RAG 검색을 통한 관련 문서 컨텍스트 수집"""
        try:
            from app.services.chat.rag_search_service import rag_search_service, RAGSearchParams
            from app.core.database import get_async_session_local
            
            async_session_local = get_async_session_local()
            async with async_session_local() as session:
                search_params = RAGSearchParams(
                    query=query,
                    container_ids=container_ids,
                    max_chunks=10,
                    similarity_threshold=0.3,
                    search_mode="hybrid"
                )
                
                result = await rag_search_service.search_for_rag_context(
                    session=session,
                    search_params=search_params,
                    enable_multiturn_context=False
                )
                
                if result and result.context_text:
                    logger.info(f"🔍 RAG 검색 성공: {len(result.chunks)}개 청크, 컨텍스트 {len(result.context_text)}자")
                    return result.context_text[:6000]  # 최대 6000자
                    
        except ImportError as e:
            logger.debug(f"RAG 서비스 import 실패: {e}")
        except Exception as e:
            logger.warning(f"RAG 검색 중 오류: {e}")
        
        return ""

    async def _extract_chat_context(self, session_id: str) -> str:
        """채팅 히스토리에서 PPT 관련 컨텍스트 추출"""
        try:
            from app.models.chat import RedisChatManager, get_redis_client
            
            redis_client = get_redis_client()
            chat_manager = RedisChatManager(redis_client)
            
            # 최근 메시지 가져오기
            messages = await chat_manager.get_recent_messages(session_id, limit=10)
            
            if not messages:
                return ""
            
            # 가장 최근 AI 응답에서 컨텍스트 추출
            context_parts = []
            for msg in reversed(messages):
                if hasattr(msg, 'content') and msg.content:
                    # AI 응답에서 유용한 정보 추출
                    content = msg.content[:2000]
                    if len(content) > 100:  # 의미 있는 길이의 메시지만
                        context_parts.append(content)
                        if len(context_parts) >= 3:  # 최대 3개 메시지
                            break
            
            if context_parts:
                return "\n---\n".join(context_parts)
                
        except Exception as e:
            logger.warning(f"채팅 히스토리 추출 실패: {e}")
        
        return ""

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """LLM 응답을 JSON으로 파싱"""
        logger.debug(f"🔍 LLM 응답 파싱 시작 (길이: {len(response)})")
        
        if not response or not response.strip():
            raise ValueError("LLM으로부터 빈 응답을 받았습니다.")
        
        cleaned_response = response.strip()
        
        # 마크다운 코드 블록 추출
        if "```json" in cleaned_response:
            cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_response:
            cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
        
        # JSON 객체 추출
        start_idx = cleaned_response.find("{")
        end_idx = cleaned_response.rfind("}")
        if start_idx != -1 and end_idx != -1:
            cleaned_response = cleaned_response[start_idx:end_idx+1]
        
        if not cleaned_response:
            raise ValueError("응답에서 JSON을 찾을 수 없습니다.")

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            logger.error(f"정제된 응답: {cleaned_response[:500]}")
            raise ValueError(f"AI가 유효하지 않은 JSON을 생성했습니다: {e}")

    def _build_system_prompt(self, slides: List[Dict]) -> str:
        """Few-shot 프롬프트를 포함한 시스템 프롬프트 생성"""
        
        # 템플릿 전체 JSON 구조를 포함
        template_json = json.dumps(slides, ensure_ascii=False, indent=2)
        
        return f"""당신은 전문 한국어 프레젠테이션 콘텐츠 생성 전문가입니다.
주어진 PPT 템플릿 구조에 맞는 전문적이고 완성도 높은 콘텐츠를 생성합니다.

## 작업 지침

1. **모든 슬라이드 필수 생성**: 템플릿의 모든 슬라이드(총 {len(slides)}개)에 대해 콘텐츠를 생성해야 합니다.
2. **모든 요소 채우기**: 각 슬라이드의 editable_elements에 있는 모든 요소에 콘텐츠를 작성합니다.
3. **역할별 콘텐츠 스타일**:
   - title: 주제를 명확히 전달하는 제목 + 부제목
   - toc: 목차 항목 (3-5개 핵심 섹션)
   - content: 상세 내용 (bullet point 3-5개, 각 50-100자)
   - conclusion/thanks: 핵심 요약 또는 감사 인사

4. **콘텐츠 품질 기준**:
   - 한국어로 작성 (전문 용어는 영어 병기 가능)
   - 비즈니스 프레젠테이션에 적합한 전문적 어조
   - 구체적이고 실용적인 내용
   - 키워드가 아닌 완성된 문장/구문 사용

## 입력 템플릿 구조 (JSON)

```json
{template_json}
```

## Few-shot 예제

### 예제 입력:
사용자 요청: "디지털 마케팅 전략 제안서"
템플릿 슬라이드:
- Slide 1 (title): textbox-0-0, textbox-0-1
- Slide 2 (toc): textbox-1-0, textbox-1-1
- Slide 3 (content): textbox-2-0, textbox-2-1, textbox-2-2

### 예제 출력:
```json
{{
  "slides": [
    {{
      "index": 1,
      "role": "title",
      "elements": [
        {{ "id": "textbox-0-0", "text": "2025 디지털 마케팅 전략 제안서" }},
        {{ "id": "textbox-0-1", "text": "데이터 기반 고객 경험 혁신 방안" }}
      ],
      "note": "인사말과 함께 프레젠테이션의 목적을 간략히 소개합니다."
    }},
    {{
      "index": 2,
      "role": "toc",
      "elements": [
        {{ "id": "textbox-1-0", "text": "목차" }},
        {{ "id": "textbox-1-1", "text": "1. 시장 현황 분석\\n2. 타겟 고객 정의\\n3. 채널별 전략\\n4. 실행 로드맵\\n5. 기대 효과" }}
      ],
      "note": "전체 발표 흐름을 안내합니다."
    }},
    {{
      "index": 3,
      "role": "content",
      "elements": [
        {{ "id": "textbox-2-0", "text": "시장 현황 분석" }},
        {{ "id": "textbox-2-1", "text": "• 국내 디지털 광고 시장 규모: 8조원 (전년 대비 15% 성장)\\n• 모바일 중심 소비 패턴 가속화\\n• AI 기반 개인화 마케팅 트렌드 확산" }},
        {{ "id": "textbox-2-2", "text": "출처: 한국인터넷진흥원, 2024" }}
      ],
      "note": "최신 시장 데이터를 인용하여 신뢰성을 높입니다."
    }}
  ]
}}
```

## 출력 형식
- JSON만 출력 (마크다운 코드 블록 없이)
- 모든 슬라이드 포함
- 각 슬라이드의 모든 editable element에 콘텐츠 제공
"""

    def _build_user_prompt(self, slides: List[Dict], query: str, context: str) -> str:
        """사용자 요청과 템플릿 요소를 포함한 상세 프롬프트 생성"""
        
        # 템플릿 구조를 명확하게 요약 (슬라이드별 요소 매핑)
        structure_summary = []
        for slide in slides:
            editable = slide.get("editable_elements", [])
            elements_desc = []
            
            for el_id in editable:
                # elements 리스트에서 해당 ID의 상세 정보 찾기
                el_detail = next((e for e in slide.get("elements", []) if e["id"] == el_id), None)
                if el_detail:
                    role = el_detail.get("element_role", "unknown")
                    orig_text = el_detail.get("content", "")[:50] if el_detail.get("content") else "(비어있음)"
                    font_size = el_detail.get("font_size", "")
                    position = el_detail.get("position", {})
                    
                    elements_desc.append(
                        f"    - {el_id}: role={role}, 원본='{orig_text}', 위치=({position.get('left', 0):.0f}, {position.get('top', 0):.0f})"
                    )
            
            structure_summary.append(f"""
## 슬라이드 {slide['index']} ({slide.get('role', 'unknown')})
- 레이아웃: {slide.get('layout_index', 'N/A')}
- 편집 가능 요소:
{chr(10).join(elements_desc) if elements_desc else '    (편집 가능 요소 없음)'}
""")

        # 참고 컨텍스트 처리
        context_section = ""
        if context and context.strip():
            context_text = context[:4000]  # 충분한 컨텍스트 제공
            context_section = f"""
## 참고 자료 (콘텐츠 작성 시 활용)
{context_text}
"""
        
        return f"""## 사용자 요청
**주제/목적:** {query}
{context_section}
## 템플릿 슬라이드 구조 (총 {len(slides)}개)
{chr(10).join(structure_summary)}

## 작업 요구사항
1. 위 {len(slides)}개 슬라이드 **모두**에 대해 콘텐츠를 생성하세요.
2. 각 슬라이드의 모든 편집 가능 요소(editable element)에 적절한 **한국어** 콘텐츠를 작성하세요.
3. 슬라이드 역할(title, toc, content, conclusion 등)에 맞는 스타일로 작성하세요.
4. 원본 텍스트를 참고하되, 사용자 요청에 맞는 새로운 콘텐츠로 대체하세요.
5. 제목 슬라이드에는 사용자 요청을 반영한 매력적인 제목과 부제목을 작성하세요.
6. 본문 슬라이드에는 구체적이고 실용적인 내용을 bullet point 형식으로 작성하세요.

JSON 형식으로만 출력하세요. 마크다운 코드 블록 없이 순수 JSON만 출력합니다.
"""

    def _post_process_content(self, content_data: Dict, original_slides: List[Dict]) -> Dict:
        """
        LLM 응답을 후처리하여 누락된 슬라이드/요소 보완
        
        - 누락된 슬라이드 추가
        - 빈 elements 배열에 기본 요소 추가
        - 슬라이드 role 정보 보완
        """
        generated_slides = content_data.get("slides", [])
        
        # 슬라이드 인덱스 매핑
        generated_map = {s.get("index"): s for s in generated_slides}
        
        processed_slides = []
        for orig_slide in original_slides:
            slide_idx = orig_slide.get("index")
            slide_role = orig_slide.get("role", "content")
            editable_elements = orig_slide.get("editable_elements", [])
            
            if slide_idx in generated_map:
                # LLM이 생성한 슬라이드 사용
                gen_slide = generated_map[slide_idx]
                
                # role 정보가 없으면 원본에서 가져오기
                if not gen_slide.get("role"):
                    gen_slide["role"] = slide_role
                
                # elements가 비어있으면 기본 요소 추가
                if not gen_slide.get("elements"):
                    gen_slide["elements"] = self._create_default_elements(
                        editable_elements, orig_slide, slide_role
                    )
                
                processed_slides.append(gen_slide)
            else:
                # 누락된 슬라이드: 기본 콘텐츠로 생성
                logger.warning(f"⚠️ 슬라이드 {slide_idx} 누락됨, 기본 콘텐츠 생성")
                default_slide = {
                    "index": slide_idx,
                    "role": slide_role,
                    "elements": self._create_default_elements(
                        editable_elements, orig_slide, slide_role
                    ),
                    "note": ""
                }
                processed_slides.append(default_slide)
        
        # 인덱스 순으로 정렬
        processed_slides.sort(key=lambda s: s.get("index", 0))
        
        logger.info(f"✅ 후처리 완료: 원본 {len(original_slides)}개, 생성 {len(generated_slides)}개, 최종 {len(processed_slides)}개")
        
        return {"slides": processed_slides}
    
    def _create_default_elements(
        self,
        editable_ids: List[str],
        orig_slide: Dict,
        slide_role: str
    ) -> List[Dict]:
        """누락된 슬라이드에 대한 기본 요소 생성"""
        elements = []
        
        for el_id in editable_ids:
            # 원본 슬라이드의 elements에서 해당 ID 찾기
            orig_element = next(
                (e for e in orig_slide.get("elements", []) if e.get("id") == el_id),
                None
            )
            
            # 기본 텍스트 결정
            if orig_element:
                default_text = orig_element.get("content", "")
                element_role = orig_element.get("element_role", "")
            else:
                default_text = ""
                element_role = ""
            
            # 빈 텍스트인 경우 역할에 따른 기본값
            if not default_text:
                if "title" in element_role.lower() or slide_role == "title":
                    default_text = "제목을 입력하세요"
                elif "subtitle" in element_role.lower():
                    default_text = "부제목"
                else:
                    default_text = "내용을 입력하세요"
            
            elements.append({
                "id": el_id,
                "text": default_text,
                "role": element_role,
                "original_text": orig_element.get("content", "") if orig_element else ""
            })
        
        return elements

template_content_generator = TemplateContentGeneratorService()
