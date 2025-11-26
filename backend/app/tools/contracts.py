"""
Tool and Agent Standard Contracts
표준 인터페이스 정의 - 모든 도구와 에이전트가 따라야 할 계약
"""
from typing import Protocol, TypedDict, Any, List, Optional, Dict, runtime_checkable
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


# =============================================================================
# Tool Metrics & Result Types
# =============================================================================

class ToolMetrics(BaseModel):
    """도구 실행 메트릭"""
    latency_ms: float = Field(description="실행 소요 시간 (밀리초)")
    provider: str = Field(default="internal", description="제공자 (internal/bedrock/azure/openai)")
    cache_hit: bool = Field(default=False, description="캐시 히트 여부")
    retries: int = Field(default=0, description="재시도 횟수")
    cost_estimate: Optional[float] = Field(default=None, description="예상 비용 ($)")
    tokens_used: Optional[int] = Field(default=None, description="사용된 토큰 수")
    items_returned: Optional[int] = Field(default=None, description="반환된 항목 수")
    trace_id: Optional[str] = Field(default=None, description="추적 ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "latency_ms": 234.5,
                "provider": "bedrock",
                "cache_hit": False,
                "retries": 0,
                "cost_estimate": 0.002,
                "tokens_used": 1500
            }
        }


class ToolResult(BaseModel):
    """도구 실행 결과 기본 타입"""
    success: bool = Field(description="실행 성공 여부")
    data: Any = Field(description="실행 결과 데이터")
    metrics: ToolMetrics = Field(description="실행 메트릭")
    errors: List[str] = Field(default_factory=list, description="오류 메시지 목록")
    trace_id: str = Field(description="추적 ID (OpenTelemetry)")
    tool_name: str = Field(description="도구 이름")
    tool_version: str = Field(default="1.0.0", description="도구 버전")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="실행 시각")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"chunks": [{"id": "1", "content": "..."}]},
                "metrics": {"latency_ms": 234.5, "provider": "internal"},
                "errors": [],
                "trace_id": "abc-123-def",
                "tool_name": "vector_search",
                "tool_version": "1.0.0",
                "timestamp": "2025-11-11T10:30:00Z"
            }
        }


# =============================================================================
# Search Tool Specific Types
# =============================================================================

class SearchChunk(BaseModel):
    """검색 결과 청크"""
    chunk_id: str = Field(description="청크 고유 ID")
    content: str = Field(description="청크 내용")
    score: float = Field(description="점수 (유사도/관련도, 0.0~1.0)")
    file_id: Optional[str] = Field(default=None, description="파일 ID")
    match_type: Optional[str] = Field(default=None, description="매칭 타입 (vector/keyword/fulltext/hybrid)")
    container_id: Optional[str] = Field(default=None, description="컨테이너 ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="추가 메타데이터")
    
    # 호환성을 위한 alias
    @property
    def similarity_score(self) -> float:
        """Backward compatibility"""
        return self.score
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "chunk_123",
                "file_id": "file_456",
                "content": "인슐린 펌프는 지속적으로 인슐린을 공급하는 장치입니다.",
                "similarity_score": 0.87,
                "match_type": "vector",
                "container_id": "container_789",
                "metadata": {"page": 5, "section": "본론"}
            }
        }


class SearchToolResult(ToolResult):
    """검색 도구 전용 결과"""
    data: List[SearchChunk] = Field(description="검색된 청크 목록")
    total_found: int = Field(description="총 발견된 개수 (필터 전)")
    filtered_count: int = Field(description="필터링 후 개수")
    search_params: Dict[str, Any] = Field(default_factory=dict, description="검색 파라미터")


class RankedResult(ToolResult):
    """재랭킹 결과"""
    data: List[SearchChunk] = Field(description="재랭킹된 청크 목록")
    original_scores: List[float] = Field(description="원본 점수 목록")
    rerank_scores: List[float] = Field(description="재랭킹 점수 목록")
    score_improvement: float = Field(description="평균 점수 향상도")


class ContextResult(ToolResult):
    """컨텍스트 빌드 결과"""
    data: str = Field(description="구성된 컨텍스트 텍스트")
    used_chunks: List[SearchChunk] = Field(description="사용된 청크 목록")
    total_tokens: int = Field(description="총 토큰 수")
    chunks_included: int = Field(description="포함된 청크 수")
    chunks_truncated: int = Field(description="잘린 청크 수")


# =============================================================================
# Tool Protocol
# =============================================================================

@runtime_checkable
class ToolProtocol(Protocol):
    """모든 도구가 구현해야 할 프로토콜"""
    name: str
    description: str
    version: str
    
    async def _arun(self, **kwargs) -> ToolResult:
        """비동기 실행 (권장)"""
        ...
    
    def _run(self, **kwargs) -> ToolResult:
        """동기 실행 (폴백)"""
        ...
    
    def validate_input(self, **kwargs) -> bool:
        """입력 검증"""
        ...


# =============================================================================
# Agent Types
# =============================================================================

class AgentIntent(str, Enum):
    """에이전트 의도 분류"""
    FACTUAL_QA = "factual_qa"              # 사실 확인 질문
    KEYWORD_SEARCH = "keyword_search"      # 키워드 검색
    EXPLORATORY = "exploratory"            # 탐색적 질문
    DOCUMENT_ANALYSIS = "document_analysis"  # 문서 분석
    PPT_GENERATION = "ppt_generation"      # PPT 생성
    COMPARISON = "comparison"              # 비교 분석
    SUMMARIZATION = "summarization"        # 요약
    WEB_SEARCH = "web_search"              # 🆕 인터넷 검색


class AgentConstraints(BaseModel):
    """에이전트 제약 조건"""
    max_tokens: int = Field(default=4000, description="최대 토큰 수")
    max_chunks: int = Field(default=10, description="최대 청크 수")
    similarity_threshold: float = Field(default=0.25, description="유사도 임계값")
    container_ids: Optional[List[str]] = Field(default=None, description="검색 대상 컨테이너")
    document_ids: Optional[List[str]] = Field(default=None, description="검색 대상 문서")
    allow_web_fallback: bool = Field(default=False, description="웹 검색 폴백 허용")
    time_limit_ms: Optional[int] = Field(default=None, description="시간 제한 (밀리초)")
    cost_limit: Optional[float] = Field(default=None, description="비용 제한 ($)")


class AgentStep(BaseModel):
    """에이전트 실행 단계"""
    step_number: int = Field(description="단계 번호")
    tool_name: str = Field(description="사용된 도구 이름")
    tool_input: Dict[str, Any] = Field(description="도구 입력")
    tool_output: ToolResult = Field(description="도구 출력")
    reasoning: str = Field(description="이 도구를 선택한 이유")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AgentResult(BaseModel):
    """에이전트 실행 결과"""
    answer: str = Field(description="최종 답변")
    references: List[SearchChunk] = Field(description="참고 문헌")
    steps: List[AgentStep] = Field(description="실행 단계 로그")
    metrics: Dict[str, Any] = Field(description="종합 메트릭")
    intent: AgentIntent = Field(description="감지된 의도")
    strategy_used: List[str] = Field(description="사용된 전략 (도구 목록)")
    success: bool = Field(description="성공 여부")
    errors: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "인슐린 펌프는 지속적으로 인슐린을 공급하는 장치입니다...",
                "references": [{"chunk_id": "1", "content": "..."}],
                "steps": [{"step_number": 1, "tool_name": "vector_search", "reasoning": "..."}],
                "metrics": {"total_latency_ms": 1234, "total_cost": 0.05},
                "intent": "factual_qa",
                "strategy_used": ["vector_search", "rerank", "context_builder"],
                "success": True,
                "errors": []
            }
        }


# =============================================================================
# Agent Protocol
# =============================================================================

@runtime_checkable
class AgentProtocol(Protocol):
    """모든 에이전트가 구현해야 할 프로토콜"""
    name: str
    description: str
    version: str
    tools: Dict[str, Any]  # tool_name -> tool_instance
    
    async def execute(
        self, 
        query: str, 
        constraints: AgentConstraints,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """에이전트 실행"""
        ...
    
    def classify_intent(self, query: str) -> AgentIntent:
        """의도 분류"""
        ...
    
    def select_strategy(
        self, 
        intent: AgentIntent, 
        constraints: AgentConstraints
    ) -> List[str]:
        """전략 선택 (도구 목록 반환)"""
        ...


# =============================================================================
# Evaluation Types
# =============================================================================

class EvaluationMetric(str, Enum):
    """평가 메트릭 타입"""
    RECALL_AT_K = "recall@k"
    NDCG_AT_K = "ndcg@k"
    MRR = "mrr"
    PRECISION_AT_K = "precision@k"
    CONTEXT_UTILIZATION = "context_utilization"
    ANSWER_FAITHFULNESS = "answer_faithfulness"


class GoldenSample(BaseModel):
    """평가용 골든 샘플"""
    query: str = Field(description="질의")
    intent: AgentIntent = Field(description="의도")
    expected_docs: List[str] = Field(description="정답 문서 ID 목록")
    expected_chunks: Optional[List[str]] = Field(default=None, description="정답 청크 ID 목록")
    min_similarity: float = Field(default=0.5, description="최소 기대 유사도")
    relevance_judgments: Dict[str, int] = Field(
        default_factory=dict, 
        description="문서 ID -> 관련도 (0~3)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """평가 결과"""
    metric: EvaluationMetric
    score: float
    k: Optional[int] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
