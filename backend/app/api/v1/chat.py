from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi import UploadFile, File, Form, Query, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import re
from pydantic import BaseModel
import json
import asyncio
import aiofiles
import base64
import os
import tempfile
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, desc, func, delete
from app.core.database import get_db
from app.services.core.ai_service import ai_service
from app.services.core.vision_service import vision_service
from app.services.search.search_service import search_service
from app.services.chat.rag_search_service import rag_search_service, RAGSearchParams
from app.services.chat.query_classification_service import query_classification_service
from app.services.chat.ai_agent_service import ai_agent_service
from app.services.chat.chat_attachment_service import chat_attachment_service
from app.services.core.audio_transcription_service import audio_transcription_service
from app.core.config import settings

from app.services.multi_agent.integrated_service import integrated_multi_agent_service
from app.schemas.chat import SelectedDocument
from app.core.dependencies import get_current_user
from app.models.chat.redis_schemas import MessageType
from app.models import User, TbChatSessions, TbChatHistory
from app.models.chat import (
    RedisChatManager,
    get_redis_client,
    MessageType,
    ChatSessionStatus,
    RedisKeyPatterns,
    RedisChatTTL,
)

import uuid
from datetime import datetime, timedelta
from loguru import logger


def build_conversation_state(
    response_text: str,
    context_info: Optional[Dict[str, Any]],
    references: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    summary_source = (response_text or "").strip()
    summary = summary_source[:400].strip() if summary_source else ""

    if not summary and summary_source:
        summary = summary_source

    keywords: List[str] = []
    topic_continuity = 0.0
    last_intent: Optional[str] = None
    hints: List[str] = []
    relevant_documents: List[Dict[str, Any]] = []

    if isinstance(context_info, dict):
        keywords = context_info.get("accumulated_keywords") or context_info.get("keywords") or []
        topic_continuity = context_info.get("topic_continuity") or context_info.get("topic_continuity_score") or 0.0
        last_intent = context_info.get("last_intent") or context_info.get("intent")
        hints = context_info.get("follow_up_questions") or context_info.get("next_questions") or []

        ctx_docs = context_info.get("relevant_documents") or []
        for doc in ctx_docs:
            if isinstance(doc, dict):
                doc_id = doc.get("id") or doc.get("document_id") or doc.get("file_id")
                relevant_documents.append({
                    "id": str(doc_id) if doc_id is not None else uuid.uuid4().hex,
                    "title": doc.get("title") or doc.get("file_name") or "관련 문서",
                    "containerName": doc.get("container_name"),
                    "similarity": doc.get("similarity") or doc.get("score")
                })
            else:
                relevant_documents.append({
                    "id": str(doc),
                    "title": str(doc),
                })

    if not relevant_documents and references:
        for ref in references[:5]:
            doc_id = ref.get("document_id") or ref.get("file_bss_info_sno") or ref.get("file_id") or uuid.uuid4().hex
            relevant_documents.append({
                "id": str(doc_id),
                "title": ref.get("title") or ref.get("file_name") or "관련 문서",
                "containerName": ref.get("container_name"),
                "similarity": ref.get("similarity_score")
            })

    state = {
        "updatedAt": datetime.utcnow().isoformat(),
        "summary": summary,
        "keywords": keywords[:10] if keywords else [],
        "topicContinuity": float(topic_continuity) if topic_continuity is not None else 0.0,
        "lastIntent": last_intent,
        "relevantDocuments": relevant_documents,
        "hints": hints or []
    }

    return state


def detect_ppt_format(text: str) -> bool:
    """
    AI 응답이 PPT 형식인지 감지하는 함수
    노트북의 is_ppt_format() 함수와 동일한 로직
    
    Args:
        text: 검사할 AI 응답 텍스트
    
    Returns:
        bool: PPT 형식이면 True, 아니면 False
    """
    if not isinstance(text, str) or not text.strip():
        return False
    
    # PPT 모드에서 사용되는 특징적 키워드들
    ppt_indicators = ['키 메시지', '상세 설명', '🔑', '📝']
    
    # 조건 1: H2 제목이 문서 앞쪽(첫 500자 내)에 존재
    first_part = text[:500]
    has_h2_early = '## ' in first_part
    
    # 조건 2: H3 슬라이드 1개 이상
    h3_count = text.count('### ')
    many_h3 = h3_count >= 1
    
    # 조건 3: PPT 특징 키워드 포함
    has_keyblocks = any(keyword in text for keyword in ppt_indicators)
    
    # 모든 조건을 만족해야 PPT 형식으로 판단
    return has_h2_early and many_h3 and has_keyblocks


def detect_ppt_intent_in_query(query: str) -> bool:
    """
    사용자 질문에서 PPT 생성 의도를 감지하는 함수
    
    Args:
        query: 사용자 질문 텍스트
    
    Returns:
        bool: PPT 생성 의도가 있으면 True, 아니면 False
    """
    if not isinstance(query, str):
        return False
    
    query_lower = query.lower()
    
    # PPT 생성 키워드들
    ppt_keywords = ['ppt', 'pptx', '프레젠테이션', '프리젠테이션', '발표 자료', '발표자료', '슬라이드']
    creation_keywords = ['만들어', '작성', '생성', '제작', '만들']
    
    # PPT 키워드가 있는지 확인
    has_ppt_keyword = any(keyword in query_lower for keyword in ppt_keywords)
    
    # 생성 의도가 있는지 확인
    has_creation_intent = any(keyword in query_lower for keyword in creation_keywords)
    
    # 둘 다 있어야 PPT 생성 의도로 판단
    return has_ppt_keyword and has_creation_intent


def fix_markdown_formatting(text: str) -> str:
    """
    LLM 응답의 마크다운 서식을 정교하게 교정합니다.
    "## 인슐린 펌프인슐린 펌프는..." 같은 복잡한 중복 패턴을 해결합니다.
    """
    if not text:
        return text

    import re

    # 1) 개행 정규화
    s = text.replace('\r\n', '\n').replace('\r', '\n')
    
    logger.info(f"🔧 [후처리] 원본: {repr(s[:100])}")

    # 2) 가장 복잡한 케이스: "## 인슐린 펌프인슐린 펌프는..."
    def fix_complex_duplication(match):
        header_mark = match.group(1)  # ##
        content = match.group(2)      # "인슐린 펌프인슐린 펌프는..."
        
        # 공백으로 단어 분리
        words = content.split()
        
        # 연속된 같은 단어/구문 패턴 찾기
        if len(words) >= 4:  # 최소 4단어 이상
            # "A B A B는" 패턴 찾기
            for i in range(len(words) - 3):
                word1 = words[i]
                word2 = words[i + 1] if i + 1 < len(words) else ""
                word3 = words[i + 2] if i + 2 < len(words) else ""
                word4 = words[i + 3] if i + 3 < len(words) else ""
                
                # "인슐린 펌프 인슐린 펌프는" 패턴
                if word1 == word3 and word2 == word4.rstrip('는은이가을를'):
                    header_text = f"{word1} {word2}"
                    remaining_words = words[i + 2:]  # "인슐린 펌프는..."부터
                    content_text = ' '.join(remaining_words)
                    
                    logger.info(f"🔧 [후처리] 복잡한 중복 발견: '{word1} {word2}' 반복")
                    return f"{header_mark} {header_text}\n\n{content_text}"
        
        # 간단한 중복 패턴: "## 인슐린인슐린은"
        for word in words:
            if len(word) > 2:
                clean_word = word.rstrip('는은이가을를에과와의로으로에서')
                if content.count(clean_word) >= 2:
                    # 첫 번째 등장을 헤더로
                    parts = content.split(clean_word, 1)
                    if len(parts) > 1 and parts[1]:
                        header_text = clean_word
                        content_text = clean_word + parts[1]
                        
                        logger.info(f"🔧 [후처리] 단순 중복 발견: '{clean_word}'")
                        return f"{header_mark} {header_text}\n\n{content_text}"
        
        # 분리하지 못한 경우 원본 반환
        return match.group(0)
    
    # 헤더 패턴 처리
    s = re.sub(r'^(#{1,6})\s*(.+)$', fix_complex_duplication, s, flags=re.MULTILINE)

    # 3) 헤더 뒤 빈 줄 강제
    s = re.sub(r'(?m)^(#{1,6}\s+[^\n]+)\n(?=\S)', r'\1\n\n', s)

    # 4) 목록 앞 빈 줄 강제
    s = re.sub(r'(?m)([^\n]\n)([-*]\s)', r'\1\n\2', s)
    s = re.sub(r'(?m)([^\n]\n)(\d+\.\s)', r'\1\n\2', s)

    # 5) 빈 헤더 제거
    s = re.sub(r'^#{1,6}\s*$', '', s, flags=re.MULTILINE)
    
    # 6) 과도한 연속 개행 정리
    s = re.sub(r'\n{3,}', '\n\n', s)
    
    logger.info(f"🔧 [후처리] 결과: {repr(s[:100])}")

    return s.strip()
    # "### 정보-" -> "### 정보\n\n-"
    s = re.sub(r'^(#{1,6}\s+[^\n]*?)([-*]\s)', r'\1\n\n\2', s, flags=re.MULTILINE)

    # 5) 헤더 뒤 빈 줄 강제 (lookahead 사용)
    s = re.sub(r'(?m)^(#{1,6}\s+[^\n]+)\n(?=\S)', r'\1\n\n', s)

    # 6) 목록 앞 빈 줄 강제
    s = re.sub(r'(?m)([^\n]\n)([-*]\s)', r'\1\n\2', s)   # 불릿 목록
    s = re.sub(r'(?m)([^\n]\n)(\d+\.\s)', r'\1\n\2', s)  # 번호 목록

    # 7) 과도한 연속 개행 정리
    s = re.sub(r'\n{3,}', '\n\n', s)

    return s.strip()


def sanitize_ppt_markdown(text: str) -> str:
    """
    PPT 의도 출력에서 흔히 섞이는 코드 펜스(``` ... ```), 불필요한 장식, 중복 헤딩을 정리합니다.
    - 삼중 백틱 라인은 제거하되 내부 내용은 유지
    - "## 제목 슬라이드" 같은 제네릭 헤딩은 제거 (실제 제목 혼동 방지)
    - 연속된 동일 헤딩 제거 (첫 번째만 유지)
    - 헤딩 앞뒤 공백 정리 및 과도한 빈 줄 축소
    """
    if not isinstance(text, str) or not text.strip():
        return text

    s = text.replace('\r\n', '\n').replace('\r', '\n')

    # 1) 코드 펜스 라인 제거 (내용은 유지)
    # ```lang  또는 ``` 만 있는 라인을 제거
    s = re.sub(r"^```[a-zA-Z0-9_-]*\s*$", "", s, flags=re.MULTILINE)

    # 2) 제네릭 제목 헤딩 제거: "## 제목 슬라이드" (문서 제목으로 잘못 인식됨)
    s = re.sub(r"(?m)^##\s*제목\s*슬라이드\s*$", "", s)

    # 3) 연속된 동일 헤딩 제거 (첫 번째만 유지)
    def remove_duplicate_headings(text):
        lines = text.split('\n')
        processed_lines = []
        last_heading = None
        
        for line in lines:
            # 헤딩인지 확인 (### 부터 ###### 까지)
            heading_match = re.match(r'^(#{3,6})\s+(.+)', line.strip())
            if heading_match:
                heading_level = heading_match.group(1)
                heading_text = heading_match.group(2).strip()
                current_heading = (heading_level, heading_text)
                
                # 이전 헤딩과 동일한지 확인
                if current_heading != last_heading:
                    processed_lines.append(line)
                    last_heading = current_heading
                # 동일한 헤딩이면 스킵 (중복 제거)
            else:
                # 헤딩이 아닌 라인은 그대로 추가
                processed_lines.append(line)
                # 헤딩이 아닌 내용이 나오면 연속 헤딩 체크 리셋
                if line.strip():  # 빈 줄이 아닌 경우만
                    last_heading = None
                    
        return '\n'.join(processed_lines)
    
    s = remove_duplicate_headings(s)

    # 4) 헤딩 뒤 최소 한 줄 공백 보장
    s = re.sub(r"(?m)^(#{2,6}\s+[^\n]+)\n(?=\S)", r"\1\n\n", s)

    # 5) 과도한 연속 개행 축소
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


from loguru import logger
from sqlalchemy import text
from fastapi.responses import FileResponse

def safe_json_serialize(obj):
    """JSON 직렬화 가능한 형태로 객체 변환"""
    if isinstance(obj, dict):
        return {k: safe_json_serialize(v) for k, v in obj.items() if not k.startswith('_')}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return safe_json_serialize(obj.__dict__)
    elif hasattr(obj, 'isoformat'):  # datetime 객체
        return obj.isoformat()
    elif hasattr(obj, '__str__') and not hasattr(obj, '__call__'):  # 메서드가 아닌 객체만
        return str(obj)
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)

def clean_references_for_json(references):
    """참조 데이터를 JSON 직렬화 가능한 형태로 정리"""
    import math
    
    if not references:
        return []
    
    cleaned = []
    for ref in references:
        cleaned_ref = {}
        for key, value in ref.items():
            if key.startswith('_'):
                continue
            if hasattr(value, '__call__'):
                continue
            if isinstance(value, (str, int, bool, type(None))):
                cleaned_ref[key] = value
            elif isinstance(value, float):
                # NaN이나 Infinity 값 처리
                if math.isnan(value) or math.isinf(value):
                    cleaned_ref[key] = None
                else:
                    cleaned_ref[key] = value
            elif isinstance(value, list):
                cleaned_ref[key] = [str(item) if hasattr(item, '__call__') else item for item in value]
            else:
                cleaned_ref[key] = str(value)
        cleaned.append(cleaned_ref)
    
    return cleaned

def clean_stats_for_json(stats):
    """통계 데이터를 JSON 직렬화 가능한 형태로 정리"""
    import math
    
    if not stats:
        return {}
    
    cleaned = {}
    for key, value in stats.items():
        if key.startswith('_'):
            continue
        if hasattr(value, '__call__'):
            continue
        if isinstance(value, (str, int, bool, type(None))):
            cleaned[key] = value
        elif isinstance(value, float):
            # NaN이나 Infinity 값 처리
            if math.isnan(value) or math.isinf(value):
                cleaned[key] = None
            else:
                cleaned[key] = value
        else:
            cleaned[key] = str(value)
    
    return cleaned

router = APIRouter(tags=["💬 Chat & QA"])

# Redis 채팅 매니저 의존성
def get_redis_chat_manager() -> RedisChatManager:
    """Redis 채팅 매니저 의존성 주입"""
    redis_client = get_redis_client()
    return RedisChatManager(redis_client)

async def save_chat_session(
    db: AsyncSession, 
    session_id: str, 
    user_emp_no: str, 
    message: str,
    response: str,
    referenced_documents: Optional[List[int]] = None,
    search_results: Optional[dict] = None,
    conversation_context: Optional[dict] = None
) -> bool:
    """
    채팅 세션을 tb_chat_sessions와 tb_chat_history에 저장/업데이트
    - 세션 메타데이터 저장 (tb_chat_sessions)
    - 실제 메시지 내용 저장 (tb_chat_history)
    """
    try:
        # 1. 세션 메타데이터 저장/업데이트
        check_query = text("""
            SELECT session_id FROM tb_chat_sessions 
            WHERE session_id = :session_id AND user_emp_no = :user_emp_no
        """)
        
        result = await db.execute(check_query, {
            "session_id": session_id,
            "user_emp_no": user_emp_no
        })
        
        existing_session = result.fetchone()
        
        if existing_session:
            # 기존 세션 업데이트
            update_query = text("""
                UPDATE tb_chat_sessions 
                SET 
                    message_count = message_count + 1,
                    last_activity = NOW(),
                    last_modified_date = NOW()
                WHERE session_id = :session_id AND user_emp_no = :user_emp_no
            """)
            
            await db.execute(update_query, {
                "session_id": session_id,
                "user_emp_no": user_emp_no
            })
        else:
            # 새 세션 생성
            # 첫 번째 메시지에서 의미있는 제목 생성
            session_title = message.strip()
            # 이모지나 특수문자 일부 제거
            import re
            session_title = re.sub(r'[🔍📄💬🎯📊🤖✨🚀]+', '', session_title)
            # 줄바꿈을 공백으로 변환
            session_title = ' '.join(session_title.split())
            # 최대 100자로 제한
            if len(session_title) > 100:
                session_title = session_title[:97] + "..."
            # 제목이 너무 짧으면 기본값
            if len(session_title) < 3:
                session_title = f"대화 {session_id[:8]}"
            
            insert_query = text("""
                INSERT INTO tb_chat_sessions (
                    session_id, user_emp_no, session_name, message_count,
                    max_messages, session_timeout_minutes,
                    is_active, last_activity, created_date, last_modified_date
                ) VALUES (
                    :session_id, :user_emp_no, :session_name, 1,
                    100, 60,
                    true, NOW(), NOW(), NOW()
                )
            """)
            
            await db.execute(insert_query, {
                "session_id": session_id,
                "user_emp_no": user_emp_no,
                "session_name": session_title
            })
        
        # 2. 🆕 실제 메시지 내용을 tb_chat_history에 저장
        insert_message_query = text("""
            INSERT INTO tb_chat_history (
                session_id,
                user_emp_no,
                user_message,
                assistant_response,
                referenced_documents,
                search_results,
                conversation_context,
                created_date
            ) VALUES (
                :session_id,
                :user_emp_no,
                :user_message,
                :assistant_response,
                :referenced_documents,
                :search_results,
                :conversation_context,
                NOW()
            )
        """)
        
        # JSONB 필드를 위한 JSON 직렬화
        import json
        search_results_json = json.dumps(search_results) if search_results else None
        conversation_context_json = json.dumps(conversation_context) if conversation_context else None
        
        await db.execute(insert_message_query, {
            "session_id": session_id,
            "user_emp_no": user_emp_no,
            "user_message": message,
            "assistant_response": response,
            "referenced_documents": referenced_documents,
            "search_results": search_results_json,
            "conversation_context": conversation_context_json
        })
        
        await db.commit()
        logger.info(f"✅ 채팅 세션 및 메시지 저장 완료: {session_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ 채팅 세션 저장 실패: {e}")
        await db.rollback()
        return False

class ChatAttachmentPayload(BaseModel):
    asset_id: str
    category: Optional[str] = "document"
    file_name: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    provider: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    use_rag: bool = True  # RAG 사용 여부
    container_ids: Optional[List[str]] = None  # 검색 대상 컨테이너
    include_references: bool = True  # 참조 정보 포함 여부
    attachments: Optional[List[ChatAttachmentPayload]] = None
    voice_asset_id: Optional[str] = None
    # RAG 전용 매개변수
    max_chunks: int = 10
    similarity_threshold: float = 0.4  # 관련성 없는 문서 필터링을 위한 엄격한 임계값
    search_mode: str = "hybrid"  # "semantic", "keyword", "hybrid"
    use_reranking: bool = True
    context_window: int = 4000

class ChatStreamRequest(BaseModel):
    """스트리밍 채팅 요청"""
    message: str
    agent_type: Optional[str] = 'general'  # AI Agent 타입
    selected_documents: Optional[List[SelectedDocument]] = []  # 선택된 문서들
    provider: Optional[str] = None
    providers: Optional[List[str]] = None  # 복수 프로바이더 지원
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    use_rag: bool = True
    container_ids: Optional[List[str]] = None
    include_references: bool = True
    max_chunks: int = 10
    max_tokens: Optional[int] = 4000  # 일반 채팅: 2000 → 4000 (충분한 답변 생성)
    temperature: Optional[float] = 0.7
    similarity_threshold: float = 0.4  # 관련성 없는 문서 필터링을 위한 엄격한 임계값
    search_mode: str = "hybrid"
    use_reranking: bool = True
    context_window: int = 4000
    attachments: Optional[List[ChatAttachmentPayload]] = None
    voice_asset_id: Optional[str] = None



class ChatResponse(BaseModel):
    response: str
    provider: str
    session_id: Optional[str] = None
    references: Optional[List[dict]] = None  # RAG 참조 정보
    context_info: Optional[dict] = None  # 컨텍스트 정보
    rag_stats: Optional[dict] = None  # RAG 검색 통계

class EmbeddingRequest(BaseModel):
    texts: List[str]
    provider: Optional[str] = None

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    provider: str

class SearchRequest(BaseModel):
    query: str
    provider: Optional[str] = None

class SearchResponse(BaseModel):
    embedding: List[float]
    provider: str

class RAGSearchRequest(BaseModel):
    """RAG 전용 검색 요청"""
    query: str
    container_ids: Optional[List[str]] = None
    max_chunks: int = 10
    similarity_threshold: float = 0.4  # 관련성 없는 문서 필터링을 위한 엄격한 임계값
    search_mode: str = "hybrid"
    use_reranking: bool = True
    context_window: int = 4000

class RAGSearchResponse(BaseModel):
    """RAG 전용 검색 응답"""
    success: bool
    chunks: List[dict]
    context_text: str
    total_tokens: int
    search_stats: dict
    reranking_applied: bool


@router.post("/chat/assets")
async def upload_chat_assets(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
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


@router.get("/chat/assets/{asset_id}")
async def download_chat_asset(
    asset_id: str,
    current_user: User = Depends(get_current_user)
):
    stored = chat_attachment_service.get(asset_id)
    if not stored:
        raise HTTPException(status_code=404, detail="첨부 파일을 찾을 수 없습니다.")

    if stored.owner_emp_no != str(current_user.emp_no):
        raise HTTPException(status_code=403, detail="첨부 파일에 대한 접근 권한이 없습니다.")

    return FileResponse(
        path=stored.path,
        media_type=stored.mime_type,
        filename=stored.file_name
    )


@router.post("/chat/transcribe")
async def transcribe_chat_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not audio_transcription_service.enabled:
        raise HTTPException(status_code=503, detail="오디오 전사 기능이 비활성화되어 있습니다.")

    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    temp_fd, temp_path_str = tempfile.mkstemp(suffix=suffix)
    os.close(temp_fd)
    temp_path = Path(temp_path_str)

    try:
        async with aiofiles.open(temp_path, "wb") as out_file:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                await out_file.write(chunk)

        transcript = await asyncio.to_thread(audio_transcription_service.transcribe, temp_path)
        return {"success": True, "transcript": transcript}
    except Exception as exc:
        logger.error(f"❌ 오디오 전사 실패: {exc}")
        raise HTTPException(status_code=500, detail="음성 텍스트 변환 중 오류가 발생했습니다.")
    finally:
        try:
            await file.close()
        except Exception:
            pass
        temp_path.unlink(missing_ok=True)


# ===== CORE CHAT ENDPOINTS =====

@router.post("/chat/stream")
async def chat_stream(
    raw_request: Request,
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """채팅 스트림 엔드포인트 (RAG + 에이전트 컨텍스트 반영) - generate_stream 함수 사용"""
    try:
        logger.info(f"🚀 채팅 스트림 요청: 메시지='{request.message}', 세션={request.session_id}, 제공자={request.provider}")
        logger.info(f"🔍 선택된 문서: {request.selected_documents}")
        logger.info(f"🔍 선택된 문서 개수: {len(request.selected_documents) if request.selected_documents else 0}")
        
        # 선택된 문서 검증 로깅
        if request.selected_documents:
            for idx, doc in enumerate(request.selected_documents):
                logger.info(f"  📄 문서 {idx+1}: id={doc.id}, fileName={doc.fileName}, fileType={doc.fileType}")
        
        # Provider는 .env 설정을 최우선 적용 (일관성 확보)
        effective_provider = settings.get_current_llm_provider()
        if request.provider and request.provider != effective_provider:
            logger.warning(f"⚠️ 요청 provider '{request.provider}'를 무시하고 설정값 '{effective_provider}' 사용")
        
        # 스트리밍 제너레이터를 즉시 실행하도록 래퍼 함수 사용
        async def stream_wrapper():
            try:
                async for chunk in generate_stream(
                    message=request.message,
                    session_id=request.session_id or str(uuid.uuid4()),
                    current_user=current_user,
                    provider=effective_provider,
                    selected_documents=request.selected_documents if request.selected_documents else None,
                    chat_manager=chat_manager,
                    agent_type=request.agent_type or 'general',
                    container_ids=request.container_ids,
                    attachments=request.attachments,
                    voice_asset_id=request.voice_asset_id,
                    max_tokens=request.max_tokens,
                    temperature=request.temperature
                ):
                    yield chunk
            except Exception as e:
                logger.error(f"스트리밍 중 오류 발생: {e}")
                error_event = {"type": "error", "content": str(e)}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
        
        return StreamingResponse(
            stream_wrapper(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )
        
    except Exception as e:
        logger.error(f"채팅 스트림 엔드포인트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 간단 세션 로드/보관 엔드포인트 (프론트 요구사항 충족용)
@router.get("/chat/sessions/{session_id}")
async def get_chat_session(
    session_id: str, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    세션의 대화 내역 조회
    - PostgreSQL 우선 조회 (영구 저장된 메시지)
    - Redis 폴백 (최근 메시지, TTL 내)
    - 메시지 목록, 참고자료 목록, 선택된 문서 목록 반환
    """
    try:
        # 1. 세션 존재 확인
        session_query = text("""
            SELECT * FROM tb_chat_sessions 
            WHERE session_id = :session_id AND user_emp_no = :user_emp_no
        """)
        session_result = await db.execute(session_query, {
            "session_id": session_id,
            "user_emp_no": str(current_user.emp_no)
        })
        session = session_result.fetchone()
        
        if not session:
            logger.warning(f"⚠️ 세션을 찾을 수 없음: {session_id}")
            return {'success': False, 'session_id': session_id, 'messages': []}
        
        # 2. PostgreSQL에서 메시지 조회 (우선)
        messages_query = text("""
            SELECT 
                chat_id,
                user_message,
                assistant_response,
                referenced_documents,
                search_results,
                conversation_context,
                created_date
            FROM tb_chat_history
            WHERE session_id = :session_id
            ORDER BY created_date
        """)
        messages_result = await db.execute(messages_query, {
            "session_id": session_id
        })
        db_messages = messages_result.fetchall()
        
        logger.info(f"📦 PostgreSQL에서 {len(db_messages)}개 메시지 조회: {session_id}")
        
        # 3. PostgreSQL에 메시지가 있으면 사용, 없으면 Redis 폴백
        if db_messages and len(db_messages) > 0:
            # PostgreSQL 메시지 사용
            frontend_msgs = []
            all_referenced_doc_ids = set()
            selected_documents = []
            
            for i, row in enumerate(db_messages):
                # 사용자 메시지
                frontend_msgs.append({
                    'id': f"user_{i}",
                    'role': 'user',
                    'content': row.user_message,
                    'timestamp': row.created_date.isoformat()
                })
                
                # AI 응답
                assistant_msg = {
                    'id': f"assistant_{i}",
                    'role': 'assistant',
                    'content': row.assistant_response,
                    'timestamp': row.created_date.isoformat()
                }
                
                # 참고자료 포함
                if row.referenced_documents:
                    assistant_msg['referenced_documents'] = row.referenced_documents
                    all_referenced_doc_ids.update(row.referenced_documents)
                
                # 검색 결과/컨텍스트 포함 (JSONB)
                if row.search_results:
                    try:
                        import json
                        search_data = json.loads(row.search_results) if isinstance(row.search_results, str) else row.search_results
                        assistant_msg['context_info'] = search_data
                        
                        # 🆕 청크 상세 정보 추출 및 포함
                        if isinstance(search_data, dict) and 'detailed_chunks' in search_data:
                            assistant_msg['detailed_chunks'] = search_data['detailed_chunks']
                            logger.debug(f"📋 메시지 {i}에 {len(search_data['detailed_chunks'])}개 청크 정보 복원")
                    except Exception as e:
                        logger.warning(f"search_results JSON 파싱 실패: {e}")
                
                frontend_msgs.append(assistant_msg)
                
                # 🆕 모든 메시지에서 선택된 문서 수집 (가장 최근 것이 우선)
                if row.conversation_context:
                    try:
                        import json
                        ctx = json.loads(row.conversation_context) if isinstance(row.conversation_context, str) else row.conversation_context
                        if isinstance(ctx, dict) and 'selected_documents' in ctx:
                            # 가장 최근 selected_documents로 업데이트
                            current_docs = ctx.get('selected_documents', [])
                            if current_docs:
                                selected_documents = current_docs
                                logger.debug(f"📄 메시지 {i}에서 {len(current_docs)}개 선택 문서 발견")
                    except Exception as e:
                        logger.warning(f"conversation_context 파싱 실패: {e}")
            
            logger.info(f"✅ PostgreSQL 메시지 변환 완료: {len(frontend_msgs)}개, 선택 문서: {len(selected_documents)}개")
            
        else:
            # PostgreSQL에 메시지 없음 → Redis 폴백
            logger.warning(f"⚠️ PostgreSQL에 메시지 없음, Redis 폴백 시도: {session_id}")
            
            chat_manager = get_redis_chat_manager()
            redis_session = await chat_manager.get_chat_session(session_id)
            
            if not redis_session or str(redis_session.user_emp_no) != str(current_user.emp_no):
                logger.warning(f"⚠️ Redis에서도 세션을 찾을 수 없음: {session_id}")
                return {'success': False, 'session_id': session_id, 'messages': []}
            
            messages = await chat_manager.get_recent_messages(session_id, limit=200)
            
            all_referenced_doc_ids = set()
            selected_documents = []
            frontend_msgs = []
            
            for idx, m in enumerate(messages):
                role = 'assistant' if m.message_type.value == 'assistant' else ('user' if m.message_type.value == 'user' else 'system')
                
                if hasattr(m, 'referenced_documents') and m.referenced_documents:
                    all_referenced_doc_ids.update(m.referenced_documents)
                
                if idx == 0 and role == 'user' and hasattr(m, 'search_context') and m.search_context:
                    if 'selected_documents' in m.search_context:
                        selected_documents = m.search_context.get('selected_documents', [])
                
                msg_data = {
                    'id': f"{role}_{m.sequence_number}",
                    'message_id': getattr(m, 'message_id', None),
                    'role': role,
                    'content': m.content,
                    'timestamp': m.timestamp.isoformat(),
                    'context_info': getattr(m, 'search_context', None) or {},
                }
                
                if role == 'assistant' and hasattr(m, 'referenced_documents') and m.referenced_documents:
                    msg_data['referenced_documents'] = m.referenced_documents
                
                frontend_msgs.append(msg_data)
            
            logger.info(f"✅ Redis 메시지 변환 완료: {len(frontend_msgs)}개")

        # 4. 참고자료 상세 정보 조회 (공통)
        referenced_docs_detail = []
        if all_referenced_doc_ids:
            try:
                from sqlalchemy import select
                from app.models.document.file_models import TbFileBssInfo
                
                query = select(TbFileBssInfo).where(
                    TbFileBssInfo.file_bss_info_sno.in_(list(all_referenced_doc_ids))
                )
                result = await db.execute(query)
                docs = result.scalars().all()
                
                for doc in docs:
                    referenced_docs_detail.append({
                        'fileId': str(doc.file_bss_info_sno),
                        'fileName': doc.file_lgc_nm,  # file_logic_name → file_lgc_nm
                        'fileType': doc.file_extsn, 
                        'containerName': getattr(doc, 'knowledge_container_id', '') or '', 
                        'uploadDate': doc.created_date.isoformat() if getattr(doc, 'created_date', None) is not None else None
                    })
                
                logger.info(f"📄 참고자료 상세 정보 {len(referenced_docs_detail)}개 조회 완료")
            except Exception as doc_error:
                logger.warning(f"참고자료 상세 정보 조회 실패: {doc_error}")

        return { 
            'success': True, 
            'session_id': session_id, 
            'messages': frontend_msgs,
            'referenced_documents': referenced_docs_detail,
            'selected_documents': selected_documents
        }
    except Exception as e:
        logger.error(f"세션 조회 실패: {e}")
        import traceback
        logger.error(f"세션 조회 실패 상세:\n{traceback.format_exc()}")
        return {'success': False, 'session_id': session_id, 'messages': []}

@router.post("/chat/sessions/{session_id}/archive")
async def archive_chat_session(session_id: str, current_user: User = Depends(get_current_user)):
    # Redis 세션을 비활성화 상태로 전환하거나, 나중에 RDB로 영구 저장하도록 표시
    try:
        chat_manager = get_redis_chat_manager()
        session = await chat_manager.get_chat_session(session_id)
        if not session or str(session.user_emp_no) != str(current_user.emp_no):
            return { 'success': False, 'message': '세션을 찾을 수 없습니다.' }
        # 단순히 세션 상태를 idle로 표기 (실제 RDB 아카이브는 별도 배치에서 수행 가능)
        session.status = ChatSessionStatus.ARCHIVED
        session_key = RedisKeyPatterns.CHAT_SESSION.format(session_id=session_id)
        await chat_manager.redis.setex(session_key, RedisChatTTL.CHAT_SESSION, json.dumps(session.to_dict()))
        return { 'success': True, 'message': f'세션 {session_id} 저장(보관) 처리되었습니다.' }
    except Exception as e:
        logger.error(f"세션 아카이브 실패: {e}")
        return { 'success': False, 'message': '세션 저장 실패' }

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    provider: Optional[str] = None
    # 원칙 1/2 준수를 위해 선택 문서 입력을 허용
    selected_documents: Optional[List[SelectedDocument]] = []
    attachments: Optional[List[ChatAttachmentPayload]] = None
    voice_asset_id: Optional[str] = None

@router.post("/chat/message")
async def send_message(
    request: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """
    동기 채팅 메시지 전송 - 완료된 응답을 한 번에 반환
    스트리밍과 동일한 로직을 사용하되 최종 결과만 JSON으로 반환
    """
    try:
        # 1. 사용자 정보 준비
        user_emp_no = str(current_user.emp_no)
        user_name = str(current_user.username)
        user_department = "기본부서"
        
        session_id = request.session_id or str(uuid.uuid4())
        message = request.message
        
        # Provider는 .env 설정을 최우선 적용 (일관성 확보)
        provider = settings.get_current_llm_provider()
        if request.provider and request.provider != provider:
            logger.warning(f"⚠️ 요청 provider '{request.provider}'를 무시하고 설정값 '{provider}' 사용")
        
        logger.info(f"🚀 동기 채팅 요청: 사용자 {user_emp_no}, 세션 {session_id}, 제공자={provider}")
        
        attachment_metadata: List[Dict[str, Any]] = []
        if request.attachments:
            for payload in request.attachments:
                try:
                    stored = chat_attachment_service.get(payload.asset_id)
                    if not stored:
                        logger.warning(f"⚠️ 첨부 자산을 찾을 수 없음: {payload.asset_id}")
                        continue
                    if stored.owner_emp_no != str(current_user.emp_no):
                        logger.warning(f"⚠️ 첨부 자산 접근 권한 없음: {payload.asset_id}")
                        continue
                    attachment_metadata.append({
                        "asset_id": stored.asset_id,
                        "file_name": stored.file_name,
                        "mime_type": stored.mime_type,
                        "size": stored.size,
                        "category": stored.category,
                        "download_url": stored.download_url,
                        "preview_url": stored.preview_url
                    })
                except Exception as exc:
                    logger.error(f"첨부 정보 조회 실패: {exc}")

        # 2. 세션 생성/확인
        existing_session = await chat_manager.get_chat_session(session_id)
        if not existing_session:
            logger.info(f"새 세션 생성: {session_id}")
            await chat_manager.create_chat_session(
                user_emp_no=user_emp_no,
                user_name=user_name,
                department=user_department,
                session_id=session_id
            )
        
        # 3. 사용자 메시지 저장
        user_context = {}
        if request.selected_documents:
            user_context["selected_documents"] = request.selected_documents
        if attachment_metadata:
            user_context["attachments"] = attachment_metadata
        if request.voice_asset_id:
            user_context["voice_asset_id"] = request.voice_asset_id

        await chat_manager.add_message(
            session_id=session_id,
            content=message,
            message_type=MessageType.USER,
            user_emp_no=user_emp_no,
            user_name=user_name,
            search_context=user_context or None
        )
        
        # 4. 멀티턴 대화 기록 가져오기
        history_messages = []
        try:
            recent_messages = await chat_manager.get_recent_messages(session_id, limit=4)
            if recent_messages:
                for msg in recent_messages:
                    history_messages.append({
                        "role": "user" if msg.message_type.value == "user" else "assistant",
                        "content": msg.content
                    })
        except Exception as e:
            logger.warning(f"채팅 기록 조회 실패: {e}")
        
        # 5. RAG 검색 및 컨텍스트 준비
        references = []
        context_info = {"rag_used": False}
        rag_stats = {"provider": provider}
        final_response = ""
        
        try:
            # AI 에이전트 서비스로 컨텍스트 준비
            prepared_prompt, references, context_info, rag_stats = await ai_agent_service.prepare_context_with_documents(
                query=message,
                selected_documents=request.selected_documents if request.selected_documents else None,
                chat_history=history_messages,
                agent_type='general',
                container_ids=None
            )
            
            # 6. 시스템 프롬프트 로드
            system_prompt = None
            try:
                prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
                if prompt_path.exists():
                    system_prompt = prompt_path.read_text(encoding='utf-8').strip()
            except Exception as e:
                logger.warning(f"시스템 프롬프트 로드 실패: {e}")
            
            # 7. 메시지 구성 (system + history + user)
            llm_messages = []
            if system_prompt:
                llm_messages.append({"role": "system", "content": system_prompt})
            
            # 기존 대화 기록 추가 (현재 사용자 메시지 제외)
            llm_messages.extend(history_messages[:-1] if history_messages else [])
            
            # 컨텍스트가 준비된 메시지 또는 원본 메시지 추가
            llm_messages.append({"role": "user", "content": prepared_prompt})
            
            # 검색 실패 시에는 LLM 호출 없이 실패 안내를 그대로 반환 (원칙 보장)
            if isinstance(context_info, dict) and context_info.get('search_failed'):
                final_response = prepared_prompt
            else:
                # 8. AI 서비스 호출 (동기 방식)
                response_content = await ai_service.chat_completion(
                    messages=llm_messages,
                    provider=provider
                )
                # 응답 텍스트 추출 (개선된 로직)
                if isinstance(response_content, dict):
                    # AI 서비스가 딕셔너리를 반환하는 경우
                    if 'response' in response_content:
                        final_response = response_content['response']
                    elif 'content' in response_content:
                        final_response = response_content['content']
                    else:
                        final_response = str(response_content)
                elif isinstance(response_content, str):
                    final_response = response_content
                elif hasattr(response_content, 'content'):
                    final_response = response_content.content
                else:
                    final_response = str(response_content)
            
            # 마크다운 포맷팅 적용
            final_response = fix_markdown_formatting(final_response)
            
            # 🔍 모드 검증 및 Fallback 메커니즘 (새로 추가)
            ppt_intent_detected = detect_ppt_intent_in_query(message)
            ppt_format_detected = detect_ppt_format(final_response)
            
            logger.info(f"모드 검증: PPT 의도={ppt_intent_detected}, PPT 형식={ppt_format_detected}")
            
            # 잘못된 모드로 응답이 생성된 경우 재시도
            needs_retry = False
            retry_reason = ""
            
            if not ppt_intent_detected and ppt_format_detected:
                # 일반 질문인데 PPT 형식으로 응답한 경우
                needs_retry = True
                retry_reason = "일반 질문에 PPT 형식 응답 생성"
            elif ppt_intent_detected and not ppt_format_detected:
                # PPT 요청인데 일반 형식으로 응답한 경우
                # RAG 컨텍스트가 없어서 안내 메시지가 나온 경우는 정상이므로 재시도 안함
                if "관련된 정보를 찾을 수 없" in final_response or "관련 자료를 찾을 수 없" in final_response:
                    logger.info("PPT 요청이지만 RAG 자료 부족으로 인한 안내 메시지 - 재시도 안함")
                    needs_retry = False
                else:
                    needs_retry = True
                    retry_reason = "PPT 요청에 일반 형식 응답 생성 (RAG 자료는 있음)"
            
            # 재시도 로직 실행
            if needs_retry:
                logger.warning(f"모드 불일치 감지: {retry_reason} - 재시도 실행")
                
                try:
                    # 강화된 시스템 프롬프트로 재시도
                    retry_system_prompt = None
                    try:
                        prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
                        if prompt_path.exists():
                            base_prompt = prompt_path.read_text(encoding='utf-8').strip()
                            
                            # 모드별 강화된 지시사항 추가
                            if not ppt_intent_detected:
                                # 일반 모드 강화
                                retry_system_prompt = base_prompt + "\n\n⚠️ CRITICAL: 이 질문은 일반적인 질문입니다. 절대로 제목(##, ###)이나 🔑📝 패턴을 사용하지 마세요. 평문으로 자연스럽게 답변하세요."
                            else:
                                # PPT 모드 강화
                                retry_system_prompt = base_prompt + "\n\n⚠️ CRITICAL: 이 질문은 PPT 생성 요청입니다. 반드시 ## 제목, ### 슬라이드, 🔑📝 패턴을 사용하여 슬라이드 형식으로 답변하세요."
                    except Exception:
                        retry_system_prompt = base_prompt if 'base_prompt' in locals() else None
                    
                    # 재시도 메시지 구성
                    retry_messages = []
                    if retry_system_prompt:
                        retry_messages.append({"role": "system", "content": retry_system_prompt})
                    
                    # 기존 대화 기록 추가 (현재 사용자 메시지 제외)
                    retry_messages.extend(history_messages[:-1] if history_messages else [])
                    retry_messages.append({"role": "user", "content": prepared_prompt})
                    
                    # AI 서비스 재호출
                    retry_response = await ai_service.chat_completion(
                        messages=retry_messages,
                        provider=provider
                    )
                    
                    # 재시도 응답 처리
                    if isinstance(retry_response, dict):
                        if 'response' in retry_response:
                            retry_final = retry_response['response']
                        elif 'content' in retry_response:
                            retry_final = retry_response['content']
                        else:
                            retry_final = str(retry_response)
                    elif isinstance(retry_response, str):
                        retry_final = retry_response
                    elif hasattr(retry_response, 'content'):
                        retry_final = retry_response.content
                    else:
                        retry_final = str(retry_response)
                    
                    retry_final = fix_markdown_formatting(retry_final)
                    
                    # 재시도 결과 검증
                    retry_ppt_format = detect_ppt_format(retry_final)
                    
                    if not ppt_intent_detected and not retry_ppt_format:
                        # 일반 질문 + 일반 응답 (성공)
                        final_response = retry_final
                        logger.info("재시도 성공: 일반 모드로 정상 응답 생성")
                    elif ppt_intent_detected and retry_ppt_format:
                        # PPT 요청 + PPT 응답 (성공)
                        final_response = retry_final
                        logger.info("재시도 성공: PPT 모드로 정상 응답 생성")
                    else:
                        # 재시도도 실패한 경우 원본 유지하되 로그 남김
                        logger.warning(f"재시도 실패: 여전히 모드 불일치 (PPT 의도={ppt_intent_detected}, PPT 형식={retry_ppt_format})")
                
                except Exception as retry_err:
                    logger.error(f"모드 재시도 실패: {retry_err}")
                    # 재시도 실패 시 원본 응답 유지
            
        except Exception as e:
            logger.error(f"RAG/AI 처리 실패, fallback 모드: {e}")
            
            # Fallback: 기본 AI 서비스 사용
            try:
                system_prompt = None
                try:
                    prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
                    if prompt_path.exists():
                        system_prompt = prompt_path.read_text(encoding='utf-8').strip()
                except Exception:
                    pass
                
                fallback_messages = []
                if system_prompt:
                    fallback_messages.append({"role": "system", "content": system_prompt})
                fallback_messages.extend(history_messages)
                fallback_messages.append({"role": "user", "content": message})
                
                response_content = await ai_service.chat_completion(
                    messages=fallback_messages,
                    provider=provider
                )
                
                # Fallback에서도 개선된 응답 처리 로직 적용
                if isinstance(response_content, dict):
                    if 'response' in response_content:
                        final_response = response_content['response']
                    elif 'content' in response_content:
                        final_response = response_content['content']
                    else:
                        final_response = str(response_content)
                elif isinstance(response_content, str):
                    final_response = response_content
                elif hasattr(response_content, 'content'):
                    final_response = response_content.content
                else:
                    final_response = str(response_content)
                    
                final_response = fix_markdown_formatting(final_response)
                
            except Exception as fallback_err:
                logger.error(f"Fallback AI 서비스 실패: {fallback_err}")
                final_response = "죄송합니다. 일시적으로 응답을 생성할 수 없습니다."
        
        # 9. AI 응답 저장
        try:
            await chat_manager.add_message(
                session_id=session_id,
                content=final_response,
                message_type=MessageType.ASSISTANT,
                user_emp_no=user_emp_no,
                user_name=user_name,
                search_context=context_info
            )
        except Exception as e:
            logger.warning(f"AI 응답 저장 실패: {e}")
        
        # 10. JSON 응답 반환
        return {
            "response": final_response,
            "provider": rag_stats.get("provider", provider),
            "session_id": session_id,
            "references": clean_references_for_json(references) if references else [],
            "context_info": clean_stats_for_json(context_info),
            "rag_stats": rag_stats,
            "attachments": attachment_metadata,
            "voice_asset_id": request.voice_asset_id
        }
        
    except Exception as e:
        logger.error(f"동기 메시지 전송 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/sessions")
async def get_chat_sessions(
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """
    채팅 세션 목록 조회
    - PostgreSQL 우선 조회 (영구 저장된 모든 세션)
    - Redis는 추가 정보용으로만 사용
    """
    try:
        # PostgreSQL에서 세션 목록 조회
        sessions_query = (
            select(
                TbChatSessions.session_id,
                TbChatSessions.session_name,
                TbChatSessions.message_count,
                TbChatSessions.last_activity,
                TbChatSessions.created_date,
                TbChatSessions.last_modified_date,
                # 실제 메시지 수 서브쿼리
                func.count(TbChatHistory.chat_id).label('actual_message_count')
            )
            .select_from(TbChatSessions)
            .outerjoin(
                TbChatHistory,
                TbChatSessions.session_id == TbChatHistory.session_id
            )
            .where(TbChatSessions.user_emp_no == str(current_user.emp_no))
            .where(TbChatSessions.is_active == True)
            .group_by(
                TbChatSessions.session_id,
                TbChatSessions.session_name,
                TbChatSessions.message_count,
                TbChatSessions.last_activity,
                TbChatSessions.created_date,
                TbChatSessions.last_modified_date
            )
            .order_by(desc(TbChatSessions.last_modified_date))
            .limit(limit)
        )
        
        result = await db.execute(sessions_query)
        db_sessions = result.all()
        
        logger.info(f"📋 PostgreSQL에서 {len(db_sessions)}개 세션 조회: user={current_user.emp_no}")
        
        sessions = []
        for row in db_sessions:
            session_id = row.session_id
            
            # 제목 처리
            title = row.session_name or "새 대화"
            if len(title) > 50:
                title = title[:50] + "..."
            
            # 실제 메시지 수 vs 선언된 메시지 수
            declared_count = row.message_count or 0
            actual_count = row.actual_message_count or 0
            
            # 메시지 수는 실제 메시지 수 우선, 없으면 선언된 수 사용
            message_count = actual_count if actual_count > 0 else declared_count
            
            # 마지막 활동 시간
            last_activity = row.last_modified_date or row.last_activity or row.created_date
            
            sessions.append({
                'session_id': session_id,
                'title': title,
                'message_count': message_count,
                'last_activity': last_activity.isoformat() if last_activity else None,
                'created_at': row.created_date.isoformat() if row.created_date else None,
                # 디버깅 정보 (프론트에서 사용 안 해도 됨)
                '_debug': {
                    'declared_count': declared_count,
                    'actual_count': actual_count
                }
            })
        
        logger.info(f"✅ 세션 목록 반환: {len(sessions)}개")
        
        return {
            "success": True,
            "sessions": sessions,
            "total": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"❌ 세션 목록 조회 오류: {e}")
        import traceback
        logger.error(f"❌ 상세 오류:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager),
    db: AsyncSession = Depends(get_db)
):
    """채팅 세션 삭제 - Redis와 PostgreSQL 모두에서 삭제"""
    try:
        # PostgreSQL에서 세션 존재 여부 및 소유자 확인 (PostgreSQL이 소스 오브 트루스)
        session_query = (
            select(TbChatSessions)
            .where(
                TbChatSessions.session_id == session_id,
                TbChatSessions.user_emp_no == str(current_user.emp_no),
                TbChatSessions.is_active == True
            )
        )
        session_result = await db.execute(session_query)
        session = session_result.scalars().first()
        if not session:
            logger.warning(f"⚠️ 삭제 요청한 세션을 찾을 수 없음: {session_id} (user={current_user.emp_no})")
            return {"success": False, "message": "세션을 찾을 수 없습니다."}

        # Redis에서 세션 제거 (있을 때만)
        redis_deleted = False
        try:
            redis_session = await chat_manager.get_chat_session(session_id)
            if redis_session:
                redis_deleted = await chat_manager.close_chat_session(session_id)
                logger.info(f"🗑️ Redis 세션 삭제 완료: {session_id}")
        except Exception as redis_error:
            logger.warning(f"⚠️ Redis 세션 삭제 중 오류: {redis_error}")

        # PostgreSQL에서 히스토리 및 세션 삭제 (트랜잭션)
        try:
            await db.execute(
                delete(TbChatHistory).where(TbChatHistory.session_id == session_id)
            )
            result = await db.execute(
                delete(TbChatSessions).where(
                    TbChatSessions.session_id == session_id,
                    TbChatSessions.user_emp_no == str(current_user.emp_no)
                )
            )
            await db.commit()

            deleted_rows = result.rowcount or 0
            logger.info(f"✅ PostgreSQL 세션 삭제 완료: {session_id} (삭제된 세션 수: {deleted_rows})")
        except Exception as pg_error:
            await db.rollback()
            logger.error(f"❌ PostgreSQL 세션 삭제 실패: {pg_error}")
            raise HTTPException(status_code=500, detail="세션 삭제 중 오류가 발생했습니다.")

        return {
            "success": True,
            "message": "세션이 삭제되었습니다.",
            "removed_from_redis": redis_deleted
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"세션 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== VISION CHAT ENDPOINT =====

@router.post("/chat/vision")
async def chat_with_vision(
    message: str = Form(...),
    images: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(None),
    provider: Optional[str] = Form("azure_openai"),
    container_ids: Optional[str] = Form(None),
    use_rag: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    chat_manager: RedisChatManager = Depends(get_redis_chat_manager)
):
    """
    이미지 포함 채팅 (간소화 버전 - Blob Storage 없이 Base64 사용)
    
    Args:
        message: 사용자 질문
        images: 업로드된 이미지 파일 리스트
        session_id: 채팅 세션 ID (선택)
        provider: AI 제공자 (azure_openai/bedrock/openai)
        container_ids: 검색 대상 컨테이너 (콤마 구분)
        use_rag: RAG 검색 사용 여부
        current_user: 현재 사용자
        db: 데이터베이스 세션
        chat_manager: Redis 채팅 매니저
    
    Returns:
        이미지 분석 결과 및 RAG 답변
    """
    try:
        logger.info(f"📸 Vision 채팅 시작: {len(images)}개 이미지, 쿼리='{message[:50]}...'")
        
        # 1. 세션 ID 생성 또는 확인
        if not session_id:
            session_id = f"vision_{uuid.uuid4().hex[:12]}"
            logger.info(f"✅ 새 Vision 세션 생성: {session_id}")
        
        # 2. 컨테이너 ID 파싱
        container_id_list = []
        if container_ids:
            try:
                container_id_list = [int(c.strip()) for c in container_ids.split(',') if c.strip()]
            except:
                logger.warning(f"⚠️ 컨테이너 ID 파싱 실패: {container_ids}")
        
        # 3. 이미지 분석 (Base64 사용)
        image_descriptions = []
        image_files_info = []
        
        for i, image in enumerate(images):
            try:
                # 이미지 데이터 읽기
                image_data = await image.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                # Vision API 분석
                description = await vision_service.analyze_image_from_base64(
                    base64_image=image_base64,
                    prompt=f"이미지를 상세히 설명하고, 주요 텍스트나 데이터가 있다면 추출해주세요.",
                    max_tokens=500
                )
                
                image_descriptions.append({
                    "image_index": i + 1,
                    "filename": image.filename or f"image_{i+1}",
                    "description": description
                })
                
                image_files_info.append({
                    "filename": image.filename or f"image_{i+1}",
                    "size": len(image_data),
                    "content_type": image.content_type or "image/jpeg"
                })
                
                logger.info(f"✅ 이미지 {i+1}/{len(images)} 분석 완료")
                
            except Exception as e:
                logger.error(f"❌ 이미지 {i+1} 분석 실패: {e}")
                image_descriptions.append({
                    "image_index": i + 1,
                    "filename": image.filename or f"image_{i+1}",
                    "description": f"이미지 분석 실패: {str(e)}"
                })
        
        # 4. 통합 쿼리 생성 (텍스트 + 이미지 설명)
        combined_query = f"{message}\n\n[첨부된 이미지 정보]\n"
        for desc in image_descriptions:
            combined_query += f"\n이미지 {desc['image_index']} ({desc['filename']}):\n{desc['description']}\n"
        
        logger.info(f"✅ 통합 쿼리 생성 완료: {len(combined_query)} 글자")
        
        # 5. AI 답변 생성 (RAG는 추후 통합 가능)
        try:
            prompt = f"""질문: {message}

[첨부된 이미지 분석 결과]
{chr(10).join([f"이미지 {d['image_index']}: {d['description']}" for d in image_descriptions])}

위 이미지 분석 결과를 바탕으로 질문에 답변해주세요."""
            
            ai_response = await ai_service.chat(
                message=prompt,
                provider=provider
            )
            
            final_response = ai_response if isinstance(ai_response, str) else ai_response.get("response", "답변을 생성할 수 없습니다.")
            logger.info(f"✅ AI 답변 생성 완료: {len(final_response)} 글자")
            
        except Exception as e:
            logger.error(f"❌ AI 답변 생성 실패: {e}")
            final_response = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
        
        # 6. 세션에 메시지 저장
        try:
            # 사용자 메시지 저장
            await chat_manager.add_message(
                session_id=session_id,
                message_type=MessageType.USER,
                content=message,
                user_emp_no=str(current_user.emp_no),
                user_name=str(current_user.username)
            )
            
            # AI 응답 저장
            await chat_manager.add_message(
                session_id=session_id,
                message_type=MessageType.ASSISTANT,
                content=final_response,
                user_emp_no=str(current_user.emp_no),
                user_name=str(current_user.username),
                model_used=provider
            )
            
            logger.info(f"✅ 세션 메시지 저장 완료: {session_id}")
            
        except Exception as e:
            logger.warning(f"⚠️ 세션 메시지 저장 실패: {e}")
        
        # 7. 응답 반환
        return {
            "response": final_response,
            "session_id": session_id,
            "provider": provider,
            "images": image_files_info,
            "image_descriptions": image_descriptions,
            "references": [],
            "context_info": {},
            "rag_stats": {}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Vision 채팅 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== END OF CHAT ENDPOINTS =====

# ===== CORE STREAMING FUNCTION =====

async def generate_stream(
    message: str,
    session_id: str,
    current_user: User,
    provider: Optional[str] = None,
    selected_documents: Optional[list] = None,
    chat_manager: Optional[RedisChatManager] = None,
    agent_type: str = 'general',
    container_ids: Optional[List[str]] = None,
    attachments: Optional[List[ChatAttachmentPayload]] = None,
    voice_asset_id: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None
):
    """
    스트리밍 응답 생성 함수 - 이전 버전에서 복원
    """
    try:
        # 사용자 정보를 async 컨텍스트 밖에서 미리 저장
        user_emp_no = str(current_user.emp_no)
        user_name = str(current_user.username)
        user_department = "기본부서"  # async 컨텍스트 문제 방지
        
        # LLM 파라미터 사전 계산
        effective_provider = provider or settings.get_current_llm_provider()
        effective_max_tokens = max_tokens or settings.max_tokens
        effective_temperature = settings.temperature if temperature is None else temperature

        logger.info(
            f"🚀 채팅 스트림 시작: 사용자 {user_emp_no}, 세션 {session_id}, "
            f"provider={effective_provider}, max_tokens={effective_max_tokens}, temperature={effective_temperature}"
        )

        # 즉시 스트림 초기 이벤트 전송 (프론트가 로딩 상태 전환 가능)
        init_event = {"type": "init", "session_id": session_id, "provider": effective_provider}
        yield f"data: {json.dumps(init_event, ensure_ascii=False)}\n\n"

        # 이후 로직에서 일관된 provider 사용
        provider = effective_provider
        
        # Redis Chat Manager 초기화
        if not chat_manager:
            chat_manager = get_redis_chat_manager()
        
        # 세션이 없으면 새로 생성
        if session_id:
            existing_session = await chat_manager.get_chat_session(session_id)
            if not existing_session:
                logger.info(f"새 세션 생성: {session_id}")
                await chat_manager.create_chat_session(
                    user_emp_no=user_emp_no,
                    user_name=user_name,
                    department=user_department,
                    session_id=session_id
                )
        else:
            # 세션 ID가 없으면 새로 생성
            session_id = str(uuid.uuid4())
            logger.info(f"새 세션 ID 생성: {session_id}")
            await chat_manager.create_chat_session(
                user_emp_no=user_emp_no,
                user_name=user_name,
                department=user_department,
                session_id=session_id
            )
        
        # 시작 이벤트
        yield f"data: {json.dumps({'type': 'start', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        
        # 선택된 문서 정보를 컨텍스트로 준비
        selected_docs_context: Optional[Dict[str, Any]] = None
        if selected_documents and len(selected_documents) > 0:
            normalized_selected_docs = []
            for doc in selected_documents:
                if isinstance(doc, dict):
                    normalized_selected_docs.append({
                        'id': doc.get('id'),
                        'fileName': doc.get('fileName'),
                        'fileType': doc.get('fileType'),
                    })
                else:
                    normalized_selected_docs.append({
                        'id': getattr(doc, 'id', None),
                        'fileName': getattr(doc, 'fileName', None),
                        'fileType': getattr(doc, 'fileType', None),
                    })
            selected_docs_context = {'selected_documents': normalized_selected_docs}

        attachment_metadata: List[Dict[str, Any]] = []
        if attachments:
            for payload in attachments:
                try:
                    stored = chat_attachment_service.get(payload.asset_id)
                    if not stored:
                        logger.warning("⚠️ 첨부 자산을 찾을 수 없음: %s", payload.asset_id)
                        continue
                    if stored.owner_emp_no != str(current_user.emp_no):
                        logger.warning("⚠️ 첨부 자산에 대한 접근 권한 없음: %s", payload.asset_id)
                        continue
                    attachment_metadata.append({
                        "asset_id": stored.asset_id,
                        "file_name": stored.file_name,
                        "mime_type": stored.mime_type,
                        "size": stored.size,
                        "category": stored.category,
                        "download_url": stored.download_url,
                        "preview_url": stored.preview_url
                    })
                except Exception as exc:
                    logger.error("첨부 정보 조회 실패: %s", exc)

        user_context = selected_docs_context.copy() if selected_docs_context else {}
        if attachment_metadata:
            user_context['attachments'] = attachment_metadata
        if voice_asset_id:
            user_context['voice_asset_id'] = voice_asset_id
        
        # 사용자 메시지를 Redis에 저장 (선택된 문서 포함)
        try:
            await chat_manager.add_message(
                session_id=session_id,
                content=message,
                message_type=MessageType.USER,
                user_emp_no=user_emp_no,
                user_name=str(user_name),
                search_context=user_context  # 선택된 문서 및 첨부 정보 저장
            )
        except Exception as e:
            logger.warning(f"사용자 메시지 저장 실패: {e}")
        
        # 멀티턴 대화를 위한 채팅 기록 미리 가져오기
        history_messages = []
        try:
            # 최근 4개 메시지 (2턴) 가져오기
            recent_messages = await chat_manager.get_recent_messages(session_id, limit=4)
            if recent_messages:
                logger.info(f"✅ 세션 {session_id}에서 멀티턴 컨텍스트용 메시지 {len(recent_messages)}개 로드")
                for msg in recent_messages:
                    history_messages.append({
                        "role": "user" if msg.message_type.value == "user" else "assistant",
                        "content": msg.content
                    })
            else:
                logger.info(f"세션 {session_id}에 이전 메시지 없음")
        except Exception as e:
            logger.warning(f"채팅 기록 조회 실패: {e}")
            history_messages = []

        # AI 에이전트 서비스 사용 가능성 검증 (경량화: 사전 프로빙 호출 제거)
        agent_available = True
        
        if not agent_available:
            logger.warning("❌ AI 에이전트 서비스 사용불가 - 기본 AI 서비스로 대체")
            
            # 멀티턴 대화를 위한 채팅 기록 가져오기 (fallback용)
            history_messages = []
            try:
                # 최근 4개 메시지 (2턴) 가져오기
                recent_messages = await chat_manager.get_recent_messages(session_id, limit=4)
                if recent_messages:
                    logger.info(f"✅ Fallback - 세션 {session_id}에서 멀티턴 컨텍스트용 메시지 {len(recent_messages)}개 로드")
                    for msg in recent_messages:
                        history_messages.append({
                            "role": "user" if msg.message_type.value == "user" else "assistant",
                            "content": msg.content
                        })
                else:
                    logger.info(f"🔍 Fallback - 세션 {session_id}에 기록이 없음, 빈 기록으로 시작")
            except Exception as e:
                logger.warning(f"⚠️ Fallback - 채팅 기록 로드 실패: {e}")
            
            # 시스템 프롬프트 로드
            system_prompt = None
            try:
                prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
                if prompt_path.exists():
                    system_prompt = prompt_path.read_text(encoding='utf-8').strip()
                    logger.info("✅ 기본 서비스용 시스템 프롬프트 로드 성공")
            except Exception as e:
                logger.warning(f"⚠️ 기본 서비스용 시스템 프롬프트 로드 실패: {e}")
            
            # 기본 AI 서비스로 스트리밍 (멀티턴 대화 지원)
            fallback_messages = []
            if system_prompt:
                fallback_messages.append({"role": "system", "content": system_prompt})
            fallback_messages.extend(history_messages)
            fallback_messages.append({"role": "user", "content": message})
            
            async for chunk in ai_service.chat_stream(
                messages=fallback_messages,
                provider=provider
            ):
                if chunk:
                    content = ""
                    if isinstance(chunk, str):
                        content = chunk
                    elif hasattr(chunk, 'content'):
                        content = chunk.content
                    elif hasattr(chunk, 'text'):
                        content = chunk.text
                    elif isinstance(chunk, dict):
                        content = chunk.get('content', '') or chunk.get('text', '') or str(chunk)
                    else:
                        content = str(chunk)
                    
                    if content:
                        response_data = {
                            "type": "content",
                            "content": content
                        }
                        yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"
            
            # 완료 이벤트
            yield f"data: {json.dumps({'type': 'complete', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return
        
        # 검색 시작 알림
        yield f"data: {json.dumps({'type': 'searching'}, ensure_ascii=False)}\n\n"
        
        # 2. 채팅 기록 가져오기 (RAG 검색용으로 정제)
        history_for_rag = []
        recent_raw_messages = []
        if chat_manager and session_id:
            try:
                recent_raw_messages = await chat_manager.get_recent_messages(session_id, limit=4)
                for msg in recent_raw_messages:
                    role = 'user' if msg.message_type.value == "user" else 'assistant'
                    # RAG 검색용 컨텍스트에서는 마크다운을 제거하여 순수 텍스트만 사용
                    clean_content = re.sub(r'#+\s*', '', msg.content)
                    history_for_rag.append({"role": role, "content": clean_content})
                logger.info(f"✅ 세션 {session_id}에서 RAG 검색용으로 정제된 메시지 {len(history_for_rag)}개 로드")
            except Exception as e:
                logger.warning(f"채팅 기록 로드 실패 (RAG용): {e}")

        # RAG 검색 및 에이전트 처리 (정제된 채팅 기록 전달)
        try:
            logger.info(f"🔍 generate_stream에서 받은 selected_documents: {selected_documents}")
            logger.info(f"🔍 selected_documents 타입: {type(selected_documents)}")
            
            normalized_docs: List[SelectedDocument] = []
            if selected_documents and len(selected_documents) > 0:
                logger.info(f"🔍 selected_documents 정규화 시작: {len(selected_documents)}개")
                for d in selected_documents:
                    if isinstance(d, SelectedDocument):
                        normalized_docs.append(d)
                    elif isinstance(d, dict):
                        normalized_docs.append(SelectedDocument(**d))

            # 선택된 문서가 없으면 최근 사용자 메시지의 search_context에서 상속
            if not normalized_docs:
                try:
                    for m in (recent_raw_messages or []):
                        if getattr(m, 'message_type', None) and m.message_type.value == "user":
                            sc = getattr(m, 'search_context', None) or {}
                            if isinstance(sc, dict) and sc.get('selected_documents'):
                                inherited = []
                                for d in sc.get('selected_documents', []):
                                    try:
                                        if isinstance(d, dict):
                                            inherited.append(SelectedDocument(**d))
                                    except Exception:
                                        continue
                                if inherited:
                                    normalized_docs = inherited
                                    logger.info(f"📄 최근 사용자 메시지에서 선택 문서 상속: {len(normalized_docs)}개")
                                    break
                except Exception as inh_err:
                    logger.warning(f"선택 문서 상속 중 경고: {inh_err}")

            # 선택된 문서가 최종 없으면 None을 전달하여 전체 문서 검색
            docs_to_pass = normalized_docs if normalized_docs else None
            logger.info(f"🔍 최종 docs_to_pass: {docs_to_pass}")
            
            # 이미지 첨부 정보 로깅
            if attachment_metadata:
                logger.info(f"🖼️ 이미지 첨부 감지: {len(attachment_metadata)}개")
                for idx, att in enumerate(attachment_metadata):
                    logger.info(f"  📎 첨부 {idx+1}: {att.get('file_name')} ({att.get('mime_type')})")

            prepared_prompt, references, context_info, rag_stats = await ai_agent_service.prepare_context_with_documents(
                query=message,
                selected_documents=docs_to_pass,
                chat_history=history_for_rag,  # 정제된 채팅 기록 전달
                agent_type='general',
                container_ids=None,
                attachments=attachment_metadata  # 🆕 이미지 첨부 정보 전달
            )
            
            chunks_count = len(references or [])
            search_complete_event = {'type': 'search_complete', 'chunks_count': chunks_count}
            yield f"data: {json.dumps(search_complete_event, ensure_ascii=False)}\n\n"
            
            context_event = {
                "type": "metadata",
                "references": clean_references_for_json(references) if not context_info.get('search_failed') else [],
                "context_info": clean_stats_for_json(context_info),
                "rag_stats": clean_stats_for_json({**rag_stats, "provider": settings.get_current_llm_provider()}),
            }
            yield f"data: {json.dumps(context_event, ensure_ascii=False)}\n\n"
            
            # 검색 실패 시에도 멀티턴 히스토리로 보완하여 LLM 생성으로 진행 (즉시 종료 금지)
            try:
                if isinstance(context_info, dict) and context_info.get('search_failed'):
                    logger.info("🔁 검색 실패 - 히스토리 기반 보완 생성으로 진행")
                    # 이후 단계에서 히스토리를 강제로 포함하도록 플래그만 남김
                    context_info['force_history_fallback'] = True
            except Exception as _e:
                logger.warning(f"검색 실패 Fallback 표시 중 경고: {_e}")
            
        except Exception as prep_err:
            logger.error(f"❌ 컨텍스트 준비 실패: {prep_err}")
            prepared_prompt, references, context_info, rag_stats = message, [], {"rag_used": False, "error": str(prep_err)}, {}
            search_complete_event = {'type': 'search_complete', 'chunks_count': 0, 'error': str(prep_err)}
            yield f"data: {json.dumps(search_complete_event, ensure_ascii=False)}\n\n"
        
        # 생성 시작 알림
        yield f"data: {json.dumps({'type': 'generating'}, ensure_ascii=False)}\n\n"

        # 1. 시스템 프롬프트 로드
        system_prompt = None
        try:
            prompt_path = Path("/home/admin/wkms-aws/backend/prompts/general.prompt")
            if prompt_path.exists():
                system_prompt = prompt_path.read_text(encoding='utf-8').strip()
                logger.info("✅ 시스템 프롬프트 로드 성공")
        except Exception as e:
            logger.warning(f"⚠️ 시스템 프롬프트 로드 실패: {e}")

        # 2. LLM용 채팅 기록 준비 (명시적 참조 여부에 따라 제어)
        history_for_llm = []
        
        # 멀티턴 컨텍스트 적용 여부 확인
        context_used = isinstance(context_info, dict) and context_info.get('context_used', False)
        explicit_reference = isinstance(context_info, dict) and context_info.get('reason') != 'no_explicit_reference'

        # 짧은 후속 질의/대명사 기반 강제 맥락 사용 완화 로직
        try:
            short_query = len(message.strip()) <= 12
            followup_pattern = re.search(r'(이거|그거|그건|그리고|근데|그림|표|논문|은요|는요|\?$)$', message.strip())
            force_history = bool(short_query or followup_pattern or (isinstance(context_info, dict) and context_info.get('force_history_fallback')))
        except Exception:
            force_history = False
        
        if force_history and not context_used:
            context_used = True
            explicit_reference = True
            if isinstance(context_info, dict):
                context_info['context_used'] = True
        
        if chat_manager and session_id and context_used and explicit_reference:
            try:
                recent_raw_messages = await chat_manager.get_recent_messages(session_id, limit=4)
                for msg in recent_raw_messages:
                    role = 'user' if msg.message_type.value == "user" else 'assistant'
                    # LLM용 기록은 원본 그대로 유지
                    history_for_llm.append({"role": role, "content": msg.content})
                logger.info(f"✅ 멀티턴 적용 - 세션 {session_id}에서 LLM용 메시지 {len(history_for_llm)}개 로드")
            except Exception as e:
                logger.warning(f"LLM용 채팅 기록 로드 실패: {e}")
        else:
            logger.info(f"📝 독립적 질문 처리 - 대화 히스토리 제외 (context_used={context_used}, explicit_ref={explicit_reference}, force={force_history})")

        # 3. AI 서비스에 전달할 최종 메시지 목록 구성
        llm_messages = []
        
        # 시스템 프롬프트와 RAG 컨텍스트를 하나의 시스템 메시지로 합치기 (Anthropic 호환)
        combined_system_content = ""
        
        # 생성 모드(게이팅) 안내 문구 구성
        mode_instruction = ""
        try:
            mode = context_info.get('selected_mode') if isinstance(context_info, dict) else None
            reason = context_info.get('gating_reason') if isinstance(context_info, dict) else None
            refs_count = 0
            try:
                refs_count = len(references) if references else 0
            except Exception:
                refs_count = 0
            if mode:
                logger.info(f"🎛️ 생성 모드: {mode}{' (' + reason + ')' if reason else ''}")
            if mode == 'outline':
                mode_instruction = (
                    "\n\n[생성 지침]\n"
                    "- 참고자료가 제한적이므로 거절하지 말고 '아웃라인 수준'의 PPT 개요를 생성하세요.\n"
                    "- Markdown 헤딩(##, ###), 🔑, 📝만 사용하고 코드펜스(```), 인라인 코드(`)는 절대 사용하지 마세요.\n"
                    "- 각 슬라이드의 제목과 3~5개의 핵심 불릿만 작성합니다.\n"
                    "- 불확실한 부분은 '확인 필요'로 표시하고, 추가로 필요한 자료/질문을 제안하세요.\n"
                    "- 참고자료가 1개 이상이면 사과/거절(자료 없음)은 금지됩니다. 최소한 아웃라인을 작성하세요.\n"
                )
            elif mode == 'full':
                mode_instruction = (
                    "\n\n[생성 지침]\n"
                    "- Markdown 헤딩(##, ###), 🔑, 📝만 사용하고 코드펜스(```), 인라인 코드(`)는 사용하지 마세요.\n"
                    "- 참고자료가 1개 이상이면 사과/거절(자료 없음)은 금지됩니다. 필요한 경우 '확인 필요'로 표시하고 내용을 구성하세요.\n"
                )
        except Exception:
            pass

        # prepared_prompt가 존재하면 이를 우선 시스템 컨텐츠로 사용 (중복 방지)
        if prepared_prompt and prepared_prompt.strip() and prepared_prompt != message:
            combined_system_content = prepared_prompt
            if mode_instruction:
                combined_system_content += mode_instruction
        else:
            if system_prompt:
                combined_system_content = system_prompt + mode_instruction
        
        # 합쳐진 시스템 메시지를 첫 번째에 추가
        if combined_system_content:
            llm_messages.append({"role": "system", "content": combined_system_content})
        
        # 채팅 기록을 LLM에 전달
        llm_messages.extend(history_for_llm)
        
        # 🆕 요약 모드일 때 사용자 메시지 재구성
        is_summarization_mode = isinstance(context_info, dict) and context_info.get('summarization_mode', False)
        
        if is_summarization_mode and prepared_prompt and prepared_prompt != message:
            # 요약 모드: 원문 컨텍스트 + 요약 지시사항
            user_message_content = f"""{prepared_prompt}

위 문서 내용을 바탕으로 다음 요청에 답변해주세요:
{message}

답변 지침:
- 문서의 핵심 내용을 체계적으로 정리하세요
- 주요 개념, 방법론, 결론을 포함하세요
- 원문의 구조를 유지하면서 간결하게 요약하세요
- 출처는 (파일명, p.페이지번호) 형식으로 표기하세요"""
            
            logger.info(f"📝 요약 모드 프롬프트 구성 완료: 원문 {len(prepared_prompt)}자 + 지시사항")
        else:
            # 일반 모드: 원본 메시지 또는 prepared_prompt
            user_message_content = prepared_prompt if prepared_prompt else message
        
        llm_messages.append({"role": "user", "content": user_message_content})

        # 디버그 로깅
        logger.info(f"🔍 LLM에 전달할 총 메시지 수: {len(llm_messages)}")
        logger.info(f"🔍 시스템 프롬프트 포함: {'YES' if combined_system_content else 'NO'}")
        try:
            rag_included = bool(references and len(references) > 0 and not (isinstance(context_info, dict) and context_info.get('search_failed')))
        except Exception:
            rag_included = False
        logger.info(f"🔍 RAG 컨텍스트 포함: {'YES' if rag_included else 'NO'}")
        if llm_messages:
            logger.info(f"🔍 마지막 사용자 메시지: {llm_messages[-1]['content'][:100]}...")

        collected_response = ""
        # PPT 의도 여부 사전 계산 (스트리밍 중 코드펜스 제거용)
        try:
            stream_ppt_intent = detect_ppt_intent_in_query(message)
        except Exception:
            stream_ppt_intent = False
        
        # 5. AI 서비스 스트리밍 호출 (실시간 토큰별 스트리밍)
        # - LLM 청크 수신이 지연될 수 있으므로, 별도 producer 태스크 + 큐 + 핑(keepalive) 이벤트로 연결 유지
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        async def _producer():
            try:
                async for _chunk in ai_service.chat_stream(
                    messages=llm_messages,
                    provider=provider,
                    max_tokens=effective_max_tokens,
                    temperature=effective_temperature
                ):
                    await queue.put(_chunk)
            except Exception as _e:
                await queue.put({"__error__": str(_e)})
            finally:
                await queue.put(None)  # sentinel

        producer_task = asyncio.create_task(_producer())

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                # 주기적 핑으로 연결 유지 및 프론트 진행 표시
                ping_event = {"type": "ping", "ts": datetime.utcnow().isoformat()}
                yield f"data: {json.dumps(ping_event, ensure_ascii=False)}\n\n"
                continue

            if item is None:
                # 생산 종료
                break

            if isinstance(item, dict) and item.get("__error__"):
                # producer에서의 예외를 스트림 에러로 전달
                error_event = {"type": "error", "message": item.get("__error__")}
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                break

            chunk = item
            if not chunk:
                continue
            content = ""
            if isinstance(chunk, str):
                content = chunk
            elif isinstance(chunk, dict):
                content = chunk.get('content', '') or chunk.get('text', '') or str(chunk)
            elif hasattr(chunk, 'content'):
                try:
                    content = chunk.content
                except Exception:
                    content = str(chunk)
            elif hasattr(chunk, 'text'):
                try:
                    content = chunk.text
                except Exception:
                    content = str(chunk)
            else:
                content = str(chunk)

            if content:
                # 실시간 표시 개선: PPT 의도 시 코드펜스(```) 마커 제거
                if stream_ppt_intent:
                    try:
                        content = content.replace("```", "")
                    except Exception:
                        pass
                # 청크 크기 제한 (클라이언트 버퍼 오버플로우 방지)
                # 큰 청크를 작은 단위로 분할 전송
                chunk_size = 500
                if len(content) > chunk_size:
                    for i in range(0, len(content), chunk_size):
                        sub_content = content[i:i+chunk_size]
                        response_data = {"type": "content", "content": sub_content}
                        yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"
                else:
                    # 실시간 토큰별 스트리밍 전송 (후처리 없음)
                    response_data = {
                        "type": "content",
                        "content": content
                    }
                    yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"
                collected_response += content

        # 종료 전 producer_task 정리
        try:
            await producer_task
        except Exception:
            pass
        
        # 🔍 디버그: LLM이 생성한 원본 답변 로그 출력 (후처리 없이 원본 그대로)
        logger.info(f"🔍 [DEBUG] LLM 원본 답변 (길이: {len(collected_response)}자):")
        logger.info(f"🔍 [DEBUG] 원본 답변 (후처리 없음):\n{collected_response}")

        # PPT 의도 시 출력 정리 (코드펜스 제거 등)
        try:
            ppt_intent = detect_ppt_intent_in_query(message)
        except Exception:
            ppt_intent = False
        final_to_store = collected_response
        if ppt_intent:
            final_to_store = sanitize_ppt_markdown(final_to_store)
            final_to_store = fix_markdown_formatting(final_to_store)
        
        # AI 응답을 Redis에 저장 (원본 LLM 답변 그대로)
        saved_message = None
        try:
            # 🔍 디버깅: references 구조 확인
            logger.info(f"🔍 [DEBUG] references 타입: {type(references)}")
            logger.info(f"🔍 [DEBUG] references 길이: {len(references) if references else 0}")
            if references and len(references) > 0:
                logger.info(f"🔍 [DEBUG] 첫 번째 reference 타입: {type(references[0])}")
                logger.info(f"🔍 [DEBUG] 첫 번째 reference 내용: {references[0]}")
                if hasattr(references[0], '__dict__'):
                    logger.info(f"🔍 [DEBUG] 첫 번째 reference 속성들: {references[0].__dict__}")
            
            # references에서 문서 ID 추출 (정규화: int 변환 및 중복 제거)
            referenced_doc_ids: List[int] = []
            if references:
                seen_ids = set()
                for ref in references:
                    doc_id = None
                    if isinstance(ref, dict):
                        # 실제 필드명은 file_bss_info_sno입니다
                        doc_id = ref.get('file_bss_info_sno') or ref.get('document_id')
                    else:
                        # 객체인 경우
                        try:
                            doc_id = getattr(ref, 'file_bss_info_sno', None) or getattr(ref, 'document_id', None)
                        except Exception:
                            doc_id = None
                    # int로 정규화 (문자열 숫자 허용)
                    if doc_id is not None:
                        try:
                            normalized = int(doc_id)
                        except Exception:
                            # 'doc_123' 같은 케이스 대응
                            try:
                                import re as _re
                                m = _re.search(r"(\d+)", str(doc_id))
                                normalized = int(m.group(1)) if m else None
                            except Exception:
                                normalized = None
                        if normalized is not None and normalized not in seen_ids:
                            seen_ids.add(normalized)
                            referenced_doc_ids.append(normalized)

            # 선택된 문서 ID 추출 (selected_documents 포함하도록 개선)
            selected_doc_ids: List[int] = []
            try:
                if 'normalized_docs' in locals() and normalized_docs:
                    for sd in normalized_docs:
                        raw_id = getattr(sd, 'id', None)
                        if raw_id is None and isinstance(sd, dict):
                            raw_id = sd.get('id') or sd.get('fileId')
                        if raw_id is not None:
                            try:
                                normalized = int(raw_id)
                            except Exception:
                                import re as _re
                                m = _re.search(r"(\d+)", str(raw_id))
                                normalized = int(m.group(1)) if m else None
                            if normalized is not None and normalized not in selected_doc_ids:
                                selected_doc_ids.append(normalized)
            except Exception as sel_err:
                logger.warning(f"선택된 문서 ID 추출 중 오류: {sel_err}")

            # 최종 저장용 문서 ID: references ∪ selected_documents (중복 제거)
            union_ids_set = set(referenced_doc_ids) | set(selected_doc_ids)
            union_doc_ids: List[int] = sorted(list(union_ids_set))

            # 정합성 체크 로그: references 길이 vs selected vs union vs used_chunks
            try:
                refs_len = len(references) if references else 0
                used_chunks_count = None
                if isinstance(context_info, dict):
                    used_chunks_count = context_info.get('used_chunks')
                logger.info(
                    f"📊 참고자료 정합성: references={refs_len}, selected={len(selected_doc_ids)}, union={len(union_doc_ids)}, used_chunks={used_chunks_count}"
                )
            except Exception:
                pass

            logger.info(f"📚 참고자료 저장 (references ∪ selected): {len(union_doc_ids)}개 문서 ID")
            
            # 🆕 청크 상세 정보 구조화 (문서명, 페이지, 내용 포함)
            detailed_chunks = []
            if references:
                for idx, ref in enumerate(references):
                    chunk_info = {
                        'index': idx + 1,
                        'file_id': ref.get('file_bss_info_sno'),
                        'file_name': ref.get('file_name', ''),
                        'chunk_index': ref.get('chunk_index', 0),
                        'page_number': ref.get('page_number'),
                        'content_preview': ref.get('content', '')[:200] if ref.get('content') else '',  # 200자 미리보기
                        'similarity_score': ref.get('similarity_score', 0.0),
                        'search_type': ref.get('search_type', 'unknown'),
                        'section_title': ref.get('section_title', ''),
                    }
                    detailed_chunks.append(chunk_info)
            
            # search_results에 청크 상세 정보 추가
            enhanced_search_results = {
                **(context_info if context_info else {}),
                'detailed_chunks': detailed_chunks,  # 🆕 청크 상세 정보
                'chunks_count': len(detailed_chunks),
                'documents_count': len(union_doc_ids)
            }
            if attachment_metadata:
                enhanced_search_results['attachments'] = attachment_metadata
            if voice_asset_id:
                enhanced_search_results['voice_asset_id'] = voice_asset_id
            
            logger.info(f"📝 청크 상세 정보 저장: {len(detailed_chunks)}개 청크, {len(union_doc_ids)}개 문서")
            
            saved_message = await chat_manager.add_message(
                session_id=session_id,
                content=final_to_store,  # 정리된 답변 저장 (PPT 의도 시 sanitize 적용)
                message_type=MessageType.ASSISTANT,
                user_emp_no=user_emp_no,
                user_name=str("AI Assistant"),
                model_used=provider or settings.get_current_llm_provider(),
                search_context=enhanced_search_results,  # 청크 정보 포함
                referenced_documents=union_doc_ids if union_doc_ids else None
            )
            
            # 🆕 PostgreSQL tb_chat_sessions 테이블에도 세션 저장/업데이트
            try:
                from sqlalchemy.ext.asyncio import AsyncSession
                from app.core.database import get_db
                
                # DB 세션 생성
                db_gen = get_db()
                db: AsyncSession = await db_gen.__anext__()
                
                try:
                    # 참고자료와 검색 결과 포함하여 저장
                    await save_chat_session(
                        db=db,
                        session_id=session_id,
                        user_emp_no=user_emp_no,
                        message=message,
                        response=final_to_store,
                        referenced_documents=union_doc_ids if union_doc_ids else None,
                        search_results=enhanced_search_results,  # 청크 상세 정보 포함
                        conversation_context=selected_docs_context if selected_docs_context else None  # 선택 문서 보존
                    )
                    logger.info(f"✅ PostgreSQL 세션 및 메시지 저장 완료: {session_id} (청크 {len(detailed_chunks)}개)")
                finally:
                    # DB 세션 정리
                    try:
                        await db_gen.aclose()
                    except:
                        pass
                        
            except Exception as db_save_error:
                logger.error(f"❌ PostgreSQL 세션 저장 실패 (Redis는 정상): {db_save_error}")
                import traceback
                logger.error(f"❌ 세션 저장 실패 상세:\n{traceback.format_exc()}")
                
        except Exception as e:
            logger.warning(f"AI 응답 저장 실패: {e}")
        
        # 완료 이벤트 (message_id 포함)
        complete_event = {
            'type': 'complete',
            'session_id': session_id,
            'message_id': saved_message.message_id if saved_message else None,
            'assistant_message_id': saved_message.message_id if saved_message else None,
            'references': clean_references_for_json(references),
             'attachments': attachment_metadata,
             'voice_asset_id': voice_asset_id,
            'context_info': clean_stats_for_json(context_info),
            'rag_stats': clean_stats_for_json({**rag_stats, "provider": settings.get_current_llm_provider()})
        }
        yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"
        try:
            state_payload = build_conversation_state(final_to_store or collected_response, context_info, references)
            yield f"data: {json.dumps({'type': 'conversation_state', 'state': state_payload}, ensure_ascii=False)}\n\n"
        except Exception as state_err:
            logger.warning(f"대화 상태 생성 실패: {state_err}")

        # 완료/종료 이벤트 (done + DONE 마커)
        done_event = {"type": "done", "session_id": session_id, "length": len(collected_response)}
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        logger.info("✅ 채팅 스트림 완료")
    except Exception as e:
        logger.error(f"❌ 스트리밍 응답 생성 실패: {e}")
        import traceback
        logger.error(f"❌ 상세 오류:\n{traceback.format_exc()}")
        error_event = {"type": "error", "message": str(e)}
        try:
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception:
            pass

# ===== Multi-Agent helper endpoints =====

@router.get("/chat/multi-agent/capabilities")
async def get_multi_agent_capabilities(current_user: User = Depends(get_current_user)):
    """프론트엔드에서 사용하는 멀티 에이전트 역량 목록 제공"""
    try:
        caps = integrated_multi_agent_service.enhanced_tool_registry.get_agent_capabilities()
        # 프론트엔드는 agent_capabilities 키를 기대함
        return {"success": True, "agent_capabilities": caps}
    except Exception as e:
        logger.error(f"멀티 에이전트 capabilities 조회 실패: {e}")
        return {"success": False, "agent_capabilities": {}, "error": str(e)}
