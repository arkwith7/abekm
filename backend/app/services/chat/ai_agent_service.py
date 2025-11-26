"""
AI Agent 관리 서비스
- 다양한 AI Agent 타입별 처리 로직
- Agent별 시스템 프롬프트 관리
- 선택된 문서 기반 RAG 처리
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.chat import AgentSystemPrompt, AGENT_SYSTEM_PROMPTS, SelectedDocument
from app.services.chat.rag_search_service import rag_search_service, RAGSearchParams
from app.services.chat.query_classification_service import QueryClassificationService
from app.services.chat.conversation_context_service import conversation_context_service
from app.services.document.extraction.text_extractor_service import TextExtractorService
from app.services.chat.chat_attachment_service import chat_attachment_service
from loguru import logger


class AIAgentService:
    """AI Agent 관리 서비스"""
    
    def __init__(self):
        # 시스템 프롬프트 기본 구성 (내장 상수)
        self.agent_configs = AGENT_SYSTEM_PROMPTS
        # backend/prompts 경로 (선택적 외부 파일 커스터마이징용)
        self.prompts_dir = Path(__file__).parents[3] / "prompts"
        if not self.prompts_dir.exists():
            logger.warning(f"⚠️ backend/prompts 디렉토리를 찾지 못했습니다: {self.prompts_dir}")

        # RAG 설정 (환경 변수 기반 오버라이드 지원)
        # 관련성 없는 문서 필터링을 위한 엄격한 임계값 사용
        self.rag_similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.4"))
        self.rag_max_chunks = int(os.getenv("RAG_MAX_CHUNKS", "10"))
        self.rag_use_reranking = os.getenv("RAG_USE_RERANKING", "true").lower() == "true"
        # 질문 분류기
        self.classifier = QueryClassificationService()
        # 텍스트 추출기
        self.text_extractor = TextExtractorService()

        logger.info(
            f"🔧 RAG 설정 로드: threshold={self.rag_similarity_threshold}, "
            f"max_chunks={self.rag_max_chunks}, reranking={self.rag_use_reranking}"
        )
        logger.info("📁 backend/prompts 디렉토리에서 시스템 프롬프트 로드 시작")
        
        # 파일 기반 프롬프트 로드
        self._load_prompts_from_files()
    
    def _load_prompts_from_files(self):
        """파일에서 프롬프트 로드하여 기본 프롬프트 덮어쓰기"""
        try:
            if not self.prompts_dir or not self.prompts_dir.exists():
                logger.debug("프롬프트 디렉토리가 없음, 기본 프롬프트 사용")
                return
            
            # general.prompt 파일 로드
            general_prompt_path = self.prompts_dir / "general.prompt"
            if general_prompt_path.exists():
                general_prompt_content = general_prompt_path.read_text(encoding="utf-8").strip()
                # 기존 general agent 프롬프트 덮어쓰기
                if 'general' in self.agent_configs:
                    self.agent_configs['general'].system_prompt = general_prompt_content
                    logger.info(f"✅ general.prompt 파일에서 프롬프트 로드 완료 ({len(general_prompt_content)}자)")
                else:
                    logger.warning("general agent 설정이 없어 프롬프트 로드 스킵")
            else:
                logger.debug("general.prompt 파일이 없음, 기본 프롬프트 사용")
                
            # 다른 agent 타입들도 필요시 로드 가능
            # presentation.prompt, summarizer.prompt 등
            
        except Exception as e:
            logger.warning(f"프롬프트 파일 로드 중 오류: {e}")
            logger.info("기본 내장 프롬프트를 계속 사용합니다")
    
    def reload_prompts(self):
        """프롬프트 파일들을 다시 로드 (향후 확장용)"""
        self._load_prompts_from_files()
        logger.info("🔄 프롬프트 재로딩 완료 (현재 기본 내장 + 파일 커스터마이징 미사용)")
    
    def get_agent_config(self, agent_type: str) -> AgentSystemPrompt:
        """Agent 타입에 따른 설정 반환"""
        return self.agent_configs.get(agent_type, self.agent_configs['general'])
    
    def get_all_agents(self) -> Dict[str, AgentSystemPrompt]:
        """모든 Agent 설정 반환"""
        return self.agent_configs
    
    async def prepare_context_with_documents(
        self, 
        query: str, 
        selected_documents: Optional[List[SelectedDocument]],
        chat_history: Optional[List[Dict[str, str]]] = None,
        agent_type: str = 'general',
        container_ids: Optional[List[str]] = None,
        similarity_threshold: Optional[float] = None,
        session_id: Optional[str] = None,
        db_session = None,
        attachments: Optional[List[Dict[str, Any]]] = None  # 🆕 이미지 첨부 정보
    ) -> tuple[str, List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        선택된 문서를 기반으로 컨텍스트 준비 (멀티턴 대화 기록 반영)
        
        Args:
            query: 사용자 질문
            selected_documents: 선택된 문서 목록
            chat_history: 대화 기록
            agent_type: AI Agent 타입
            container_ids: 컨테이너 ID 목록
            similarity_threshold: 유사도 임계값 (Chat API에서 전달받은 값 우선 사용)
            session_id: 세션 ID (컨텍스트 서비스용)
            db_session: 데이터베이스 세션
            attachments: 첨부된 이미지 메타데이터 리스트 (CLIP 기반 유사도 검색용)
            
        Returns:
            tuple: (enhanced_query, references, context_info, rag_stats)
        """
        agent_config = self.get_agent_config(agent_type)
        system_prompt = agent_config.system_prompt
        
        # Chat API에서 전달받은 임계값을 우선 사용, 없으면 기본값 사용
        effective_threshold = similarity_threshold if similarity_threshold is not None else self.rag_similarity_threshold
        logger.info(f"🎚️ 유사도 임계값: {effective_threshold} (API 전달값: {similarity_threshold}, 기본값: {self.rag_similarity_threshold})")
        
        try:
            # 🎯 통합 질의 분석: 재작성 + 의도 분류 + 도구 선택
            conversation_history = []
            if session_id and db_session:
                conversation_history = await conversation_context_service._get_conversation_history(db_session, session_id)
            
            analysis_result = await conversation_context_service.analyze_query_with_intent(
                original_query=query,
                conversation_history=conversation_history,
                document_ids=[doc.id for doc in selected_documents] if selected_documents else None,
                container_ids=container_ids
            )
            
            logger.info(f"🎯 질의 분석 결과: intent={analysis_result['intent']}, confidence={analysis_result['confidence']:.2f}, tools={analysis_result['required_tools']}")
            logger.info(f"✍️ 재작성 질의: '{query[:50]}...' → '{analysis_result['rewritten_query'][:50]}...'")
            
            # 재작성된 질의문 사용
            search_query = analysis_result['rewritten_query']
            context_metadata = {
                "analysis": analysis_result,
                "context_used": True
            }
            
            # 🔧 도구 라우팅
            intent = analysis_result['intent']
            required_tools = analysis_result['required_tools']
            
            # 1. 도구 미지원 처리
            if intent == 'unsupported' or not required_tools:
                logger.warning(f"⚠️ 지원하지 않는 요청: {analysis_result['reasoning']}")
                return "", [], {
                    "rag_used": False, 
                    "unsupported": True,
                    "reason": analysis_result['reasoning']
                }, {
                    "rag_used": False,
                    "unsupported": True,
                    "message": "죄송합니다. 해당 요청을 처리할 수 있는 도구가 아직 준비되지 않았습니다."
                }
            
            # 2. 문서 로더 (요약)
            if 'document_loader' in required_tools:
                logger.info(f"📚 document_loader 사용 - 선택 문서 원문 로드")
                if selected_documents and len(selected_documents) > 0:
                    return await self._load_documents_for_summarization(
                        selected_documents=selected_documents,
                        db_session=db_session,
                        max_chunks=self.rag_max_chunks
                    )
                else:
                    logger.warning(f"⚠️ document_loader 요청이지만 선택된 문서 없음 - 검색으로 폴백")
                    # 폴백: hybrid_search로 처리
            
            # 3. 하이브리드 검색 (일반 질문, 비교 등)
            # 기존 분류 로직 유지 (호환성)
            classification = await self.classifier.classify_query(query)
            logger.info(f"📋 기존 분류 (참고용): type={classification.query_type} need_rag={classification.needs_rag} conf={classification.confidence:.2f}")

            # 🆕 이미지 첨부 시 질의문 추가 보강 (이미지 검색용)
            image_query_rewritten = False
            
            # 🆕 문서 첨부 처리 (Chat with File)
            attached_document_context = ""
            if attachments:
                # 1. 이미지 처리
                image_attachments = [
                    att for att in attachments 
                    if att.get('mime_type', '').startswith('image/')
                ]
                
                if image_attachments:
                    logger.info(f"🖼️ 이미지 첨부 감지 ({len(image_attachments)}개) - 질의문 재작성 시도")
                    rewritten_query, rewrite_metadata = await conversation_context_service.rewrite_query_for_image_search(
                        original_query=query,
                        image_count=len(image_attachments),
                        selected_documents=selected_documents
                    )
                    
                    if rewrite_metadata.get("rewritten"):
                        search_query = rewritten_query
                        image_query_rewritten = True
                        context_metadata["image_rewrite"] = rewrite_metadata
                        logger.info(f"✍️ 이미지 질의문 재작성 완료: '{query[:30]}...' → '{search_query[:50]}...'")

                # 2. 문서 처리 (PDF, DOCX 등)
                doc_attachments = [
                    att for att in attachments 
                    if not att.get('mime_type', '').startswith('image/') and not att.get('mime_type', '').startswith('audio/')
                ]
                
                if doc_attachments:
                    logger.info(f"📎 문서 첨부 감지 ({len(doc_attachments)}개) - 텍스트 추출 및 컨텍스트 주입 시도")
                    extracted_texts = []
                    
                    for doc_att in doc_attachments:
                        asset_id = doc_att.get('asset_id')
                        if not asset_id:
                            continue
                            
                        stored_file = chat_attachment_service.get(asset_id)
                        if not stored_file:
                            logger.warning(f"⚠️ 첨부 파일 찾을 수 없음: {asset_id}")
                            continue
                            
                        # 파일 크기 제한 (10MB)
                        MAX_FILE_SIZE = 10 * 1024 * 1024
                        if stored_file.size > MAX_FILE_SIZE:
                            logger.warning(f"⚠️ 파일 크기 초과 ({stored_file.size} bytes) - 처리 건너뜀: {stored_file.file_name}")
                            extracted_texts.append(f"[파일: {stored_file.file_name}]\n(파일이 너무 커서 내용을 읽을 수 없습니다. 10MB 이하의 파일만 지원합니다.)")
                            continue
                            
                        try:
                            # 텍스트 추출
                            extraction_result = await self.text_extractor.extract_text_from_file(
                                file_path=str(stored_file.path),
                                file_extension=Path(stored_file.file_name).suffix
                            )
                            
                            if extraction_result.get('success') and extraction_result.get('text'):
                                text_content = extraction_result['text']
                                # 텍스트 길이 제한 (30,000자)
                                MAX_TEXT_LENGTH = 30000
                                if len(text_content) > MAX_TEXT_LENGTH:
                                    text_content = text_content[:MAX_TEXT_LENGTH] + "\n...(내용이 너무 길어 생략됨)"
                                    
                                extracted_texts.append(f"[첨부 파일 내용: {stored_file.file_name}]\n{text_content}")
                                logger.info(f"✅ 문서 텍스트 추출 성공: {stored_file.file_name} ({len(text_content)}자)")
                            else:
                                logger.warning(f"⚠️ 텍스트 추출 실패: {stored_file.file_name}")
                        except Exception as e:
                            logger.error(f"❌ 문서 처리 중 오류: {e}")
                            
                    if extracted_texts:
                        attached_document_context = "\n\n".join(extracted_texts)
                        # 검색 쿼리에 문서 내용이 있다는 힌트 추가 (선택 사항)
                        # search_query += " (첨부된 문서 내용을 참고하여 답변해줘)"
            
            # 멀티턴 컨텍스트 기반 검색어 보강 (이미지 재작성이 없었을 때만)
            if not image_query_rewritten and classification.needs_rag and session_id and db_session:
                try:
                    enhanced_query, context_metadata = await conversation_context_service.enhance_query_with_context(
                        current_query=query,
                        session_id=session_id,
                        db_session=db_session
                    )
                    
                    if context_metadata.get("context_used"):
                        search_query = enhanced_query
                        topic_continuity = context_metadata.get("topic_continuity", 0.0)
                        logger.info(f"🔗 컨텍스트 강화 적용: 연속성={topic_continuity:.2f}, 원문='{query[:50]}...' → 강화='{search_query[:50]}...'")
                    else:
                        reason = context_metadata.get('reason', 'unknown')
                        if reason == 'no_explicit_reference':
                            logger.info(f"📝 독립적 질문 감지 - 명시적 참조 없음: '{query[:30]}...'")
                        else:
                            logger.info(f"🚫 컨텍스트 강화 생략: {reason}")
                        search_query = query  # 원본 사용
                        
                except Exception as ctx_error:
                    logger.warning(f"⚠️ 컨텍스트 서비스 오류, 원본 질문 사용: {ctx_error}")
                    search_query = query
                    
            else:
                # 세션 ID나 DB 세션이 없는 경우 원본 질문 사용
                search_query = query
                context_metadata = {"context_used": False, "reason": "no_session_context"}
                logger.info("📝 세션 컨텍스트 없음 - 독립적 질문으로 처리")

            if not classification.needs_rag and 'hybrid_search' not in required_tools:
                logger.info(f"RAG 불필요, 대화 기록 기반으로 답변 생성 유도.")
                return "", [], {"rag_used": False, "query_classification": classification.query_type}, {"rag_used": False}

            if selected_documents and len(selected_documents) > 0:
                logger.info(f"🎯 Agent '{agent_type}' - 선택된 문서 기반 RAG: {len(selected_documents)}개 문서")
                
                document_ids = [doc.id for doc in selected_documents]
                document_info = "\n".join([f"- {doc.fileName} ({doc.fileType})" for doc in selected_documents])
                
                rag_params = RAGSearchParams(
                    query=search_query,
                    document_ids=document_ids,
                    limit=self.rag_max_chunks,
                    threshold=effective_threshold,
                    similarity_threshold=effective_threshold,
                    search_mode='hybrid',
                    reranking=self.rag_use_reranking
                )
                
                enhanced_query = self._enhance_query_for_agent(search_query, agent_type, document_info)
            else:
                # 선택된 문서가 없을 때는 전체 문서에서 검색
                logger.info(f"� Agent '{agent_type}' - 전체 문서 기반 RAG 검색")
                
                rag_params = RAGSearchParams(
                    query=search_query,
                    document_ids=None,  # 전체 문서 검색
                    limit=self.rag_max_chunks,
                    threshold=effective_threshold,
                    similarity_threshold=effective_threshold,
                    search_mode='hybrid',
                    reranking=self.rag_use_reranking
                )
                
                document_info = "전체 문서를 대상으로 검색"
                enhanced_query = self._enhance_query_for_agent(search_query, agent_type, document_info)
            
            # 🆕 첨부 문서 컨텍스트가 있으면 프롬프트에 추가
            if attached_document_context:
                logger.info("📎 첨부 문서 컨텍스트를 프롬프트에 추가합니다.")
                enhanced_query = f"""
[첨부된 문서 내용]
{attached_document_context}

[사용자 질문]
{enhanced_query}
"""

            logger.info(f"🔧 RAG 파라미터: threshold={rag_params.similarity_threshold}, max_chunks={rag_params.limit}, reranking={rag_params.reranking}")
            
            # RAG 검색 실행 (간단 캐싱: 동일 세션 내 동일 쿼리/문서 셋 중복 호출 방지)
            cache_key = None
            try:
                sel_ids = ",".join(sorted([str(d.id) for d in selected_documents])) if selected_documents else "ALL"
                cache_key = f"{session_id or 'no-session'}::{agent_type}::{search_query}::{sel_ids}::{container_ids or []}::{effective_threshold}"
            except Exception:
                cache_key = None
            if not hasattr(self, "_last_ctx_cache"):
                self._last_ctx_cache = {}
            if cache_key and cache_key in self._last_ctx_cache:
                logger.info("🧠 RAG 결과 캐시 적중 - 중복 호출 방지")
                search_result = self._last_ctx_cache[cache_key]
            else:
                search_result = await rag_search_service.search_with_rag(
                    rag_params,
                    container_ids=container_ids,
                    attachments=attachments  # 🆕 이미지 첨부 정보 전달
                )
                if cache_key:
                    self._last_ctx_cache[cache_key] = search_result
            
            # 디버그: search_result 구조 확인
            logger.info(f"🔍 search_result 타입: {type(search_result)}")
            logger.info(f"🔍 search_result 키들: {list(search_result.keys()) if isinstance(search_result, dict) else 'Not a dict'}")
            
            # 검색 실패 처리 (청크 수 확인)
            references = search_result.get('references', [])  # 이제 used_chunks가 들어옴
            all_references = search_result.get('all_references', None)
            used_count = len(references) if references else 0
            total_count = len(all_references) if isinstance(all_references, list) else None
            logger.info(f"🔍 추출된 references 수(used): {used_count} / 전체 후보: {total_count}")
            
            if len(references) == 0:
                logger.warning(f"🔍 RAG 검색 실패 - 키워드 기반 폴백 검색 시도")
                
                # 키워드 기반 폴백 검색 시도 (선택된 문서가 있는 경우만)
                if selected_documents and len(selected_documents) > 0:
                    document_ids = [doc.id for doc in selected_documents]
                    fallback_result = await self._try_keyword_fallback_search(
                        query, document_ids, container_ids
                    )
                    
                    if fallback_result and len(fallback_result.get('references', [])) > 0:
                        logger.info(f"✅ 키워드 폴백 검색 성공 - 청크 수: {len(fallback_result['references'])}")
                        return system_prompt, fallback_result.get('references', []), fallback_result.get('context_info', {}), fallback_result.get('rag_stats', {})
                
                # 폴백도 실패한 경우 검색 실패 응답 생성
                logger.warning(f"🔍 키워드 폴백 검색도 실패 - 검색 실패 응답 생성")
                fallback_response = await self._generate_search_failure_response(
                    query, selected_documents or [], agent_type
                )
                # 검색 실패 시 빈 참고자료 반환하여 프론트엔드에서 참고자료 표시하지 않도록 함
                return fallback_response, [], {'search_failed': True, 'no_references': True}, {'chunks_found': 0, 'search_status': 'failed'}
            
            # 1) 기본 컨텍스트/통계
            context_info = search_result.get('context_info', {})
            rag_stats = search_result.get('rag_stats', {})
            try:
                avg_sim = float(rag_stats.get('avg_similarity', 0.0) or 0.0)
            except Exception:
                avg_sim = 0.0

            # 2) 저품질 감지 시 전체 검색으로 폴백
            final_result = search_result
            if selected_documents and len(selected_documents) > 0:
                try:
                    low_quality = (avg_sim < 0.28) or (used_count < 2)
                    if low_quality:
                        # 원칙 1 준수: 선택 문서가 있을 때는 전체 검색으로 폴백하지 않고 실패 안내를 반환
                        logger.info("🧩 저품질 판단 → 선택 문서 스코프 내 실패로 처리하고 안내 메시지 반환")
                        failure_response = await self._generate_search_failure_response(
                            query, selected_documents, agent_type
                        )
                        return failure_response, [], {'search_failed': True, 'low_quality': True}, {
                            'chunks_found': used_count,
                            'search_status': 'failed_low_quality',
                            'avg_similarity': avg_sim
                        }
                except Exception as fb_err:
                    logger.warning(f"폴백 처리 중 오류: {fb_err}")

            # 3) 게이팅/모드 결정 (최종 used_count 기반)
            ppt_intent = self._detect_ppt_intent(query)
            selected_mode = "full"
            gating_reason = ""
            if ppt_intent:
                if used_count >= 3:
                    selected_mode = "full"
                elif used_count >= 1:
                    selected_mode = "outline"
                    gating_reason = "근거 제한(참고 1-2개)으로 아웃라인 모드 적용"
                else:
                    selected_mode = "decline"
                    gating_reason = "참고자료 0개"
            context_info = context_info or {}
            if isinstance(context_info, dict):
                context_info["selected_mode"] = selected_mode
                if gating_reason:
                    context_info["gating_reason"] = gating_reason

            # 4) 프롬프트 구성 (최종 컨텍스트 사용)
            if selected_documents and len(selected_documents) > 0:
                context_enhanced_prompt = (
                    f"{system_prompt}\n\n"
                    f"선택된 문서 정보:\n{document_info}\n\n"
                    f"🚨 시스템 제공 참조문서 개수: {used_count}개 🚨\n"
                    f"아래는 검색으로 수집한 관련 컨텍스트입니다. 답변 시 적극적으로 활용하세요.\n---\n"
                    f"{final_result.get('context_text', '')}"
                )
            else:
                context_enhanced_prompt = (
                    f"{system_prompt}\n\n"
                    f"전체 지식베이스를 검색하여 관련 정보를 찾아 답변해주세요.\n\n"
                    f"🚨 시스템 제공 참조문서 개수: {used_count}개 🚨\n"
                    f"아래는 검색으로 수집한 관련 컨텍스트입니다. 답변 시 적극적으로 활용하세요.\n---\n"
                    f"{final_result.get('context_text', '')}"
                )

            # 5) context_info에 통계 및 멀티턴 메타데이터 주입 및 반환
            ctx_info = final_result.get('context_info', {}) or {}
            try:
                if isinstance(ctx_info, dict):
                    ctx_info.setdefault('used_chunks', used_count)
                    if total_count is not None:
                        ctx_info.setdefault('total_chunks', total_count)
                    if 'selected_mode' in context_info:
                        ctx_info['selected_mode'] = context_info['selected_mode']
                    if 'gating_reason' in context_info:
                        ctx_info['gating_reason'] = context_info['gating_reason']
                    
                    # 멀티턴 컨텍스트 메타데이터 추가
                    if isinstance(context_metadata, dict):
                        ctx_info['context_used'] = context_metadata.get('context_used', False)
                        ctx_info['multiterm_reason'] = context_metadata.get('reason', 'no_context')
                        
            except Exception:
                pass
            return context_enhanced_prompt, references, ctx_info, rag_stats or final_result.get('rag_stats', {})
                
        except Exception as e:
            logger.error(f"❌ Agent context 준비 중 오류: {e}")
            # 인사 / 일반 대화일 가능성이 높은 초단문은 부드러운 폴백
            if len(query.strip()) <= 10:
                soft_fallback = "안녕하세요! 도움이 필요하시면 문서나 궁금한 내용을 말씀해주세요. 😊"
                return soft_fallback, [], {"rag_used": False, "error": str(e)}, {"rag_used": False}
            # 기타는 기존 시스템 프롬프트
            return system_prompt, [], {"rag_used": False, "error": str(e)}, {"rag_used": False}
    
    def _enhance_query_for_agent(
        self, 
        query: str, 
        agent_type: str, 
        document_info: Optional[str] = None
    ) -> str:
        """Agent 타입에 따른 질문 보강"""
        
        enhancements = {
            'summarizer': "다음 내용을 요약해주세요:",
            'keyword-extractor': "다음 내용에서 주요 키워드를 추출해주세요:",
            'presentation': "다음 내용으로 프레젠테이션을 만들어주세요:",
            'template': "다음 내용을 템플릿 형태로 정리해주세요:",
            'knowledge-graph': "다음 내용의 지식 그래프를 만들어주세요:",
            'analyzer': "다음 내용을 분석해주세요:",
            'insight': "다음 내용에서 인사이트를 도출해주세요:",
            'report-generator': "다음 내용으로 보고서를 작성해주세요:",
            'script-generator': "다음 내용으로 발표 스크립트를 만들어주세요:",
            'key-points': "다음 내용의 핵심 포인트를 추출해주세요:"
        }
        
        if agent_type in enhancements and agent_type != 'general':
            prefix = enhancements[agent_type]
            if document_info:
                return f"{prefix}\n\n참고 문서: {document_info}\n\n질문: {query}"
            else:
                return f"{prefix}\n\n{query}"
        
        return query

    def _detect_ppt_intent(self, query: str) -> bool:
        try:
            if not isinstance(query, str):
                return False
            q = query.lower()
            has_ppt = any(k in q for k in ["ppt", "pptx", "presentation", "프레젠테이션", "프리젠테이션", "슬라이드", "발표자료", "제품소개"])
            has_create = any(k in q for k in ["만들", "작성", "생성", "제작"])
            return bool(has_ppt and has_create)
        except Exception:
            return False

    def _build_non_rag_agent_response(self, query: str, qtype: str) -> str:
        """에이전트 경로에서 인사/일반대화/시스템문의 분류 시 즉시 응답 생성"""
        if qtype == "greeting":
            return "안녕하세요! 웅진 지식관리시스템 AI 어시스턴트입니다. 😊\n\n무엇을 도와드릴까요?"
        if qtype == "general_chat":
            # 간단한 응답들에 대해 자연스러운 대답
            query_lower = query.lower().strip()
            if "네" in query_lower or "응" in query_lower:
                return "네, 계속해서 궁금한 것을 물어보세요!"
            elif "고마" in query_lower or "감사" in query_lower:
                return "천만에요! 언제든 도움이 필요하시면 말씀해주세요."
            elif "좋" in query_lower:
                return "감사합니다! 다른 도움이 필요하시면 언제든 말씀해주세요."
            else:
                return "네, 잘 알겠습니다. 궁금한 것이 있으시면 편하게 물어보세요!"
        if qtype == "system_inquiry":
            return (
                "다음 기능들을 지원하고 있어요:\n\n"
                "- 📚 문서 검색 및 질의응답\n"
                "- 📝 문서 요약\n" 
                "- 📊 PPT 자동 생성\n"
                "- 🔍 키워드/인사이트 추출\n\n"
                "무엇을 도와드릴까요?"
            )
        return "네, 더 구체적으로 말씀해주시면 관련 자료를 찾아 도와드릴게요!"
    
    async def _generate_search_failure_response(
        self, 
        query: str, 
        selected_documents: List[SelectedDocument],
        agent_type: str = 'general'
    ) -> str:
        """검색 실패 시 안내 응답 생성"""
        try:
            # 검색 실패 전용 프롬프트 로드
            failure_template = None
            try:
                if self.prompts_dir and self.prompts_dir.exists():
                    search_failure_prompt_path = self.prompts_dir / "search-failure.prompt"
                    if search_failure_prompt_path.exists():
                        failure_template = search_failure_prompt_path.read_text(encoding='utf-8').strip()
            except Exception as fe:
                logger.debug(f"search-failure.prompt 로드 실패: {fe}")
            if not failure_template:
                failure_template = """🔍 **검색 결과**

{failure_lead}

## 📋 검색 대상 문서
{selected_documents}

## 💡 **검색을 개선하려면**
- **더 구체적인 키워드**를 사용해보세요
- **다른 표현**으로 질문해보세요  
- **문서 제목이나 섹션명**을 포함해보세요

{suggestions_section}

다른 방식으로 질문해주시면 더 정확한 답변을 드릴 수 있습니다! 😊"""
            
            # 선택된 문서 정보 구성
            document_list = "\n".join([
                f"📄 {doc.fileName} ({doc.fileType})"
                for doc in selected_documents
            ])
            # 선택 문서 유무에 따른 리드 문구 구성
            if selected_documents and len(selected_documents) > 0:
                failure_lead = "선택하신 문서들을 검토했지만, 질의하신 내용과 직접적으로 관련된 정보를 찾기 어려웠습니다."
            else:
                failure_lead = "전체 문서를 검색했지만, 질의하신 내용과 직접적으로 관련된 정보를 찾기 어려웠습니다."

            # 문서 기반 추천 질문 생성 (간단 휴리스틱)
            suggestions: List[str] = []
            # 파일명에서 확장자 제거 후 핵심 키워드 추출
            for doc in selected_documents[:3]:  # 최대 3개만 활용
                base = doc.fileName.rsplit('.', 1)[0]
                # 한글/영문 혼합 정리
                base_clean = base.replace('_', ' ').replace('-', ' ').strip()
                if not base_clean:
                    continue
                suggestions.extend([
                    f"'{base_clean}' 문서의 핵심 요약은?",
                    f"'{base_clean}' 문서에서 주요 절차 단계는?",
                    f"'{base_clean}' 문서의 목적과 적용 범위를 설명해줘",
                    f"'{base_clean}' 문서 기반으로 작성해야 할 산출물은?"
                ])

            # 선택된 문서가 없거나 추출 실패 시 일반 제안
            if not suggestions:
                suggestions = [
                    "어떤 제품 / 프로세스 / 문서 유형인지 더 구체적으로 적어주세요",
                    "문서 제목에 포함된 고유 용어(예: SOP, WI, 규격명)를 질문에 포함해보세요",
                    "필요한 결과 형태(요약, 절차, 정의 등)를 명시해보세요"
                ]

            # 중복 제거 및 상위 N개 제한
            seen = set()
            unique_suggestions = []
            for s in suggestions:
                if s not in seen:
                    seen.add(s)
                    unique_suggestions.append(s)
            unique_suggestions = unique_suggestions[:6]

            suggestions_md = "\n".join(f"- {s}" for s in unique_suggestions)
            
            # 추천 질문 섹션 구성
            suggestions_section = ""
            if suggestions_md:
                suggestions_section = f"""
## 🤔 **이런 질문은 어떠세요?**
{suggestions_md}"""
            
            # 연관 문서 추천 (선택 문서 제외)
            related_docs_md = ""
            try:
                from app.services.chat.rag_search_service import rag_search_service
                exclude_ids = [doc.id for doc in selected_documents]
                recommendations = await rag_search_service.recommend_related_documents(
                    query=query,
                    exclude_document_ids=exclude_ids,
                    limit=5,
                    threshold=0.22
                )
                if recommendations:
                    # 1) 사용자 지정 템플릿 (문자열 포함 시 그대로 사용)
                    custom_tpl = os.getenv("DOCUMENT_VIEWER_URL_TEMPLATE")  # 예: https://kms/viewer?doc={file_id}
                    link_mode = os.getenv("DOCUMENT_VIEWER_LINK_MODE", "scheme")  # scheme | template
                    scheme_prefix = os.getenv("DOCUMENT_VIEWER_SCHEME", "doc-open://file")
                    lines: List[str] = []
                    for r in recommendations:
                        file_id = r.get('file_id')
                        file_name = r.get('file_name') or '문서'
                        safe_name = file_name.replace(']', '\\]').replace('[', '\\[')
                        max_sim = r.get('max_similarity', 0.0)
                        pct = int(round(max_sim * 100))
                        ext = ''
                        if '.' in file_name:
                            ext = file_name.rsplit('.', 1)[-1]
                        if link_mode == 'template' and custom_tpl:
                            # 템플릿 치환 (미포함 시 {file_id} 추가)
                            if '{file_id}' in custom_tpl:
                                url = custom_tpl.replace('{file_id}', str(file_id))
                            else:
                                sep = '&' if '?' in custom_tpl else '?'
                                url = f"{custom_tpl}{sep}fileId={file_id}"
                            # 단순 외부 링크 (새탭) - 프론트 인터셉트가 필요하면 scheme 사용 권장
                        else:
                            # 기본: 커스텀 스킴 (프론트 마크다운 a 태그 인터셉트)
                            # 인코딩 (간단 처리)
                            from urllib.parse import quote
                            q_name = quote(file_name)
                            q_ext = quote(ext)
                            url = f"{scheme_prefix}?docId={file_id}&name={q_name}&ext={q_ext}&sim={pct}"
                        # 유사도 표시: HTML span 대신 마크다운 텍스트만 사용 (프론트엔드에서 패턴 매칭 가능)
                        # 패턴: (유사도 {pct}%)  -> 예: (유사도 87%)
                        # 필요 시 프론트에서 /\(유사도 (\d+)%\)/ 패턴으로 뱃지 스타일 적용
                        lines.append(f"- [{safe_name}]({url}) (유사도 {pct}%)")
                    related_docs_md = "\n".join(lines)
            except Exception as rec_err:
                logger.debug(f"연관 문서 추천 스킵: {rec_err}")

            # 템플릿 placeholder 보호: 존재하지 않을 경우 안전 처리
            # format 호출 시 필요한 placeholder만 제공
            format_kwargs: Dict[str, Any] = {"selected_documents": document_list, "failure_lead": failure_lead}
            if "{document_suggestions}" in failure_template:
                format_kwargs["document_suggestions"] = suggestions_md
            if "{suggestions_section}" in failure_template:
                format_kwargs["suggestions_section"] = suggestions_section
            if "{related_documents}" in failure_template:
                format_kwargs["related_documents"] = related_docs_md or "(연관 문서 후보 없음)"
            else:
                # 템플릿에 섹션이 없다면 꼬리에 추가
                if related_docs_md:
                    failure_template += f"\n\n### 🔗 연관 문서 후보\n\n{related_docs_md}\n"
                if not "{suggestions_section}" in failure_template:
                    failure_template += suggestions_section
            
            try:
                response = failure_template.format(**format_kwargs)
            except KeyError as ke:
                # 예상치 못한 placeholder가 추가된 경우 안전 폴백
                logger.warning(f"⚠️ 검색 실패 템플릿 키 누락: {ke}. 제공된 키만 사용해 재시도")
                safe_template = failure_template
                for missing_key in ["document_suggestions", "selected_documents", "related_documents", "suggestions_section"]:
                    if f"{{{missing_key}}}" in safe_template and missing_key not in format_kwargs:
                        safe_template = safe_template.replace(f"{{{missing_key}}}", "")
                response = safe_template.format(**format_kwargs)
            
            logger.info(f"✅ 검색 실패 응답 생성 완료: {len(selected_documents)}개 문서")
            return response
            
        except Exception as e:
            logger.error(f"❌ 검색 실패 응답 생성 중 오류: {e}")
            # 최소한의 기본 메시지
            return f"""# ❌ 시스템 오류

죄송합니다. **"{query}"**에 대한 검색 중 오류가 발생했습니다.

---

## 🔄 **다시 시도해주세요**
- 잠시 후 동일한 질문으로 다시 시도해보세요
- 다른 키워드나 표현으로 질문해보세요  
- 문제가 지속되면 관리자에게 문의해주세요

---

💬 **이용에 불편을 드려 죄송합니다.**"""
    
    async def _try_keyword_fallback_search(
        self,
        query: str,
        document_ids: List[str],
        container_ids: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """키워드 기반 폴백 검색"""
        try:
            # 더 관대한 검색 파라미터로 재시도
            fallback_params = RAGSearchParams(
                query=query,
                limit=self.rag_max_chunks,
                threshold=0.15,  # 매우 낮은 임계값
                similarity_threshold=0.15,
                search_mode='keyword',  # 키워드 검색만 사용
                reranking=False,  # 리랭킹 비활성화로 속도 향상
                document_ids=document_ids
            )
            
            logger.info(f"🔄 폴백 검색 시도: threshold=0.15, mode=keyword")
            
            # 키워드 기반 검색 실행
            fallback_result = await rag_search_service.search_with_rag(
                fallback_params,
                container_ids=container_ids
            )
            
            return fallback_result
            
        except Exception as e:
            logger.error(f"❌ 키워드 폴백 검색 중 오류: {e}")
            return None
    
    async def _load_documents_for_summarization(
        self,
        selected_documents: List[SelectedDocument],
        db_session: AsyncSession,
        max_chunks: int = 50
    ) -> tuple[str, List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        요약 요청 시 선택 문서의 원문을 직접 로드
        
        🔧 DocumentLoaderTool 사용: 검색 없이 문서 chunk를 순서대로 로드
        """
        try:
            from app.tools.document.document_loader_tool import document_loader_tool
            
            document_ids = [int(doc.id) for doc in selected_documents]
            logger.info(f"� [Summarization] DocumentLoaderTool 사용: {len(document_ids)}개 문서")
            
            # DocumentLoaderTool로 문서 로드
            tool_result = await document_loader_tool._arun(
                document_ids=document_ids,
                db_session=db_session,
                max_chunks=max_chunks,
                user_emp_no=None  # 권한 확인은 이미 API 레벨에서 완료
            )
            
            if not tool_result.success or not tool_result.data:
                # chunk가 없으면 명확한 오류 메시지
                logger.warning(f"⚠️ 선택 문서의 내용을 찾을 수 없음: {document_ids}")
                logger.warning(f"   도구 오류: {tool_result.errors}")
                
                doc_names = [doc.fileName for doc in selected_documents]
                failure_msg = f"""죄송합니다. 선택하신 문서의 내용을 찾을 수 없습니다:

{chr(10).join(f'- {name}' for name in doc_names)}

이 문서가 아직 처리 중이거나, 시스템 오류가 발생했을 수 있습니다.
다른 문서를 선택하시거나, 잠시 후 다시 시도해 주세요."""
                
                return failure_msg, [], {"chunks_count": 0, "documents_count": 0}, {"rag_used": False, "summarization_mode": True}
            
            # SearchChunk를 컨텍스트로 변환
            chunks_data = []
            context_parts = []
            
            for chunk in tool_result.data:
                file_name = chunk.metadata.get("file_name", f"문서 {chunk.file_id}")
                page_number = chunk.metadata.get("page_number", "?")
                context_parts.append(f"[{file_name} - p.{page_number}]\n{chunk.content}")
                
                chunks_data.append({
                    "file_id": chunk.file_id,
                    "file_name": file_name,
                    "chunk_index": chunk.metadata.get("chunk_index", 0),
                    "page_number": page_number,
                    "content": chunk.content[:500],  # 미리보기용
                    "similarity_score": chunk.score,
                    "search_type": chunk.match_type
                })
            
            context_text = "\n\n---\n\n".join(context_parts)
            
            logger.info(
                f"✅ [Summarization] 문서 로드 완료: {len(chunks_data)}개 청크, "
                f"{len(context_text)}자, latency={tool_result.metrics.latency_ms:.1f}ms"
            )
            
            context_info = {
                "chunks_count": len(chunks_data),
                "documents_count": len(set(c["file_id"] for c in chunks_data)),
                "total_tokens": len(context_text) // 4,  # 대략적인 토큰 수
                "summarization_mode": True,
                "tool_used": "document_loader",
                "tool_latency_ms": tool_result.metrics.latency_ms
            }
            
            rag_stats = {
                "rag_used": True,
                "summarization_mode": True,
                "search_skipped": True,
                "direct_load": True,
                "tool_name": tool_result.tool_name,
                "tool_version": tool_result.tool_version
            }
            
            return context_text, chunks_data, context_info, rag_stats
            
        except Exception as e:
            logger.error(f"❌ 요약용 문서 로드 실패: {e}")
            import traceback
            traceback.print_exc()
            
            failure_msg = f"""죄송합니다. 문서를 불러오는 중 오류가 발생했습니다.

오류: {str(e)}

잠시 후 다시 시도해 주세요."""
            
            return failure_msg, [], {"chunks_count": 0}, {"rag_used": False, "error": str(e)}
    
    def validate_agent_requirements(
        self, 
        agent_type: str, 
        selected_documents: List[SelectedDocument]
    ) -> tuple[bool, str]:
        """Agent 요구사항 검증"""
        
        agent_config = self.get_agent_config(agent_type)
        
        if agent_config.required_documents and len(selected_documents) == 0:
            return False, f"'{agent_config.name}' 에이전트는 문서 선택이 필요합니다."
        
        return True, "OK"
    
    def get_response_format_instruction(self, agent_type: str) -> str:
        """Agent별 응답 형식 지시사항"""
        
        agent_config = self.get_agent_config(agent_type)
        
        format_instructions = {
            'text': "",
            'markdown': "\n\n응답을 마크다운 형식으로 작성해주세요.",
            'json': "\n\n응답을 JSON 형식으로 구조화해주세요.",
        }
        
        return format_instructions.get(agent_config.output_format, "")


# 싱글톤 인스턴스
ai_agent_service = AIAgentService()
