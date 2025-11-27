"""
Patent Intelligence API - 특허 분석 에이전트 엔드포인트

엔터프라이즈 경쟁 인텔리전스를 위한 특허 검색 및 분석 API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import uuid
import json
import asyncio

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.agents.patent import patent_analysis_agent_tool
from loguru import logger


router = APIRouter(prefix="/intelligence/patent", tags=["patent-intelligence"])


# =============================================================================
# Request/Response Models
# =============================================================================

class PatentAnalysisRequest(BaseModel):
    """특허 분석 요청"""
    query: str = Field(..., min_length=1, description="검색 쿼리 또는 분석 요청")
    analysis_type: str = Field(
        default="search",
        description="분석 유형: search, comparison, trend, portfolio, gap"
    )
    our_company: Optional[str] = Field(None, description="우리 회사명 (비교 분석 시)")
    competitor: Optional[str] = Field(None, description="경쟁사명 (비교 분석 시)")
    jurisdiction: str = Field(default="KR", description="관할권: KR, US, EP, ALL")
    date_from: Optional[str] = Field(None, description="출원일 시작 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="출원일 종료 (YYYY-MM-DD)")
    ipc_codes: Optional[List[str]] = Field(None, description="IPC 분류 코드 필터")
    max_results: int = Field(default=50, ge=1, le=200, description="최대 결과 수")
    include_visualization: bool = Field(default=True, description="시각화 데이터 포함")
    time_range_years: int = Field(default=5, ge=1, le=20, description="트렌드 분석 기간 (년)")


class VisualizationData(BaseModel):
    """시각화 데이터"""
    chart_type: str = Field(description="차트 유형: bar, line, pie, radar, timeline")
    title: str = Field(description="차트 제목")
    data: Dict[str, Any] = Field(description="차트 데이터")
    options: Dict[str, Any] = Field(default_factory=dict, description="차트 옵션")


class PatentSummary(BaseModel):
    """특허 요약"""
    patent_number: str
    title: str
    applicant: str
    application_date: Optional[str]
    status: str
    jurisdiction: str
    relevance_score: float
    url: Optional[str]


class PatentAnalysisResponse(BaseModel):
    """특허 분석 응답"""
    success: bool = Field(description="성공 여부")
    analysis_type: str = Field(description="수행된 분석 유형")
    summary: str = Field(description="분석 결과 요약 (자연어)")
    patents: List[PatentSummary] = Field(default_factory=list, description="검색된 특허 목록")
    total_patents: int = Field(default=0, description="총 특허 수")
    analysis_result: Optional[Dict[str, Any]] = Field(None, description="상세 분석 결과")
    visualizations: List[VisualizationData] = Field(default_factory=list, description="시각화 데이터")
    insights: List[str] = Field(default_factory=list, description="핵심 인사이트")
    recommendations: List[str] = Field(default_factory=list, description="권장 사항")
    trace_id: str = Field(description="추적 ID")
    elapsed_ms: float = Field(description="처리 시간 (ms)")
    errors: List[str] = Field(default_factory=list, description="오류 목록")


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/analyze", response_model=PatentAnalysisResponse)
async def analyze_patents(
    request: PatentAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특허 분석 실행
    
    지원 분석 유형:
    - search: 특허 검색
    - comparison: 경쟁사 특허 비교
    - trend: 시계열 트렌드 분석
    - portfolio: 포트폴리오 분석
    - gap: 기술 공백 분석
    """
    try:
        user_emp_no = str(current_user.emp_no)
        logger.info(f"🔬 [PatentAPI] 사용자: {user_emp_no}, 분석: {request.analysis_type}, 쿼리: '{request.query[:50]}...'")
        
        # 에이전트 실행
        result = await patent_analysis_agent_tool._arun(
            query=request.query,
            analysis_type=request.analysis_type,
            our_company=request.our_company,
            competitor=request.competitor,
            jurisdiction=request.jurisdiction,
            date_from=request.date_from,
            date_to=request.date_to,
            ipc_codes=request.ipc_codes,
            max_results=request.max_results,
            include_visualization=request.include_visualization,
            time_range_years=request.time_range_years
        )
        
        # 특허 목록 변환
        patents_summary = []
        for p in result.get("patents", []):
            patents_summary.append(PatentSummary(
                patent_number=p.get("patent_number", ""),
                title=p.get("title", ""),
                applicant=p.get("applicant", ""),
                application_date=p.get("application_date"),
                status=p.get("status", "unknown"),
                jurisdiction=p.get("jurisdiction", "KR"),
                relevance_score=p.get("relevance_score", 0.0),
                url=p.get("url")
            ))
        
        # 시각화 데이터 변환
        visualizations = []
        for v in result.get("visualizations", []):
            visualizations.append(VisualizationData(
                chart_type=v.get("chart_type", "bar"),
                title=v.get("title", ""),
                data=v.get("data", {}),
                options=v.get("options", {})
            ))
        
        return PatentAnalysisResponse(
            success=result.get("success", False),
            analysis_type=result.get("analysis_type", request.analysis_type),
            summary=result.get("summary", ""),
            patents=patents_summary,
            total_patents=result.get("total_patents", len(patents_summary)),
            analysis_result=result.get("analysis_result"),
            visualizations=visualizations,
            insights=result.get("insights", []),
            recommendations=result.get("recommendations", []),
            trace_id=result.get("trace_id", str(uuid.uuid4())),
            elapsed_ms=result.get("elapsed_ms", 0),
            errors=result.get("errors", [])
        )
        
    except Exception as e:
        logger.error(f"❌ [PatentAPI] 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"특허 분석 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/analyze/stream")
async def analyze_patents_stream(
    request: PatentAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    특허 분석 실행 (SSE 스트리밍)
    
    실시간으로 분석 진행 상황을 스트리밍합니다.
    """
    async def generate():
        trace_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            user_emp_no = str(current_user.emp_no)
            logger.info(f"🔬 [PatentAPI/Stream] 사용자: {user_emp_no}, 분석: {request.analysis_type}")
            
            # 시작 이벤트
            yield f"data: {json.dumps({'event': 'start', 'trace_id': trace_id, 'analysis_type': request.analysis_type})}\n\n"
            
            # 검색 단계
            yield f"data: {json.dumps({'event': 'step', 'step': 'searching', 'message': '특허 데이터베이스 검색 중...'})}\n\n"
            await asyncio.sleep(0.1)
            
            # 분석 실행
            yield f"data: {json.dumps({'event': 'step', 'step': 'analyzing', 'message': f'{request.analysis_type} 분석 수행 중...'})}\n\n"
            
            result = await patent_analysis_agent_tool._arun(
                query=request.query,
                analysis_type=request.analysis_type,
                our_company=request.our_company,
                competitor=request.competitor,
                jurisdiction=request.jurisdiction,
                date_from=request.date_from,
                date_to=request.date_to,
                ipc_codes=request.ipc_codes,
                max_results=request.max_results,
                include_visualization=request.include_visualization,
                time_range_years=request.time_range_years
            )
            
            # 시각화 생성 단계
            if request.include_visualization:
                yield f"data: {json.dumps({'event': 'step', 'step': 'visualizing', 'message': '시각화 데이터 생성 중...'})}\n\n"
                await asyncio.sleep(0.1)
            
            elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 완료 이벤트
            yield f"data: {json.dumps({'event': 'complete', 'result': result, 'elapsed_ms': elapsed_ms})}\n\n"
            
        except Exception as e:
            logger.error(f"❌ [PatentAPI/Stream] 오류: {e}")
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/search")
async def search_patents(
    query: str,
    applicant: Optional[str] = None,
    jurisdiction: str = "KR",
    max_results: int = 20,
    current_user: User = Depends(get_current_user)
):
    """
    간단한 특허 검색 API
    
    빠른 검색을 위한 단순화된 엔드포인트
    """
    try:
        result = await patent_analysis_agent_tool._arun(
            query=query,
            analysis_type="search",
            our_company=applicant,
            jurisdiction=jurisdiction,
            max_results=max_results,
            include_visualization=False
        )
        
        return {
            "success": result.get("success", False),
            "patents": result.get("patents", []),
            "total": result.get("total_patents", 0),
            "summary": result.get("summary", "")
        }
        
    except Exception as e:
        logger.error(f"❌ [PatentAPI/Search] 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/detail/{patent_id}")
async def get_patent_detail(
    patent_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    특허 상세 정보 조회
    
    SerpAPI Google Patents Details API를 통해 상세 정보를 가져옵니다.
    """
    try:
        from app.tools.retrieval.patent_search_tool import PatentSearchTool
        
        tool = PatentSearchTool()
        detail = await tool.get_patent_details(patent_id)
        
        if not detail:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"특허를 찾을 수 없습니다: {patent_id}"
            )
        
        return {
            "success": True,
            "patent": detail.model_dump()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [PatentAPI/Detail] 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
