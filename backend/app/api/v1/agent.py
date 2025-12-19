"""
Agent-based Chat API - PaperSearchAgent를 사용한 새로운 채팅 엔드포인트
Feature flag로 점진적 전환 가능

통합된 엔드포인트:
- /agent/chat - 기본 채팅
- /agent/chat/stream - 스트리밍 채팅
- /agent/chat/assets - 첨부파일 업로드
- /agent/chat/assets/{asset_id} - 첨부파일 다운로드
- /agent/chat/transcribe - 음성→텍스트 변환
- /agent/sessions - 세션 관리
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid
import os
import tempfile
import asyncio
import aiofiles
from botocore.exceptions import ClientError
from urllib.parse import quote

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.models import User
from app.agents import paper_search_agent
from app.agents.supervisor_agent import supervisor_agent
from langchain_core.messages import HumanMessage
from app.tools.contracts import AgentConstraints, AgentIntent, AgentResult
from loguru import logger
from app.services.document.extraction.text_extractor_service import TextExtractorService
from app.services.chat.chat_attachment_service import chat_attachment_service
from app.services.core.audio_transcription_service import audio_transcription_service
from pathlib import Path


# 태그는 main.py에서 include_router 시 설정됨 (tags=["🤖 Agent RAG"])
router = APIRouter()


def _should_force_ppt_generation(message: str, tool: Optional[str]) -> bool:
    """사용자 질의나 도구 선택을 기반으로 PPT 생성을 강제할지 여부를 판단."""
    if tool == 'ppt':
        return True

    if not message:
        return False

    lowered = message.lower()
    ppt_keywords = [
        "ppt",
        "프레젠테이션",
        "프리젠테이션",
        "발표자료",
        "발표 자료",
        "슬라이드",
        "presentation"
    ]
    # 간단한 휴리스틱: 키워드가 포함되어 있고 "만들", "작성", "생성" 등의 동사가 함께 등장하면 PPT 요청으로 간주
    action_keywords = ["만들", "작성", "생성", "제작", "작성해", "만들어", "create", "generate"]
    contains_ppt = any(keyword in lowered for keyword in ppt_keywords)
    contains_action = any(action in lowered for action in action_keywords)
    return contains_ppt and contains_action


# Request/Response 모델
class AgentChatRequest(BaseModel):
    """Agent 기반 채팅 요청"""
    message: str = Field(..., min_length=1, description="사용자 질의")
    images: Optional[List[str]] = Field(None, description="이미지 목록 (Base64)")
    session_id: Optional[str] = Field(None, description="세션 ID")
    
    # 제약 조건
    max_chunks: int = Field(10, ge=1, le=50, description="최대 청크 수")
    max_tokens: int = Field(4000, ge=100, le=8000, description="최대 토큰 수")  # 2000 → 4000 (일반 RAG와 동일)
    similarity_threshold: float = Field(0.25, ge=0.0, le=1.0, description="유사도 임계값")  # 0.5 → 0.25로 낮춤 (일반 RAG와 동일)
    
    # 필터링
    container_ids: Optional[List[str]] = Field(None, description="컨테이너 ID 필터")
    document_ids: Optional[List[str]] = Field(None, description="문서 ID 필터")
    
    # 🆕 첨부 파일 (Chat with File)
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="첨부 파일 목록 (asset_id, mime_type 등)")
    
    # 🆕 도구 강제 선택
    tool: Optional[str] = Field(None, description="강제 선택할 도구 (ppt, web-search 등)")


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
    Agent 기반 채팅 엔드포인트 (Supervisor Architecture)
    
    Supervisor Agent를 사용하여:
    1. 사용자 의도 파악 (검색 vs PPT 생성 vs 기타)
    2. 적절한 Worker Agent (SearchAgent, PresentationAgent) 호출
    3. 결과 통합 및 반환
    """
    try:
        user_emp_no = str(current_user.emp_no)
        logger.info(f"🤖 [AgentChat] 사용자: {user_emp_no}, 질의: '{request.message[:50]}...'")
        
        # Supervisor 실행
        initial_state = {
            "messages": [HumanMessage(content=request.message)],
            "next": "",
            "shared_context": {}
        }
        
        # LangGraph 실행
        final_state = await supervisor_agent.ainvoke(initial_state)
        
        # 결과 추출
        messages = final_state["messages"]
        last_message = messages[-1]
        answer = last_message.content
        shared_context = final_state.get("shared_context", {})
        
        # SearchAgent 결과 복원
        search_result = shared_context.get("search_agent_result")
        
        # 기본값 설정
        references_response = []
        detailed_chunks_response = []
        steps_response = []
        metrics = {}
        intent = "general"
        strategy_used = []
        
        if search_result:
            # SearchAgent가 실행된 경우 정보 복원
            intent = search_result.intent.value
            strategy_used = search_result.strategy_used
            metrics = search_result.metrics
            
            # Steps
            for step in search_result.steps:
                steps_response.append(AgentStepResponse(
                    step_number=step.step_number,
                    tool_name=step.tool_name,
                    reasoning=step.reasoning,
                    latency_ms=step.tool_output.metrics.latency_ms,
                    items_returned=step.tool_output.metrics.items_returned,
                    success=step.tool_output.success
                ))
            
            # References & Chunks
            for idx, ref in enumerate(search_result.references):
                file_id = ref.file_id
                file_name = None
                chunk_index = 0
                page_number = None
                
                if ref.metadata:
                    file_name = ref.metadata.get("file_name") or ref.metadata.get("title")
                    chunk_index = ref.metadata.get("chunk_index", 0)
                    page_number = ref.metadata.get("page_number")
                
                references_response.append(ReferenceDocument(
                    chunk_id=ref.chunk_id,
                    content=ref.content,
                    score=ref.score,
                    document_id=ref.metadata.get("document_id") if ref.metadata else None,
                    title=file_name,
                    page_number=page_number
                ))
                
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
        
        # PresentationAgent가 실행된 경우 (마지막 메시지가 PresentationAgent인 경우)
        if getattr(last_message, "name", "") == "PresentationAgent":
            intent = "presentation_generation"
            # PPT 생성 관련 메트릭이나 스텝 추가 가능
            steps_response.append(AgentStepResponse(
                step_number=len(steps_response) + 1,
                tool_name="PresentationAgent",
                reasoning="Generated presentation based on search results.",
                latency_ms=0,
                success=True
            ))

        logger.info(f"✅ [AgentChat] 완료: {len(references_response)}개 참조")
        
        return AgentChatResponse(
            answer=answer,
            intent=intent,
            strategy_used=strategy_used,
            references=references_response,
            detailed_chunks=detailed_chunks_response,
            steps=steps_response,
            metrics=metrics,
            success=True,
            errors=[]
        )
        
    except Exception as e:
        logger.error(f"❌ [AgentChat] 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent 실행 실패: {str(e)}"
        )


@router.post("/agent/chat/v2", response_model=AgentChatResponse)
async def agent_chat_v2(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """V2 라우트 유지용 alias: 현재는 기존 `paper_search_agent`로 처리합니다."""
    try:
        user_emp_no = str(current_user.emp_no)
        logger.info(f"🤖🆕 [AgentChatV2] 사용자: {user_emp_no}, 질의: '{request.message[:50]}...'")

        constraints_obj = AgentConstraints(
            max_chunks=request.max_chunks,
            max_tokens=request.max_tokens,
            similarity_threshold=request.similarity_threshold,
            container_ids=request.container_ids,
            document_ids=request.document_ids,
        )

        context = {
            "user_emp_no": user_emp_no,
            "session_id": request.session_id or str(uuid.uuid4()),
        }

        # 대화 히스토리 조회 (멀티턴 지원)
        history: List[Dict[str, str]] = []
        if request.session_id:
            try:
                from app.models.chat.chat_models import TbChatHistory
                from sqlalchemy import select

                history_stmt = (
                    select(TbChatHistory)
                    .where(TbChatHistory.session_id == request.session_id)
                    .order_by(TbChatHistory.created_date.asc())
                    .limit(10)
                )
                history_result = await db.execute(history_stmt)
                history_records = history_result.scalars().all()

                for record in history_records:
                    if record.user_message:
                        history.append({"role": "user", "content": record.user_message})
                    if record.assistant_response:
                        history.append({"role": "assistant", "content": record.assistant_response})

                logger.info(f"📚 [AgentChatV2] 히스토리 로드: {len(history)}개 메시지")
            except Exception as e:
                logger.warning(f"⚠️ 히스토리 로드 실패: {e}")

        result: AgentResult = await paper_search_agent.execute(
            query=request.message,
            db_session=db,
            constraints=constraints_obj,
            context=context,
            history=history,
            images=request.images or [],
            attachments=request.attachments or [],
        )

        steps_response: List[AgentStepResponse] = []
        for step in result.steps:
            steps_response.append(
                AgentStepResponse(
                    step_number=step.step_number,
                    tool_name=step.tool_name,
                    reasoning=step.reasoning,
                    latency_ms=0,
                    success=True,
                )
            )

        references_response: List[ReferenceDocument] = []
        detailed_chunks_response: List[DetailedChunk] = []

        for idx, ref in enumerate(result.references or []):
            file_name = None
            chunk_index = 0
            page_number = None

            if ref.metadata:
                file_name = ref.metadata.get("file_name") or ref.metadata.get("title")
                chunk_index = ref.metadata.get("chunk_index", 0)
                page_number = ref.metadata.get("page_number")

            references_response.append(
                ReferenceDocument(
                    chunk_id=ref.chunk_id,
                    content=ref.content,
                    score=ref.score,
                    document_id=ref.metadata.get("document_id") if ref.metadata else None,
                    title=file_name,
                    page_number=page_number,
                )
            )

            detailed_chunks_response.append(
                DetailedChunk(
                    index=idx + 1,
                    file_id=int(ref.file_id) if ref.file_id and str(ref.file_id).isdigit() else 0,
                    file_name=file_name or "문서",
                    chunk_index=chunk_index,
                    page_number=page_number,
                    content_preview=(ref.content or "")[:200],
                    similarity_score=ref.score,
                    search_type="agent",
                    section_title=file_name or "",
                )
            )

        logger.info(f"✅ [AgentChatV2] 완료: {len(result.steps)}개 단계")

        return AgentChatResponse(
            answer=result.answer,
            intent=result.intent.value if result.intent else "general",
            strategy_used=result.strategy_used or [],
            references=references_response,
            detailed_chunks=detailed_chunks_response,
            steps=steps_response,
            metrics=result.metrics or {},
            success=result.success,
            errors=result.errors or [],
        )

    except Exception as e:
        logger.error(f"❌ [AgentChatV2] 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent V2 실행 실패: {str(e)}",
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
            
            # 📚 대화 히스토리 조회 (멀티턴 지원)
            chat_history_messages = []
            session_attached_files = []  # 🆕 세션에 저장된 첨부 파일
            if request.session_id:
                try:
                    from app.models.chat.chat_models import TbChatHistory
                    from sqlalchemy import select
                    
                    history_stmt = (
                        select(TbChatHistory)
                        .where(TbChatHistory.session_id == request.session_id)
                        .order_by(TbChatHistory.created_date.asc())
                    )
                    history_result = await db.execute(history_stmt)
                    history_records = history_result.scalars().all()
                    
                    for record in history_records:
                        if record.user_message:
                            chat_history_messages.append({"role": "user", "content": record.user_message})
                        if record.assistant_response:
                            chat_history_messages.append({"role": "assistant", "content": record.assistant_response})
                        
                        # 🆕 세션의 첨부 파일 로드 (가장 최근 것만)
                        if record.model_parameters and isinstance(record.model_parameters, dict):
                            attached = record.model_parameters.get('attached_files', [])
                            if attached and isinstance(attached, list):
                                session_attached_files = attached  # 최신 파일 목록으로 갱신
                            
                    logger.info(f"📚 [AgentChatStream] 히스토리 로드: {len(chat_history_messages)}개 메시지, 세션 첨부파일: {len(session_attached_files)}개")
                except Exception as e:
                    logger.warning(f"⚠️ 히스토리 로드 실패: {e}")
            
            # 🧠 Step 1: 질의 분석
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'started', 'message': '질문을 분석하고 있습니다...'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)  # UI 업데이트 시간
            
            # 🆕 이미지 분석 (request.images + attachments에서 이미지 추출)
            image_description = ""
            images_to_analyze = list(request.images) if request.images else []
            
            # 🆕 문서 첨부 처리 (Chat with File)
            attached_document_context = ""
            attached_files = []  # 첨부 파일 메타데이터 (프론트엔드 표시용)
            
            # 🆕 세션에 저장된 첨부 파일을 기본으로 사용
            all_attachments = []
            if session_attached_files:
                # 세션의 첨부 파일을 첨부 목록으로 변환
                for sf in session_attached_files:
                    all_attachments.append({
                        'asset_id': sf.get('asset_id') or sf.get('id'),
                        'id': sf.get('asset_id') or sf.get('id'),
                        'category': sf.get('category', 'document'),
                        'file_name': sf.get('file_name', ''),
                        'mime_type': sf.get('mime_type', ''),
                        'file_size': sf.get('file_size', 0)
                    })
                logger.info(f"📎 [AgentChatStream] 세션 첨부 파일 복원: {len(all_attachments)}개")
            
            # 현재 요청의 첨부 파일 추가 (중복 제거)
            if request.attachments:
                existing_ids = {att.get('asset_id') or att.get('id') for att in all_attachments}
                for att in request.attachments:
                    att_id = att.get('asset_id') or att.get('id')
                    if att_id and att_id not in existing_ids:
                        all_attachments.append(att)
                        logger.info(f"🆕 [AgentChatStream] 새 첨부 파일 추가: {att.get('file_name', att_id)}")
            
            if all_attachments:
                # 🆕 첨부 파일에서 이미지 추출하여 분석 대상에 추가
                image_attachments = [
                    att for att in all_attachments 
                    if att.get('mime_type', '').startswith('image/')
                ]
                
                if image_attachments:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'image_analysis', 'status': 'started', 'message': f'첨부된 이미지 {len(image_attachments)}개를 분석하고 있습니다...'}, ensure_ascii=False)}\n\n"
                    
                    # 이미지 파일 로드 (base64로 변환)
                    for img_att in image_attachments:
                        asset_id = img_att.get('asset_id') or img_att.get('id')
                        if not asset_id:
                            continue
                        
                        stored_file = chat_attachment_service.get(asset_id)
                        if stored_file:
                            try:
                                import base64
                                img_data = None
                                
                                # S3 스토리지 처리
                                if getattr(stored_file, 'storage_backend', 'local') == 's3':
                                    if chat_attachment_service.s3_client:
                                        response = chat_attachment_service.s3_client.get_object(
                                            Bucket=chat_attachment_service.s3_bucket,
                                            Key=str(stored_file.path)
                                        )
                                        img_data = response['Body'].read()
                                    else:
                                        logger.error(f"❌ S3 클라이언트 초기화 실패: {asset_id}")
                                        continue
                                # 로컬 스토리지 처리
                                else:
                                    with open(stored_file.path, 'rb') as f:
                                        img_data = f.read()
                                
                                if img_data:
                                    img_base64 = base64.b64encode(img_data).decode('utf-8')
                                    # MIME 타입에 따라 헤더 추가
                                    mime = img_att.get('mime_type', 'image/jpeg')
                                    images_to_analyze.append(f"data:{mime};base64,{img_base64}")
                                    logger.info(f"📷 [AgentChatStream] 이미지 로드: {img_att.get('file_name')}")
                            except Exception as e:
                                logger.error(f"❌ 이미지 로드 실패: {asset_id}, {e}")
                
                # 🆕 이미지 분석 도구 실행
                if images_to_analyze:
                    try:
                        image_tool = paper_search_agent.tools.get('image_analysis')
                        if image_tool:
                            image_description = await image_tool._arun(
                                images=images_to_analyze,
                                query=request.message,
                                detail_level="detailed"
                            )
                            logger.info(f"✅ [AgentChatStream] 이미지 분석 완료: {len(image_description)}자")
                            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'image_analysis', 'status': 'completed', 'message': f'이미지 분석 완료 ({len(images_to_analyze)}개)'}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        logger.error(f"❌ [AgentChatStream] 이미지 분석 실패: {e}")
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'image_analysis', 'status': 'error', 'message': f'이미지 분석 실패: {str(e)}'}, ensure_ascii=False)}\n\n"
                
                # 문서 파일 필터링 (이미지/오디오 제외)
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'started', 'message': '첨부된 문서를 분석하고 있습니다...'}, ensure_ascii=False)}\n\n"
                
                doc_attachments = [
                    att for att in all_attachments 
                    if not att.get('mime_type', '').startswith('image/') and not att.get('mime_type', '').startswith('audio/')
                ]
                
                if doc_attachments:
                    text_extractor = TextExtractorService()
                    extracted_texts = []
                    
                    for doc_att in doc_attachments:
                        asset_id = doc_att.get('asset_id') or doc_att.get('id')
                        if not asset_id:
                            continue
                            
                        stored_file = chat_attachment_service.get(asset_id)
                        if not stored_file:
                            logger.warning(f"⚠️ 첨부 파일 찾을 수 없음: {asset_id}")
                            continue
                            
                        # 파일 크기 제한 (3MB - Upstage API 제한 대응)
                        MAX_FILE_SIZE = 3 * 1024 * 1024
                        if stored_file.size > MAX_FILE_SIZE:
                            file_size_mb = stored_file.size / (1024 * 1024)
                            extracted_texts.append(f"[파일: {stored_file.file_name}]\n(파일이 너무 큽니다: {file_size_mb:.1f}MB. 채팅에서는 3MB 이하의 파일만 처리 가능합니다. 문서 업로드 기능을 사용해주세요.)")
                            logger.warning(f"⚠️ 파일 크기 초과: {stored_file.file_name} ({file_size_mb:.1f}MB)")
                            continue
                            
                        try:
                            # 텍스트 추출
                            import tempfile
                            import os
                            
                            extraction_path = str(stored_file.path)
                            is_temp_file = False
                            
                            # S3 스토리지인 경우 임시 파일로 다운로드
                            if getattr(stored_file, 'storage_backend', 'local') == 's3':
                                if chat_attachment_service.s3_client:
                                    suffix = Path(stored_file.file_name).suffix
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                                        chat_attachment_service.s3_client.download_fileobj(
                                            chat_attachment_service.s3_bucket,
                                            str(stored_file.path),
                                            tmp
                                        )
                                        extraction_path = tmp.name
                                        is_temp_file = True
                                else:
                                    logger.error(f"❌ S3 클라이언트 초기화 실패: {asset_id}")
                                    continue
                            
                            file_ext = Path(stored_file.file_name).suffix
                            
                            extraction_result = await text_extractor.extract_text_from_file(
                                file_path=extraction_path,
                                file_extension=file_ext
                            )
                            
                            # 임시 파일 삭제
                            if is_temp_file and os.path.exists(extraction_path):
                                os.unlink(extraction_path)
                            
                            if extraction_result.get('success') and extraction_result.get('text'):
                                text_content = extraction_result['text']
                                # 텍스트 길이 제한 (30,000자)
                                MAX_TEXT_LENGTH = 30000
                                if len(text_content) > MAX_TEXT_LENGTH:
                                    text_content = text_content[:MAX_TEXT_LENGTH] + "\n...(내용이 너무 길어 생략됨)"
                                    
                                extracted_texts.append(f"[첨부 파일 내용: {stored_file.file_name}]\n{text_content}")
                                attached_files.append({
                                    "file_name": stored_file.file_name,
                                    "file_size": stored_file.size,
                                    "text_length": len(text_content)
                                })
                                logger.info(f"✅ 문서 텍스트 추출 성공: {stored_file.file_name} ({len(text_content)}자)")
                            else:
                                logger.warning(f"⚠️ 텍스트 추출 실패: {stored_file.file_name}")
                        except Exception as e:
                            logger.error(f"❌ 문서 처리 중 오류: {e}")
                            # 임시 파일 정리 (에러 발생 시)
                            if 'is_temp_file' in locals() and is_temp_file and 'extraction_path' in locals() and os.path.exists(extraction_path):
                                try:
                                    os.unlink(extraction_path)
                                except:
                                    pass
                            
                    if extracted_texts:
                        attached_document_context = "\n\n".join(extracted_texts)
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'completed', 'message': f'첨부 문서 {len(extracted_texts)}개 내용을 추출했습니다.'}, ensure_ascii=False)}\n\n"

            # 🆕 특허 에이전트는 UI에서 명시적으로 선택되었을 때만 실행
            normalized_tool = (request.tool or "").lower()
            if request.tool and request.tool != normalized_tool:
                request.tool = normalized_tool
            skip_rewrite = request.tool == 'patent'

            # 🆕 Query Rewrite 적용 (특허 의도는 원문 유지)
            rewritten_query = request.message
            if not skip_rewrite and (chat_history_messages or image_description):
                rewritten_query = await paper_search_agent.rewrite_query(request.message, chat_history_messages, image_description)
                if rewritten_query != request.message:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'started', 'message': f'문맥을 고려하여 질문을 구체화했습니다: {rewritten_query}'}, ensure_ascii=False)}\n\n"
            elif skip_rewrite:
                logger.info("🛑 [AgentChatStream] 특허 도구 질의는 리라이트를 건너뜁니다")

            intent = await paper_search_agent.classify_intent(rewritten_query)
            keywords = await paper_search_agent._extract_keywords(rewritten_query)

            # 🆕 PPT 강제 모드 (도구 선택 또는 명시적 질의)
            if _should_force_ppt_generation(request.message, request.tool):
                if intent != AgentIntent.PPT_GENERATION:
                    logger.info("🧭 [AgentChatStream] 사용자 질의에서 PPT 생성 의도를 강제로 감지했습니다")
                intent = AgentIntent.PPT_GENERATION
            
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'query_analysis', 'status': 'completed', 'result': {'intent': intent.value, 'keywords': keywords}, 'message': f'의도: {intent.value}, 키워드: {keywords}'}, ensure_ascii=False)}\n\n"
            
            # 🆕 PPT 생성 의도 감지 시 하이브리드 모드 (구조화 답변 + 즉시 PPT 생성)
            if intent == AgentIntent.PPT_GENERATION:
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': ['hybrid_ppt_generation']}, 'message': 'PPT를 바로 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
                
                try:
                    # Step 1: 구조화된 답변 생성 (백그라운드 저장용)
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'ppt_content', 'status': 'started', 'message': 'PPT 콘텐츠를 구조화하고 있습니다...'}, ensure_ascii=False)}\n\n"
                    
                    # RAG 검색 실행
                    strategy = ['keyword_search', 'fulltext_search', 'deduplicate', 'rerank', 'context_builder']
                    retrieval_result = await paper_search_agent.execute_strategy(
                        strategy=strategy,
                        query=rewritten_query,
                        keywords=keywords,
                        constraints=constraints,
                        db_session=db,
                        context=context,
                        attached_document_context=attached_document_context
                    )
                    context_text = retrieval_result.get('context_text', '')
                    
                    # 구조화된 답변 생성
                    structured_answer = await paper_search_agent.generate_answer(
                        query=rewritten_query,
                        context=context_text,
                        intent=intent,
                        history=chat_history_messages
                    )
                    
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'ppt_content', 'status': 'completed', 'message': f'콘텐츠 구조화 완료 ({len(structured_answer)}자)'}, ensure_ascii=False)}\n\n"
                    
                    # Step 2: 즉시 PPT 생성 (Unified Agent)
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'ppt_generation', 'status': 'started', 'message': 'PPT 파일을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
                    
                    from app.agents.presentation.unified_presentation_agent import unified_presentation_agent

                    import uuid

                    run_id = str(uuid.uuid4())
                    
                    ppt_result = await unified_presentation_agent.run(
                        mode="quick",
                        pattern="tool_calling",
                        # Use the (rewritten) user query so PPT title/filename match the request.
                        topic=rewritten_query,
                        context_text=structured_answer,
                        max_slides=8,
                        run_id=run_id,
                        user_id=int(user_emp_no) if str(user_emp_no).isdigit() else None,
                    )

                    # Fallback to deterministic LangGraph-backed flow when tool-calling
                    # doesn't work (unsupported) or doesn't actually create a PPT file.
                    should_fallback_to_react = False
                    if not ppt_result.get("success"):
                        should_fallback_to_react = True
                    if not ppt_result.get("file_name") and not ppt_result.get("filename"):
                        should_fallback_to_react = True
                    if not ppt_result.get("file_path"):
                        should_fallback_to_react = True

                    if should_fallback_to_react:
                        ppt_result = await unified_presentation_agent.run(
                            mode="quick",
                            pattern="react",
                            topic=rewritten_query,
                            context_text=structured_answer,
                            max_slides=8,
                            run_id=run_id,
                            user_id=int(user_emp_no) if str(user_emp_no).isdigit() else None,
                        )
                    
                    success = ppt_result.get("success", False)
                    file_name = ppt_result.get("file_name")
                    file_path = ppt_result.get("file_path")
                    
                    if success and file_name:
                        # 다운로드 URL 생성
                        import urllib.parse
                        file_url = f"/api/v1/agent/presentation/download/{urllib.parse.quote(file_name)}"
                        
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'ppt_generation', 'status': 'completed', 'message': f'PPT 생성 완료 ({file_name})'}, ensure_ascii=False)}\n\n"
                        
                        # 간결한 성공 메시지
                        final_response = f"✅ **PPT 생성 완료!**\n\n📎 [{file_name}]({file_url})"
                        
                        # 메타데이터에 구조화 답변 포함 (모달에서 사용)
                        metadata = {
                            "intent": intent.value,
                            "strategy_used": ["hybrid_ppt_generation"],
                            "detailed_chunks": [],
                            "ppt_file_url": file_url,
                            "ppt_file_name": file_name,
                            "structured_content": structured_answer,  # 🆕 구조화 답변 저장
                            "slide_count": ppt_result.get("slide_count", 0),
                            "iterations": ppt_result.get("iterations", 0),
                            "execution_time": ppt_result.get("execution_time", 0),
                            "run_id": ppt_result.get("run_id") or run_id,
                            "trace_id": ppt_result.get("trace_id") or run_id,
                            "retrieval_metrics": retrieval_result.get("metrics", {})
                        }
                    else:
                        error_msg = ppt_result.get("error", "알 수 없는 오류")
                        final_response = f"❌ PPT 생성 실패: {error_msg}"
                        metadata = {
                            "intent": intent.value,
                            "strategy_used": ["hybrid_ppt_generation"],
                            "error": error_msg
                        }
                    
                    # 답변 전송
                    yield f"event: content\ndata: {json.dumps({'delta': final_response}, ensure_ascii=False)}\n\n"
                    yield f"event: metadata\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                    yield f"event: done\ndata: {json.dumps({'success': True, 'session_id': context.get('session_id')}, ensure_ascii=False)}\n\n"
                    return
                    
                except Exception as ppt_error:
                    error_text = (str(ppt_error) or "").strip()
                    if not error_text:
                        error_text = f"{type(ppt_error).__name__} (no message)"

                    # NOTE: This project uses loguru; `exc_info=True` is ignored.
                    # Use loguru's exception capture to include traceback.
                    try:
                        logger.opt(exception=ppt_error).error("❌ [HybridPPT] 생성 실패: {}", error_text)
                    except Exception:
                        logger.exception("❌ [HybridPPT] 생성 실패")

                    yield (
                        "event: reasoning_step\n"
                        f"data: {json.dumps({'stage': 'ppt_generation', 'status': 'error', 'message': f'PPT 생성 실패: {error_text}'}, ensure_ascii=False)}\n\n"
                    )
                    yield f"event: error\ndata: {json.dumps({'error': error_text}, ensure_ascii=False)}\n\n"
                    return

            # 🔍 Step 2: 전략 선택
            strategy = paper_search_agent.select_strategy(intent, constraints)
            
            # 🆕 도구 강제 선택 적용
            if request.tool:
                if request.tool == 'web-search':
                    strategy = ['internet_search', 'context_builder']
                    intent = AgentIntent.WEB_SEARCH
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': strategy}, 'message': '사용자 요청에 따라 웹 검색을 수행합니다.'}, ensure_ascii=False)}\n\n"
                elif request.tool == 'ppt':
                    intent = AgentIntent.PPT_GENERATION
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': ['presentation_agent']}, 'message': '사용자 요청에 따라 PPT 생성을 수행합니다.'}, ensure_ascii=False)}\n\n"
                elif request.tool == 'patent':
                    # 🆕 특허 분석 에이전트 실행
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': ['patent_analysis']}, 'message': '특허 분석 전문가에게 작업을 위임합니다.'}, ensure_ascii=False)}\n\n"
                    
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'patent_analysis', 'status': 'started', 'message': 'KIPRIS/Google Patents에서 특허를 검색하고 있습니다...'}, ensure_ascii=False)}\n\n"
                    
                    try:
                        from app.agents.patent import patent_analysis_agent_tool
                        
                        # 특허 분석 실행
                        patent_result = await patent_analysis_agent_tool._arun(
                            query=request.message,
                            analysis_type="search",  # 기본: 검색
                            jurisdiction="KR",
                            max_results=20,
                            include_visualization=True
                        )
                        
                        # 특허 분석 결과를 답변으로 포맷
                        total_patents = patent_result.get("total_patents", 0)
                        summary = patent_result.get("summary", "")
                        
                        completed_msg = f"특허 검색 완료: {total_patents}건"
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'patent_analysis', 'status': 'completed', 'message': completed_msg}, ensure_ascii=False)}\n\n"
                        patents = patent_result.get("patents", [])
                        visualizations = patent_result.get("visualizations", [])
                        insights = patent_result.get("insights", [])
                        
                        # 답변 전송
                        yield f"event: content\ndata: {json.dumps({'delta': summary}, ensure_ascii=False)}\n\n"
                        
                        # 메타데이터 전송 (특허 목록, 시각화 포함)
                        metadata = {
                            "intent": "patent_analysis",
                            "strategy_used": ["patent_analysis"],
                            "detailed_chunks": [],
                            "patent_results": {
                                "patents": patents[:10],  # 상위 10건
                                "total_patents": patent_result.get("total_patents", 0),
                                "visualizations": visualizations,
                                "insights": insights,
                                "source": patent_result.get("analysis_result", {}).get("source", "kipris")
                            }
                        }
                        yield f"event: metadata\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"
                        
                        # 히스토리 저장
                        try:
                            from app.models.chat.chat_models import TbChatHistory
                            
                            history_entry = TbChatHistory(
                                session_id=context.get("session_id"),
                                user_emp_no=user_emp_no,
                                user_message=request.message,
                                assistant_response=summary,
                                model_parameters={"tool": "patent", "total_patents": total_patents},
                                created_date=datetime.utcnow()
                            )
                            db.add(history_entry)
                            await db.commit()
                        except Exception as save_error:
                            logger.warning(f"⚠️ 히스토리 저장 실패: {save_error}")
                        
                        yield f"event: done\ndata: {json.dumps({'success': True, 'session_id': context.get('session_id')}, ensure_ascii=False)}\n\n"
                        return
                        
                    except Exception as patent_error:
                        logger.error(f"❌ 특허 분석 실패: {patent_error}")
                        error_msg = f"특허 분석 실패: {str(patent_error)}"
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'patent_analysis', 'status': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': str(patent_error)}, ensure_ascii=False)}\n\n"
                        return

                elif request.tool == 'deep-research':
                    yield (
                        "event: reasoning_step\n"
                        f"data: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': ['deep_research']}, 'message': 'Deep Research를 수행합니다 (웹 검색 + 내부 지식).'}, ensure_ascii=False)}\n\n"
                    )

                    yield (
                        "event: reasoning_step\n"
                        f"data: {json.dumps({'stage': 'deep_research', 'status': 'started', 'message': '리서치 계획을 수립하고 자료를 수집하고 있습니다...'}, ensure_ascii=False)}\n\n"
                    )

                    try:
                        from app.agents.deep_research_agent import deep_research_agent
                        from app.agents.base.agent_protocol import AgentExecutionContext

                        deep_ctx = AgentExecutionContext(
                            session_id=context.get('session_id'),
                            user_id=int(user_emp_no) if str(user_emp_no).isdigit() else None,
                            max_tokens=request.max_tokens,
                            max_iterations=10,
                            timeout_seconds=300,
                        )

                        deep_input = {
                            'query': rewritten_query,
                            'db_session': db,
                            'constraints': constraints,
                            'attached_document_context': attached_document_context,
                            'context': context,
                            'chat_history': chat_history_messages,
                            'max_sub_questions': 5,
                            'max_loops': 2,
                        }

                        deep_result = await deep_research_agent.execute(deep_input, deep_ctx)

                        report_md = (deep_result.output or {}).get('report_markdown', '') if deep_result.success else ''
                        sources = (deep_result.output or {}).get('sources', []) if deep_result.success else []

                        if not report_md:
                            raise RuntimeError('Deep Research 리포트 생성 실패')

                        # Save report as an attachment
                        safe_ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                        report_filename = f"deep-research-report-{safe_ts}.md"
                        stored = await chat_attachment_service.save_bytes(
                            report_md.encode('utf-8'),
                            owner_emp_no=user_emp_no,
                            file_name=report_filename,
                            mime_type='text/markdown',
                        )
                        download_url = f"/api/v1/agent/chat/assets/{stored.asset_id}"

                        # Attach to metadata (also persisted for session restore)
                        attached_files.append({
                            'asset_id': stored.asset_id,
                            'id': stored.asset_id,
                            'category': stored.category,
                            'file_name': stored.file_name,
                            'mime_type': stored.mime_type,
                            'file_size': stored.size,
                            'download_url': download_url,
                        })

                        yield (
                            "event: reasoning_step\n"
                            f"data: {json.dumps({'stage': 'deep_research', 'status': 'completed', 'message': f'리포트 생성 완료 ({stored.file_name})'}, ensure_ascii=False)}\n\n"
                        )

                        # Stream: link + report
                        final_prefix = f"✅ **Deep Research 리포트 생성 완료**\n\n📎 [{stored.file_name}]({download_url})\n\n---\n\n"
                        for chunk in (final_prefix + report_md):
                            yield f"event: content\ndata: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"

                        # Build detailed chunks from sources for UI references
                        detailed_chunks = []
                        has_internet = False
                        for idx_s, s in enumerate(sources[:20]):
                            url = s.get('url')
                            if url:
                                has_internet = True
                            file_name = s.get('title') or 'Source'
                            file_id = s.get('file_id')
                            detailed_chunks.append({
                                'index': idx_s + 1,
                                'file_id': int(file_id) if file_id and str(file_id).isdigit() else 0,
                                'file_name': file_name,
                                'chunk_index': 0,
                                'page_number': s.get('page_number'),
                                'content_preview': file_name,
                                'similarity_score': 0.0,
                                'search_type': 'internet' if url else 'hybrid',
                                'section_title': file_name,
                                'url': url,
                                'full_content': None,
                            })

                        metadata = {
                            'intent': 'deep_research',
                            'strategy_used': ['deep_research'],
                            'detailed_chunks': detailed_chunks,
                            'search_stats': {},
                            'total_chunks_searched': 0,
                            'chunks_used': len(detailed_chunks),
                            'attached_files': attached_files,
                            'answer_source': 'mixed_search' if has_internet else 'database_search',
                            'has_attachments': bool(attached_files),
                            'has_internet_results': has_internet,
                        }
                        yield f"event: metadata\ndata: {json.dumps(metadata, ensure_ascii=False)}\n\n"

                        # Persist to session history
                        try:
                            from app.models.chat.chat_models import TbChatSessions, TbChatHistory
                            from sqlalchemy import select, update
                            from datetime import datetime as dt

                            session_id = context.get('session_id')

                            session_stmt = select(TbChatSessions).where(TbChatSessions.session_id == session_id)
                            session_result = await db.execute(session_stmt)
                            existing_session = session_result.scalar_one_or_none()
                            if not existing_session:
                                new_session = TbChatSessions(
                                    session_id=session_id,
                                    user_emp_no=user_emp_no,
                                    session_name=f"Agent Chat - {request.message[:30]}...",
                                    session_description="AI Agent 채팅 세션",
                                    default_container_id=request.container_ids[0] if request.container_ids else None,
                                    allowed_containers=request.container_ids,
                                    is_active=True,
                                    last_activity=dt.utcnow(),
                                    message_count=1,
                                )
                                db.add(new_session)
                            else:
                                update_stmt = (
                                    update(TbChatSessions)
                                    .where(TbChatSessions.session_id == session_id)
                                    .values(
                                        last_activity=dt.utcnow(),
                                        message_count=TbChatSessions.message_count + 1,
                                    )
                                )
                                await db.execute(update_stmt)

                            history_entry = TbChatHistory(
                                session_id=session_id,
                                user_emp_no=user_emp_no,
                                knowledge_container_id=request.container_ids[0] if request.container_ids else None,
                                accessible_containers=request.container_ids,
                                user_message=request.message,
                                assistant_response=(final_prefix + report_md)[:60000],
                                search_query=rewritten_query,
                                search_results={
                                    'chunks': detailed_chunks[:10],
                                    'total_searched': 0,
                                    'total_used': len(detailed_chunks),
                                },
                                referenced_documents=None,
                                model_used='agent/deep_research',
                                model_parameters={
                                    'tool': 'deep-research',
                                    'attached_files': attached_files,
                                },
                                conversation_context={
                                    'deep_research': True,
                                    'has_internet_results': has_internet,
                                },
                            )
                            db.add(history_entry)
                            await db.commit()
                        except Exception as save_error:
                            logger.warning(f"⚠️ Deep Research 히스토리 저장 실패: {save_error}")
                            try:
                                await db.rollback()
                            except Exception:
                                pass

                        yield f"event: done\ndata: {json.dumps({'success': True, 'session_id': context.get('session_id')}, ensure_ascii=False)}\n\n"
                        return

                    except Exception as deep_error:
                        logger.error(f"❌ Deep Research 실패: {deep_error}")
                        error_msg = f"Deep Research 실패: {str(deep_error)}"
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'deep_research', 'status': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"
                        yield f"event: error\ndata: {json.dumps({'error': str(deep_error)}, ensure_ascii=False)}\n\n"
                        return
            
            # 🆕 멀티모달 검색: 이미지가 있으면 multimodal_search 추가
            has_images = bool(images_to_analyze)
            has_text_attachments = bool(attached_document_context)
            
            if has_images:
                # 이미지가 있으면 멀티모달 검색을 전략에 추가
                if "multimodal_search" not in strategy:
                    # 검색 전략 앞부분에 추가 (벡터 검색과 병렬로 실행되도록)
                    search_tools = ["vector_search", "keyword_search", "fulltext_search"]
                    first_search_idx = next((i for i, t in enumerate(strategy) if t in search_tools), 0)
                    strategy.insert(first_search_idx, "multimodal_search")
                logger.info(f"📷 [AgentChatStream] 이미지 첨부 감지 → 멀티모달 검색 추가")
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': strategy, 'multimodal': True}, 'message': '이미지와 텍스트를 함께 검색합니다.'}, ensure_ascii=False)}\n\n"
            elif has_text_attachments:
                # 텍스트 문서만 있으면 기존 전략 유지
                logger.info(f"📎 [AgentChatStream] 첨부 문서 컨텍스트: {len(attached_document_context)}자")
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': strategy}, 'message': '첨부 문서와 데이터베이스를 함께 검색합니다.'}, ensure_ascii=False)}\n\n"
            else:
                logger.info(f"🔍 [AgentChatStream] 검색 전략 선택: {strategy}")
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'strategy_selection', 'status': 'completed', 'result': {'strategy': strategy}, 'message': f'검색 전략: {strategy}'}, ensure_ascii=False)}\n\n"
            
            # 📊 Step 3: 도구 실행 (하이브리드 검색)
            all_chunks = []
            search_stats = {}
            
            for idx, tool_name in enumerate(strategy):
                if tool_name in ["vector_search", "keyword_search", "fulltext_search", "multimodal_search", "internet_search"]:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'search', 'status': 'started', 'tool': tool_name, 'message': f'{tool_name} 실행 중...'}, ensure_ascii=False)}\n\n"
                    
                    try:
                        # 🆕 multimodal_search는 이미지 데이터 전달
                        if tool_name == "multimodal_search":
                            if not images_to_analyze:
                                logger.warning("⚠️ multimodal_search 호출됨, 하지만 이미지 없음")
                                continue
                            
                            # 첫 번째 이미지만 사용 (추후 다중 이미지 지원 가능)
                            tool_result = await paper_search_agent._execute_tool(
                                tool_name=tool_name,
                                query=rewritten_query,
                                db_session=db,
                                keywords=keywords,
                                constraints=constraints,
                                chunks=all_chunks,
                                context={
                                    **context,
                                    "image_data": images_to_analyze[0],  # Base64 이미지 (data:image/...;base64,...)
                                    "top_k": 10
                                }
                            )
                        else:
                            tool_result = await paper_search_agent._execute_tool(
                                tool_name=tool_name,
                                query=rewritten_query,
                                db_session=db,
                                keywords=keywords,
                                constraints=constraints,
                                chunks=all_chunks,
                                context=context
                            )
                        
                        if not getattr(tool_result, 'success', False):
                            logger.warning(f"⚠️ 도구 실행 실패: {tool_name}, errors={getattr(tool_result, 'errors', [])}")
                            try:
                                await db.rollback()
                            except Exception as rollback_error:
                                logger.error(f"롤백 실패 ({tool_name}): {rollback_error}")
                            continue

                        if hasattr(tool_result, 'data'):
                            new_chunks = tool_result.data
                            all_chunks.extend(new_chunks)
                            search_stats[tool_name] = {
                                'count': len(new_chunks),
                                'avg_score': sum(c.score for c in new_chunks) / len(new_chunks) if new_chunks else 0
                            }
                            
                            yield f"event: search_progress\ndata: {json.dumps({'tool': tool_name, 'chunks_found': len(new_chunks), 'total_chunks': len(all_chunks), 'avg_similarity': round(search_stats[tool_name]['avg_score'], 3)}, ensure_ascii=False)}\n\n"
                    
                    except Exception as e:
                        logger.error(f"검색 실패 ({tool_name}): {e}")
                        try:
                            await db.rollback()
                        except Exception as rollback_error:
                            logger.error(f"롤백 실패 ({tool_name}): {rollback_error}")
                        yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'search', 'status': 'error', 'tool': tool_name, 'message': f'검색 실패: {str(e)}'}, ensure_ascii=False)}\n\n"
                
                elif tool_name in ["deduplicate", "rerank"]:
                    yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'postprocess', 'status': 'started', 'tool': tool_name, 'message': f'{tool_name} 처리 중...'}, ensure_ascii=False)}\n\n"
                    
                    try:
                        tool_result = await paper_search_agent._execute_tool(
                            tool_name=tool_name,
                            query=rewritten_query,  # 🆕 재작성된 쿼리 사용
                            db_session=db,
                            keywords=keywords,
                            constraints=constraints,
                            chunks=all_chunks,
                            context=context
                        )
                        
                        if not getattr(tool_result, 'success', False):
                            logger.warning(f"⚠️ 후처리 도구 실패: {tool_name}, errors={getattr(tool_result, 'errors', [])}")
                            try:
                                await db.rollback()
                            except Exception as rollback_error:
                                logger.error(f"롤백 실패 ({tool_name}): {rollback_error}")
                            continue
                        if hasattr(tool_result, 'data'):
                            before_count = len(all_chunks)
                            all_chunks = tool_result.data
                            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'postprocess', 'status': 'completed', 'tool': tool_name, 'before': before_count, 'after': len(all_chunks), 'message': f'{tool_name}: {before_count}개 → {len(all_chunks)}개'}, ensure_ascii=False)}\n\n"
                    
                    except Exception as e:
                        logger.error(f"후처리 실패 ({tool_name}): {e}")
                        try:
                            await db.rollback()
                        except Exception as rollback_error:
                            logger.error(f"롤백 실패 ({tool_name}): {rollback_error}")
            
            # 🏗️ Step 4: 컨텍스트 구성
            yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'context_building', 'status': 'started', 'message': '컨텍스트를 구성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            
            context_result = await paper_search_agent._execute_tool(
                tool_name="context_builder",
                query=rewritten_query,  # 🆕 재작성된 쿼리 사용
                db_session=db,
                keywords=keywords,
                constraints=constraints,
                chunks=all_chunks,
                context=None
            )
            
            context_text = context_result.data if isinstance(context_result.data, str) else ""
            used_chunks = getattr(context_result, 'used_chunks', all_chunks[:5])
            
            # 🆕 첨부 파일 컨텍스트 추가 (문서 + 이미지)
            if attached_document_context or image_description:
                parts = []
                
                # 이미지 설명 추가
                if image_description:
                    parts.append(f"[첨부 이미지 분석 결과]\n{image_description}")
                
                # 문서 내용 추가
                if attached_document_context:
                    parts.append(f"[첨부 문서 내용]\n{attached_document_context}")
                
                # 검색 결과 추가 (있는 경우)
                if context_text and context_text.strip():
                    parts.append(f"[참고: 데이터베이스 검색 결과]\n{context_text}")
                
                context_text = "\n\n".join(parts)
            
            token_count = len(context_text.split())  # 간단한 토큰 추정
            
            # 컨텍스트 구성 완료 메시지
            if attached_document_context or image_description:
                source_types = []
                if image_description:
                    source_types.append("이미지")
                if attached_document_context:
                    source_types.append("문서")
                source_msg = " + ".join(source_types)
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'context_building', 'status': 'completed', 'tokens': token_count, 'max_tokens': constraints.max_tokens, 'chunks_used': 0, 'message': f'첨부 {source_msg} 기반 컨텍스트 구성 완료: {token_count} 토큰'}, ensure_ascii=False)}\n\n"
            else:
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'context_building', 'status': 'completed', 'tokens': token_count, 'max_tokens': constraints.max_tokens, 'chunks_used': len(used_chunks), 'message': f'컨텍스트 구성 완료: {token_count} 토큰, {len(used_chunks)}개 청크 사용'}, ensure_ascii=False)}\n\n"
            
            # ✍️ Step 5: 답변 생성
            if image_description and not attached_document_context:
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'answer_generation', 'status': 'started', 'message': '이미지 분석 결과를 바탕으로 답변을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            elif attached_document_context:
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'answer_generation', 'status': 'started', 'message': '첨부 파일을 분석하여 답변을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            else:
                yield f"event: reasoning_step\ndata: {json.dumps({'stage': 'answer_generation', 'status': 'started', 'message': '답변을 생성하고 있습니다...'}, ensure_ascii=False)}\n\n"
            
            # AI 답변 생성 (스트리밍) - DEFAULT_LLM_PROVIDER 설정 따름
            answer = await paper_search_agent.generate_answer(
                query=request.message, 
                context=context_text, 
                intent=intent,
                history=chat_history_messages
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
                
                # 🆕 인터넷 검색 결과인지 확인
                is_internet_search = (
                    chunk.match_type == "internet" or 
                    chunk.container_id in ["internet", "tavily", "bing", "duckduckgo"] or
                    (chunk.metadata and chunk.metadata.get("source") in ["internet", "tavily", "bing", "duckduckgo"])
                )
                
                # 🆕 인터넷 검색 결과용 필드
                url = chunk.metadata.get("url") if chunk.metadata else None
                search_type = "internet" if is_internet_search else "hybrid"
                
                # 🆕 인터넷 검색 결과인 경우 파일명을 타이틀로 설정
                if is_internet_search and chunk.metadata:
                    file_name = chunk.metadata.get("title") or chunk.metadata.get("file_name") or "웹 검색 결과"
                
                detailed_chunks.append({
                    "index": idx + 1,
                    "file_id": int(file_id) if file_id and str(file_id).isdigit() else 0,
                    "file_name": file_name,
                    "chunk_index": chunk.metadata.get("chunk_index", 0) if chunk.metadata else 0,
                    "page_number": chunk.metadata.get("page_number") if chunk.metadata else None,
                    "content_preview": chunk.content[:200] if chunk.content else "",
                    "similarity_score": chunk.score,
                    "search_type": search_type,
                    "section_title": file_name,
                    "url": url,  # 🆕 인터넷 검색 결과 URL
                    "full_content": chunk.content if is_internet_search else None  # 🆕 전체 콘텐츠 (인터넷 검색)
                })
            
            # 🆕 인터넷 검색만 사용했는지 확인
            has_internet_only = (
                len(detailed_chunks) > 0 and 
                all(c.get("search_type") == "internet" for c in detailed_chunks)
            )
            has_mixed_search = (
                len(detailed_chunks) > 0 and 
                any(c.get("search_type") == "internet" for c in detailed_chunks) and
                any(c.get("search_type") != "internet" for c in detailed_chunks)
            )
            
            # 🆕 answer_source 결정 (인터넷 검색 구분)
            if attached_files and not used_chunks:
                answer_source = "attached_documents"
            elif has_internet_only:
                answer_source = "internet_search"
            elif has_mixed_search:
                answer_source = "mixed_search"
            elif used_chunks:
                answer_source = "database_search"
            else:
                answer_source = "general"
            
            metadata = {
                "intent": intent.value,
                "strategy_used": strategy,
                "detailed_chunks": detailed_chunks,
                "search_stats": search_stats,
                "total_chunks_searched": len(all_chunks),
                "chunks_used": len(used_chunks),
                "attached_files": attached_files,  # 🆕 첨부 파일 메타데이터
                "answer_source": answer_source,  # 🆕 답변 출처 (internet_search, mixed_search, database_search, attached_documents, general)
                "has_attachments": bool(attached_files),  # 🆕 첨부 파일 존재 여부
                "has_internet_results": has_internet_only or has_mixed_search  # 🆕 인터넷 검색 결과 포함 여부
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
                        "similarity_threshold": effective_threshold,
                        "attached_files": attached_files  # 🆕 첨부 파일 정보 저장
                    },
                    conversation_context={
                        "search_stats": search_stats,
                        "reasoning_steps": len(strategy),
                        "has_attachments": bool(attached_document_context),  # 🆕 첨부 파일 존재 여부
                        "attachment_context_length": len(attached_document_context) if attached_document_context else 0
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


# =============================================================================
# 📎 첨부파일 관리 엔드포인트 (chat.py에서 통합)
# =============================================================================

@router.post("/agent/chat/assets")
async def upload_agent_chat_assets(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """채팅 첨부파일 업로드 (이미지, 문서, 오디오)
    
    Args:
        files: 업로드할 파일 리스트
        current_user: 현재 사용자 (인증)
    
    Returns:
        {"success": true, "assets": [...]}
    """
    if not files:
        raise HTTPException(status_code=400, detail="업로드할 파일이 없습니다.")

    assets = []
    for upload in files:
        try:
            stored = await chat_attachment_service.save(upload, str(current_user.emp_no))
            assets.append({
                "asset_id": stored.asset_id,
                "file_name": stored.file_name,
                "mime_type": stored.mime_type,
                "size": stored.size,
                "category": stored.category,
                "preview_url": stored.preview_url,
                "download_url": stored.download_url
            })
        except Exception as exc:
            logger.error(f"❌ 첨부 파일 업로드 실패: {exc}")
            raise HTTPException(status_code=500, detail="첨부 파일 업로드 중 오류가 발생했습니다.")

    return {"success": True, "assets": assets}


@router.get("/agent/chat/assets/{asset_id}")
async def download_agent_chat_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user)
):
    """채팅 첨부파일 다운로드
    
    Args:
        asset_id: 파일 식별자
        current_user: 현재 사용자 (인증)
    
    Returns:
        파일 스트림 또는 FileResponse
    """
    stored = chat_attachment_service.get(asset_id)
    if not stored:
        raise HTTPException(status_code=404, detail="첨부 파일을 찾을 수 없습니다.")

    stored_owner = str(stored.owner_emp_no) if stored.owner_emp_no else None
    current_emp_no = str(current_user.emp_no)
    logger.info(f"🔐 [AgentChatAsset] 접근 시도: asset={asset_id}, stored_owner={stored_owner}, current={current_emp_no}")

    if stored_owner != current_emp_no:
        logger.warning(f"❌ [AgentChatAsset] 권한 없음: {current_emp_no} != {stored_owner}")
        raise HTTPException(status_code=403, detail="첨부 파일에 대한 접근 권한이 없습니다.")

    # S3 스토리지 처리
    if stored.storage_backend == "s3":
        if not chat_attachment_service.s3_client:
            logger.error("S3 client is not initialized but storage_backend is s3")
            raise HTTPException(status_code=500, detail="스토리지 설정 오류가 발생했습니다.")
            
        try:
            # S3에서 파일 스트림 가져오기
            s3_response = chat_attachment_service.s3_client.get_object(
                Bucket=chat_attachment_service.s3_bucket,
                Key=str(stored.path)
            )
            
            # 파일명 인코딩 처리 (RFC 5987)
            encoded_filename = quote(stored.file_name)
            
            return StreamingResponse(
                s3_response['Body'],
                media_type=stored.mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        except ClientError as e:
            logger.error(f"S3 Download Error: {e}")
            raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"S3 Streaming Error: {e}")
            raise HTTPException(status_code=500, detail="파일 다운로드 중 오류가 발생했습니다.")

    # 로컬 스토리지 처리
    return FileResponse(
        path=stored.path,
        media_type=stored.mime_type,
        filename=stored.file_name
    )


# =============================================================================
# 🎤 음성 변환 엔드포인트 (chat.py에서 통합)
# =============================================================================

@router.post("/agent/chat/transcribe")
async def transcribe_agent_chat_audio(
    file: UploadFile = File(...),
    language: str = Form("ko-KR"),
    current_user: User = Depends(get_current_user)
):
    """음성 파일을 텍스트로 변환 (AWS Transcribe)
    
    Args:
        file: 오디오 파일 (webm, mp3, wav, m4a 등)
        language: 언어 코드 (ko-KR, en-US, ja-JP, zh-CN 등)
        current_user: 현재 사용자 (인증)
    
    Returns:
        {"success": true, "transcript": "변환된 텍스트"}
    """
    if not audio_transcription_service.enabled:
        raise HTTPException(status_code=503, detail="오디오 전사 기능이 비활성화되어 있습니다.")

    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix)
    os.close(temp_fd)
    temp_path = Path(temp_path_str)

    try:
        # 파일 저장
        async with aiofiles.open(temp_path, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await out_file.write(chunk)

        logger.info(
            "🎤 [AGENT-TRANSCRIBE] 변환 요청 - user: %s, file: %s, size: %d bytes, language: %s",
            current_user.username,
            file.filename,
            temp_path.stat().st_size,
            language
        )

        # AWS Transcribe 변환 (동기 → 비동기 래핑)
        transcript = await asyncio.to_thread(
            audio_transcription_service.transcribe, 
            temp_path,
            language
        )
        
        logger.info(
            "✅ [AGENT-TRANSCRIBE] 변환 완료 - user: %s, text_length: %d",
            current_user.username,
            len(transcript)
        )
        
        return {"success": True, "transcript": transcript}
        
    except Exception as exc:
        logger.error(f"❌ [AGENT-TRANSCRIBE] 변환 실패: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="음성 텍스트 변환 중 오류가 발생했습니다.")
    finally:
        try:
            await file.close()
        except Exception:
            pass
        temp_path.unlink(missing_ok=True)

