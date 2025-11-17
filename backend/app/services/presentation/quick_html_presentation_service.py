"""Quick HTML Presentation Service

Generates a self-contained HTML slide deck from DeckSpec/SlideSpec.
Keeps core policies aligned with PPT generator: exclusive visualization per slide,
numeric gating for charts, and optional table/process extraction from bullets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from html import escape
import re
from pathlib import Path
import math

from loguru import logger

from app.core.config import settings
from .ppt_models import DeckSpec, SlideSpec


@dataclass
class HTMLBuildResult:
    html: str
    saved_path: Optional[str] = None


class QuickHTMLPresentationService:
    def __init__(self) -> None:
        self.upload_dir = Path(settings.file_upload_path or settings.upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    # ---- Public API ----
    def build_quick_html(self, spec: DeckSpec, file_basename: Optional[str] = None, save: bool = False) -> HTMLBuildResult:
        """Builds a single HTML document for the given deck spec.

        Returns HTMLBuildResult with inline CSS/markup. If save=True, also writes to uploads and returns the path.
        """
        logger.info(f"[HTML] Building deck: topic='{spec.topic}', slides={len(spec.slides)}")
        html = self._render_deck(spec)

        saved_path: Optional[str] = None
        if save:
            name = (file_basename or (spec.topic or 'deck')).strip() or 'deck'
            safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
            out_path = self.upload_dir / f"{safe_name}.html"
            out_path.write_text(html, encoding='utf-8')
            saved_path = str(out_path)
            logger.info(f"[HTML] Saved: {saved_path}")

        return HTMLBuildResult(html=html, saved_path=saved_path)

    # ---- Rendering ----
    def _render_deck(self, spec: DeckSpec) -> str:
        head = self._render_head()
        body = self._render_body(spec)
        return f"<!DOCTYPE html>\n<html lang=\"ko\">\n{head}\n{body}\n</html>"

    def _render_head(self) -> str:
        # Rich CSS theme for PPT-like visuals
        return """
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>프레젠테이션</title>
<style>
:root{--bg:#0b1220;--paper:#ffffff;--soft:#f5f7fb;--fg:#101828;--muted:#667085;--pri:#2563eb;--pri-700:#1d4ed8;--acc:#f97316;--succ:#10b981;--warn:#f59e0b;}
html,body{margin:0;padding:0;background:linear-gradient(160deg,#eef2ff 0%,#f8fafc 100%);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,'Noto Sans KR','Apple SD Gothic Neo','맑은 고딕',sans-serif;}
.deck{padding:28px;}
.slide{background:var(--paper);border-radius:16px;box-shadow:0 8px 32px rgba(16,24,40,.12);padding:36px;margin:24px auto;max-width:1200px;position:relative;overflow:hidden;}
.slide.role-title{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);color:#e2e8f0;padding:64px 48px;}
.slide.role-title .title{color:#f8fafc;} .slide.role-title .key{color:#cbd5e1;}
.slide.role-agenda .title{color:#111827;} .slide.role-agenda .bullets li{margin:8px 0;}
.slide.role-agenda ol.agenda-list{list-style:none;margin:16px 0 0 0;padding:0;counter-reset:agenda;display:flex;flex-direction:column;gap:10px;}
.slide.role-agenda ol.agenda-list li{display:flex;align-items:center;gap:14px;background:#f1f5f9;padding:12px 16px;border-radius:12px;box-shadow:0 1px 2px rgba(0,0,0,.05);}
.slide.role-agenda ol.agenda-list li .agenda-num{width:34px;height:34px;border-radius:50%;background:linear-gradient(180deg,#3b82f6,#1d4ed8);color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;box-shadow:0 4px 10px -2px rgba(29,78,216,.4);}
.slide.role-agenda ol.agenda-list li .agenda-text{font-weight:600;color:#0f172a;letter-spacing:.2px;}
.slide.role-thanks{display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;min-height:400px;background:linear-gradient(135deg,#f8fafc 0%,#e2e8f0 100%);}
.slide.role-thanks .title{font-size:48px;font-weight:900;color:#1e293b;margin:0;}
.slide.role-thanks .key{font-size:24px;color:#64748b;margin:16px 0 0 0;}
.slide::after{content:'';position:absolute;inset:auto -40px -40px auto;width:240px;height:240px;background:radial-gradient(closest-side,rgba(37,99,235,.15),transparent);border-radius:50%;filter:blur(6px);}
.title{font-size:32px;font-weight:800;margin:0 0 10px;} .key{font-size:18px;color:var(--muted);margin:10px 0 18px;}
.content{display:flex;gap:20px;align-items:flex-start;} .col{flex:1 1 0;}
.content.stack{flex-direction:column;} .content.split{align-items:stretch;}
.bullets{margin:0;padding-left:20px;} .bullets li{margin:6px 0;line-height:1.5;}
.table-wrap{overflow:auto;border:1px solid #e5e7eb;border-radius:10px;background:#fff} table{border-collapse:collapse;width:100%;}
th,td{border-bottom:1px solid #e5e7eb;padding:10px 12px;font-size:14px;text-align:left;} th{background:#f9fafb;font-weight:700;color:#0f172a;}
.viz{display:flex;justify-content:center;align-items:center;} svg{max-width:100%;height:auto;}
.axis text{fill:#64748b;font-size:12px} .grid line{stroke:#e2e8f0} .bar{filter:drop-shadow(0 1px 2px rgba(0,0,0,.15));}
.badge{display:inline-flex;gap:8px;align-items:center;font-weight:700;font-size:12px;background:#eff6ff;color:#1e40af;padding:6px 10px;border-radius:999px;border:1px solid #dbeafe;}
.stepper{display:flex;justify-content:center;gap:24px;flex-wrap:wrap;margin-top:8px}
.step-item{display:flex;flex-direction:column;align-items:center;min-width:120px}
.step-circle{width:40px;height:40px;border-radius:999px;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#60a5fa,#2563eb);color:#fff;font-weight:800;box-shadow:0 4px 12px rgba(37,99,235,.35)}
.step-label{margin-top:8px;color:#0f172a;font-weight:600;text-align:center}
.connector{align-self:center;width:56px;height:4px;border-radius:2px;background:#c7d2fe;box-shadow:inset 0 0 0 1px #bfdbfe}
.meta{font-size:12px;color:#6b7280;margin-top:8px;}
</style>
</head>
"""

    def _render_body(self, spec: DeckSpec) -> str:
        # Fallback: ensure at least one content slide besides title/thanks
        slides = list(spec.slides)
        if slides:
            non_meta = [s for s in slides if not re.search(r"감사|thank", (s.title or ''), re.IGNORECASE) and not (slides.index(s) == 0)]
            only_title_and_thanks = (len(slides) <= 2 and any(re.search(r"감사|thank", (s.title or ''), re.IGNORECASE) for s in slides))
            only_thanks = (len(slides) == 1 and any(re.search(r"감사|thank", (s.title or ''), re.IGNORECASE) for s in slides))
            if (not non_meta) and (only_title_and_thanks or only_thanks):
                topic = spec.topic or '발표자료'
                from .ppt_models import SlideSpec as _SS
                synth = _SS(
                    title=f"{topic} 개요",
                    key_message=f"{topic}의 핵심 개요를 요약합니다.",
                    bullets=["주요 특징 및 장점", "핵심 구성 요소", "활용/적용 방안"],
                    layout="title-and-content"
                )
                # 삽입 위치: 제목 뒤(있다면) / 아니면 맨 앞
                insert_pos = 1 if len(slides) and not re.search(r"감사|thank", (slides[0].title or ''), re.IGNORECASE) else 0
                slides.insert(insert_pos, synth)
                logger.warning("[HTML] 본문 슬라이드 누락으로 자동 개요 슬라이드 삽입")
        slides_html = [self._render_slide(i, s, len(slides)) for i, s in enumerate(slides)]
        return f"<body><div class=\"deck\">{''.join(slides_html)}</div></body>"

    def _render_slide(self, idx: int, s: SlideSpec, total: int) -> str:
        title = escape(s.title or "")
        key = escape(s.key_message or "")
        bullets = s.bullets or []

        # Determine semantic role
        role = None
        if getattr(s, 'style', None) and isinstance(s.style, dict):
            role = s.style.get('role')
        if not role:
            if idx == 0:
                role = 'title'
            elif re.search(r"목차|\bTOC\b|\bAgenda\b|📑", s.title or ''):
                role = 'agenda'
            elif re.search(r"감사합니다|감사|Thank you|Thanks", s.title or '', re.IGNORECASE):
                role = 'thanks'
            else:
                role = 'content'

        # Detect visualization (exclusive)
        hints = self._detect_visualization_hints(s)
        choice = 'none'
        if hints['chart']:
            # choose donut if sums to ~100
            vals = [p[1] for p in (hints.get('pairs') or [])]
            s_val = sum(vals) if vals else 0
            if vals and 85 <= s_val <= 115:
                choice = 'donut'
            else:
                choice = 'chart'
        elif hints['table']:
            choice = 'table'
        elif hints['process']:
            choice = 'process'

        left = self._render_bullets(bullets) if not (choice in ('table','process') and hints.get(f'{choice}_from_bullets')) else ''
        right = ''
        below = ''

        if choice == 'chart':
            right = self._render_chart_svg(hints)
        elif choice == 'donut':
            right = self._render_donut_svg(hints)
        elif choice == 'table':
            below = self._render_table_from_bullets(bullets)
        elif choice == 'process':
            below = self._render_process(bullets)

        # Layout: chart/donut -> split columns, else stack
        if choice in ('chart','donut'):
            content = f"<div class='content split'><div class='col'>{left}</div><div class='col viz'>{right}</div></div>"
        else:
            content = f"<div class='content stack'><div class='col'>{left}</div><div class='col'>{below}</div></div>"

        # Title/Agenda/Thanks special rendering
        role_cls = f"role-{role}" if role else ''
        if role == 'title':
            hero = (
                f"<section class='slide {role_cls}' data-index='{idx}'>"
                f"<div class='badge'>📊 프레젠테이션</div>"
                f"<h1 class='title' style='font-size:48px;line-height:1.1;margin:10px 0 12px'>{title}</h1>"
                f"<div class='key' style='font-size:20px'>{key}</div>"
                f"</section>"
            )
            return hero
        elif role == 'thanks':
            thanks = (
                f"<section class='slide {role_cls}' data-index='{idx}'>"
                f"<h1 class='title'>{title}</h1>"
                f"<div class='key'>{key}</div>"
                f"</section>"
            )
            return thanks

        if role == 'agenda':
            # 번호는 렌더링 단계에서 동적으로 부여 (불릿에 사전 번호 금지)
            items_html = []
            for n, txt in enumerate(bullets, start=1):
                safe = escape(re.sub(r'^\s*(\d+\.|[-•])\s*', '', txt))
                items_html.append(f"<li><span class='agenda-num'>{n}</span><span class='agenda-text'>{safe}</span></li>")
            agenda_html = f"<ol class='agenda-list'>{''.join(items_html)}</ol>"
            return f"<section class='slide {role_cls}' data-index='{idx}'><h2 class='title'>{title}</h2><div class='key'>{key}</div>{agenda_html}</section>"

        return f"<section class='slide {role_cls}' data-index='{idx}'><h2 class='title'>{title}</h2><div class='key'>{key}</div>{content}</section>"

    # ---- Helpers ----
    def _render_bullets(self, bullets: List[str]) -> str:
        if not bullets:
            return ""
        items = ''.join(f"<li>{escape(b)}</li>" for b in bullets)
        return f"<ul class='bullets'>{items}</ul>"

    def _detect_visualization_hints(self, s: SlideSpec) -> Dict[str, Any]:
        text = ' '.join([s.title or '', s.key_message or '', *[b or '' for b in (s.bullets or [])]])
        numeric_score = len(re.findall(r"\d+%?|%", text))
        # detect pairs label: number
        pairs: List[Tuple[str, float]] = []
        for b in s.bullets or []:
            m = re.match(r"\s*([^:：]+)\s*[:：]\s*([\d.]+)%?\s*$", b)
            if m:
                label = m.group(1).strip()
                try:
                    val = float(m.group(2))
                except Exception:
                    continue
                pairs.append((label, val))

        table_from_bullets = len(pairs) >= 2
        process_from_bullets = any(re.match(r"^\s*([0-9]+[.)]|[①-⑤]|step\s*\d+|단계)\s*", b, re.I) for b in (s.bullets or []))

        # choose
        chart = numeric_score >= 2 and len(pairs) >= 2
        table = (not chart) and table_from_bullets
        process = (not chart and not table) and process_from_bullets

        return {
            'chart': chart,
            'table': table,
            'process': process,
            'pairs': pairs,
            'numeric_score': numeric_score,
            'table_from_bullets': table_from_bullets,
            'process_from_bullets': process_from_bullets,
        }

    def _render_table_from_bullets(self, bullets: List[str]) -> str:
        rows: List[Tuple[str, str]] = []
        for b in bullets or []:
            m = re.match(r"\s*([^:：]+)\s*[:：]\s*(.+)$", b)
            if m:
                rows.append((m.group(1).strip(), m.group(2).strip()))
        if not rows:
            return ''
        thead = "<thead><tr><th>항목</th><th>내용</th></tr></thead>"
        body = ''.join(f"<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>" for k, v in rows)
        return f"<div class='table-wrap'><table>{thead}<tbody>{body}</tbody></table></div>"

    def _render_process(self, bullets: List[str]) -> str:
        steps = [re.sub(r"^\s*([0-9]+[.)]|[①-⑤]|step\s*\d+|단계)\s*", "", b, flags=re.I).strip() for b in (bullets or [])]
        steps = [s for s in steps if s][:5]
        if not steps:
            return ''
        # SVG-like stepper using styled divs
        parts: List[str] = []
        for i, st in enumerate(steps):
            parts.append(
                "<div class='step-item'>"
                f"<div class='step-circle'>{i+1}</div>"
                f"<div class='step-label'>{escape(st)}</div>"
                "</div>"
            )
            if i + 1 < len(steps):
                parts.append("<div class='connector'></div>")
        return f"<div class='stepper'>{''.join(parts)}</div>"

    def _render_chart_svg(self, hints: Dict[str, Any]) -> str:
        pairs: List[Tuple[str, float]] = hints.get('pairs') or []
        if not pairs:
            return ''
        # Enhanced horizontal bar chart with grid and gradients
        labels = [p[0] for p in pairs][:6]
        values = [p[1] for p in pairs][:6]
        max_val = max(values) if values else 0.0
        width, bar_h, gap, left_w, right_pad, top_pad, bottom_pad = 720, 26, 12, 140, 24, 24, 28
        chart_h = top_pad + bottom_pad + len(labels) * (bar_h + gap) - gap
        svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {chart_h}' role='img' aria-label='막대 차트'>",
               "<defs>",
               "<linearGradient id='barGrad' x1='0' x2='1' y1='0' y2='0'>",
               "<stop offset='0%' stop-color='#60a5fa'/>",
               "<stop offset='100%' stop-color='#2563eb'/>",
               "</linearGradient>",
               "</defs>"]
        # grid
        grid_x0 = left_w
        grid_x1 = width - right_pad
        steps = 4
        for i in range(steps + 1):
            gx = grid_x0 + (grid_x1 - grid_x0) * i / steps
            svg.append(f"<line class='grid' x1='{gx}' y1='{top_pad-6}' x2='{gx}' y2='{chart_h-bottom_pad+6}' stroke='#e2e8f0' stroke-width='1' />")
            tick_val = (max_val * i / steps) if max_val > 0 else 0
            svg.append(f"<text class='axis' x='{gx}' y='{top_pad-10}' text-anchor='middle'>{tick_val:g}</text>")
        # bars
        y = top_pad
        for label, v in zip(labels, values):
            w = 0 if max_val <= 0 else (grid_x1 - grid_x0) * (v / max_val)
            svg.append(f"<text class='axis' x='{left_w-10}' y='{y+bar_h-8}' text-anchor='end'>{escape(label)}</text>")
            svg.append(f"<rect class='bar' x='{left_w}' y='{y}' width='{max(0,int(w))}' height='{bar_h}' rx='6' fill='url(#barGrad)' />")
            svg.append(f"<text x='{left_w + w + 8}' y='{y+bar_h-8}' fill='#0f172a' font-weight='700'>{v:g}</text>")
            y += bar_h + gap
        svg.append("</svg>")
        return ''.join(svg)

    def _render_donut_svg(self, hints: Dict[str, Any]) -> str:
        pairs: List[Tuple[str, float]] = hints.get('pairs') or []
        if not pairs:
            return ''
        labels = [p[0] for p in pairs][:6]
        values = [max(0.0, float(p[1])) for p in pairs][:6]
        total = sum(values)
        if total <= 0:
            return ''
        # donut geometry
        cx, cy, r1, r2 = 180, 140, 60, 100
        colors = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4']
        svg = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 360 220' role='img' aria-label='도넛 차트'>"]
        start = -math.pi/2
        for i, (label, val) in enumerate(zip(labels, values)):
            frac = val / total
            if frac <= 0:
                continue
            end = start + frac * 2 * math.pi
            large = 1 if (end - start) > math.pi else 0
            x1, y1 = cx + r2*math.cos(start), cy + r2*math.sin(start)
            x2, y2 = cx + r2*math.cos(end), cy + r2*math.sin(end)
            xi, yi = cx + r1*math.cos(end), cy + r1*math.sin(end)
            xj, yj = cx + r1*math.cos(start), cy + r1*math.sin(start)
            path = (
                f"M {x1:.2f} {y1:.2f} "
                f"A {r2} {r2} 0 {large} 1 {x2:.2f} {y2:.2f} "
                f"L {xi:.2f} {yi:.2f} "
                f"A {r1} {r1} 0 {large} 0 {xj:.2f} {yj:.2f} Z"
            )
            color = colors[i % len(colors)]
            svg.append(f"<path d='{path}' fill='{color}' opacity='0.92'></path>")
            # label
            mid = (start + end)/2
            lx, ly = cx + (r2+18)*math.cos(mid), cy + (r2+18)*math.sin(mid)
            svg.append(f"<text x='{lx:.2f}' y='{ly:.2f}' font-size='12' fill='#0f172a' text-anchor='middle'>{escape(label)}</text>")
            start = end
        svg.append(f"<circle cx='{cx}' cy='{cy}' r='{r1-2}' fill='#ffffff' stroke='#e5e7eb' />")
        svg.append("</svg>")
        return ''.join(svg)


quick_html_service = QuickHTMLPresentationService()
