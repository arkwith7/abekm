#!/usr/bin/env python3
"""
템플릿 없는 PPT 디자인 개선 예시 코드
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_FILL

def apply_enhanced_design_to_quick_ppt():
    """템플릿 없는 PPT에 적용 가능한 디자인 개선사항들"""
    
    print("🎨 템플릿 없는 PPT 디자인 개선 방안:")
    print("=" * 60)
    
    print("\n1. 📄 슬라이드 배경색 적용:")
    print("   - 제목 슬라이드: 진한 파란색 배경 (#003366)")
    print("   - 목차 슬라이드: 연한 파란색 배경 (#E6F3FF)")
    print("   - 내용 슬라이드: 흰색 배경 + 상단 색상 띠")
    print("   - 마무리 슬라이드: 그라데이션 배경")
    
    print("\n2. 🎯 페이지 타이틀 디자인:")
    print("   - 배경색이 있는 타이틀 박스")
    print("   - 둥근 모서리 적용")
    print("   - 그림자 효과")
    print("   - 아이콘 추가 (📊, 🔒, 💡 등)")
    
    print("\n3. 📝 텍스트박스 데코레이션:")
    print("   - 키 메시지: 연한 노란색 배경 + 굵은 테두리")
    print("   - 불릿 포인트: 색상별 불릿 아이콘")
    print("   - 중요 내용: 강조 박스 (색상 배경)")
    
    print("\n4. 🔧 적용 가능한 python-pptx 메소드들:")
    
    design_methods = {
        "배경색 설정": [
            "slide.background.fill.solid()",
            "slide.background.fill.fore_color.rgb = RGBColor(r, g, b)"
        ],
        "텍스트박스 배경": [
            "textbox.fill.solid()",
            "textbox.fill.fore_color.rgb = RGBColor(r, g, b)",
            "textbox.fill.transparency = 0.2  # 투명도"
        ],
        "테두리 효과": [
            "textbox.line.color.rgb = RGBColor(r, g, b)",
            "textbox.line.width = Pt(2)",
            "textbox.line.dash_style = MSO_LINE.DASH"
        ],
        "그림자 효과": [
            "textbox.shadow.inherit = False",
            "textbox.shadow.style = MSO_SHADOW.OFFSET_DIAGONAL",
            "textbox.shadow.distance = Pt(3)"
        ],
        "그라데이션": [
            "shape.fill.gradient()",
            "shape.fill.gradient_stops[0].color.rgb = RGBColor(r1, g1, b1)",
            "shape.fill.gradient_stops[1].color.rgb = RGBColor(r2, g2, b2)"
        ]
    }
    
    for category, methods in design_methods.items():
        print(f"\n   🎨 {category}:")
        for method in methods:
            print(f"      • {method}")
    
    print("\n5. 🌈 색상 팔레트 제안:")
    color_palettes = {
        "비즈니스 블루": {
            "primary": "#003366",
            "secondary": "#0066CC", 
            "accent": "#3399FF",
            "background": "#F0F7FF",
            "text": "#FFFFFF"
        },
        "프로페셔널 그린": {
            "primary": "#1B5E20",
            "secondary": "#388E3C",
            "accent": "#66BB6A", 
            "background": "#E8F5E8",
            "text": "#FFFFFF"
        },
        "모던 그레이": {
            "primary": "#37474F",
            "secondary": "#607D8B",
            "accent": "#90A4AE",
            "background": "#F5F5F5",
            "text": "#FFFFFF"
        }
    }
    
    for palette_name, colors in color_palettes.items():
        print(f"\n   🎨 {palette_name}:")
        for color_type, hex_code in colors.items():
            print(f"      • {color_type}: {hex_code}")

def demonstrate_design_code():
    """실제 적용 가능한 코드 예시"""
    
    print("\n" + "=" * 60)
    print("🛠️ 실제 구현 코드 예시:")
    print("=" * 60)
    
    code_examples = {
        "슬라이드 배경색": '''
# 슬라이드 배경색 설정
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = RGBColor(0, 51, 102)  # 진한 파란색
        ''',
        
        "타이틀 박스 배경": '''
# 타이틀 텍스트박스에 배경색과 테두리 추가
title_box.fill.solid()
title_box.fill.fore_color.rgb = RGBColor(0, 102, 204)  # 파란색 배경
title_box.line.color.rgb = RGBColor(0, 51, 102)        # 진한 파란색 테두리
title_box.line.width = Pt(2)
        ''',
        
        "키 메시지 강조": '''
# 키 메시지 박스에 노란색 배경 + 그림자
key_msg_box.fill.solid()
key_msg_box.fill.fore_color.rgb = RGBColor(255, 248, 220)  # 연한 노란색
key_msg_box.shadow.inherit = False
key_msg_box.shadow.style = MSO_SHADOW.OFFSET_DIAGONAL
key_msg_box.shadow.distance = Pt(3)
        ''',
        
        "불릿 포인트 색상": '''
# 불릿 포인트별 다른 색상 적용
bullet_colors = [
    RGBColor(0, 102, 204),    # 파란색
    RGBColor(51, 153, 102),   # 초록색  
    RGBColor(255, 153, 0),    # 주황색
    RGBColor(153, 51, 153)    # 보라색
]

for i, bullet in enumerate(slide_spec.bullets):
    para.font.color.rgb = bullet_colors[i % len(bullet_colors)]
        '''
    }
    
    for title, code in code_examples.items():
        print(f"\n🔧 {title}:")
        print(code)

if __name__ == "__main__":
    apply_enhanced_design_to_quick_ppt()
    demonstrate_design_code()
    
    print("\n" + "=" * 60)
    print("✅ 디자인 개선 가능성 분석 완료")
    print("📝 다음 단계: quick_ppt_generator_service.py 파일 수정")
    print("=" * 60)
