"""
Patent Functional Tools
특허 분석을 위한 기능별 도구 모음 (Layer 2)

1. PatentDiscoveryTool: 특허 탐색 및 리스트 확보
2. PatentDetailTool: 특허 상세 분석 (청구항, 전문)
3. PatentLegalTool: 권리/행정 상태 분석
"""
from typing import List, Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from loguru import logger

try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain.tools import BaseTool

from app.clients.kipris import KiprisClient, KiprisPatentBasic, KiprisPatentDetail, KiprisLegalStatus

# =============================================================================
# 1. Patent Discovery Tool
# =============================================================================

class PatentDiscoveryInput(BaseModel):
    """특허 탐색 도구 입력"""
    query: str = Field(description="검색 키워드 (예: 'AI 반도체', '이차전지')")
    applicant: Optional[str] = Field(None, description="출원인 (회사명)")
    date_from: Optional[str] = Field(None, description="검색 시작일 (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="검색 종료일 (YYYY-MM-DD)")
    ipc_code: Optional[str] = Field(None, description="IPC 분류 코드 (예: 'G06N')")
    max_results: int = Field(default=30, description="최대 결과 수")

class PatentDiscoveryTool(BaseTool):
    """
    특허 탐색 도구 (Patent Discovery)
    
    목적: 광범위한 특허 탐색 및 리스트 확보
    특징: 무거운 데이터(전문, 청구항)는 제외하고 서지 정보 위주로 빠르게 검색
    """
    name: str = "patent_discovery"
    description: str = """특허 탐색 및 리스트 확보 도구.
키워드, 출원인, 날짜, IPC 코드를 조합하여 특허를 검색합니다.
결과는 특허 번호, 제목, 출원인, 날짜, 상태 등의 기본 정보를 포함합니다.
상세 내용(청구항 등)이나 법적 상태가 필요한 경우 PatentDetailTool이나 PatentLegalTool을 사용하세요.
"""
    args_schema: Type[BaseModel] = PatentDiscoveryInput
    
    def _run(self, **kwargs):
        raise NotImplementedError("Use _arun instead")

    async def _arun(
        self,
        query: str,
        applicant: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        ipc_code: Optional[str] = None,
        max_results: int = 30
    ) -> Dict[str, Any]:
        client = KiprisClient()
        try:
            # 1. 출원인 코드로 변환 시도 (정확도 향상)
            customer_no = None
            if applicant:
                customer_no = await client.search_applicant_code(applicant)
                if customer_no:
                    logger.info(f"🔍 [Discovery] 출원인 '{applicant}' -> 코드 '{customer_no}' 변환 성공")
            
            # 2. 검색 실행
            results, total_count = await client.search_patents(
                query=query,
                applicant=applicant,
                ipc_code=ipc_code,
                date_from=date_from,
                date_to=date_to,
                max_results=max_results,
                customer_no=customer_no
            )
            
            logger.info(f"✅ [Discovery] {len(results)}건 검색 완료 (총 {total_count}건)")
            return {
                "patents": [r.model_dump() for r in results],
                "total_count": total_count
            }
            
        except Exception as e:
            logger.error(f"❌ [Discovery] Error: {e}")
            return {"patents": [], "total_count": 0}
        finally:
            await client.close()

# =============================================================================
# 2. Patent Detail Tool
# =============================================================================

class PatentDetailInput(BaseModel):
    """특허 상세 도구 입력"""
    patent_number: str = Field(description="특허 출원번호 (예: '10-2023-1234567')")

class PatentDetailTool(BaseTool):
    """
    특허 상세 분석 도구 (Patent Detail)
    
    목적: 특정 특허의 기술적 내용 심층 분석
    특징: 청구항(Claims), 상세설명, 발명자 정보 등 상세 데이터를 로딩
    """
    name: str = "patent_detail"
    description: str = """특허 상세 정보 조회 도구.
특허 번호를 입력받아 청구항(Claims), 상세설명, 발명자, 우선권 정보 등을 조회합니다.
기술적인 내용을 깊이 있게 분석할 때 사용합니다.
"""
    args_schema: Type[BaseModel] = PatentDetailInput

    def _run(self, **kwargs):
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, patent_number: str) -> Dict[str, Any]:
        client = KiprisClient()
        try:
            # 상세 정보 조회 (청구항 포함)
            detail = await client.get_biblio_detail(patent_number)
            
            if not detail:
                return {"error": "Patent not found"}
                
            logger.info(f"✅ [Detail] {patent_number} 상세 정보 조회 완료")
            return detail.model_dump()
            
        except Exception as e:
            logger.error(f"❌ [Detail] Error: {e}")
            return {"error": str(e)}
        finally:
            await client.close()

# =============================================================================
# 3. Patent Legal Tool
# =============================================================================

class PatentLegalInput(BaseModel):
    """특허 권리 분석 도구 입력"""
    patent_number: str = Field(description="특허 출원번호")

class PatentLegalTool(BaseTool):
    """
    특허 권리/행정 분석 도구 (Patent Legal)
    
    목적: 특허의 법적 유효성 및 권리 상태 확인
    특징: 현재 권리 상태(등록/포기/소멸), 심사 이력 등을 확인
    """
    name: str = "patent_legal"
    description: str = """특허 법적 상태 조회 도구.
특허 번호를 입력받아 현재 권리 상태(등록, 거절, 소멸, 포기 등)와 심사 이력을 조회합니다.
특허의 유효성이나 권리 범위를 판단할 때 사용합니다.
"""
    args_schema: Type[BaseModel] = PatentLegalInput

    def _run(self, **kwargs):
        raise NotImplementedError("Use _arun instead")

    async def _arun(self, patent_number: str) -> Dict[str, Any]:
        client = KiprisClient()
        try:
            status = await client.get_legal_status(patent_number)
            
            if not status:
                # 상세 정보에서 상태만이라도 가져오기 시도
                detail = await client.get_biblio_detail(patent_number)
                if detail:
                    return {
                        "application_number": patent_number,
                        "current_status": detail.legal_status or "Unknown",
                        "note": "행정정보 API 실패로 서지정보의 상태를 반환함"
                    }
                return {"error": "Legal status not found"}
            
            logger.info(f"✅ [Legal] {patent_number} 법적 상태 조회 완료")
            return status.model_dump()
            
        except Exception as e:
            logger.error(f"❌ [Legal] Error: {e}")
            return {"error": str(e)}
        finally:
            await client.close()
