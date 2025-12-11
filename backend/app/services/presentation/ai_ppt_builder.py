"""
AI PPT Builder - SimplePPTBuilder wrapper for AI-First Pipeline

AI 매핑을 받아서 PPT를 생성하는 간단한 빌더.
SimplePPTBuilder를 래핑하여 AI-First 파이프라인과 호환되는 인터페이스 제공.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.presentation.simple_ppt_builder import SimplePPTBuilder

logger = logging.getLogger(__name__)


class AIPPTBuilder:
    """
    AI-First 파이프라인용 PPT 빌더.
    
    SimplePPTBuilder를 래핑하여 AI 매핑 형식을 지원.
    """
    
    def __init__(self, template_path: str, output_dir: str = "uploads"):
        """
        Args:
            template_path: 템플릿 PPT 파일 경로
            output_dir: 출력 디렉토리
        """
        self.template_path = template_path
        self.output_dir = output_dir
        self._builder = SimplePPTBuilder(template_path, output_dir)
    
    def build(
        self,
        mappings: List[Dict[str, Any]],
        output_filename: Optional[str] = None,
        presentation_title: Optional[str] = None,
        slide_replacements: Optional[List[Dict[str, Any]]] = None,  # 🆕 v3.4
        dynamic_slide_ops: Optional[Dict[str, Any]] = None,         # 🆕 v3.7
    ) -> Dict[str, Any]:
        """
        AI 매핑을 적용하여 PPT 생성.
        
        Args:
            mappings: AI 매핑 리스트 (slideIndex, elementId, generatedText, originalName 포함)
            output_filename: 출력 파일명 (없으면 presentation_title 또는 자동 생성)
            presentation_title: 프레젠테이션 제목 (파일명 생성용)
            slide_replacements: 슬라이드 대체 정보 (🆕 v3.4)
            dynamic_slide_ops: 동적 슬라이드 연산 정보 (🆕 v3.7)
                - mode: 'expand' | 'reduce'
                - operations: 추가/삭제할 슬라이드 정보 리스트
        
        Returns:
            빌드 결과 딕셔너리
        """
        logger.info(f"🔨 [AIPPTBuilder] 시작: {len(mappings)}개 매핑")
        if slide_replacements:
            logger.info(f"  🔄 슬라이드 대체: {len(slide_replacements)}개")
        if dynamic_slide_ops:
            logger.info(f"  📐 동적 슬라이드: mode={dynamic_slide_ops.get('mode')}")
        
        try:
            # 파일명 결정
            if not output_filename and presentation_title:
                # 제목에서 파일명 생성 (특수문자 제거)
                safe_title = "".join(c if c.isalnum() or c in ' _-' else '_' for c in presentation_title)
                safe_title = safe_title[:50].strip()
                output_filename = safe_title if safe_title else "presentation"
            
            if not output_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"ai_generated_{timestamp}"
            
            # .pptx 확장자 추가
            if not output_filename.endswith('.pptx'):
                output_filename = f"{output_filename}.pptx"
            
            # AI 매핑 형식을 SimplePPTBuilder 형식으로 변환
            builder_mappings = self._convert_mappings(mappings)
            
            logger.info(f"  📋 변환된 매핑: {len(builder_mappings)}개")
            
            # SimplePPTBuilder로 빌드 (🆕 v3.4: slide_replacements 전달, v3.7: dynamic_slide_ops)
            result = self._builder.build(
                builder_mappings, 
                output_filename,
                slide_replacements=slide_replacements,
                dynamic_slide_ops=dynamic_slide_ops,  # 🆕 v3.7
            )
            
            if result.get("success"):
                logger.info(f"✅ [AIPPTBuilder] 완료: {result.get('file_path')}")
                
                # 통계 추가
                result["stats"] = {
                    "applied": result.get("applied_count", 0),
                    "failed": result.get("failed_count", 0),
                    "skipped": len(mappings) - len(builder_mappings),
                    "total": len(mappings),
                }
                
                # file_name 추가
                result["file_name"] = output_filename
                
                # 🆕 v3.7: 동적 슬라이드 처리 결과 추가
                if dynamic_slide_ops:
                    result["dynamic_slides_applied"] = True
                    result["dynamic_slides_mode"] = dynamic_slide_ops.get('mode')
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [AIPPTBuilder] 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "file_path": None,
                "file_name": None,
            }
    
    def _convert_mappings(
        self,
        ai_mappings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        AI 매핑 형식을 SimplePPTBuilder 형식으로 변환.
        
        AI 매핑:
            {
                "slideIndex": 0,
                "elementId": "textbox-0-0",
                "generatedText": "새 콘텐츠",
                "originalName": "TextBox 1",
                "isEnabled": True,
                "elementRole": "main_title"
            }
        
        SimplePPTBuilder 매핑:
            {
                "slideIndex": 0,
                "elementId": "textbox-0-0",
                "newContent": "새 콘텐츠",
                "originalName": "TextBox 1",
                "isEnabled": True
            }
        """
        converted = []
        
        for m in ai_mappings:
            # isEnabled=False면 스킵
            if not m.get("isEnabled", True):
                logger.debug(f"⏭️ 비활성화 매핑 스킵: {m.get('elementId')}")
                continue
            
            # 콘텐츠 추출
            new_content = m.get("generatedText") or m.get("newContent") or ""
            
            # 🔧 FIX: originalName 없어도 elementId로 매칭 가능
            # UI 편집 데이터는 originalName이 없을 수 있음
            element_id = m.get("elementId", "")
            original_name = m.get("originalName", "")
            
            # elementId와 originalName 둘 다 없으면 스킵
            if not element_id and not original_name:
                logger.debug(f"⚠️ elementId, originalName 둘 다 없는 매핑 스킵")
                continue
            
            converted.append({
                "slideIndex": m.get("slideIndex", 0),
                "elementId": element_id,
                "newContent": new_content,
                "originalName": original_name,  # 빈 문자열 허용
                "objectType": m.get("objectType", "textbox"),
                "isEnabled": True,
                "metadata": m.get("metadata", {}),
            })
        
        logger.info(f"📋 매핑 변환: {len(ai_mappings)} → {len(converted)} (비활성화/무효 제외)")
        
        return converted


def build_ppt_from_ai_mappings(
    template_path: str,
    mappings: List[Dict[str, Any]],
    output_filename: Optional[str] = None,
    presentation_title: Optional[str] = None,
    output_dir: str = "uploads",
    slide_replacements: Optional[List[Dict[str, Any]]] = None,  # 🆕 v3.4
    dynamic_slide_ops: Optional[Dict[str, Any]] = None,         # 🆕 v3.7
) -> Dict[str, Any]:
    """
    편의 함수: AI 매핑으로 PPT 생성
    
    Args:
        template_path: 템플릿 PPT 경로
        mappings: AI 매핑 리스트
        output_filename: 출력 파일명
        presentation_title: 프레젠테이션 제목
        output_dir: 출력 디렉토리
        slide_replacements: 슬라이드 대체 정보 (🆕 v3.4)
        dynamic_slide_ops: 동적 슬라이드 연산 정보 (🆕 v3.7)
            - mode: 'expand' | 'reduce'
            - operations: 추가/삭제할 슬라이드 정보 리스트
    
    Returns:
        빌드 결과 딕셔너리
    """
    builder = AIPPTBuilder(template_path, output_dir)
    return builder.build(mappings, output_filename, presentation_title, slide_replacements, dynamic_slide_ops)
