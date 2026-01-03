"""
통합 멀티 에이전트 서비스
기존 단일 에이전트 시스템과 새로운 멀티 에이전트 시스템을 통합
"""

from typing import Dict, Any, List, Optional, Union
from loguru import logger
import asyncio
from datetime import datetime
import json

from app.agents.catalog import agent_catalog
from app.core.config import settings
from app.services.core.ai_service import ai_service
from app.services.chat.ai_agent_service import ai_agent_service
from app.services.multi_agent.langgraph_workflow import multi_agent_orchestrator
from app.services.multi_agent.agent_tools import tool_registry
from app.services.multi_agent.enhanced_agent_tools import enhanced_tool_registry
from app.schemas.chat import SelectedDocument


class IntegratedMultiAgentService:
    """통합 멀티 에이전트 서비스"""
    
    def __init__(self):
        self.orchestrator = multi_agent_orchestrator
        self.tool_registry = tool_registry
        self.enhanced_tool_registry = enhanced_tool_registry  # 새로운 확장된 툴 레지스트리
        self.legacy_agent_service = ai_agent_service
        self.new_agent_registry = agent_catalog
        self.enable_new_summary_agent = settings.enable_new_summary_agent
        self.enable_new_presentation_agent = settings.enable_new_presentation_agent
        
        # 에이전트 실행 모드
        self.execution_modes = {
            "single": "기존 단일 에이전트 방식",
            "multi": "새로운 멀티 에이전트 워크플로우",
            "hybrid": "상황에 따른 동적 선택"
        }
        
        # 워크플로우 타입별 에이전트 매핑
        self.workflow_mappings = {
            "simple_qa": "single",  # 단순 질답
            "document_analysis": "multi",  # 문서 분석
            "presentation_creation": "multi",  # 프레젠테이션 생성
            "comprehensive_report": "multi",  # 종합 보고서
            "quick_summary": "single",  # 빠른 요약
            "insight_extraction": "multi"  # 인사이트 추출
        }
        
    async def process_request(
        self,
        user_query: str,
        agent_type: str = "general",
        selected_documents: Optional[List[SelectedDocument]] = None,
        execution_mode: str = "hybrid",
        provider: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        요청 처리 - 단일/멀티 에이전트 모드 동적 선택
        
        Args:
            user_query: 사용자 질문
            agent_type: 에이전트 타입
            selected_documents: 선택된 문서들
            execution_mode: 실행 모드 (single/multi/hybrid)
            provider: AI 프로바이더
        """
        
        try:
            logger.info(f"🎯 통합 멀티 에이전트 요청 처리 시작")
            logger.info(f"📝 질문: {user_query[:100]}...")
            logger.info(f"🤖 에이전트: {agent_type}")
            logger.info(f"⚙️ 실행 모드: {execution_mode}")
            
            # 1. 요청 분석 및 최적 실행 모드 결정
            optimal_mode = self._determine_execution_mode(
                user_query, agent_type, selected_documents, execution_mode
            )
            
            logger.info(f"🎯 결정된 실행 모드: {optimal_mode}")
            
            # 2. 모드별 처리 분기
            if optimal_mode == "single":
                return await self._execute_single_agent(
                    user_query, agent_type, selected_documents, provider, **kwargs
                )
            elif optimal_mode == "multi":
                return await self._execute_multi_agent_workflow(
                    user_query, agent_type, selected_documents, provider, **kwargs
                )
            return {
                "success": False,
                "error": f"Unknown execution mode resolved: {optimal_mode}",
                "fallback_response": "요청 처리 중 지원되지 않는 실행 모드입니다."
            }
        except Exception as e:  # ensure try has except
            logger.error(f"❌ 통합 멀티 에이전트 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_response": "요청 처리 중 오류가 발생했습니다."
            }

    def _determine_execution_mode(
        self,
        user_query: str,
        agent_type: str,
        selected_documents: Optional[List[SelectedDocument]],
        requested_mode: str
    ) -> str:
        """최적 실행 모드 결정"""
        if requested_mode in ["single", "multi"]:
            return requested_mode
        doc_count = len(selected_documents) if selected_documents else 0
        query_length = len(user_query)
        if doc_count == 0 and query_length < 100:
            return "single"
        if doc_count > 3 or agent_type in ["analyzer", "report-generator", "presentation"]:
            return "multi"
        if agent_type in ["summarizer", "keyword-extractor"] and doc_count <= 2:
            return "single"
        return "multi"
    
    async def _execute_single_agent(
        self,
        user_query: str,
        agent_type: str,
        selected_documents: Optional[List[SelectedDocument]],
        provider: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """단일 에이전트 실행"""
        
        logger.info(f"🔸 단일 에이전트 실행: {agent_type}")
        
        try:
            # 선택된 문서가 None인 경우 빈 리스트로 처리
            documents = selected_documents or []

            # 새로운 아키텍처 적용 여부 판단
            use_new_architecture = (
                (agent_type == "summarizer" and self.enable_new_summary_agent)
                or (agent_type == "presentation" and self.enable_new_presentation_agent)
            )

            if use_new_architecture:
                new_agent_tool = self.new_agent_registry.get_tool(agent_type)
                if new_agent_tool:
                    logger.info("🆕 신규 에이전트 아키텍처 사용: %s", agent_type)
                    return await self._execute_new_agent_tool(
                        new_agent_tool,
                        user_query,
                        agent_type,
                        documents,
                        provider,
                        **kwargs,
                    )
            
            # 확장된 툴 레지스트리에서 해당 에이전트의 툴 확인
            agent_tool = self.enhanced_tool_registry.get_tool_by_agent_type(agent_type)
            
            if agent_tool:
                # 새로운 툴 기반 실행
                logger.info(f"🔧 에이전트 툴 사용: {agent_tool.name}")
                
                # 에이전트별 입력 준비
                tool_input = self._prepare_tool_input(agent_type, user_query, documents)
                
                # 비동기 실행 우선 (_arun 존재 시)
                tool_result = None
                arun = getattr(agent_tool, "_arun", None)
                if callable(arun):
                    try:
                        import inspect
                        arun_result = arun(**tool_input)
                        if inspect.isawaitable(arun_result):
                            tool_result = await arun_result
                        else:
                            tool_result = arun_result  # 이미 동기 반환
                    except Exception as async_e:
                        logger.warning(f"비동기 툴 실행 실패, 동기 폴백 시도: {async_e}")
                if tool_result is None:
                    # 동기 폴백 경로 - 다양한 시그니처 대응
                    try:
                        tool_result = agent_tool._run(**tool_input)
                    except TypeError as e1:
                        try:
                            tool_result = agent_tool._run(tool_input=json.dumps(tool_input))
                        except TypeError as e2:
                            try:
                                tool_result = agent_tool._run("", **tool_input)
                            except Exception as e3:
                                logger.error(f"모든 툴 호출 방법 실패: e1={e1}, e2={e2}, e3={e3}")
                                raise e3
                
                return {
                    "success": True,
                    "execution_mode": "single",
                    "agent_type": agent_type,
                    "tool_used": agent_tool.name,
                    "response": self._format_tool_response(tool_result, agent_type),
                    "tool_result": tool_result,
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "provider": provider or "tool",
                        "processing_time_ms": 1000
                    }
                }
            else:
                # 기존 AI Agent 서비스 활용 (Fallback)
                enhanced_query, references, context_info, rag_stats = await self.legacy_agent_service.prepare_context_with_documents(
                    query=user_query,
                    selected_documents=documents,
                    agent_type=agent_type
                )
                
                # AI 서비스로 응답 생성
                response = await ai_service.chat(enhanced_query, provider)
                
                return {
                    "success": True,
                    "execution_mode": "single",
                    "agent_type": agent_type,
                    "response": response,
                    "references": references,
                    "context_info": context_info,
                    "rag_stats": rag_stats,
                    "metadata": {
                        "timestamp": datetime.now().isoformat(),
                        "provider": provider or "default",
                        "processing_time_ms": 1000
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ 단일 에이전트 실행 실패: {e}")
            raise
    
    async def _execute_new_agent_tool(
        self,
        agent_tool,
        user_query: str,
        agent_type: str,
        selected_documents: List[SelectedDocument],
        provider: Optional[str],
        **kwargs,
    ) -> Dict[str, Any]:
        """Execute an agent that follows the new modular architecture."""

        documents_payload: List[Dict[str, Any]] = []
        for doc in selected_documents:
            if hasattr(doc, "model_dump"):
                documents_payload.append(doc.model_dump())
            elif isinstance(doc, dict):
                documents_payload.append(doc)
            else:
                documents_payload.append(
                    {
                        "id": getattr(doc, "id", None),
                        "fileName": getattr(doc, "fileName", None),
                        "fileType": getattr(doc, "fileType", None),
                        "metadata": getattr(doc, "metadata", {}) or {},
                    }
                )

        attachments = kwargs.get("attachment_paths") or kwargs.get("attachments") or []
        if isinstance(attachments, str):
            attachments = [attachments]
        agent_options = kwargs.get("agent_options") or {}
        user_emp_no = kwargs.get("user_emp_no") or kwargs.get("login_emp_no")

        logger.debug(
            "[IntegratedMultiAgent] 신규 아키텍처 입력 구성: docs=%s attachments=%s",
            len(documents_payload),
            len(attachments),
        )

        passthrough_keys = {"request_type", "summarization_type"}
        extra_args = {k: kwargs[k] for k in passthrough_keys if k in kwargs}

        # Presentation agent는 context_text 필드 필요
        if agent_type == "presentation":
            context_text = kwargs.get("context_text") or user_query
            tool_result = await agent_tool._arun(
                context_text=context_text,
                topic=kwargs.get("topic"),
                documents=documents_payload,
                options=agent_options,
                template_style=agent_options.get("template_style", "business"),
                presentation_type=agent_options.get("presentation_type", "general"),
                quick_mode=agent_options.get("quick_mode", False),
                **extra_args,
            )
        else:
            # Summary agent 등 기존 경로
            tool_result = await agent_tool._arun(
                query=user_query,
                documents=documents_payload,
                attachment_paths=attachments,
                options=agent_options,
                user_emp_no=user_emp_no,
                **extra_args,
            )

        # Presentation agent는 file_path 기반 응답 포맷
        if agent_type == "presentation":
            file_path = tool_result.get("file_path", "")
            file_name = tool_result.get("file_name", "")
            slide_count = tool_result.get("slide_count", 0)
            
            if file_path and file_name:
                response_text = (
                    f"## 📊 프레젠테이션 생성 완료\n\n"
                    f"✅ 파일: `{file_name}`\n"
                    f"📑 슬라이드 수: {slide_count}개\n\n"
                    f"다운로드가 준비되었습니다."
                )
            else:
                response_text = tool_result.get("error", "프레젠테이션 생성 실패")
        else:
            response_text = (
                tool_result.get("response")
                or tool_result.get("summary")
                or tool_result.get("answer")
                or ""
            )

        metrics = tool_result.get("metrics")
        processing_time = None
        if isinstance(metrics, dict):
            processing_time = metrics.get("latency_ms")

        return {
            "success": tool_result.get("success", False),
            "execution_mode": "single",
            "agent_type": agent_type,
            "tool_used": getattr(agent_tool, "name", agent_type),
            "response": response_text,
            "tool_result": tool_result,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "provider": provider or "tool",
                "processing_time_ms": processing_time,
                "new_architecture": True,
            },
        }

    async def _execute_multi_agent_workflow(
        self,
        user_query: str,
        agent_type: str,
        selected_documents: Optional[List[SelectedDocument]],
        provider: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """멀티 에이전트 워크플로우 실행"""
        
        logger.info(f"🔹 멀티 에이전트 워크플로우 실행: {agent_type}")
        
        try:
            # 워크플로우 타입 결정
            workflow_type = self._map_agent_to_workflow(agent_type)
            
            # 선택된 문서들을 딕셔너리 형태로 변환
            documents_dict = []
            if selected_documents:
                for doc in selected_documents:
                    documents_dict.append({
                        "id": doc.id,
                        "fileName": doc.fileName,
                        "fileType": doc.fileType,
                        "filePath": doc.filePath,
                        "metadata": doc.metadata or {}
                    })
            
            # 멀티 에이전트 오케스트레이터 실행
            workflow_result = await self.orchestrator.execute_workflow(
                user_query=user_query,
                selected_documents=documents_dict,
                workflow_type=workflow_type
            )
            
            # 결과 포맷팅
            return {
                "success": True,
                "execution_mode": "multi",
                "agent_type": agent_type,
                "workflow_type": workflow_type,
                "workflow_result": workflow_result,
                "response": self._format_multi_agent_response(workflow_result),
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "provider": provider or "default",
                    "workflow_steps": workflow_result.get("metadata", {}).get("completed_steps", []),
                    "processing_time_ms": 3000  # 실제 측정값으로 대체
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 멀티 에이전트 워크플로우 실행 실패: {e}")
            raise
    
    def _map_agent_to_workflow(self, agent_type: str) -> str:
        """에이전트 타입을 워크플로우 타입으로 매핑"""
        mapping = {
            "general": "simple_qa",
            "summarizer": "quick_summary", 
            "analyzer": "document_analysis",
            "presentation": "presentation_creation",
            "report-generator": "comprehensive_report",
            "insight": "insight_extraction",
            "keyword-extractor": "document_analysis"
        }
        
        return mapping.get(agent_type, "document_analysis")
    
    def _format_multi_agent_response(self, workflow_result: Dict[str, Any]) -> str:
        """멀티 에이전트 워크플로우 결과를 응답 형식으로 변환"""
        
        try:
            # 워크플로우 결과에서 주요 내용 추출
            summary = workflow_result.get("summary", "")
            insights = workflow_result.get("key_insights", [])
            presentation = workflow_result.get("presentation_outline", {})
            
            # 응답 텍스트 구성
            response_parts = []
            
            if summary:
                response_parts.append(f"## 📊 분석 요약\n{summary}")
            
            if insights:
                response_parts.append("## 💡 핵심 인사이트")
                for i, insight in enumerate(insights[:5], 1):
                    response_parts.append(f"{i}. {insight}")
            
            if presentation and presentation.get("slides"):
                response_parts.append("## 🎨 프레젠테이션 구성")
                slides = presentation.get("slides", [])
                for slide in slides[:3]:  # 처음 3개 슬라이드만 표시
                    response_parts.append(f"- {slide.get('title', '제목 없음')}")
            
            return "\n\n".join(response_parts) if response_parts else "분석이 완료되었습니다."
            
        except Exception as e:
            logger.error(f"❌ 응답 포맷팅 실패: {e}")
            return "멀티 에이전트 워크플로우가 완료되었습니다."
    
    def _prepare_tool_input(
        self, 
        agent_type: str, 
        user_query: str, 
        documents: List[SelectedDocument]
    ) -> Dict[str, Any]:
        """에이전트 타입에 따른 툴 입력 준비"""
        
        # 문서를 딕셔너리 형태로 변환
        docs_dict = []
        for doc in documents:
            docs_dict.append({
                "id": doc.id,
                "fileName": doc.fileName,
                "fileType": doc.fileType,
                "content": getattr(doc, 'content', ''),
                "metadata": doc.metadata or {}
            })
        
        # 에이전트별 입력 매핑
        if agent_type == 'general':
            return {
                "query": user_query, 
                "context": f"{len(documents)}개 문서 참조",
                "documents": docs_dict  # 문서 정보도 포함
            }
        elif agent_type == 'summarizer':
            return {"documents": docs_dict, "summary_type": "comprehensive"}
        elif agent_type == 'keyword-extractor':
            return {"documents": docs_dict, "max_keywords": 20, "include_phrases": True}
        elif agent_type == 'presentation':
            # PPT 옵션 마커 파싱 ([[PPT_OPTS:{...}]])
            import re, json as _json
            slide_count = 8
            template_style = "business"
            include_charts = True
            original_query = user_query
            try:
                m = re.search(r"^\s*\[\[PPT_OPTS:(\{.*?\})\]\]\\n?", user_query)
                if m:
                    opts_raw = m.group(1)
                    opts = _json.loads(opts_raw)
                    slide_count = int(opts.get("slide_count", slide_count)) if opts.get("slide_count") else slide_count
                    template_style = opts.get("template_style", template_style) or template_style
                    include_charts = bool(opts.get("include_charts", include_charts))
                    # 마커 제거 후 순수 사용자 질의
                    user_query = user_query[m.end():]
            except Exception:
                user_query = original_query  # 파싱 실패 시 원문 유지
            # 선택 문서 기반 컨텍스트 결합
            if documents:
                meta_lines = []
                for d in documents[:5]:
                    meta = d.metadata or {}
                    meta_lines.append(f"- {getattr(d,'fileName','문서')} (type={getattr(d,'fileType','?')}, pages={meta.get('page_count') or meta.get('pages') or '?'} )")
                doc_context = "선택 문서 개요:\n" + "\n".join(meta_lines)
                combined_content = user_query + "\n\n" + doc_context
            else:
                combined_content = user_query
            return {"content": combined_content, "slide_count": slide_count, "template_style": template_style, "include_charts": include_charts}
        elif agent_type == 'analyzer':
            return {"documents": docs_dict, "analysis_depth": "standard"}
        elif agent_type == 'insight':
            return {"data_sources": docs_dict, "insight_types": ["trend", "pattern", "anomaly"]}
        else:
            return {"query": user_query, "documents": docs_dict}
    
    def _format_tool_response(self, tool_result: Any, agent_type: str) -> str:
        """툴 실행 결과를 사용자 친화적 응답으로 변환"""
        
        if not tool_result.get("success", False):
            return f"죄송합니다. {agent_type} 처리 중 오류가 발생했습니다."
        
        # 에이전트별 응답 포맷팅
        if agent_type == 'general':
            return tool_result.get("response", "응답을 생성했습니다.")
        
        elif agent_type == 'summarizer':
            summary = tool_result.get("executive_summary", "")
            findings = tool_result.get("key_findings", [])
            response = f"## 📋 문서 요약\n\n{summary}\n\n### 주요 발견사항\n"
            for i, finding in enumerate(findings[:3], 1):
                response += f"{i}. {finding}\n"
            return response
        
        elif agent_type == 'keyword-extractor':
            keywords = tool_result.get("keywords", [])
            response = "## 🔍 추출된 키워드\n\n"
            for kw in keywords[:10]:
                response += f"- **{kw['keyword']}** (빈도: {kw['frequency']}, 관련도: {kw['relevance']:.2f})\n"
            return response
        
        elif agent_type == 'presentation':
            file_path = tool_result.get("file_path", "")
            if file_path:
                file_name = file_path.split('/')[-1]
                return f"## 📊 프레젠테이션 생성 완료\n\n✅ 파일이 생성되었습니다: `{file_name}`\n\n다운로드 링크가 제공됩니다."
            return "프레젠테이션이 생성되었습니다."
        
        elif agent_type == 'analyzer':
            overview = tool_result.get("document_overview", {})
            content = tool_result.get("content_analysis", {})
            response = f"## 🔬 문서 분석 결과\n\n"
            response += f"- 분석 문서: {overview.get('total_documents', 0)}개\n"
            response += f"- 가독성 점수: {content.get('readability_score', 0):.2f}\n"
            response += f"- 복잡도: {content.get('complexity_level', 'unknown')}\n"
            return response
        
        elif agent_type == 'insight':
            insights = tool_result.get("insights", [])
            response = "## 💡 도출된 인사이트\n\n"
            for i, insight in enumerate(insights[:3], 1):
                response += f"### {i}. {insight['title']}\n"
                response += f"{insight['description']}\n"
                response += f"**신뢰도**: {insight['confidence']:.2f} | **영향도**: {insight['impact']}\n\n"
            return response
        
        else:
            return "처리가 완료되었습니다."
    
    async def get_available_workflows(self) -> Dict[str, Any]:
        """사용 가능한 워크플로우 목록 반환"""
        return {
            "execution_modes": self.execution_modes,
            "workflow_types": list(self.workflow_mappings.keys()),
            "agent_mappings": self.workflow_mappings,
            "available_tools": self.tool_registry.get_tool_descriptions(),
            "enhanced_tools": self.enhanced_tool_registry.get_tool_descriptions(),
            "agent_capabilities": self.enhanced_tool_registry.get_agent_capabilities()
        }
    
    async def stream_multi_agent_process(
        self,
        user_query: str,
        agent_type: str = "general",
        selected_documents: Optional[List[SelectedDocument]] = None,
        provider: Optional[str] = None
    ):
        """멀티 에이전트 프로세스 스트리밍"""
        
        try:
            # 초기 상태 전송
            yield {
                "type": "workflow_start",
                "agent_type": agent_type,
                "documents_count": len(selected_documents) if selected_documents else 0
            }
            
            # 단계별 진행 상황 스트리밍 (모의 구현)
            steps = [
                {"step": "document_analysis", "status": "processing", "message": "문서 분석 중..."},
                {"step": "document_analysis", "status": "completed", "message": "문서 분석 완료"},
                {"step": "insight_extraction", "status": "processing", "message": "인사이트 추출 중..."},
                {"step": "insight_extraction", "status": "completed", "message": "인사이트 추출 완료"},
                {"step": "summary_generation", "status": "processing", "message": "요약 생성 중..."},
                {"step": "summary_generation", "status": "completed", "message": "요약 생성 완료"},
                {"step": "presentation_build", "status": "processing", "message": "프레젠테이션 구성 중..."},
                {"step": "presentation_build", "status": "completed", "message": "프레젠테이션 구성 완료"}
            ]
            
            for step in steps:
                await asyncio.sleep(0.5)  # 실제로는 각 단계 완료 대기
                yield {
                    "type": "step_update",
                    **step
                }
            
            # 최종 결과 처리
            final_result = await self._execute_multi_agent_workflow(
                user_query, agent_type, selected_documents, provider
            )
            
            yield {
                "type": "workflow_complete",
                "result": final_result
            }
            
        except Exception as e:
            logger.error(f"❌ 멀티 에이전트 스트리밍 실패: {e}")
            yield {
                "type": "error",
                "message": str(e)
            }


# 전역 통합 서비스 인스턴스
integrated_multi_agent_service = IntegratedMultiAgentService()
