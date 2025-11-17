from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class SelectedDocument(BaseModel):
    """선택된 문서 정보"""
    id: str  # 문서 ID (file_id 또는 document_id)
    fileName: str  # 파일명
    fileType: str  # 파일 타입/확장자
    filePath: Optional[str] = None  # 파일 경로
    metadata: Optional[dict] = {}  # 추가 메타데이터
    
    class Config:
        # 추가 필드 허용 (하위 호환성)
        extra = "allow"

class FileInfo(BaseModel):
    file_logic_name: str
    file_path: str
    file_view_link: Optional[str] = None
    download_sas_link: Optional[str] = None

class ChatRequest(BaseModel):
    question: str
    agent_type: Optional[str] = 'general'  # AI Agent 타입
    selected_documents: Optional[List[SelectedDocument]] = []  # 선택된 문서들
    loginEmpNo: Optional[str] = None
    sessionId: Optional[str] = None
    filePhysicalName: Optional[str] = None
    # 스트리밍 관련 파라미터
    use_streaming: Optional[bool] = True
    max_tokens: Optional[int] = 2000
    temperature: Optional[float] = 0.7

class ChatResponse(BaseModel):
    status: str
    pretty_answer: str
    file_info: Optional[List[FileInfo]] = []
    agent_type: Optional[str] = None
    selected_documents_count: Optional[int] = 0

class AgentSystemPrompt(BaseModel):
    """AI Agent별 시스템 프롬프트 설정"""
    agent_type: str
    name: str
    system_prompt: str
    description: str
    required_documents: bool = False
    output_format: str = 'text'

# AI Agent별 시스템 프롬프트 정의
AGENT_SYSTEM_PROMPTS = {
    'general': AgentSystemPrompt(
        agent_type='general',
        name='일반 AI',
        system_prompt='당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 정확하고 친절하게 답변해주세요.',
        description='일반적인 질문 답변',
        required_documents=False,
        output_format='text'
    ),
    'summarizer': AgentSystemPrompt(
        agent_type='summarizer',
        name='문서 요약',
        system_prompt='당신은 문서 요약 전문가입니다. 제공된 문서의 핵심 내용을 간결하고 명확하게 요약해주세요. 주요 포인트를 불릿 포인트로 정리하고, 전체적인 흐름을 파악할 수 있도록 구조화해주세요.',
        description='문서 내용 요약 및 분석',
        required_documents=True,
        output_format='markdown'
    ),
    'keyword-extractor': AgentSystemPrompt(
        agent_type='keyword-extractor',
        name='키워드 추출',
        system_prompt='당신은 키워드 추출 전문가입니다. 제공된 문서에서 중요한 키워드와 핵심 개념을 추출해주세요. 빈도수가 높고 의미가 있는 키워드들을 카테고리별로 분류하여 제시해주세요.',
        description='핵심 키워드 및 개념 추출',
        required_documents=True,
        output_format='json'
    ),
    'presentation': AgentSystemPrompt(
        agent_type='presentation',
        name='PPT 생성',
        system_prompt='당신은 프레젠테이션 제작 전문가입니다. 제공된 내용을 바탕으로 효과적인 PowerPoint 슬라이드 구조를 제안해주세요. 제목, 주요 내용, 시각적 요소 등을 포함하여 슬라이드별로 구성해주세요.',
        description='PowerPoint 프레젠테이션 생성',
        required_documents=False,
        output_format='markdown'
    ),
    'template': AgentSystemPrompt(
        agent_type='template',
        name='템플릿 기반 문서',
        system_prompt='당신은 템플릿 기반 문서 작성 전문가입니다. 사용자의 요구사항에 맞는 문서 템플릿을 제공하고, 해당 템플릿에 맞게 내용을 구성해주세요.',
        description='템플릿 기반 문서 생성',
        required_documents=False,
        output_format='markdown'
    ),
    'knowledge-graph': AgentSystemPrompt(
        agent_type='knowledge-graph',
        name='지식 그래프',
        system_prompt='당신은 지식 그래프 분석 전문가입니다. 제공된 정보들 간의 관계와 연결점을 파악하여 지식 그래프 형태로 구조화해주세요. 개념 간의 관계를 명확히 표현해주세요.',
        description='지식 그래프 및 관계 분석',
        required_documents=True,
        output_format='json'
    ),
    'analyzer': AgentSystemPrompt(
        agent_type='analyzer',
        name='문서 분석',
        system_prompt='당신은 문서 분석 전문가입니다. 제공된 문서의 구조, 내용, 패턴을 심층 분석하고, 문서의 특징과 개선점을 제시해주세요.',
        description='문서 심층 분석',
        required_documents=True,
        output_format='markdown'
    ),
    'insight': AgentSystemPrompt(
        agent_type='insight',
        name='인사이트 도출',
        system_prompt='당신은 인사이트 도출 전문가입니다. 제공된 데이터나 문서에서 숨겨진 패턴과 의미있는 인사이트를 발견하고, 실행 가능한 제안사항을 제시해주세요.',
        description='데이터 인사이트 및 트렌드 분석',
        required_documents=True,
        output_format='markdown'
    ),
    'report-generator': AgentSystemPrompt(
        agent_type='report-generator',
        name='보고서 생성',
        system_prompt='당신은 보고서 작성 전문가입니다. 제공된 정보를 바탕으로 전문적이고 체계적인 보고서를 작성해주세요. 서론, 본론, 결론의 구조를 갖추고 객관적인 분석을 포함해주세요.',
        description='전문 보고서 작성',
        required_documents=True,
        output_format='markdown'
    ),
    'script-generator': AgentSystemPrompt(
        agent_type='script-generator',
        name='발표 스크립트',
        system_prompt='당신은 발표 스크립트 작성 전문가입니다. 제공된 내용을 바탕으로 청중의 관심을 끌고 이해하기 쉬운 발표 스크립트를 작성해주세요. 적절한 톤앤매너와 흐름을 고려해주세요.',
        description='발표 및 연설 스크립트 생성',
        required_documents=False,
        output_format='text'
    ),
    'key-points': AgentSystemPrompt(
        agent_type='key-points',
        name='핵심 포인트 추출',
        system_prompt='당신은 핵심 포인트 추출 전문가입니다. 제공된 문서에서 가장 중요한 핵심 포인트들을 추출하고, 우선순위에 따라 정리해주세요. 각 포인트의 중요도와 근거를 함께 제시해주세요.',
        description='핵심 포인트 및 요점 추출',
        required_documents=True,
        output_format='markdown'
    )
}

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 10
    threshold: Optional[float] = 0.7

class SearchResult(BaseModel):
    id: str
    content: str
    metadata: dict
    similarity_score: float

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_count: int

class DocumentCreate(BaseModel):
    title: str
    content: str
    file_path: str
    metadata: Optional[dict] = {}

class DocumentResponse(BaseModel):
    id: str
    title: str
    content: str
    file_path: str
    metadata: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
