"""
Agent-based Chat API - PaperSearchAgent를 사용한 새로운 채팅 엔드포인트
Feature flag로 점진적 전환 가능
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.agents import paper_search_agent
from app.tools.contracts import AgentConstraints, AgentIntent, AgentResult
from loguru import logger


router = APIRouter(tags=["agent"])


# Request/Response 모델
class AgentChatRequest(BaseModel):
    """Agent 기반 채팅 요청"""
    message: str = Field(..., min_length=1, description="사용자 질의")
    session_id: Optional[str] = Field(None, description="세션 ID")
    
    # 제약 조건
    max_chunks: int = Field(10, ge=1, le=50, description="최대 청크 수")
    max_tokens: int = Field(4000, ge=100, le=8000, description="최대 토큰 수")  # 2000 → 4000 (일반 RAG와 동일)
    similarity_threshold: float = Field(0.25, ge=0.0, le=1.0, description="유사도 임계값")  # 0.5 → 0.25로 낮춤 (일반 RAG와 동일)
    
    # 필터링
    container_ids: Optional[List[str]] = Field(None, description="컨테이너 ID 필터")
    document_ids: Optional[List[str]] = Field(None, description="문서 ID 필터")


class AgentStepResponse(BaseModel):
    """에이전트 실행 단계"""
    step_number: int
    tool_name: str
    reasoning: str
    latency_ms: float
    items_returned: Optional[int] = None
    success: bool


class ReferenceDocument(BaseModel):
    """참조 문서"""
    chunk_id: str
    content: str
    score: float
    document_id: Optional[str] = None
    title: Optional[str] = None
    page_number: Optional[int] = None


class DetailedChunk(BaseModel):
    """상세 청크 정보 (일반 채팅과 동일 형식)"""
    index: int
    file_id: int
    file_name: str
    chunk_index: int
    page_number: Optional[int] = None
    content_preview: str
    similarity_score: float
    search_type: str
    section_title: str = ""


class AgentChatResponse(BaseModel):
    """Agent 기반 채팅 응답"""
    answer: str
    intent: str
    strategy_used: List[str]
    references: List[ReferenceDocument]
    detailed_chunks: List[DetailedChunk] = []  # 🆕 일반 채팅과 동일 형식
    steps: List[AgentStepResponse]
    metrics: Dict[str, Any]
    success: bool
    errors: List[str] = []


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Agent 기반 채팅 엔드포인트
    
    PaperSearchAgent를 사용하여:
    1. 질의 의도 분석
    2. 동적 전략 선택 (도구 조합)
    3. 도구 순차 실행
    4. 컨텍스트 구성 및 답변 생성
    
    기존 /chat/message와 병행 운영 가능 (A/B 테스트)
    """
    try:
        user_emp_no = str(current_user.emp_no)
        logger.info(f"🤖 [AgentChat] 사용자: {user_emp_no}, 질의: '{request.message[:50]}...'")
        
        # similarity_threshold 보정 (0.5 이상이면 0.25로 낮춤)
        effective_threshold = request.similarity_threshold
        if effective_threshold >= 0.5:
            logger.warning(f"⚠️ threshold {effective_threshold} → 0.25로 보정 (검색 결과 확보)")
            effective_threshold = 0.25
        
        # 제약 조건 생성
        constraints = AgentConstraints(
            max_chunks=request.max_chunks,
            max_tokens=request.max_tokens,
            similarity_threshold=effective_threshold,
            container_ids=request.container_ids,
            document_ids=request.document_ids
        )
        
        # 컨텍스트 생성
        context = {
            "user_emp_no": user_emp_no,
            "session_id": request.session_id or str(uuid.uuid4())
        }
        
        # Agent 실행
        result: AgentResult = await paper_search_agent.execute(
            query=request.message,
            db_session=db,
            constraints=constraints,
            context=context
        )
        
        # 응답 변환
        steps_response = []
        for step in result.steps:
            steps_response.append(AgentStepResponse(
                step_number=step.step_number,
                tool_name=step.tool_name,
                reasoning=step.reasoning,
                latency_ms=step.tool_output.metrics.latency_ms,
                items_returned=step.tool_output.metrics.items_returned,
                success=step.tool_output.success
            ))
        
        references_response = []
        detailed_chunks_response = []
        
        for idx, ref in enumerate(result.references):
            # SearchChunk에서 file_id와 metadata 정보 추출
            file_id = ref.file_id  # SearchChunk.file_id (직접 필드)
            file_name = None
            chunk_index = 0
            page_number = None
            
            if ref.metadata:
                file_name = ref.metadata.get("file_name") or ref.metadata.get("title")
                chunk_index = ref.metadata.get("chunk_index", 0)
                page_number = ref.metadata.get("page_number")
            
            # ReferenceDocument (기존 호환성)
            references_response.append(ReferenceDocument(
                chunk_id=ref.chunk_id,
                content=ref.content,
                score=ref.score,
                document_id=ref.metadata.get("document_id") if ref.metadata else None,
                title=file_name,  # file_name을 title로 사용
                page_number=page_number
            ))
            
            # DetailedChunk (일반 채팅과 동일 형식)
            detailed_chunks_response.append(DetailedChunk(
                index=idx + 1,
                file_id=int(file_id) if file_id and str(file_id).isdigit() else 0,
                file_name=file_name or "문서",
                chunk_index=chunk_index,
                page_number=page_number,
                content_preview=ref.content[:200] if ref.content else "",
                similarity_score=ref.score,
                search_type="agent",
                section_title=file_name or ""
            ))
        
        logger.info(
            f"✅ [AgentChat] 완료: {result.metrics.get('total_latency_ms', 0):.1f}ms, "
            f"{len(result.references)}개 참조, {len(result.steps)}개 단계"
        )
        
        return AgentChatResponse(
            answer=result.answer,
            intent=result.intent.value,
            strategy_used=result.strategy_used,
            references=references_response,
            detailed_chunks=detailed_chunks_response,  # 🆕 일반 채팅과 동일 형식
            steps=steps_response,
            metrics=result.metrics,
            success=result.success,
            errors=result.errors
        )
        
    except Exception as e:
        logger.error(f"❌ [AgentChat] 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent 실행 실패: {str(e)}"
        )


@router.post("/agent/compare", response_model=Dict[str, Any])
async def compare_architectures(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    A/B 비교 엔드포인트
    
    동일한 질의를 두 가지 아키텍처로 실행하여 비교:
    1. 기존 rag_search_service (monolithic)
    2. 새로운 paper_search_agent (agent-based)
    
    평가 및 성능 분석에 사용
    """
    try:
        user_emp_no = str(current_user.emp_no)
        logger.info(f"📊 [Compare] 사용자: {user_emp_no}, 질의: '{request.message[:50]}...'")
        
        # 제약 조건
        constraints = AgentConstraints(
            max_chunks=request.max_chunks,
            max_tokens=request.max_tokens,
            similarity_threshold=request.similarity_threshold,
            container_ids=request.container_ids,
            document_ids=request.document_ids
        )
        
        context = {
            "user_emp_no": user_emp_no,
            "session_id": request.session_id or str(uuid.uuid4())
        }
        
        # 새 아키텍처 실행
        start_time_new = datetime.utcnow()
        result_new: AgentResult = await paper_search_agent.execute(
            query=request.message,
            db_session=db,
            constraints=constraints,
            context=context
        )
        latency_new = (datetime.utcnow() - start_time_new).total_seconds() * 1000
        
        # 기존 아키텍처 실행
        # TODO: rag_search_service 호출 (현재는 mock)
        latency_old = 0.0
        result_old = {
            "answer": "[기존 아키텍처 결과 - TODO: rag_search_service 통합]",
            "references": [],
            "chunks_found": 0
        }
        
        # 비교 결과
        comparison = {
            "query": request.message,
            "old_architecture": {
                "answer": result_old["answer"],
                "latency_ms": latency_old,
                "chunks_found": result_old["chunks_found"],
                "implementation": "rag_search_service (monolithic)"
            },
            "new_architecture": {
                "answer": result_new.answer,
                "latency_ms": latency_new,
                "chunks_found": result_new.metrics.get("chunks_found", 0),
                "chunks_used": result_new.metrics.get("chunks_used", 0),
                "intent": result_new.intent.value,
                "strategy": result_new.strategy_used,
                "tools_used": len(result_new.steps),
                "implementation": "paper_search_agent (agent-based)"
            },
            "improvement": {
                "latency_diff_ms": latency_old - latency_new,
                "latency_improvement_pct": ((latency_old - latency_new) / latency_old * 100) if latency_old > 0 else 0,
            },
            "observability": {
                "agent_steps": [
                    {
                        "tool": step.tool_name,
                        "reasoning": step.reasoning,
                        "latency_ms": step.tool_output.metrics.latency_ms
                    }
                    for step in result_new.steps
                ]
            }
        }
        
        logger.info(
            f"📊 [Compare] 완료 - 신규: {latency_new:.1f}ms, 구: {latency_old:.1f}ms"
        )
        
        return comparison
        
    except Exception as e:
        logger.error(f"❌ [Compare] 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"비교 실행 실패: {str(e)}"
        )


@router.post("/agent/chat/stream")
async def agent_chat_stream(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    🆕 Agent 기반 채팅 스트리밍 엔드포인트
    
    실시간으로 AI의 사고 과정(Reasoning)과 답변을 스트리밍:
    1. reasoning_step: 각 도구 실행 단계 (질의 분석, 검색, 재정렬 등)
    2. search_progress: 검색 진행 상황 (벡터 검색, 키워드 검색 결과)
    3. content: 답변 텍스트 (청크 단위)
    4. metadata: 최종 메타데이터 (참고 문서, 메트릭)
    5. done: 완료
    """
    import json
    import asyncio
    from fastapi.responses import StreamingResponse
    
    async def event_generator():
        try:
            user_emp_no = str(current_user.emp_no)
            logger.info(f"🤖 [AgentChatStream] 사용자: {user_emp_no}, 질의: '{request.message[:50]}...'")
            
            # 제약 조건 생성
            effective_threshold = request.similarity_threshold
            if effective_threshold >= 0.5:
                effective_threshold = 0.25
            
            constraints = AgentConstraints(
                max_chunks=request.max_chunks,
                max_tokens=request.max_tokens,
                similarity_threshold=effective_threshold,
                container_ids=request.container_ids,
                document_ids=request.document_ids
            )
            
            context = {
                "user_emp_no": user_emp_no,
                "session_id": request.session_id or str(uuid.uuid4())
            }
            
            # 🧠 Step 1: 질의 분석
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'started', 'message': '질문을 분석하고 있습니다...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)  # UI 업데이트 시간
            
            intent = paper_search_agent.classify_intent(request.message)
            keywords = await paper_search_agent._extract_keywords(request.message)
            
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'completed', 'result': {'intent': intent.value, 'keywords': keywords}, 'message': f'의도: {intent.value}, 키워드: {keywords}'}, ensure_ascii=False)}\n\n"
            
            # 🔍 Step 2: 전략 선택
            strategy = paper_search_agent.select_strategy(intent, constraints)
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': strategy}, 'message': f'검색 전략: {strategy}'}, ensure_ascii=False)}\n\n"
            
            # 📊 Step 3: 도구 실행 (하이브리드 검색)
            all_chunks = []
            search_stats = {}
            
            for idx, tool_name in enumerate(strategy):
                if tool_name in ["vector_search", "keyword_search", "fulltext_search"]:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'search', 'status': 'started', 'tool': tool_name, 'message': f'{tool_name} 실행 중...'}, ensure_ascii=False)}\n\n"
                    
                    try:
                        tool_result = await paper_search_agent._execute_tool(
                            tool_name=tool_name,
                            query=request.message,
                            db_session=db,
                            keywords=keywords,
                            constraints=constraints,
                            chunks=all_chunks,
                            context=context
                        )
                        
                        if tool_result.success and hasattr(tool_result, 'data'):
                            new_chunks = tool_result.data
                            all_chunks.extend(new_chunks)
                            search_stats[tool_name] = {
                                'count': len(new_chunks),
                                'avg_score': sum(c.score for c in new_chunks) / len(new_chunks) if new_chunks else 0
                            }
                            
                            yield f"event: search_progress\ndata: {json.dumps({'tool': tool_name, 'chunks_found': len(new_chunks), 'total_chunks': len(all_chunks), 'avg_similarity': round(search_stats[tool_name]['avg_score'], 3)}, ensure_ascii=False)}\n\n"
                    
                    except Exception as e:
                        logger.error(f"검색 실패 ({tool_name}): {e}")
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'search', 'status': 'error', 'tool': tool_name, 'message': f'검색 실패: {str(e)}'}, ensure_ascii=False)}\n\n"
                
                elif tool_name in ["deduplicate", "rerank"]:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'postprocess', 'status': 'started', 'tool': tool_name, 'message': f'{tool_name} 처리 중...'}, ensure_ascii=False)}\n\n"
                    
                    try:
                        tool_result = await paper_search_agent._execute_tool(
                            tool_name=tool_name,
                            query=request.message,
                            db_session=db,
                            keywords=keywords,
                            constraints=constraints,
                            chunks=all_chunks,
                            context=context
                        )
                        
                        if tool_result.success and hasattr(tool_result, 'data'):
                            before_count = len(all_chunks)
                            all_chunks = tool_result.data
                            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'postprocess', 'status': 'completed', 'tool': tool_name, 'before': before_count, 'after': len(all_chunks), 'message': f'{tool_name}: {before_count}개 → {len(all_chunks)}개'}, ensure_ascii=False)}\n\n"
                    
                    except Exception as e:
                        logger.error(f"후처리 실패 ({tool_name}): {e}")
            
            # 🏗️ Step 4: 컨텍스트 구성
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'context_building', 'status': 'started', 'message': '컨텍스트를 구성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            
            context_result = await paper_search_agent._execute_tool(
                tool_name="context_builder",
                query=request.message,
                db_session=db,
                keywords=keywords,
                constraints=constraints,
                chunks=all_chunks,
                context=None
            )
            
            context_text = context_result.data if isinstance(context_result.data, str) else ""
            used_chunks = getattr(context_result, 'used_chunks', all_chunks[:5])
            
            token_count = len(context_text.split())  # 간단한 토큰 추정
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'context_building', 'status': 'completed', 'tokens': token_count, 'max_tokens': constraints.max_tokens, 'chunks_used': len(used_chunks), 'message': f'컨텍스트 구성 완료: {token_count} 토큰, {len(used_chunks)}개 청크 사용'}, ensure_ascii=False)}\n\n"
            
            # ✍️ Step 5: 답변 생성
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'answer_generation', 'status': 'started', 'message': '답변을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            
            prompt = f"""다음 컨텍스트를 참고하여 질문에 답변해주세요.

컨텍스트:
{context_text}

질문: {request.message}

답변:"""
            
            # AI 답변 생성 (스트리밍)
            answer = await paper_search_agent.ai_service.chat(
                message=prompt,
                provider="azure_openai"
            )
            
            # 답변을 청크로 나눠서 전송
            if isinstance(answer, str):
                chunk_size = 50
                for i in range(0, len(answer), chunk_size):
                    chunk = answer[i:i+chunk_size]
                    yield f"event: content\ndata: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.05)  # 스트리밍 효과
            
            # 📋 Step 6: 메타데이터 전송
            detailed_chunks = []
            for idx, chunk in enumerate(used_chunks):
                file_id = chunk.file_id
                file_name = chunk.metadata.get("file_name") if chunk.metadata else "문서"
                
                detailed_chunks.append({
                    "index": idx + 1,
                    "file_id": int(file_id) if file_id and str(file_id).isdigit() else 0,
                    "file_name": file_name,
                    "chunk_index": chunk.metadata.get("chunk_index", 0) if chunk.metadata else 0,
                    "page_number": chunk.metadata.get("page_number") if chunk.metadata else None,
                    "content_preview": chunk.content[:200] if chunk.content else "",
                    "similarity_score": chunk.score,
                    "search_type": "hybrid",
                    "section_title": file_name
                })
            
            metadata = {
                "intent": intent.value,
                "strategy_used": strategy,
                "detailed_chunks": detailed_chunks,
                "search_stats": search_stats,
                "total_chunks_searched": len(all_chunks),
                "chunks_used": len(used_chunks)
            }
            
            yield f"event: metadata\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"
            
            # 💾 세션 및 대화 내역 저장
            try:
                from app.models.chat.chat_models import TbChatSessions, TbChatHistory
                from sqlalchemy import select, update
                from datetime import datetime as dt
                
                session_id = context.get("session_id")
                user_emp_no = context.get("user_emp_no")
                
                # 세션 존재 확인
                session_stmt = select(TbChatSessions).where(TbChatSessions.session_id == session_id)
                session_result = await db.execute(session_stmt)
                existing_session = session_result.scalar_one_or_none()
                
                if not existing_session:
                    # 새 세션 생성
                    new_session = TbChatSessions(
                        session_id=session_id,
                        user_emp_no=user_emp_no,
                        session_name=f"Agent Chat - {request.message[:30]}...",
                        session_description="AI Agent 채팅 세션",
                        default_container_id=request.container_ids[0] if request.container_ids else None,
                        allowed_containers=request.container_ids,
                        is_active=True,
                        last_activity=dt.utcnow(),
                        message_count=1
                    )
                    db.add(new_session)
                    logger.info(f"✅ [AgentSession] 새 세션 생성: {session_id}")
                else:
                    # 기존 세션 업데이트
                    update_stmt = (
                        update(TbChatSessions)
                        .where(TbChatSessions.session_id == session_id)
                        .values(
                            last_activity=dt.utcnow(),
                            message_count=TbChatSessions.message_count + 1
                        )
                    )
                    await db.execute(update_stmt)
                    logger.info(f"✅ [AgentSession] 세션 업데이트: {session_id}")
                
                # 대화 내역 저장
                referenced_doc_ids = list(set([
                    int(chunk["file_id"]) 
                    for chunk in detailed_chunks 
                    if chunk.get("file_id") and chunk["file_id"] > 0
                ]))
                
                chat_history = TbChatHistory(
                    session_id=session_id,
                    user_emp_no=user_emp_no,
                    knowledge_container_id=request.container_ids[0] if request.container_ids else None,
                    accessible_containers=request.container_ids,
                    user_message=request.message,
                    assistant_response=answer,
                    search_query=request.message,
                    search_results={
                        "chunks": detailed_chunks[:10],  # 최대 10개만 저장
                        "total_searched": len(all_chunks),
                        "total_used": len(used_chunks)
                    },
                    referenced_documents=referenced_doc_ids if referenced_doc_ids else None,
                    model_used="agent/paper_search_agent",
                    model_parameters={
                        "intent": intent.value,
                        "strategy": strategy,
                        "max_chunks": request.max_chunks,
                        "similarity_threshold": effective_threshold
                    },
                    conversation_context={
                        "search_stats": search_stats,
                        "reasoning_steps": len(strategy)
                    }
                )
                db.add(chat_history)
                await db.commit()
                
                logger.info(f"💾 [AgentSession] 대화 저장 완료: session={session_id}, docs={len(referenced_doc_ids)}")
                
            except Exception as save_error:
                logger.error(f"❌ [AgentSession] 저장 실패: {save_error}")
                await db.rollback()
                # 저장 실패해도 스트리밍은 계속 진행
            
            # ✅ 완료
            yield f"event: done\ndata: {json.dumps({'success': True, 'session_id': context.get('session_id')}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ [AgentChatStream] 오류: {error_msg}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/agent/sessions/{session_id}")
async def get_agent_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Agent 세션 복원
    
    세션 메타데이터 + 대화 히스토리 조회
    """
    try:
        from app.models.chat.chat_models import TbChatSessions, TbChatHistory
        from sqlalchemy import select
        
        user_emp_no = str(current_user.emp_no)
        
        # 세션 조회
        session_stmt = (
            select(TbChatSessions)
            .where(
                TbChatSessions.session_id == session_id,
                TbChatSessions.user_emp_no == user_emp_no  # 권한 확인
            )
        )
        session_result = await db.execute(session_stmt)
        session = session_result.scalar_one_or_none()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"세션을 찾을 수 없습니다: {session_id}"
            )
        
        # 대화 히스토리 조회
        history_stmt = (
            select(TbChatHistory)
            .where(TbChatHistory.session_id == session_id)
            .order_by(TbChatHistory.created_date.asc())
        )
        history_result = await db.execute(history_stmt)
        history_records = history_result.scalars().all()
        
        # 응답 변환
        messages = []
        for record in history_records:
            messages.append({
                "chat_id": record.chat_id,
                "user_message": record.user_message,
                "assistant_response": record.assistant_response,
                "referenced_documents": record.referenced_documents or [],
                "search_results": record.search_results,
                "model_used": record.model_used,
                "model_parameters": record.model_parameters,
                "created_date": record.created_date.isoformat()
            })
        
        return {
            "session_id": session.session_id,
            "session_name": session.session_name,
            "session_description": session.session_description,
            "user_emp_no": session.user_emp_no,
            "default_container_id": session.default_container_id,
            "allowed_containers": session.allowed_containers,
            "is_active": session.is_active,
            "last_activity": session.last_activity.isoformat(),
            "message_count": session.message_count,
            "created_date": session.created_date.isoformat(),
            "messages": messages
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [AgentSession] 복원 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 복원 실패: {str(e)}"
        )


@router.get("/agent/sessions")
async def list_agent_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """
    사용자의 Agent 세션 목록 조회
    """
    try:
        from app.models.chat.chat_models import TbChatSessions
        from sqlalchemy import select
        
        user_emp_no = str(current_user.emp_no)
        
        stmt = (
            select(TbChatSessions)
            .where(TbChatSessions.user_emp_no == user_emp_no)
            .order_by(TbChatSessions.last_activity.desc())
            .limit(limit)
            .offset(offset)
        )
        
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "session_name": s.session_name,
                    "last_activity": s.last_activity.isoformat(),
                    "message_count": s.message_count,
                    "is_active": s.is_active
                }
                for s in sessions
            ],
            "total": len(sessions),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"❌ [AgentSession] 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"세션 목록 조회 실패: {str(e)}"
        )


@router.get("/agent/health")
async def agent_health():
    """Agent 시스템 상태 확인"""
    return {
        "status": "healthy",
        "agent": paper_search_agent.name,
        "version": paper_search_agent.version,
        "tools": list(paper_search_agent.tools.keys()),
        "timestamp": datetime.utcnow().isoformat()
    }
