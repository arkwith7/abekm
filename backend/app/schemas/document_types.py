"""
문서 유형 정의 및 처리 옵션 스키마

📌 문서 유형 (Document Type)
- 문서의 구조와 처리 방식을 결정하는 파이프라인 선택 기준
- 실제 구현된 처리 파이프라인만 정의 (2025-10-27 기준)
- common_codes.csv의 DOCUMENT_TYPE 그룹과 동기화
"""
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class DocumentType(str, Enum):
    """
    문서 유형 정의 (처리 파이프라인 기준)
    
    ✅ 구현된 파이프라인:
    - GENERAL: 일반 문서 (기본 파이프라인)
    - ACADEMIC_PAPER: 학술 논문 (Figure/Reference 추출)
    
    🔜 향후 구현 예정:
    - PATENT: 특허 문서 (서지정보 추출 - DB 연동 필요)
    """
    GENERAL = "general"
    ACADEMIC_PAPER = "academic_paper"
    PATENT = "patent"  # 향후 구현
    UNSTRUCTURED_TEXT = "unstructured_text"
    
    @property
    def display_name(self) -> str:
        """화면 표시명"""
        names = {
            "general": "일반 문서",
            "academic_paper": "학술 논문",
            "patent": "특허 문서",
            "unstructured_text": "비구조화 텍스트",
        }
        return names.get(self.value, self.value)
    
    @property
    def description(self) -> str:
        """설명"""
        descriptions = {
            "general": "기술보고서, 업무문서, 프레젠테이션 등 일반 문서",
            "academic_paper": "Journal paper, Conference paper, Thesis (Figure/Reference 추출)",
            "patent": "특허 출원서, 등록 특허 (서지정보 추출 - 향후 구현)",
            "unstructured_text": "기사/블로그/게시글/광고 카피 등 섹션 구조가 약한 텍스트 (Character/Stream 기반 청킹)",
        }
        return descriptions.get(self.value, "")
    
    @property
    def icon(self) -> str:
        """아이콘"""
        icons = {
            "general": "📄",
            "academic_paper": "📚",
            "patent": "📜",
            "unstructured_text": "📰",
        }
        return icons.get(self.value, "📄")
    
    @property
    def supported_formats(self) -> list[str]:
        """지원 파일 형식"""
        formats = {
            "general": ["pdf", "docx", "pptx", "xlsx", "txt", "hwp"],
            "academic_paper": ["pdf", "docx"],
            "patent": ["pdf", "docx", "xml"],
            "unstructured_text": ["txt", "pdf", "docx", "md", "html"],
        }
        return formats.get(self.value, ["pdf", "docx"])

class AcademicPaperOptions(BaseModel):
    """학술 논문 처리 옵션"""
    extract_figures: bool = Field(True, description="Figure/Table 캡션 추출")
    parse_references: bool = Field(True, description="References 섹션 파싱")
    extract_equations: bool = Field(False, description="수식(LaTeX) 추출")
    priority_sections: list[str] = Field(
        default=["abstract", "conclusion"],
        description="우선 처리 섹션"
    )
    figure_caption_required: bool = Field(True, description="캡션이 있는 Figure만 추출")

class PatentOptions(BaseModel):
    """
    특허 문서 처리 옵션
    
    ⚠️ 향후 구현 예정 (특허 서지정보 DB 연동 필요)
    """
    extract_claims: bool = Field(True, description="Claims 섹션 추출")
    parse_citations: bool = Field(True, description="인용 특허 파싱")
    technical_field_extraction: bool = Field(True, description="기술 분야 추출")
    priority_claims: bool = Field(True, description="Claims 우선 처리")

class DocumentTypeInfo(BaseModel):
    """문서 유형 정보 (API 응답용)"""
    id: str
    name: str
    description: str
    icon: str
    supported_formats: list[str]
    default_options: Dict[str, Any] = {}

class ProcessingOptionsFactory:
    """처리 옵션 팩토리"""
    
    @staticmethod
    def get_default_options(document_type: DocumentType) -> Dict[str, Any]:
        """
        문서 유형별 기본 처리 옵션
        
        ✅ 구현된 파이프라인:
        - GENERAL: 기본 옵션 없음
        - ACADEMIC_PAPER: Figure/Reference 추출 옵션
        
        🔜 향후 구현:
        - PATENT: Claims/서지정보 추출 옵션 (DB 연동 필요)
        """
        if document_type == DocumentType.ACADEMIC_PAPER:
            return AcademicPaperOptions().dict()
        elif document_type == DocumentType.PATENT:
            return PatentOptions().dict()
        else:
            return {}
    
    @staticmethod
    def validate_options(
        document_type: DocumentType, 
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """처리 옵션 검증 및 병합"""
        default_options = ProcessingOptionsFactory.get_default_options(document_type)
        
        # 기본값에 사용자 옵션 병합
        merged_options = {**default_options, **options}
        
        # 유형별 검증
        if document_type == DocumentType.ACADEMIC_PAPER:
            validated = AcademicPaperOptions(**merged_options)
            return validated.dict()
        elif document_type == DocumentType.PATENT:
            validated = PatentOptions(**merged_options)
            return validated.dict()
        else:
            return merged_options

def get_all_document_types() -> list[DocumentTypeInfo]:
    """모든 문서 유형 정보 반환 (API용)"""
    return [
        DocumentTypeInfo(
            id=doc_type.value,
            name=doc_type.display_name,
            description=doc_type.description,
            icon=doc_type.icon,
            supported_formats=doc_type.supported_formats,
            default_options=ProcessingOptionsFactory.get_default_options(doc_type)
        )
        for doc_type in DocumentType
    ]

def get_pipeline_name(document_type: DocumentType) -> str:
    """
    문서 유형별 파이프라인 이름
    
    ✅ 실제 구현된 파이프라인:
    - GeneralPipeline: 일반 문서 처리
    - AcademicPaperPipeline: 학술 논문 처리
    
    🔜 향후 구현 예정:
    - PatentPipeline: 특허 문서 처리 (서지정보 DB 연동 후)
    """
    names = {
        DocumentType.GENERAL: "GeneralPipeline",
        DocumentType.ACADEMIC_PAPER: "AcademicPaperPipeline",
        DocumentType.PATENT: "PatentPipeline",  # 향후 구현
        DocumentType.UNSTRUCTURED_TEXT: "GeneralPipeline",
    }
    return names.get(document_type, "GeneralPipeline")

# ===== 업로드 API용 스키마 =====

class DocumentUploadRequest(BaseModel):
    """문서 업로드 요청 (Form 데이터)"""
    container_id: str = Field(..., description="컨테이너 ID")
    document_type: str = Field("general", description="문서 유형")
    processing_options: Optional[str] = Field(None, description="처리 옵션 (JSON string)")
    use_multimodal: bool = Field(True, description="멀티모달 파이프라인 사용 여부")

class DocumentTypeSelectionResponse(BaseModel):
    """문서 유형 선택 API 응답"""
    success: bool
    document_types: list[DocumentTypeInfo]
    total: int
