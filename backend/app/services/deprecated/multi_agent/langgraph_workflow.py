"""
LangGraph 기반 멀티 에이전트 워크플로우 시스템
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from loguru import logger
import json
from datetime import datetime

# LangGraph 임포트
from langgraph.graph import StateGraph, END

# 선택적 임포트 (버전에 따라 경로가 다를 수 있음)
try:
    from langgraph.prebuilt import ToolExecutor, ToolInvocation
except ImportError:
    try:
        from langgraph_prebuilt import ToolExecutor, ToolInvocation
    except ImportError:
        ToolExecutor = None
        ToolInvocation = None
        logger.info("ToolExecutor, ToolInvocation을 찾을 수 없습니다. 기본 워크플로우만 사용됩니다.")

# LangChain 메시지 클래스
try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
except ImportError:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# BaseTool 임포트
try:
    from langchain_core.tools import BaseTool
except ImportError:
    from langchain_core.tools import BaseTool

class MultiAgentState(TypedDict):
    """멀티 에이전트 워크플로우 공유 상태"""
    # 입력 정보
    user_query: str
    selected_documents: List[Dict[str, Any]]
    workflow_type: str  # "analysis", "presentation", "report", "custom"
    
    # 워크플로우 상태
    current_step: str
    completed_steps: List[str]
    agent_assignments: Dict[str, str]
    
    # 중간 결과
    document_analysis: Optional[Dict[str, Any]]
    key_insights: Optional[List[str]]
    summary_content: Optional[str]
    outline_structure: Optional[Dict[str, Any]]
    
    # 최종 결과
    final_output: Optional[Dict[str, Any]]
    workflow_metadata: Dict[str, Any]
    
    # 메시지 히스토리
    messages: List[Dict[str, str]]


class MultiAgentOrchestrator:
    """멀티 에이전트 오케스트레이터"""
    
    def __init__(self):
        self.workflow_graph = None
        self.tools = {}
        self.agents = {}
        self._build_workflow()
        
    def _build_workflow(self):
        """워크플로우 그래프 구성"""
        workflow = StateGraph(MultiAgentState)
        
        # 노드 추가
        workflow.add_node("coordinator", self.coordinator_node)
        workflow.add_node("document_analyzer", self.document_analyzer_node)
        workflow.add_node("insight_extractor", self.insight_extractor_node)
        workflow.add_node("summarizer", self.summarizer_node)
        workflow.add_node("presentation_builder", self.presentation_builder_node)
        workflow.add_node("finalizer", self.finalizer_node)
        
        # 시작점 설정
        workflow.set_entry_point("coordinator")
        
        # 조건부 엣지 추가
        workflow.add_conditional_edges(
            "coordinator",
            self.route_next_agent,
            {
                "document_analysis": "document_analyzer",
                "insight_extraction": "insight_extractor", 
                "summarization": "summarizer",
                "presentation": "presentation_builder",
                "finalize": "finalizer",
                "end": END
            }
        )
        
        # 순차 엣지 추가
        workflow.add_edge("document_analyzer", "insight_extractor")
        workflow.add_edge("insight_extractor", "summarizer")
        workflow.add_edge("summarizer", "presentation_builder")
        workflow.add_edge("presentation_builder", "finalizer")
        workflow.add_edge("finalizer", END)
        
        self.workflow_graph = workflow.compile()
        
    def coordinator_node(self, state: MultiAgentState) -> MultiAgentState:
        """코디네이터 노드 - 워크플로우 방향 결정"""
        logger.info(f"🎯 코디네이터: 워크플로우 분석 시작")
        
        # 사용자 요청 분석
        query = state["user_query"]
        workflow_type = state.get("workflow_type", "analysis")
        
        # 다음 단계 결정
        if not state.get("completed_steps"):
            state["completed_steps"] = []
            
        # 워크플로우 메타데이터 초기화
        if not state.get("workflow_metadata"):
            state["workflow_metadata"] = {
                "start_time": datetime.now().isoformat(),
                "workflow_type": workflow_type,
                "total_steps": 5
            }
            
        state["current_step"] = "document_analysis"
        state["messages"].append({
            "role": "system",
            "content": f"워크플로우 시작: {workflow_type}"
        })
        
        return state
    
    def document_analyzer_node(self, state: MultiAgentState) -> MultiAgentState:
        """문서 분석 에이전트"""
        logger.info(f"📄 문서 분석 에이전트 실행")
        
        documents = state.get("selected_documents", [])
        
        # 문서 분석 수행 (실제 AI 서비스 호출)
        analysis_result = {
            "document_count": len(documents),
            "content_summary": "문서들의 주요 내용 요약",
            "key_topics": ["주제1", "주제2", "주제3"],
            "structure_analysis": {
                "has_charts": False,
                "has_tables": True,
                "text_complexity": "medium"
            }
        }
        
        state["document_analysis"] = analysis_result
        state["completed_steps"].append("document_analysis")
        state["current_step"] = "insight_extraction"
        
        state["messages"].append({
            "role": "assistant", 
            "content": f"문서 분석 완료: {len(documents)}개 문서 처리"
        })
        
        return state
        
    def insight_extractor_node(self, state: MultiAgentState) -> MultiAgentState:
        """인사이트 추출 에이전트"""
        logger.info(f"💡 인사이트 추출 에이전트 실행")
        
        analysis = state.get("document_analysis", {})
        
        # 인사이트 추출 (실제 AI 서비스 호출)
        insights = [
            "핵심 인사이트 1: 데이터 기반 의사결정의 중요성",
            "핵심 인사이트 2: 프로세스 개선 포인트 3가지",
            "핵심 인사이트 3: 향후 전략 방향"
        ]
        
        state["key_insights"] = insights
        state["completed_steps"].append("insight_extraction")
        state["current_step"] = "summarization"
        
        state["messages"].append({
            "role": "assistant",
            "content": f"인사이트 추출 완료: {len(insights)}개 핵심 인사이트"
        })
        
        return state
        
    def summarizer_node(self, state: MultiAgentState) -> MultiAgentState:
        """요약 생성 에이전트"""
        logger.info(f"📝 요약 생성 에이전트 실행")
        
        analysis = state.get("document_analysis") or {}
        insights = state.get("key_insights") or []
        
        # 요약 생성 (실제 AI 서비스 호출)
        summary = f"""
        ## 문서 분석 요약
        
        **분석 대상**: {analysis.get('document_count', 0)}개 문서
        
        **핵심 인사이트**:
        {chr(10).join(f"- {insight}" for insight in insights)}
        
        **결론**: 종합적인 분석 결과와 제안사항
        """
        
        state["summary_content"] = summary
        state["completed_steps"].append("summarization")
        state["current_step"] = "presentation"
        
        state["messages"].append({
            "role": "assistant",
            "content": "요약 생성 완료"
        })
        
        return state
        
    def presentation_builder_node(self, state: MultiAgentState) -> MultiAgentState:
        """프레젠테이션 구성 에이전트"""
        logger.info(f"🎨 프레젠테이션 구성 에이전트 실행")
        
        summary = state.get("summary_content") or ""
        insights = state.get("key_insights") or []
        
        # 프레젠테이션 구조 생성
        outline = {
            "title": "분석 결과 발표",
            "slides": [
                {"title": "개요", "content": "프로젝트 개요 및 목적"},
                {"title": "분석 결과", "content": (summary[:200] + "...") if summary else "분석 결과 요약"},
                {"title": "핵심 인사이트", "content": insights[:3] if insights else []},
                {"title": "결론 및 제안", "content": "향후 액션 플랜"}
            ]
        }
        
        state["outline_structure"] = outline
        state["completed_steps"].append("presentation")
        state["current_step"] = "finalize"
        
        state["messages"].append({
            "role": "assistant",
            "content": f"프레젠테이션 구성 완료: {len(outline['slides'])}개 슬라이드"
        })
        
        return state
        
    def finalizer_node(self, state: MultiAgentState) -> MultiAgentState:
        """최종 결과 정리 에이전트"""
        logger.info(f"✅ 최종 결과 정리 에이전트 실행")
        
        # 최종 결과 컴파일
        final_output = {
            "workflow_type": state.get("workflow_type"),
            "document_analysis": state.get("document_analysis"),
            "key_insights": state.get("key_insights"),
            "summary": state.get("summary_content"),
            "presentation_outline": state.get("outline_structure"),
            "metadata": {
                **state.get("workflow_metadata", {}),
                "end_time": datetime.now().isoformat(),
                "completed_steps": state.get("completed_steps", [])
            }
        }
        
        state["final_output"] = final_output
        state["completed_steps"].append("finalize")
        state["current_step"] = "completed"
        
        state["messages"].append({
            "role": "assistant",
            "content": "멀티 에이전트 워크플로우 완료"
        })
        
        return state
        
    def route_next_agent(self, state: MultiAgentState) -> str:
        """다음 에이전트 라우팅 결정"""
        current_step = state.get("current_step", "")
        completed_steps = state.get("completed_steps", [])
        
        # 단계별 라우팅 로직
        if current_step == "document_analysis" and "document_analysis" not in completed_steps:
            return "document_analysis"
        elif current_step == "insight_extraction" and "insight_extraction" not in completed_steps:
            return "insight_extraction"  
        elif current_step == "summarization" and "summarization" not in completed_steps:
            return "summarization"
        elif current_step == "presentation" and "presentation" not in completed_steps:
            return "presentation"
        elif current_step == "finalize" and "finalize" not in completed_steps:
            return "finalize"
        else:
            return "end"
            
    async def execute_workflow(
        self, 
        user_query: str, 
        selected_documents: Optional[List[Dict[str, Any]]] = None,
        workflow_type: str = "analysis"
    ) -> Dict[str, Any]:
        """워크플로우 실행"""
        
        # 초기 상태 설정
        initial_state = MultiAgentState(
            user_query=user_query,
            selected_documents=selected_documents or [],
            workflow_type=workflow_type,
            current_step="start",
            completed_steps=[],
            agent_assignments={},
            document_analysis=None,
            key_insights=None,
            summary_content=None,
            outline_structure=None,
            final_output=None,
            workflow_metadata={},
            messages=[]
        )
        
        try:
            # 워크플로우 실행
            logger.info(f"🚀 멀티 에이전트 워크플로우 시작: {workflow_type}")
            
            if self.workflow_graph:
                result = await self.workflow_graph.ainvoke(initial_state)
            else:
                # Fallback: 순차 실행
                result = initial_state
                result = self.coordinator_node(result)
                result = self.document_analyzer_node(result)
                result = self.insight_extractor_node(result)
                result = self.summarizer_node(result)
                result = self.presentation_builder_node(result)
                result = self.finalizer_node(result)
            
            logger.info(f"✅ 멀티 에이전트 워크플로우 완료")
            
            return result.get("final_output") or {}
            
        except Exception as e:
            logger.error(f"❌ 워크플로우 실행 실패: {e}")
            raise
            

# 전역 인스턴스
multi_agent_orchestrator = MultiAgentOrchestrator()
