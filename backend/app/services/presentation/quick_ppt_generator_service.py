"""Quick PPT Generator Service - general.prompt 규칙 기반 원클릭 생성"""
from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from loguru import logger
from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE

from app.core.config import settings
from .ppt_models import SlideSpec, DeckSpec


class QuickPPTGeneratorService:
    """
    general.prompt [발표 자료 생성 모드] 규칙 기반 원클릭 PPT 생성 서비스
    
    지원하는 구조:
    1. 제목 슬라이드 (필수) - ## 제목 + ### 📋 발표 개요
    2. 목차 슬라이드 (5개 이상 슬라이드시 필수) - ### 📑 발표 목차
    3. 본문 슬라이드들 - ### 제목 + 🔑 키 메시지 + 📝 상세 설명
    4. 마무리 슬라이드 (필수) - ### 감사합니다
    
    파싱 대상 패턴:
    - H2 레벨: ## 발표 제목
    - H3 레벨: ### 슬라이드 제목
    - 🔑 **키 메시지**: 핵심 내용 1~2문장
    - 📝 **상세 설명**: 불릿 포인트들
    """
    
    def __init__(self):
        self.upload_dir = Path(settings.file_upload_path or settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 간단한 색상 테마 (비즈니스용)
        self.colors = {
            "primary": RGBColor(0, 102, 204),
            "secondary": RGBColor(102, 153, 255), 
            "text": RGBColor(51, 51, 51),
            "background": RGBColor(248, 249, 250)
        }

    def _detect_visualization_hints(self, slide_spec: SlideSpec) -> Dict[str, Any]:
        """슬라이드 내용에서 시각화 힌트를 감지합니다."""
        hints = {
            "chart": False,
            "table": False,
            "diagram": False,
            "process": False,
            "comparison": False,
            "chart_type": None,
            "chart_data": None,
            # 추가 메타
            "numeric_score": 0,
            "table_from_bullets": False,
            "process_from_bullets": False,
        }
        
        # 모든 텍스트 결합
        all_text = f"{slide_spec.title} {slide_spec.key_message} {' '.join(slide_spec.bullets)}"
        all_text = all_text.lower()
        
        # 차트 관련 키워드
        chart_keywords = [
            "증가", "감소", "성장", "하락", "비율", "퍼센트", "%", "추이", "변화",
            "비교", "대비", "점유율", "시장", "매출", "수익", "통계", "데이터"
        ]
        
        # 표 관련 키워드  
        table_keywords = [
            "항목", "구분", "분류", "목록", "리스트", "사양", "스펙", "기능",
            "가격", "요금", "비용", "계획", "일정", "단계"
        ]
        
        # 프로세스/다이어그램 키워드
        process_keywords = [
            "단계", "과정", "절차", "순서", "흐름", "프로세스", "워크플로",
            "다음", "이후", "진행", "구조", "조직도", "관계"
        ]
        
        # 숫자 신호 집계 (차트 신뢰도 향상)
        num_count = 0
        percent_count = 0
        for b in slide_spec.bullets or []:
            s = (b or "").strip()
            num_count += len(re.findall(r"\b\d+(?:[\.,]\d+)?\b", s))
            percent_count += s.count("%")
        hints["numeric_score"] = num_count + percent_count

        # 차트 감지: 키워드 + 숫자 신호가 있는 경우에만 활성화
        if any(keyword in all_text for keyword in chart_keywords) and hints["numeric_score"] >= 2:
            hints["chart"] = True
            # 간단한 차트 타입 결정
            if any(word in all_text for word in ["증가", "감소", "성장", "추이"]):
                hints["chart_type"] = "line"
            elif any(word in all_text for word in ["비율", "점유율", "퍼센트", "%"]):
                hints["chart_type"] = "pie"
            else:
                hints["chart_type"] = "column"
        
        # 표 감지
        if any(keyword in all_text for keyword in table_keywords):
            hints["table"] = True
            hints["table_from_bullets"] = True  # 키워드 기반 표는 불릿에서 생성됨
        else:
            # 불릿 포인트에 ":" 또는 " - " 패턴이 2개 이상 존재하면 표로 간주
            colon_style_count = 0
            for b in slide_spec.bullets:
                s = (b or "").strip()
                if not s:
                    continue
                if ":" in s or " - " in s or "|" in s:  # 파이프(|) 추가
                    colon_style_count += 1
            if colon_style_count >= 2:
                hints["table"] = True
                hints["table_from_bullets"] = True
        
        # 프로세스 다이어그램 감지
        if any(keyword in all_text for keyword in process_keywords) or any(
            (b or "").strip().startswith(("1.", "2.", "-", "•", "*")) for b in slide_spec.bullets
        ):
            hints["process"] = True
            hints["process_from_bullets"] = True
            
        # 비교 구조 감지
        if any(word in all_text for word in ["vs", "대비", "비교", "차이"]):
            hints["comparison"] = True
            
        logger.info(f"🎨 시각화 힌트 감지: {hints}")
        return hints

    def _create_sample_chart(self, slide, chart_type: str, title: str, x=None, y=None, cx=None, cy=None):
        """샘플 차트를 생성합니다.
        위치와 크기(x, y, cx, cy)가 전달되면 해당 영역에 렌더링합니다.
        """
        try:
            # 차트 데이터 준비
            chart_data = CategoryChartData()
            
            if chart_type == "pie":
                # 파이 차트
                chart_data.categories = ['제품 A', '제품 B', '제품 C', '기타']
                chart_data.add_series('시장 점유율', (40, 30, 20, 10))
            elif chart_type == "line":
                # 선 차트 (추이)
                chart_data.categories = ['1Q', '2Q', '3Q', '4Q']
                chart_data.add_series('매출 증가율', (15, 25, 35, 45))
            else:
                # 기본: 컬럼 차트
                chart_data.categories = ['현재', '목표', '예상']
                chart_data.add_series('성과 지표', (75, 100, 95))
            
            # 차트 타입 결정
            if chart_type == "pie":
                chart_type_enum = XL_CHART_TYPE.PIE
            elif chart_type == "line":
                chart_type_enum = XL_CHART_TYPE.LINE
            else:
                chart_type_enum = XL_CHART_TYPE.COLUMN_CLUSTERED
            
            # 차트 위치 및 크기 (기본값)
            if x is None or y is None or cx is None or cy is None:
                x, y, cx, cy = Inches(1), Inches(3), Inches(8), Inches(4)
            chart = slide.shapes.add_chart(chart_type_enum, x, y, cx, cy, chart_data).chart
            
            # 차트 제목
            if chart.has_title:
                chart.chart_title.text_frame.text = title or "데이터 시각화"
                
            logger.info(f"✅ {chart_type} 차트 생성 완료")
            return chart
            
        except Exception as e:
            logger.warning(f"⚠️ 차트 생성 실패: {e}")
            return None

    def _create_simple_table(self, slide, title: str, bullets: List[str], x=None, y=None, cx=None, cy=None):
        """간단한 표를 생성합니다. 위치와 크기를 명시적으로 지정할 수 있습니다."""
        try:
            from pptx.table import Table
            
            # 불릿 포인트를 표 형태로 변환
            rows = min(len(bullets) + 1, 6)  # 최대 5개 데이터 행 + 헤더
            cols = 2
            
            # 표 위치 및 크기 (기본값)
            if x is None or y is None or cx is None or cy is None:
                x, y, cx, cy = Inches(1), Inches(2.5), Inches(8), Inches(4)
            
            # 표 생성
            table = slide.shapes.add_table(rows, cols, x, y, cx, cy).table
            
            # 헤더 설정
            table.cell(0, 0).text = "항목"
            table.cell(0, 1).text = "내용"
            
            # 헤더 스타일링
            for col in range(cols):
                cell = table.cell(0, col)
                cell.fill.solid()
                cell.fill.fore_color.rgb = self.colors["primary"]
                cell.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 255, 255)
                cell.text_frame.paragraphs[0].font.bold = True
            
            # 데이터 행 채우기
            for i, bullet in enumerate(bullets[:rows-1]):
                if i + 1 < rows:
                    # 간단한 파싱: "항목: 내용" 형태 감지
                    if ":" in bullet:
                        parts = bullet.split(":", 1)
                        table.cell(i + 1, 0).text = parts[0].strip()
                        table.cell(i + 1, 1).text = parts[1].strip()
                    else:
                        table.cell(i + 1, 0).text = f"항목 {i + 1}"
                        table.cell(i + 1, 1).text = bullet

            # 본문 셀 기본 스타일 (가독성)
            for r in range(1, rows):
                for c in range(cols):
                    try:
                        p = table.cell(r, c).text_frame.paragraphs[0]
                        p.font.size = Pt(12)
                        p.font.name = '맑은 고딕'
                        p.font.color.rgb = RGBColor(30, 30, 30)
                    except Exception:
                        pass
            
            logger.info(f"✅ 표 생성 완료: {rows}x{cols}")
            return table
            
        except Exception as e:
            logger.warning(f"⚠️ 표 생성 실패: {e}")
            return None

    def _create_process_diagram(self, slide, title: str, bullets: List[str], y: Optional[float] = None):
        """프로세스 다이어그램을 생성합니다. y가 지정되면 해당 높이에 배치합니다."""
        try:
            # 단계별 박스 생성
            step_count = min(len(bullets), 5)  # 최대 5단계
            box_width = Inches(1.5)
            box_height = Inches(0.8)
            spacing = Inches(0.3)
            
            # 중앙 정렬을 위한 시작 위치 계산
            total_width = (box_width * step_count) + (spacing * (step_count - 1))
            start_x = (Inches(10) - total_width) / 2
            box_y = y if y is not None else Inches(3.5)
            
            for i in range(step_count):
                x = start_x + (box_width + spacing) * i
                
                # 단계 박스 생성
                shape = slide.shapes.add_shape(
                    MSO_SHAPE.ROUNDED_RECTANGLE, x, box_y, box_width, box_height
                )
                
                # 박스 스타일링
                shape.fill.solid()
                shape.fill.fore_color.rgb = self.colors["secondary"]
                shape.line.color.rgb = self.colors["primary"]
                
                # 텍스트 추가
                text_frame = shape.text_frame
                text_frame.clear()
                p = text_frame.paragraphs[0]
                p.text = f"단계 {i + 1}"
                p.font.bold = True
                p.font.size = Pt(12)
                p.alignment = PP_ALIGN.CENTER
                
                # 단계 내용 추가
                if i < len(bullets):
                    p2 = text_frame.add_paragraph()
                    p2.text = bullets[i][:20] + "..." if len(bullets[i]) > 20 else bullets[i]
                    p2.font.size = Pt(10)
                    p2.alignment = PP_ALIGN.CENTER
                
                # 화살표 추가 (마지막 단계 제외)
                if i < step_count - 1:
                    arrow_x = x + box_width + spacing/4
                    arrow_y = box_y + box_height/2 - Inches(0.1)
                    arrow = slide.shapes.add_shape(
                        MSO_SHAPE.RIGHT_ARROW, arrow_x, arrow_y, spacing/2, Inches(0.2)
                    )
                    arrow.fill.solid()
                    arrow.fill.fore_color.rgb = self.colors["primary"]
            
            logger.info(f"✅ 프로세스 다이어그램 생성 완료: {step_count}단계")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ 프로세스 다이어그램 생성 실패: {e}")
            return False

    def generate_fixed_outline(self, topic: str, context_text: str, max_slides: int = 8) -> DeckSpec:
        """
        general.prompt [발표 자료 생성 모드] 규칙 기반 아웃라인 생성
        
        파싱 규칙:
        1. ## 제목 → 발표 제목 추출
        2. ### 📋 발표 개요 → 제목 슬라이드 상세 정보 (건너뜀)
        3. ### 📑 발표 목차 → 목차 슬라이드 정보 추출
        4. ### 일반 제목 → 본문 슬라이드 생성
           - 🔑 **키 메시지**: 추출
           - 📝 **상세 설명**: 불릿 포인트 추출
        5. ### 감사합니다 → 마무리 슬라이드
        
        생성 구조:
        - 제목 슬라이드 (필수)
        - 목차 슬라이드 (5개 이상 슬라이드시)
        - 본문 슬라이드들
        - 마무리 슬라이드 (없으면 기본 요약 슬라이드 생성)
        
        Args:
            topic: 발표 주제 (fallback 제목용)
            context_text: AI 생성 텍스트 (general.prompt 형식)
            max_slides: 최대 슬라이드 수
            
        Returns:
            DeckSpec: 생성된 프레젠테이션 구조
        """
        try:
            logger.info(f"🚀 원클릭 고정 구조 생성 시작: topic='{topic[:50]}', max_slides={max_slides}")
            # 선처리: 코드 펜스 제거, 제네릭 헤더 제거, 중복 헤딩 제거 (채팅창 서식 영향 제거)
            def _pre_sanitize(md: str) -> str:
                s = md.replace('\r\n', '\n').replace('\r', '\n')
                # 코드펜스 제거 (라인 자체 제거)
                s = re.sub(r"^```[a-zA-Z0-9_-]*\s*$", "", s, flags=re.MULTILINE)
                # 제네릭 '## 제목 슬라이드' 제거
                s = re.sub(r"(?m)^##\s*제목\s*슬라이드\s*$", "", s)
                
                # 연속된 동일 헤딩 제거 (첫 번째만 유지)
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
                
                # 헤더 뒤 공백 보장
                s = re.sub(r"(?m)^(#{2,6}\s+[^\n]+)\n(?=\S)", r"\1\n\n", s)
                # 과도한 개행 축소
                s = re.sub(r"\n{3,}", "\n\n", s)
                return s.strip()

            context_text = _pre_sanitize(context_text or "")
            logger.info(f"📝 입력 컨텍스트 길이: {len(context_text)} 문자")
            logger.info(f"📝 입력 컨텍스트 앞 200자: '{context_text[:200]}'")
            
            max_slides = max(3, min(max_slides, 20))
            
            # 더 강력한 섹션 추출 로직
            lines = [ln.strip() for ln in (context_text or "").split("\n") if ln.strip()]
            logger.info(f"📄 총 라인 수: {len(lines)}")
            
            # 실제 문서 제목 추출 (첫 번째 헤딩이나 제목 라인에서)
            actual_title = topic  # 기본값
            logger.info(f"🔍 제목 추출 시작 - 기본값: '{topic}'")
            logger.info(f"🔍 분석할 라인 수: {len(lines[:5])}")
            # 첫 5줄 중 의미 없는 서두(예: "알겠습니다.", "네 알겠습니다") 제거 후 스캔
            acknowledgement_pattern = re.compile(r'^(알겠습니다|네|예|좋습니다|확인했습니다|네,? 알겠습니다|알겠어요)[\.\s]*$', re.IGNORECASE)
            scan_candidates = []
            for raw_line in lines[:5]:
                # H2/H3 는 그대로 사용
                if raw_line.startswith('#'):
                    scan_candidates.append(raw_line)
                    continue
                # 의례적 확인 문구 단독 또는 확인 문구 + 작성 의도 문장 스킵
                if acknowledgement_pattern.match(raw_line) or re.match(r'^(알겠습니다|네|예|좋습니다|확인했습니다)[^\n]{0,40}(작성|만들|생성).*$', raw_line):
                    logger.info(f"⏭️ 인사/확인 문구 스킵: '{raw_line}'")
                    continue
                scan_candidates.append(raw_line)
            for i, line in enumerate(scan_candidates):  # 후보 라인에서 찾기
                line = line.strip()
                logger.info(f"🔍 라인 {i+1}: '{line}'")
                if line.startswith('###') and not line.startswith('####'):
                    # ### 헤딩에서 제목 추출
                    candidate = line.lstrip('#').strip()
                    # '📋 발표 개요', '📑 발표 목차'는 제목이 아님
                    if re.match(r'^📋\s*발표\s*개요', candidate) or re.match(r'^📑\s*발표\s*목차', candidate):
                        continue
                    # '제목 슬라이드' 같은 제네릭 표현 제외
                    if re.match(r'^제목\s*슬라이드$', candidate):
                        continue
                    actual_title = candidate
                    logger.info(f"🎯 문서 제목 추출 (###): '{actual_title}'")
                    break
                elif line.startswith('##') and not line.startswith('###'):
                    # ## 헤딩에서 제목 추출
                    candidate = line.lstrip('#').strip()
                    if re.match(r'^제목\s*슬라이드$', candidate):
                        # 제네릭 제목은 스킵하고 다음 후보 탐색
                        continue
                    actual_title = candidate
                    logger.info(f"🎯 문서 제목 추출 (##): '{actual_title}'")
                    break
                elif (not line.startswith('#') and len(line) > 5 and len(line) <= 50 and 
                      ('제품' in line or '소개' in line or '시스템' in line or '서비스' in line)):
                    # 일반 텍스트에서 제목으로 보이는 라인 추출
                    actual_title = line
                    logger.info(f"🎯 문서 제목 추출 (텍스트): '{actual_title}'")
                    break
            logger.info(f"🎯 최종 제목: '{actual_title}'")

            # 제목 정규화 (의례적 문구/요청 표현 제거, 간결 표현으로 압축)
            def _normalize_title(primary: str, user_topic: str) -> str:
                base = primary.strip() or user_topic.strip()
                # 1) 앞부분 확인/응답 제거
                base = re.sub(r'^(알겠습니다|네|예|좋습니다|확인했습니다|네 알겠습니다)[\.,\s]+', '', base)
                # 2) 작성/요청/지시형 표현 제거
                #   긴 패턴(요청/하겠습니다 포함) → 간단 패턴 순서 적용
                base = re.sub(r'(?:에 대한)?\s*소개\s*프레?젠테이션\s*자료를?\s*(?:작성|만들|생성)?(?:하겠습니다|해\s*주[세요]*|주[세요]*|해요|해)?\s*$', ' 소개자료', base)
                base = re.sub(r'(?:에 대한)?\s*소개\s*프레?젠테이션\s*자료를?$', ' 소개자료', base)
                base = re.sub(r'(프레?젠테이션|발표\s*자료|PPT|ppt)\s*(자료)?\s*(작성|만들|생성)?(해|해\s*주[세요]*|주[세요]*)?\s*$', '', base)
                base = re.sub(r'(작성|만들|생성)해?\s*주[세요]*$', '', base)
                base = re.sub(r'(작성|만들|생성)하겠습니다$', '', base)
                # 3) 불필요한 조사/어미 정리
                base = re.sub(r'(에 대한)$', '', base)
                # 4) 공백 정리
                base = re.sub(r'\s+', ' ', base).strip()
                # 5) '소개'로 끝나면 '소개자료'로 보강
                if base.endswith('소개') and len(base) <= 20:  # 과도하게 길어지는 것 방지
                    base = base + '자료'
                # 6) 너무 길면 핵심 키워드 압축: 공백으로 분리 후 6단어 제한
                parts = base.split()
                if len(parts) > 6:
                    base = ' '.join(parts[:6])
                # 7) 남은 문장부호 제거
                base = re.sub(r'[\.?!]+$', '', base)
                # 8) 빈 경우 폴백
                return base or '발표자료'

            normalized_title = _normalize_title(actual_title, topic)
            if normalized_title != actual_title:
                logger.info(f"🧹 제목 정규화: '{actual_title}' -> '{normalized_title}'")
                actual_title = normalized_title
            
            # 1) 패턴 기반(🔑/📝) 구조 파싱 시도 -> 실패 시 기존 휴리스틱
            structured_sections = self._parse_ai_structured_sections(context_text, deck_title=actual_title, max_sections=max_slides-3)
            if structured_sections:
                logger.info(f"✅ 패턴 기반 섹션 파싱 성공: {len(structured_sections)}개")
                sections = structured_sections
            else:
                logger.info("ℹ️ 패턴 기반 파싱 실패 또는 섹션 부족 -> 휴리스틱 파싱 사용")
                sections = self._parse_structured_content(lines, max_slides-3, exclude_title=actual_title)

            # 🔧 상세 설명 분리 섹션(📝)을 이전 헤딩 섹션과 병합하여 불필요한 '📝 **상세 설명**' 슬라이드 제거
            sections = self._merge_detail_sections(sections)
            
            logger.info(f"🎯 추출된 섹션 수: {len(sections)}")
            for i, section in enumerate(sections):
                logger.info(f"  섹션 {i+1}: '{section['title'][:30]}...' (bullets: {len(section.get('bullets', []))}개)")
            
            slides: List[SlideSpec] = []

            # ------------------------------------------------------------------
            # 안전장치: 본문 슬라이드 누락 방지
            #  - 섹션이 전혀 없거나
            #  - '감사합니다' 형태만 단독 존재하는 경우 → 최소 1개 본문 섹션 생성
            # ------------------------------------------------------------------
            def _synthesize_basic_section(topic_text: str) -> dict:
                return {
                    'title': f'{topic_text} 개요',
                    'key_message': f'{topic_text}의 핵심 개요를 요약합니다.',
                    'bullets': [
                        '주요 특징 및 장점',
                        '핵심 구성 요소',
                        '적용 또는 활용 방안'
                    ],
                    'slide_type': 'content'
                }

            if not sections:
                logger.warning('⚠️ 추출된 섹션이 없어 기본 개요 섹션 하나를 생성합니다.')
                sections = [_synthesize_basic_section(actual_title or topic)]
            else:
                non_summary = [s for s in sections if not (s.get('slide_type') == 'summary' or '감사' in s.get('title',''))]
                if not non_summary:
                    logger.warning('⚠️ 마무리/감사 슬라이드만 감지되어 기본 개요 본문을 앞에 삽입합니다.')
                    sections = [_synthesize_basic_section(actual_title or topic)] + sections
            
            # =====================================================================
            # General.prompt 4단계 구조에 따른 슬라이드 생성
            # 1. 제목 슬라이드 (필수)
            # 2. 목차 슬라이드 (5개 이상 슬라이드시 필수)  
            # 3. 본문 슬라이드들 (내용에 따라)
            # 4. 마무리 슬라이드 (필수)
            # =====================================================================
            
            # 1) 제목 슬라이드 - general.prompt 제목 슬라이드 규칙 적용
            title_slide = SlideSpec(
                title=actual_title or "발표자료", 
                key_message="발표의 핵심 내용을 한 문장으로 요약", 
                bullets=[
                    "발표 목적 및 배경",
                    "대상 청중 또는 활용 분야", 
                    f"예상 소요 시간: {max(5, len(sections) * 2)}분"
                ], 
                layout="title-slide"
            )
            slides.append(title_slide)
            logger.info("✅ 제목 슬라이드 생성 (general.prompt 규칙)")
            
            # 2) 목차 슬라이드 - general.prompt: 5개 이상 슬라이드시 필수
            content_slide_count = len(sections)
            total_expected_slides = 2 + content_slide_count + 1  # 제목 + 목차 + 내용들 + 마무리
            
            if total_expected_slides >= 5:
                toc_items = []
                # 본문 슬라이드들의 제목으로 목차 구성
                for i, s in enumerate(sections, start=1):
                    section_title = s["title"]
                    # 기존 번호 및 특수 문자 제거 (번호는 렌더링 단계에서 부여)
                    clean_title = re.sub(r'^\s*(\d+\.|\#+|📝|🎯)\s*', '', section_title).strip()
                    toc_items.append(clean_title)
                
                toc_slide = SlideSpec(
                    title="📑 발표 목차", 
                    key_message=f"총 {content_slide_count}개 슬라이드로 구성된 발표입니다", 
                    bullets=toc_items, 
                    layout="title-and-content"
                )
                slides.append(toc_slide)
                logger.info("✅ 목차 슬라이드 생성 (5개 이상 슬라이드 조건 충족)")
            else:
                logger.info("ℹ️ 목차 슬라이드 생략 (5개 미만 슬라이드)")
            
            # 3) 본문 슬라이드들 - general.prompt 본문 규칙 적용
            for i, s in enumerate(sections):
                # 슬라이드 타입 확인 (일반 내용 vs 마무리)
                slide_type = s.get('slide_type', 'content')
                
                # 페이지 제목 정리
                page_title = re.sub(r'^\s*(\d+\.|\#+)\s*', '', s["title"]).strip()
                
                # 키 메시지가 없으면 기본값 설정
                key_message = s.get("key_message", "") or f"{page_title}의 핵심 내용입니다."
                
                content_slide = SlideSpec(
                    title=page_title, 
                    key_message=key_message, 
                    bullets=s.get("bullets", [])[:8],  # 최대 8개 불릿
                    layout="title-and-content"
                )
                slides.append(content_slide)
                
                if slide_type == 'summary':
                    logger.info(f"✅ 마무리 슬라이드 생성: '{page_title[:20]}...'")
                else:
                    logger.info(f"✅ 본문 슬라이드 생성: '{page_title[:20]}...'")
            
            # 4) 기본 마무리 슬라이드 (감사 인사 슬라이드가 없는 경우에만)
            has_summary_slide = any(
                s.get('slide_type') == 'summary' or 
                '감사합니다' in s.get('title', '') or
                '감사' in s.get('title', '')
                for s in sections
            )
            if not has_summary_slide:
                summary_slide = SlideSpec(
                    title="감사합니다", 
                    key_message="", 
                    bullets=[], 
                    layout="title-and-content"
                )
                slides.append(summary_slide)
                logger.info("✅ 기본 마무리 슬라이드 생성 (감사 인사)")
            else:
                logger.info("ℹ️ 기본 마무리 슬라이드 생략 (이미 감사 인사 슬라이드 존재)")
            
            deck = DeckSpec(topic=actual_title or "발표자료", slides=slides, max_slides=len(slides))
            logger.info(f"🎉 Enhanced 구조 DeckSpec 생성 완료: 총 {len(slides)}개 슬라이드")
            logger.info(f"📊 구성: 제목(1) + 목차({1 if total_expected_slides >= 5 else 0}) + 본문({len(sections)}) + 마무리({0 if has_summary_slide else 1})")
            return deck
            
        except Exception as e:
            logger.error(f"generate_fixed_outline 실패: {e}")
            # general.prompt 규칙에 따른 Enhanced 폴백 구조
            fallback_slides = [
                # 1. 제목 슬라이드
                SlideSpec(
                    title=topic or "발표자료", 
                    key_message="발표의 핵심 내용을 한 문장으로 요약", 
                    bullets=[
                        "발표 목적 및 배경",
                        "대상 청중 또는 활용 분야",
                        "예상 소요 시간: 10분"
                    ], 
                    layout="title-slide"
                ),
                # 2. 본문 슬라이드
                SlideSpec(
                    title="주요 내용", 
                    key_message="핵심 주제에 대한 상세 내용을 제시합니다.", 
                    bullets=[
                        "주요 특징 및 장점",
                        "실무 적용 방안", 
                        "기대 효과 및 결과"
                    ], 
                    layout="title-and-content"
                ),
                # 3. 마무리 슬라이드 (감사 인사)
                SlideSpec(
                    title="감사합니다", 
                    key_message="", 
                    bullets=[], 
                    layout="title-and-content"
                )
            ]
            logger.info(f"⚠️ Enhanced 폴백 구조 사용: {len(fallback_slides)}개 슬라이드 (general.prompt 규칙)")
            return DeckSpec(topic=topic or "발표자료", slides=fallback_slides, max_slides=len(fallback_slides))

    def build_quick_pptx(self, spec: DeckSpec, file_basename: Optional[str] = None) -> str:
        """원클릭 전용 빌더: 템플릿/매핑 비적용, 단순 구조"""
        logger.info(f"🏗️ 원클릭 PPT 빌드 시작: {len(spec.slides)}개 슬라이드, topic='{spec.topic}'")
        
        try:
            # 파일명 생성
            if not file_basename:
                raw_topic = spec.topic or 'presentation'
                # 불필요/의례적 서두 제거
                raw_topic = re.sub(r'^(알겠습니다|네|좋습니다|좋아요|확인했습니다|예|okay|OK|Ok)[,_\s]+', '', raw_topic, flags=re.IGNORECASE)
                # 너무 긴 자연어 문장일 경우 첫 구(마침표/줄바꿈 전)만 사용
                first_clause = re.split(r'[\n\.?!]', raw_topic)[0]
                if len(first_clause) < 4:  # 너무 짧으면 원문 사용
                    first_clause = raw_topic
                safe_topic = re.sub(r'[^\w\s-]', '', first_clause).strip()
                safe_topic = re.sub(r'[-\s]+', '_', safe_topic)
                safe_topic = safe_topic[:40]  # 더 짧은 제한
                if not safe_topic:
                    safe_topic = 'deck'
                file_basename = f"quick_presentation_{safe_topic}"
            
            filename = f"{file_basename}.pptx"
            output_path = self.upload_dir / filename
            
            # 새 프레젠테이션 생성
            prs = Presentation()
            
            for i, slide_spec in enumerate(spec.slides):
                logger.info(f"📄 슬라이드 {i+1} 생성 중: '{slide_spec.title}'")
                
                if i == 0:
                    # 제목 슬라이드
                    slide_layout = prs.slide_layouts[0]  # Title Slide
                    slide = prs.slides.add_slide(slide_layout)
                    
                    # 🎨 제목 슬라이드 배경색 적용 (진한 파란색)
                    try:
                        slide.background.fill.solid()
                        slide.background.fill.fore_color.rgb = RGBColor(0, 51, 102)  # #003366
                    except Exception as e:
                        logger.warning(f"제목 슬라이드 배경색 적용 실패: {e}")
                    
                    title = slide.shapes.title
                    if title:
                        title.text = slide_spec.title
                        # 🎨 제목 텍스트 색상을 흰색으로 변경
                        try:
                            title_para = title.text_frame.paragraphs[0]
                            title_para.font.color.rgb = RGBColor(255, 255, 255)  # 흰색
                            title_para.font.bold = True
                            title_para.font.size = Pt(44)
                        except Exception as e:
                            logger.warning(f"제목 텍스트 스타일 적용 실패: {e}")
                elif slide_spec.title == "감사합니다":
                    # 마지막 슬라이드
                    slide_layout = prs.slide_layouts[0]  # Title Slide 
                    slide = prs.slides.add_slide(slide_layout)
                    
                    # 🎨 마무리 슬라이드 그라데이션 배경 적용
                    try:
                        slide.background.fill.gradient()
                        gradient_stops = slide.background.fill.gradient_stops
                        gradient_stops[0].color.rgb = RGBColor(0, 102, 204)   # 파란색
                        gradient_stops[1].color.rgb = RGBColor(51, 153, 102) # 초록색
                    except Exception as e:
                        logger.warning(f"마무리 슬라이드 그라데이션 배경 적용 실패: {e}")
                        # 폴백: 단색 배경
                        try:
                            slide.background.fill.solid()
                            slide.background.fill.fore_color.rgb = RGBColor(0, 102, 204)
                        except:
                            pass
                    
                    title = slide.shapes.title
                    if title:
                        title.text = slide_spec.title
                        # 🎨 마무리 제목 텍스트 스타일
                        try:
                            title_para = title.text_frame.paragraphs[0]
                            title_para.font.color.rgb = RGBColor(255, 255, 255)  # 흰색
                            title_para.font.bold = True
                            title_para.font.size = Pt(40)
                        except Exception as e:
                            logger.warning(f"마무리 제목 스타일 적용 실패: {e}")
                    
                    if slide_spec.key_message:
                        subtitle = slide.placeholders[1] if len(slide.placeholders) > 1 else None
                        if subtitle and getattr(subtitle, 'has_text_frame', False):
                            subtitle_tf = getattr(subtitle, 'text_frame', None)
                            if subtitle_tf:
                                subtitle_tf.text = slide_spec.key_message
                                # 🎨 부제목 텍스트 스타일
                                try:
                                    subtitle_para = subtitle_tf.paragraphs[0]
                                    subtitle_para.font.color.rgb = RGBColor(255, 255, 255)  # 흰색
                                    subtitle_para.font.size = Pt(24)
                                except Exception as e:
                                    logger.warning(f"부제목 스타일 적용 실패: {e}")
                else:
                    # 내용 / 목차 / 마무리 외 일반 슬라이드
                    is_agenda = ('발표 목차' in slide_spec.title) or ('📑' in slide_spec.title)
                    slide_layout = prs.slide_layouts[6]  # Blank layout
                    slide = prs.slides.add_slide(slide_layout)

                    if is_agenda:
                        # 목차 전용 레이아웃
                        try:
                            slide.background.fill.solid()
                            slide.background.fill.fore_color.rgb = RGBColor(240, 246, 255)
                        except Exception:
                            pass
                        self._create_agenda_layout(slide, slide_spec)
                    else:
                        # 일반 내용 슬라이드: 흰색 배경 + 상단 색상 띠
                        try:
                            slide.background.fill.solid()
                            slide.background.fill.fore_color.rgb = RGBColor(255, 255, 255)
                            from pptx.enum.shapes import MSO_SHAPE
                            color_strip = slide.shapes.add_shape(
                                MSO_SHAPE.RECTANGLE,
                                Inches(0), Inches(0),
                                Inches(10), Inches(0.3)
                            )
                            color_strip.fill.solid()
                            color_strip.fill.fore_color.rgb = RGBColor(0, 102, 204)
                            color_strip.line.fill.background()
                        except Exception as e:
                            logger.warning(f"내용 슬라이드 배경 설정 실패: {e}")
                        self._create_three_tier_layout(slide, slide_spec)
                
                logger.info(f"✅ 슬라이드 {i+1} 완료")
            
            # 파일 저장
            prs.save(str(output_path))
            logger.info(f"✅ 원클릭 PPT 빌드 완료: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"build_quick_pptx 실패: {e}")
            raise

    def _add_simple_content(self, slide, spec: SlideSpec):
        """간단한 콘텐츠 추가 (목차 구분)"""
        try:
            # 콘텐츠 영역 찾기
            content_placeholder = None
            for shape in slide.placeholders:
                if shape.placeholder_format.idx == 1:  # 일반적으로 콘텐츠 플레이스홀더
                    content_placeholder = shape
                    break
            
            if not content_placeholder:
                logger.warning(f"⚠️ '{spec.title}' 슬라이드에 콘텐츠 플레이스홀더를 찾을 수 없습니다")
                return
            
            tf = content_placeholder.text_frame
            tf.clear()
            tf.word_wrap = True
            
            # 목차 슬라이드 구분
            is_agenda = spec.title in ['목차', 'Agenda', 'Contents']
            
            if is_agenda:
                # 목차: 불릿만 표시
                for i, bullet in enumerate(spec.bullets):
                    if bullet and bullet.strip():
                        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                        p.text = bullet.strip()
                        p.level = 0
                        p.font.size = Pt(20)
                        p.font.color.rgb = self.colors['text']
                        logger.info(f"✅ 목차 항목 추가: '{bullet[:30]}...'")
            else:
                # 일반 슬라이드: 키 메시지 + 불릿
                paragraph_added = False
                
                # 키 메시지 추가
                if spec.key_message and spec.key_message.strip():
                    p = tf.paragraphs[0]
                    p.text = spec.key_message.strip()
                    p.level = 0
                    p.font.size = Pt(22)
                    p.font.bold = True
                    p.font.color.rgb = self.colors['text']
                    paragraph_added = True
                    logger.info(f"✅ 키 메시지 추가: '{spec.key_message[:30]}...'")
                
                # 불릿 포인트 추가
                for i, bullet in enumerate(spec.bullets):
                    if bullet and bullet.strip():
                        if paragraph_added:
                            p = tf.add_paragraph()
                        else:
                            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                            paragraph_added = True
                        
                        p.text = f"• {bullet.strip()}"
                        p.level = 1
                        p.font.size = Pt(18)
                        p.font.color.rgb = self.colors['text']
                        logger.info(f"✅ 불릿 추가: '{bullet[:30]}...'")
            
            logger.info(f"🎯 '{spec.title}' 슬라이드 콘텐츠 완료")
            
        except Exception as e:
            logger.error(f"_add_simple_content 실패: {e}")

    def _parse_structured_content(self, lines: List[str], max_sections: int, exclude_title: Optional[str] = None) -> List[Dict[str, Any]]:
        """구조화된 컨텍스트에서 섹션별 상세 내용 추출"""
        sections = []
        current_section = None
        current_bullets = []
        in_detail_block = False  # 📝 상세 설명 블록 여부
        detail_block_patterns = [
            re.compile(r'^📝\s*(\*\*)?상세\s*설명(\*\*)?:'),
            re.compile(r'^(📝\s*)?상세\s*설명\s*:')
        ]
        key_message_patterns = [
            re.compile(r'^🔑\s*(\*\*)?키\s*메시지(\*\*)?:'),
            re.compile(r'^키\s*메시지\s*:')
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                # 빈 줄 -> 상세 설명 블록 종료 신호 가능
                if in_detail_block:
                    in_detail_block = False
                continue

            # 헤딩 패턴 감지 (더 정교한 조건)
            is_heading = False
            if line.startswith(('#', '##', '###')):
                is_heading = True
            elif (re.match(r'^\d+\.\s+[가-힣A-Za-z]', line) and len(line) <= 30):  # 짧은 제목일 때만 헤딩으로 인식
                is_heading = True
            elif (line.endswith(':') and len(line) <= 50 and
                  not re.match(r'.*[0-9]+.*[x×].*[0-9]+', line) and  # 크기/측정값이 아닌 경우
                  not re.search(r'[0-9]+\s*(units?|mg/dL|mm|g|일)', line)):  # 단위가 없는 경우
                is_heading = True

            # 키 메시지 패턴 감지
            if any(pat.match(line) for pat in key_message_patterns):
                if current_section:
                    key_msg = re.sub(r'^🔑\s*(\*\*)?키\s*메시지(\*\*)?:?\s*', '', line).strip()
                    if not key_msg:
                        key_msg = line.split(':', 1)[-1].strip()
                    current_section['key_message'] = key_msg[:300]
                    logger.info(f"🔑 키 메시지 캡처: section='{current_section.get('title','')}' len={len(key_msg)}")
                continue

            # 상세 설명 블록 시작 (변형 패턴 포함)
            if any(pat.match(line) for pat in detail_block_patterns):
                in_detail_block = True
                logger.info("📝 상세 설명 블록 시작")
                continue

            if is_heading:
                # 새 섹션 시작
                title = re.sub(r'^#+\s*|\d+\.\s*|:$', '', line).strip()
                
                # 문서 제목과 동일한 섹션은 제외 (중복 방지)
                if exclude_title and title == exclude_title:
                    logger.info(f"🚫 문서 제목과 동일한 섹션 제외: '{title}'")
                    continue
                
                # 이전 섹션 저장
                if current_section:
                    current_section['bullets'] = current_bullets[:6]
                    sections.append(current_section)
                
                current_section = {
                    'title': title,
                    'key_message': f"{title}의 핵심 내용입니다.",
                    'bullets': []
                }
                current_bullets = []
                
            elif current_section:
                # 현재 섹션의 내용 라인 처리
                # 상세 설명 블록이면 모두 상세 bullet 처리
                if in_detail_block:
                    if len(line) > 3:
                        current_bullets.append(line[:400])
                    continue
                if line.startswith('-'):
                    # 불릿 포인트
                    bullet_text = line.lstrip('- ').strip()
                    if bullet_text and len(bullet_text) > 5:
                        current_bullets.append(bullet_text)
                elif re.match(r'^\d+\.\s+', line) and len(line) > 30:  # 긴 numbered list는 bullet으로 처리
                    # 번호 목록 (1. 2. 3. 등)
                    bullet_text = re.sub(r'^\d+\.\s*', '', line).strip()
                    if bullet_text and len(bullet_text) > 5:
                        current_bullets.append(bullet_text)
                elif line.endswith(':') and len(line) <= 60:
                    # 소제목 (콜론으로 끝나는 짧은 라인)
                    subtitle = line.rstrip(':')
                    current_bullets.append(f"**{subtitle}**")
                elif ':' in line and len(line.split(':')) == 2:
                    # 키-값 쌍 (예: "크기: 60mm x 45mm x 15mm")
                    key, value = line.split(':', 1)
                    if len(key.strip()) <= 20 and len(value.strip()) > 0:
                        current_bullets.append(f"{key.strip()}: {value.strip()}")
                elif len(line) > 20 and not line.startswith('**'):
                    # 일반 텍스트 (키 메시지로 사용하거나 불릿으로 변환)
                    if (len(current_bullets) == 0 and len(line) <= 200 and
                        not re.search(r'^[가-힣A-Za-z]+:', line)):  # 키-값 형태가 아닌 경우
                        # 긴 문단은 키메시지로 사용
                        current_section['key_message'] = line
                    elif len(line) <= 200:  # 더 긴 텍스트도 bullet으로 허용
                        current_bullets.append(line)
                elif len(line) > 10:  # 짧은 텍스트도 bullet으로 추가
                    current_bullets.append(line)
                elif line.startswith('**') and line.endswith('**'):
                    # 굵은 텍스트 (소제목)
                    clean_text = line.strip('*')
                    if len(clean_text) <= 80:
                        current_bullets.append(clean_text)
        
        # 마지막 섹션 저장
        if current_section:
            current_section['bullets'] = current_bullets[:6]
            sections.append(current_section)
        
        # 빈 섹션이나 너무 적은 내용의 섹션 필터링 및 보완
        valid_sections = []
        for section in sections[:max_sections]:
            if section.get('title'):
                # 불릿이 없으면 키 메시지라도 있는지 확인
                if not section.get('bullets') and section.get('key_message'):
                    # 키 메시지를 불릿으로 변환
                    key_msg = section['key_message']
                    if len(key_msg) > 100:
                        # 긴 메시지는 문장 단위로 분할
                        sentences = [s.strip() for s in key_msg.split('.') if s.strip()]
                        section['bullets'] = sentences[:3]
                        section['key_message'] = f"{section['title']}에 대한 핵심 내용입니다."
                    else:
                        section['bullets'] = [key_msg]
                        section['key_message'] = f"{section['title']}에 대한 핵심 내용입니다."
                
                valid_sections.append(section)
        
        logger.info(f"📊 구조화 파싱 완료: {len(valid_sections)}개 유효 섹션")
        return valid_sections

    # ---------------- Pattern-based parser ----------------
    def _parse_ai_structured_sections(self, context_text: str, deck_title: str, max_sections: int) -> Optional[List[Dict[str, Any]]]:
        """general.prompt의 [발표 자료 생성 모드] 규칙에 따른 구조적 파싱
        
        파싱 대상 구조:
        1. ## [발표 제목] - 제목 슬라이드 (H2)
        2. ### 📋 발표 개요 - 제목 슬라이드의 상세 정보
        3. ### 📑 발표 목차 - 목차 슬라이드
        4. ### [슬라이드 제목] - 본문 슬라이드들 (H3)
        5. ### 📝 핵심 요약 또는 ### 🎯 향후 계획 및 실행방안 - 마무리 슬라이드
        """
        try:
            lines = [ln.rstrip() for ln in context_text.splitlines() if ln is not None]
            total = len(lines)
            logger.info(f"🧪 enhanced 패턴 파서 시작 lines={total}")

            sections: List[Dict[str, Any]] = []
            presentation_title = ""
            toc_content = []
            i = 0
            
            # 정규표현식 패턴 정의
            h2_regex = re.compile(r'^##\s+(.+)$')  # ## 제목
            h3_regex = re.compile(r'^###\s+(.+)$')  # ### 슬라이드 제목
            km_regex = re.compile(r'^🔑\s*\*\*(?:키\s*메시지|핵심\s*주제|다음\s*단계|주요\s*결론)\*\*:?\s*(.*)$')  # 🔑 **키 메시지/핵심 주제/다음 단계/주요 결론**:
            detail_regex = re.compile(r'^📝\s*\*\*(?:상세\s*설명|발표\s*배경|실행\s*계획|핵심\s*포인트)\*\*:?\s*(.*)$')  # 📝 **상세 설명/발표 배경/실행 계획/핵심 포인트**:
            overview_regex = re.compile(r'^###\s*📋\s*발표\s*개요')  # ### 📋 발표 개요
            toc_regex = re.compile(r'^###\s*📑\s*발표\s*목차')  # ### 📑 발표 목차
            # 정책 변경: 마무리 슬라이드는 이제 '### 감사합니다' 한 형태만 인정
            summary_regex = re.compile(r'^###\s*감사합니다\s*$')  # 마무리 슬라이드

            # 1. 제목 추출 (H2 레벨)
            while i < total:
                line = lines[i].strip()
                h2_match = h2_regex.match(line)
                if h2_match:
                    presentation_title = h2_match.group(1).strip()
                    logger.info(f"🎯 발표 제목 추출: '{presentation_title}'")
                    break
                i += 1
            
            # 2. H3 슬라이드들 파싱
            i = 0
            while i < total:
                line = lines[i].strip()
                h3_match = h3_regex.match(line)
                
                if h3_match:
                    slide_title = h3_match.group(1).strip()
                    
                    # 특수 슬라이드 처리
                    if overview_regex.match(line):
                        # 발표 개요 슬라이드 - 제목 슬라이드 정보로 처리하고 건너뜀
                        logger.info("🏷️ 발표 개요 슬라이드 발견 - 제목 슬라이드 정보로 처리")
                        i += 1
                        continue
                    elif toc_regex.match(line):
                        # 목차 슬라이드 - 별도 처리하고 건너뜀
                        logger.info("📑 목차 슬라이드 발견 - 별도 처리")
                        toc_content = self._extract_toc_content(lines, i)
                        i += 1
                        continue
                    elif summary_regex.match(line):
                        # 마무리 슬라이드 - 본문과 동일하게 처리하되 특별 표시
                        logger.info(f"🏁 마무리 슬라이드 발견: '{slide_title}'")
                    
                    # 일반 본문 슬라이드 파싱
                    key_message = ""
                    detail_bullets = []
                    j = i + 1
                    
                    # 다음 H3까지 또는 파일 끝까지 내용 수집
                    while j < total:
                        current_line = lines[j].strip()
                        
                        # 다음 H3 슬라이드 발견시 중단
                        if h3_regex.match(current_line):
                            break
                            
                        # 키 메시지 추출
                        km_match = km_regex.match(current_line)
                        if km_match:
                            key_message = km_match.group(1).strip()
                            logger.info(f"🔑 키 메시지 추출: '{key_message[:50]}...'")
                        
                        # 상세 설명 시작 감지
                        elif detail_regex.match(current_line):
                            # 📝 **상세 설명**: 이후 불릿 포인트들 수집
                            detail_match = detail_regex.match(current_line)
                            if detail_match and detail_match.group(1).strip():
                                # 같은 줄에 내용이 있으면 첫 번째 불릿으로 추가
                                detail_bullets.append(detail_match.group(1).strip())
                            
                            # 다음 줄부터 불릿 포인트들 수집
                            k = j + 1
                            while k < total:
                                bullet_line = lines[k].strip()
                                if not bullet_line:
                                    k += 1
                                    continue
                                # 다음 섹션 시작시 중단
                                if (h3_regex.match(bullet_line) or 
                                    km_regex.match(bullet_line) or 
                                    detail_regex.match(bullet_line)):
                                    break
                                # 불릿 포인트 수집
                                if bullet_line.startswith(('-', '•', '*')):
                                    bullet_text = bullet_line.lstrip('-•* ').strip()
                                    if bullet_text:
                                        detail_bullets.append(bullet_text[:300])
                                elif bullet_line and len(bullet_line) > 3:
                                    # 일반 텍스트도 불릿으로 처리
                                    detail_bullets.append(bullet_line[:300])
                                k += 1
                            j = k - 1  # 외부 루프 조정
                        
                        # 💡 패턴 없이도 불릿 포인트나 일반 텍스트 수집 (AI 응답 유연성 증대)
                        elif current_line.startswith(('-', '•', '*')):
                            bullet_text = current_line.lstrip('-•* ').strip()
                            if bullet_text:
                                detail_bullets.append(bullet_text[:300])
                                logger.info(f"📋 직접 불릿 수집: '{bullet_text[:30]}...'")
                        
                        # 💡 키워드로 시작하는 줄도 불릿으로 처리 (AI가 다양한 형식 사용)
                        elif current_line and len(current_line) > 10 and any(keyword in current_line for keyword in ["기능", "특징", "장점", "요구사항", "사양", "포인트"]):
                            detail_bullets.append(current_line[:300])
                            logger.info(f"📋 키워드 기반 불릿 수집: '{current_line[:30]}...'")
                        
                        j += 1
                    
                    # 슬라이드 정보가 충분한 경우 추가
                    if slide_title and (key_message or detail_bullets):
                        sections.append({
                            'title': slide_title,
                            'key_message': key_message or f"{slide_title}의 핵심 내용입니다.",
                            'bullets': detail_bullets[:8],  # 최대 8개 불릿
                            'slide_type': 'summary' if summary_regex.match(line) else 'content'
                        })
                        logger.info(f"📄 슬라이드 추가: '{slide_title}' (bullets: {len(detail_bullets)}개)")
                        
                        if len(sections) >= max_sections:
                            break
                    
                    i = j
                    continue
                
                i += 1

            # 결과 검증 및 반환
            if len(sections) >= 1:  # 1개 이상이면 사용 (기존 2개에서 완화)
                logger.info(f"✅ Enhanced 패턴 파싱 완료: {len(sections)}개 슬라이드")
                logger.info(f"📋 발표 제목: '{presentation_title}'")
                logger.info(f"📑 목차 항목: {len(toc_content)}개")
                
                # 목차와 실제 슬라이드 일치성 검증
                if toc_content and len(toc_content) > len(sections):
                    logger.warning(f"⚠️ 목차-슬라이드 불일치: 목차 {len(toc_content)}개 vs 실제 {len(sections)}개")
                    logger.warning(f"⚠️ 누락된 슬라이드: {toc_content[len(sections):]}")
                
                return sections
            else:
                logger.info("ℹ️ Enhanced 패턴 파싱 섹션 수 부족 -> None 반환")
                return None
                
        except Exception as e:
            logger.warning(f"Enhanced 패턴 파싱 실패: {e}")
            return None

    def _extract_toc_content(self, lines: List[str], start_index: int) -> List[str]:
        """목차 슬라이드에서 목차 항목들을 추출합니다."""
        toc_items = []
        i = start_index + 1
        
        try:
            while i < len(lines):
                line = lines[i].strip()
                
                # 다음 H3 슬라이드 발견시 중단
                if line.startswith('###'):
                    break
                    
                # 번호 목록 형태의 목차 항목 추출 (1. 항목명)
                if re.match(r'^\d+\.\s+', line):
                    item = re.sub(r'^\d+\.\s+', '', line).strip()
                    if item:
                        toc_items.append(item)
                # 불릿 형태의 목차 항목 추출 (- 항목명)
                elif line.startswith(('-', '•', '*')):
                    item = line.lstrip('-•* ').strip()
                    if item:
                        toc_items.append(item)
                
                i += 1
                
            logger.info(f"📑 목차 항목 {len(toc_items)}개 추출: {toc_items[:3]}...")
            return toc_items[:10]  # 최대 10개 항목
            
        except Exception as e:
            logger.warning(f"목차 추출 실패: {e}")
            return []

    def _merge_detail_sections(self, sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """'📝 상세 설명' 형태의 섹션을 직전 실제 섹션에 병합.
        - 제목이 '📝'로 시작하거나 '상세 설명' 포함 + 불릿만 있고 의미있는 key_message 거의 없으면 병합
        - 병합 시 불릿 extend, key_message 유지 (기존 key_message 우선)
        """
        if not sections:
            return sections
        merged: List[Dict[str, Any]] = []
        for sec in sections:
            title = sec.get('title','')
            is_detail_like = (title.startswith('📝') or '상세 설명' in title) and len(title) <= 20
            if is_detail_like and merged:
                prev = merged[-1]
                prev_bullets = prev.get('bullets', [])
                add_bullets = [b for b in sec.get('bullets', []) if b not in prev_bullets]
                if add_bullets:
                    prev['bullets'].extend(add_bullets)
                    logger.info(f"🔗 상세 설명 섹션 병합: '{title}' -> '{prev.get('title')}', 추가 불릿 {len(add_bullets)}개")
                # 상세 설명 섹션 자체는 추가하지 않음
                continue
            merged.append(sec)
        # 슬라이드 한도 보호
        return merged

    def _create_three_tier_layout(self, slide, slide_spec: SlideSpec):
        """3단계 구조 레이아웃 생성: 제목 + 키메시지 + 내용 (🎨 디자인 개선 + 시각화 요소 적용)"""
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN
        from pptx.dml.color import RGBColor
        from pptx.enum.dml import MSO_FILL
        
        try:
            # 🎨 시각화 힌트 감지
            viz_hints = self._detect_visualization_hints(slide_spec)
            
            # 표준 슬라이드 크기 사용 (16:9 비율)
            slide_width = Inches(10)
            slide_height = Inches(7.5)
            
            margin_lr = Inches(0.5)
            gap = Inches(0.3)

            # 1. 상단: 페이지 타이틀 텍스트 박스
            title_left = margin_lr
            title_top = Inches(0.5)
            title_width = slide_width - margin_lr * 2
            title_height = Inches(1)
            
            title_box = slide.shapes.add_textbox(title_left, title_top, title_width, title_height)
            title_frame = title_box.text_frame
            title_frame.text = slide_spec.title
            title_frame.margin_left = Inches(0.1)
            title_frame.margin_right = Inches(0.1)
            title_frame.margin_top = Inches(0.1)
            title_frame.margin_bottom = Inches(0.1)
            
            # 🎨 타이틀 박스 디자인 개선
            try:
                # 타이틀 박스 배경색 (연한 파란색)
                title_box.fill.solid()
                title_box.fill.fore_color.rgb = RGBColor(240, 247, 255)  # #F0F7FF
                
                # 타이틀 박스 테두리 (진한 파란색)
                title_box.line.color.rgb = RGBColor(0, 102, 204)  # #0066CC
                title_box.line.width = Pt(2)
                
                # 그림자 효과 추가 (기본 그림자 적용)
                try:
                    title_box.shadow.inherit = False
                    # 기본 그림자 설정 (MSO_SHADOW 없이)
                    title_box.shadow.distance = Pt(3)
                    title_box.shadow.blur_radius = Pt(4)
                    title_box.shadow.color.rgb = RGBColor(128, 128, 128)  # 회색 그림자
                except Exception as shadow_e:
                    logger.debug(f"그림자 효과 적용 실패 (정상): {shadow_e}")
                    
            except Exception as e:
                logger.warning(f"타이틀 박스 디자인 적용 실패: {e}")
            
            # 제목 스타일링
            title_para = title_frame.paragraphs[0]
            title_para.alignment = PP_ALIGN.LEFT
            title_font = title_para.font
            title_font.name = '맑은 고딕'
            title_font.size = Pt(28)
            title_font.bold = True
            title_font.color.rgb = RGBColor(0, 51, 102)  # 진한 파란색
            
            # 2. 중간: 키 메시지 텍스트 박스 (1-2줄)
            if slide_spec.key_message and slide_spec.key_message.strip():
                key_msg_left = margin_lr
                key_msg_top = Inches(1.8)
                key_msg_width = slide_width - margin_lr * 2
                key_msg_height = Inches(1.2)
                
                key_msg_box = slide.shapes.add_textbox(key_msg_left, key_msg_top, key_msg_width, key_msg_height)
                key_msg_frame = key_msg_box.text_frame
                key_msg_frame.text = slide_spec.key_message
                key_msg_frame.margin_left = Inches(0.15)
                key_msg_frame.margin_right = Inches(0.15)
                key_msg_frame.margin_top = Inches(0.15)
                key_msg_frame.margin_bottom = Inches(0.15)
                key_msg_frame.word_wrap = True
                
                # 🎨 키 메시지 박스 디자인 개선
                try:
                    # 연한 노란색 배경
                    key_msg_box.fill.solid()
                    key_msg_box.fill.fore_color.rgb = RGBColor(255, 248, 220)  # #FFF8DC
                    
                    # 주황색 테두리
                    key_msg_box.line.color.rgb = RGBColor(255, 153, 0)  # #FF9900
                    key_msg_box.line.width = Pt(1.5)
                    
                except Exception as e:
                    logger.warning(f"키 메시지 박스 디자인 적용 실패: {e}")
                
                # 키 메시지 스타일링
                key_msg_para = key_msg_frame.paragraphs[0]
                key_msg_para.alignment = PP_ALIGN.LEFT
                key_msg_font = key_msg_para.font
                key_msg_font.name = '맑은 고딕'
                key_msg_font.size = Pt(18)
                key_msg_font.bold = True  # 🎨 키 메시지를 굵게 강조
                key_msg_font.color.rgb = RGBColor(102, 51, 0)  # 🎨 진한 갈색으로 변경
                
                content_top = Inches(3.2)
            else:
                content_top = Inches(1.8)
            
            # 3. 본문 + 시각화 레이아웃 계산
            content_left = margin_lr
            content_width_full = slide_width - margin_lr * 2
            content_height_full = slide_height - content_top - Inches(0.5)

            # 단일 시각화 선택 (중복 방지: 차트 > 표 > 프로세스)
            viz_choice = "none"
            if viz_hints["chart"]:
                viz_choice = "chart"
            elif viz_hints["table"]:
                viz_choice = "table"
            elif viz_hints["process"]:
                viz_choice = "process"

            use_two_columns = viz_choice == "chart"  # 차트가 있으면 좌우 2단 구성

            if use_two_columns:
                # 좌: 텍스트, 우: 차트
                left_w = max(Inches(4.8), content_width_full * 0.52)
                right_w = content_width_full - left_w - gap
                content_width = left_w
                content_height = content_height_full
                chart_x = content_left + left_w + gap
                chart_y = content_top
                chart_cx = right_w
                chart_cy = content_height
            else:
                # 단일 컬럼 텍스트 상단, 시각화 하단
                content_width = content_width_full
                # 표/프로세스가 있으면 텍스트 영역 축소
                if viz_hints["table"] or viz_hints["process"]:
                    content_height = max(Inches(2.0), content_height_full * 0.5)
                else:
                    content_height = content_height_full

            # 텍스트 박스 생성 - 표나 프로세스가 불릿에서 파생되면 중복 방지
            content_box = None
            content_frame = None
            
            # 중복 방지 로직 강화: 표/프로세스가 불릿에서 생성될 때 텍스트 박스 생략
            show_text = True
            bullets_have_structure = False
            
            # 불릿에 구조화된 데이터가 있는지 확인
            if slide_spec.bullets:
                structured_count = 0
                for bullet in slide_spec.bullets:
                    if bullet and (":" in bullet or "|" in bullet or " - " in bullet):
                        structured_count += 1
                
                bullets_have_structure = structured_count >= len(slide_spec.bullets) * 0.6  # 60% 이상
            
            if viz_choice == "table" and (viz_hints.get("table_from_bullets", False) or bullets_have_structure):
                show_text = False
                logger.info("📋 표가 불릿에서 생성되므로 텍스트 박스 생략 (중복 방지)")
            elif viz_choice == "process" and (viz_hints.get("process_from_bullets", False) or bullets_have_structure):
                show_text = False
                logger.info("🔄 프로세스가 불릿에서 생성되므로 텍스트 박스 생략 (중복 방지)")

            if show_text and slide_spec.bullets and len(slide_spec.bullets) > 0:
                content_box = slide.shapes.add_textbox(content_left, content_top, content_width, content_height)
                content_frame = content_box.text_frame
                content_frame.margin_left = Inches(0.15)
                content_frame.margin_right = Inches(0.15)
                content_frame.margin_top = Inches(0.15)
                content_frame.margin_bottom = Inches(0.15)
                content_frame.word_wrap = True

                # 🎨 컨텐츠 박스 디자인
                try:
                    content_box.fill.solid()
                    content_box.fill.fore_color.rgb = RGBColor(248, 249, 250)
                    content_box.line.color.rgb = RGBColor(220, 220, 220)
                    content_box.line.width = Pt(1)
                except Exception as e:
                    logger.warning(f"컨텐츠 박스 디자인 적용 실패: {e}")

                # 🌈 불릿 포인트 색상 팔레트
                bullet_colors = [
                    RGBColor(0, 102, 204), RGBColor(51, 153, 102), RGBColor(255, 153, 0),
                    RGBColor(153, 51, 153), RGBColor(204, 51, 51), RGBColor(51, 102, 153),
                    RGBColor(153, 102, 51), RGBColor(102, 153, 153)
                ]

                bullet_icons = ["🔹", "🔸", "💎", "⭐", "🎯", "📌", "✨", "🔥"]

                max_bullets = 8 if not use_two_columns else 6
                for i, bullet in enumerate(slide_spec.bullets[:max_bullets]):
                    if not bullet or not bullet.strip():
                        continue
                    para = content_frame.paragraphs[0] if i == 0 else content_frame.add_paragraph()
                    para.text = f"{bullet_icons[i % len(bullet_icons)]} {bullet.strip()}"
                    para.alignment = PP_ALIGN.LEFT
                    para.level = 0
                    pf = para.font
                    pf.name = '맑은 고딕'
                    pf.size = Pt(16)
                    pf.color.rgb = bullet_colors[i % len(bullet_colors)]
                    para.space_after = Pt(8)

            # 시각화 요소 배치 (단일 선택)
            if viz_choice == "chart" and len(slide_spec.bullets) >= 3:
                logger.info(f"📊 차트 추가: {viz_hints['chart_type']}")
                self._create_sample_chart(
                    slide,
                    viz_hints["chart_type"],
                    slide_spec.title,
                    x=chart_x,
                    y=chart_y,
                    cx=chart_cx,
                    cy=chart_cy,
                )
            elif viz_choice in ("table", "process"):
                # 차트가 없으면 하단에 표 또는 프로세스를 배치
                viz_top = content_top + (content_height if content_frame else 0)
                viz_top += gap if content_frame else 0

                if viz_choice == "table" and len(slide_spec.bullets) >= 2:
                    logger.info("📋 표 추가")
                    self._create_simple_table(
                        slide,
                        slide_spec.title,
                        slide_spec.bullets,
                        x=margin_lr,
                        y=viz_top,
                        cx=content_width_full,
                        cy=max(Inches(1.8), slide_height - viz_top - Inches(0.5)),
                    )
                elif viz_choice == "process" and len(slide_spec.bullets) >= 3:
                    logger.info("🔄 프로세스 다이어그램 추가")
                    self._create_process_diagram(slide, slide_spec.title, slide_spec.bullets, y=viz_top)
            
            logger.info(f"✅ 3단계 레이아웃 생성 완료: '{slide_spec.title}' (시각화: {viz_hints})")
            
        except Exception as e:
            logger.error(f"3단계 레이아웃 생성 실패: {e}")

    def _create_agenda_layout(self, slide, slide_spec: SlideSpec):
        """목차(Agenda) 전용 레이아웃: 번호 + 항목 텍스트 수직 나열"""
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        try:
            title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(1))
            tf = title_box.text_frame
            tf.text = slide_spec.title.replace('📑', '').strip() or '목차'
            p = tf.paragraphs[0]
            p.font.size = Pt(34)
            p.font.bold = True
            p.font.color.rgb = RGBColor(20, 60, 110)

            # 항목 영역
            y_start = Inches(1.4)
            gap = Pt(8)
            num_w = Inches(0.5)
            text_left = Inches(1.2)
            max_items = min(12, len(slide_spec.bullets))
            for idx, raw in enumerate(slide_spec.bullets[:max_items]):
                if not raw:
                    continue
                y_off = y_start + Inches(0.55)*idx
                # 1) 배경 원을 먼저 생성하여 텍스트가 위에 오도록 함
                try:
                    from pptx.enum.shapes import MSO_SHAPE
                    circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.48), y_off, Inches(0.56), Inches(0.56))
                    circ.fill.solid()
                    # 더 어두운 블루로 대비 강화
                    circ.fill.fore_color.rgb = RGBColor(0,70,150)  # #004696
                    # 가는 테두리로 경계 강조
                    try:
                        circ.line.width = Pt(0.75)
                        circ.line.color.rgb = RGBColor(255,255,255)
                    except Exception:
                        pass
                except Exception:
                    circ = None  # 실패해도 계속 진행

                # 2) 번호 텍스트 박스 (원 위)
                num_box = slide.shapes.add_textbox(Inches(0.5), y_off, num_w, Inches(0.56))
                n_tf = num_box.text_frame
                n_tf.text = str(idx+1)
                n_p = n_tf.paragraphs[0]
                n_p.font.size = Pt(20)
                n_p.font.bold = True
                n_p.font.color.rgb = RGBColor(255,255,255)
                # 그림자(가독성 향상) - 실패해도 무시
                try:
                    shadow = num_box.shadow
                    shadow.inherit = False
                    shadow.blur_radius = Pt(4)
                except Exception:
                    pass

                # 3) 항목 텍스트
                item_box = slide.shapes.add_textbox(text_left, y_off, Inches(8), Inches(0.56))
                i_tf = item_box.text_frame
                i_tf.text = raw.strip()
                ip = i_tf.paragraphs[0]
                ip.font.size = Pt(20)
                ip.font.color.rgb = RGBColor(45,45,45)
        except Exception as e:
            logger.error(f"목차 레이아웃 생성 실패: {e}")


# 전역 인스턴스
quick_ppt_service = QuickPPTGeneratorService()

# ---------------------------------------------------------------------------
# Markdown Export Helper
#  - 일부 프론트엔드(채팅창)에서는 HTML 대신 general.prompt 규칙의 마크다운을
#    그대로 보여주길 원하므로 DeckSpec -> Markdown 변환 헬퍼를 제공한다.
#  - 기존 generate_fixed_outline 결과(슬라이드 순서)는 그대로 사용.
#  - HTML 전송 로직을 대체하여 "📝 PPT 생성 설정" 버튼 클릭 시 AI 답변 탭에
#    구조화된 마크다운이 출력되도록 활용된다.
# ---------------------------------------------------------------------------
def deck_to_markdown(deck: DeckSpec) -> str:
    """Convert a DeckSpec produced by QuickPPTGeneratorService into markdown
    following the formatting rules in general.prompt (발표 자료 생성 모드).

    Returns:
        str: markdown string
    """
    lines: list[str] = []
    if not deck.slides:
        return ""

    def _clean(txt: str) -> str:
        return (txt or "").strip()

    # 1. 제목 슬라이드 (첫 슬라이드 고정)
    first = deck.slides[0]
    topic = first.title or deck.topic or "발표자료"
    lines.append(f"## {topic}")
    lines.append("")
    lines.append("### 📋 발표 개요")
    key_msg = first.key_message or "발표의 핵심 내용을 한 문장으로 요약"
    lines.append(f"\n🔑 **핵심 주제**: {key_msg}")
    # 제목 슬라이드 불릿 -> 발표 배경 항목으로 사용
    title_bullets = first.bullets or []
    if title_bullets:
        lines.append("\n📝 **발표 배경**:")
        for b in title_bullets:
            lines.append(f"- {_clean(b)}")
    lines.append("")

    # 나머지 슬라이드 순회 (목차 / 본문 / 마무리)
    for slide in deck.slides[1:]:
        title = slide.title or ""
        norm_title = title.strip()
        is_thanks = bool(re.search(r"감사합니다|감사|Thank you|Thanks", norm_title, re.IGNORECASE))
        is_agenda = bool(re.search(r"목차|📑", norm_title)) and not is_thanks

        if is_agenda:
            lines.append("### 📑 발표 목차")
            # key_message -> 전체 구성 문장 (없으면 자동 생성)
            total_contents = sum(1 for s in deck.slides if s not in (deck.slides[0], slide) and not re.search(r"감사", s.title or ""))
            agenda_key = slide.key_message or f"총 {total_contents}개 슬라이드로 구성된 발표입니다"
            lines.append(f"\n🔑 **전체 구성**: {agenda_key}")
            bullets = slide.bullets or []
            if bullets:
                lines.append("\n📝 **주요 내용**:")
                for i, b in enumerate(bullets, start=1):
                    # 기존 숫자/불릿 제거 후 재번호 매김
                    cleaned = re.sub(r'^\s*(\d+\.|[-•])\s*', '', _clean(b))
                    lines.append(f"{i}. {cleaned}")
            lines.append("")
            continue

        if is_thanks:
            lines.append("### 감사합니다")
            lines.append("\n🔑 **메시지**: 감사합니다")
            lines.append("")
            continue

        # 일반 본문 슬라이드
        lines.append(f"### {norm_title}")
        key = slide.key_message or f"{norm_title}의 핵심 내용을 요약합니다."
        lines.append(f"\n🔑 **키 메시지**: {key}")
        bullets = slide.bullets or []
        if bullets:
            lines.append("\n📝 **상세 설명**:")
            for b in bullets:
                lines.append(f"- {_clean(b)}")
        lines.append("")

    # Trim trailing blank lines
    while lines and lines[-1].strip() == "":
        lines.pop()
    return "\n".join(lines) + "\n"

