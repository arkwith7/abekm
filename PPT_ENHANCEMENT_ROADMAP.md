# 🎨 PPT 템플릿 메타데이터 기반 고급 생성 시스템 개선 계획

## 📋 현재 상황 분석

### ✅ **현재 두 가지 PPT 생성 방식**
1. **"PPT로 만들기"**: 기본 구조화된 PPT (개선 대상 아님)
2. **"PPT 아웃라인 보기"**: 템플릿 기반 디자인 적용 PPT (🎯 집중 개선 대상)

### 🎯 **개선 목표**
- 템플릿의 디자인, 도식화, 폰트, 컬러 등 모든 스타일 메타데이터 추출
- 사용자가 텍스트만 제공하면 템플릿과 동일한 디자인이 자동 적용
- 페이지별 유연한 내용 추가/변경 기능

## 🔧 **1단계: 템플릿 메타데이터 추출 시스템**

### **1.1 Backend - 템플릿 분석 서비스 확장**

```python
# backend/app/services/presentation/template_metadata_extractor.py
class TemplateMetadataExtractor:
    """템플릿의 모든 디자인 메타데이터를 추출하고 관리"""
    
    def extract_comprehensive_metadata(self, template_path: Path) -> Dict[str, Any]:
        return {
            'design_system': self._extract_design_system(),
            'color_palette': self._extract_color_palette(),
            'typography': self._extract_typography(),
            'layout_patterns': self._extract_layout_patterns(),
            'slide_layouts': self._extract_slide_layouts(),
            'shape_styles': self._extract_shape_styles(),
            'chart_styles': self._extract_chart_styles(),
            'animation_styles': self._extract_animation_styles()
        }
    
    def _extract_design_system(self) -> Dict[str, Any]:
        """디자인 시스템 추출 (마스터 슬라이드, 테마 등)"""
        pass
    
    def _extract_color_palette(self) -> List[Dict[str, str]]:
        """색상 팔레트 추출"""
        pass
    
    def _extract_typography(self) -> Dict[str, Any]:
        """폰트, 텍스트 스타일 추출"""
        pass
    
    def _extract_layout_patterns(self) -> List[Dict[str, Any]]:
        """레이아웃 패턴 분석"""
        pass
```

### **1.2 Backend - API 확장**

```python
# backend/app/api/v1/chat.py - 새로운 엔드포인트 추가

@router.get("/presentation/templates/{template_id}/metadata")
async def get_template_metadata(template_id: str):
    """템플릿의 상세 메타데이터 반환"""
    pass

@router.get("/presentation/templates/{template_id}/design-system")
async def get_template_design_system(template_id: str):
    """템플릿의 디자인 시스템 정보 반환"""
    pass

@router.post("/presentation/build-with-style-transfer")
async def build_with_style_transfer(request: StyleTransferRequest):
    """텍스트를 템플릿 스타일로 자동 변환하여 PPT 생성"""
    pass
```

## 🔧 **2단계: Frontend UX 개선**

### **2.1 PresentationOutlineModal 고도화**

```tsx
// frontend/src/pages/user/chat/components/presentation/PresentationOutlineModal.tsx

interface TemplateMetadata {
    id: string;
    name: string;
    designSystem: {
        colorPalette: ColorPalette;
        typography: Typography;
        layoutPatterns: LayoutPattern[];
    };
    slideLayouts: SlideLayout[];
    previewThumbnails: string[];
}

const PresentationOutlineModal: React.FC<Props> = ({ ... }) => {
    const [templateMetadata, setTemplateMetadata] = useState<TemplateMetadata | null>(null);
    const [isStyleTransferEnabled, setIsStyleTransferEnabled] = useState(true);
    
    // 템플릿 메타데이터 로드
    useEffect(() => {
        if (selectedTemplateId) {
            loadTemplateMetadata(selectedTemplateId);
        }
    }, [selectedTemplateId]);
    
    const loadTemplateMetadata = async (templateId: string) => {
        // API 호출하여 템플릿 메타데이터 로드
    };
    
    return (
        <div className="enhanced-outline-modal">
            {/* 개선된 탭 구조 */}
            <EnhancedTabNavigation />
            
            {/* 템플릿 프리뷰 및 메타데이터 */}
            <TemplatePreviewPanel metadata={templateMetadata} />
            
            {/* 실시간 스타일 적용 에디터 */}
            <LiveStyleEditor 
                outline={outline}
                templateMetadata={templateMetadata}
                onStyleChange={handleStyleChange}
            />
            
            {/* 페이지별 세부 편집 */}
            <SlideBySlideEditor 
                slides={outline.sections}
                templateMetadata={templateMetadata}
                onSlideChange={handleSlideChange}
            />
        </div>
    );
};
```

### **2.2 새로운 컴포넌트들**

```tsx
// LiveStyleEditor: 실시간 스타일 적용 에디터
const LiveStyleEditor: React.FC<{
    outline: OutlineData;
    templateMetadata: TemplateMetadata;
    onStyleChange: (changes: StyleChanges) => void;
}> = ({ outline, templateMetadata, onStyleChange }) => {
    return (
        <div className="live-style-editor">
            <ColorPaletteSelector palette={templateMetadata.designSystem.colorPalette} />
            <TypographySelector typography={templateMetadata.designSystem.typography} />
            <LayoutPatternSelector patterns={templateMetadata.designSystem.layoutPatterns} />
            <RealTimePreview outline={outline} appliedStyles={appliedStyles} />
        </div>
    );
};

// SlideBySlideEditor: 페이지별 세부 편집
const SlideBySlideEditor: React.FC<{
    slides: SlideSection[];
    templateMetadata: TemplateMetadata;
    onSlideChange: (slideId: string, changes: SlideChanges) => void;
}> = ({ slides, templateMetadata, onSlideChange }) => {
    return (
        <div className="slide-by-slide-editor">
            {slides.map(slide => (
                <SlideEditPanel
                    key={slide.id}
                    slide={slide}
                    availableLayouts={templateMetadata.slideLayouts}
                    onContentChange={(changes) => onSlideChange(slide.id, changes)}
                />
            ))}
        </div>
    );
};
```

## 🔧 **3단계: 고급 기능 구현**

### **3.1 텍스트 기반 자동 스타일 적용**

```python
# backend/app/services/presentation/style_transfer_service.py
class StyleTransferService:
    """텍스트를 템플릿 스타일로 자동 변환"""
    
    def apply_template_style_to_content(
        self,
        content: str,
        template_metadata: Dict[str, Any],
        slide_type: str = 'content'
    ) -> Dict[str, Any]:
        """
        사용자가 제공한 텍스트를 템플릿의 스타일로 자동 변환
        """
        return {
            'styled_content': self._apply_typography_styles(content, template_metadata['typography']),
            'layout_suggestion': self._suggest_layout(content, template_metadata['layout_patterns']),
            'color_mapping': self._apply_color_scheme(content, template_metadata['color_palette']),
            'shape_elements': self._generate_shape_elements(content, template_metadata['shape_styles'])
        }
```

### **3.2 실시간 미리보기 시스템**

```tsx
// RealTimePreviewCanvas: 실시간 PPT 미리보기
const RealTimePreviewCanvas: React.FC<{
    outline: OutlineData;
    templateMetadata: TemplateMetadata;
    currentSlideIndex: number;
}> = ({ outline, templateMetadata, currentSlideIndex }) => {
    const [previewData, setPreviewData] = useState<PreviewData | null>(null);
    
    useEffect(() => {
        // 변경사항이 있을 때마다 실시간으로 미리보기 업데이트
        generatePreview();
    }, [outline, templateMetadata, currentSlideIndex]);
    
    const generatePreview = async () => {
        const response = await fetch('/api/v1/chat/presentation/preview', {
            method: 'POST',
            body: JSON.stringify({
                outline,
                templateId: templateMetadata.id,
                slideIndex: currentSlideIndex
            })
        });
        
        const data = await response.json();
        setPreviewData(data);
    };
    
    return (
        <div className="real-time-preview">
            <canvas
                ref={canvasRef}
                className="ppt-preview-canvas"
                width={960}
                height={720}
            />
            <PreviewControls onSlideChange={setCurrentSlideIndex} />
        </div>
    );
};
```

## 🔧 **4단계: 구현 우선순위**

### **Phase 1: 핵심 메타데이터 추출** (2주)
1. TemplateMetadataExtractor 구현
2. 색상, 폰트, 레이아웃 패턴 추출 로직
3. API 엔드포인트 추가

### **Phase 2: Frontend UX 개선** (3주)
1. PresentationOutlineModal 리팩토링
2. 실시간 템플릿 프리뷰 구현
3. 페이지별 편집 인터페이스

### **Phase 3: 고급 기능** (2주)
1. 자동 스타일 적용 시스템
2. 실시간 미리보기
3. 드래그 앤 드롭 편집

### **Phase 4: 최적화 및 테스트** (1주)
1. 성능 최적화
2. 사용자 테스트 및 피드백 반영

## 🎯 **기대 효과**

1. **사용자 경험 향상**
   - 텍스트만 입력하면 프로 수준의 디자인 자동 적용
   - 실시간 미리보기로 결과 예측 가능

2. **템플릿 활용도 극대화**
   - 템플릿의 모든 디자인 요소를 완전히 활용
   - 일관성 있는 브랜드 아이덴티티 적용

3. **생산성 향상**
   - 디자인 시간 대폭 단축
   - 전문 디자이너 수준의 결과물 생성
