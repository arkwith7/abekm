// 프레젠테이션 관련 타입 정의

export interface TemplateLayout {
  layout_index: number;
  layout_name: string;
  layout_type: string;
  placeholders: Array<{
    type: string;
    idx: number;
    has_text: boolean;
  }>;
  text_shapes_count: number;
  image_shapes_count: number;
  chart_shapes_count: number;
  total_shapes: number;
  supports_title: boolean;
  supports_content: boolean;
  supports_image: boolean;
  supports_chart: boolean;
}

export interface TemplateLayoutsResponse {
  success: boolean;
  template_id: string;
  layouts: {
    template_path: string;
    total_layouts: number;
    layouts: TemplateLayout[];
    slide_masters_count: number;
  };
}

export interface SlideLayoutSelection {
  slideIndex: number;
  layoutIndex: number;
  layoutName: string;
  layoutType: string;
}

export interface ChartData {
  type: 'column' | 'bar' | 'line' | 'pie';
  title: string;
  categories: string[];
  series: { name: string; values: number[] }[];
}

export interface DiagramData {
  type: 'none' | 'chart' | 'process' | 'cycle' | 'hierarchy' | 'relationship' | 'pyramid';
  data?: any;
  chart?: ChartData;
}

export interface ExtendedOutlineSection {
  title: string;
  bullets?: string[];
  layoutSelection?: SlideLayoutSelection;
  diagram?: DiagramData;
}

export interface ExtendedOutlineData {
  title?: string;
  sections: ExtendedOutlineSection[];
  templateLayoutSelections?: SlideLayoutSelection[];
}

// 🎯 새로운 단순화된 메타데이터 타입
export interface SimpleElementStyle {
  fontSize?: string;
  fontWeight?: string;
  alignment?: string;
  width?: string;
  height?: string;
}

export interface SimpleListItem {
  index?: string;
  text: string;
  title?: string;
  description?: string;
}

export interface SimpleElement {
  id: string;
  type: 'textbox' | 'image' | 'list' | 'table' | 'chart' | 'shape';
  position: string; // 'center', 'top-left-header', 'bottom-right' 등
  content?: string;
  style?: SimpleElementStyle;
  items?: SimpleListItem[]; // list 타입인 경우
  headers?: string[]; // table 타입인 경우
  rows?: Record<string, string>[]; // table 타입인 경우
}

export interface SimpleSlide {
  pageNumber: number;
  layout: string;
  elements: SimpleElement[];
}

export interface SimpleTemplateMetadata {
  presentationTitle: string;
  totalPages: number;
  slides: SimpleSlide[];
}

export interface SimpleMetadataResponse {
  success: boolean;
  template_id: string;
  metadata: SimpleTemplateMetadata;
}

// 🎯 텍스트박스 매핑 관련 타입
export interface TextBoxMapping {
  slideIndex: number;
  elementId: string;
  elementType: string;
  originalContent?: string;
  assignedContent?: string;
  contentSource: 'ai_answer' | 'user_input' | 'keep_original';
  position: string;
  action?: 'keep_original' | 'replace_content' | 'hide_object'; // 액션 정보 추가
  // 🆕 확장 필드들 (백엔드 호환성)
  objectType?: string;
  isEnabled?: boolean;
  metadata?: any;
}

export interface ContentSegment {
  id: string;
  content: string;
  type: 'paragraph' | 'title' | 'bullet' | 'table_data';
  priority: number; // 중요도 (1-10)
  suggestedPosition?: string; // 추천 위치
}

export interface SlideMapping {
  slideIndex: number;
  layout: string;
  textBoxMappings: TextBoxMapping[];
  contentSegments: ContentSegment[];
}
