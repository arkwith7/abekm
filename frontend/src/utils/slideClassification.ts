/**
 * 슬라이드 분류 및 영역 분할 유틸리티
 */

// 슬라이드 종류 타입 정의
export type SlideType = 'title' | 'toc' | 'content' | 'ending';

// 슬라이드 종류 한글 표시명
export const SLIDE_TYPE_LABELS: Record<SlideType, string> = {
  title: '제목 슬라이드',
  toc: '목차 슬라이드',
  content: '컨텐츠 슬라이드',
  ending: '종료인사 슬라이드'
};

// 컨텐츠 슬라이드 영역 타입 정의
export type ContentAreaType = 'page_title' | 'key_message' | 'main_content';

// 컨텐츠 영역 한글 표시명
export const CONTENT_AREA_LABELS: Record<ContentAreaType, string> = {
  page_title: '페이지 타이틀 영역',
  key_message: '페이지 키 메시지 영역',
  main_content: '페이지 컨텐츠 영역'
};

// 슬라이드 영역 분할 (상하 8개, 좌우 14개)
export interface SlideArea {
  row: number; // 1-8
  col: number; // 1-14  
  type: ContentAreaType;
}

/**
 * 슬라이드 레이아웃명을 기반으로 슬라이드 종류 분류
 */
export function classifySlideType(layoutName: string): SlideType {
  const normalizedName = layoutName.toLowerCase().trim();

  // 제목 슬라이드 판별
  if (normalizedName.includes('제목') || normalizedName.includes('title')) {
    return 'title';
  }

  // 목차 슬라이드 판별  
  if (normalizedName.includes('목차') || normalizedName.includes('toc') ||
    normalizedName.includes('contents') || normalizedName.includes('index')) {
    return 'toc';
  }

  // 종료인사 슬라이드 판별
  if (normalizedName.includes('종료') || normalizedName.includes('감사') ||
    normalizedName.includes('thank') || normalizedName.includes('end')) {
    return 'ending';
  }

  // 기본값은 컨텐츠 슬라이드
  return 'content';
}

/**
 * 오브젝트 위치를 기반으로 컨텐츠 영역 분류
 * 슬라이드를 상하 8개 영역, 좌우 14개 영역으로 분할
 */
export function classifyContentArea(
  leftPx: number,
  topPx: number,
  slideWidthPx: number = 960.17,
  slideHeightPx: number = 720.0
): ContentAreaType {
  // 상하 8개 영역으로 분할
  const rowHeight = slideHeightPx / 8;
  // Use floor+1 and clamp to [1,8] so topPx=0 falls into row 1
  let row = Math.floor(topPx / rowHeight) + 1;
  row = Math.max(1, Math.min(8, row)); // clamp

  // 좌우 14개 영역으로 분할 (현재는 row 기반 분류만 사용)
  // const colWidth = slideWidthPx / 14;
  // const col = Math.ceil(leftPx / colWidth); // 1-14

  // 1. 페이지 타이틀 영역 (상단 첫번째 영역)
  if (row === 1) {
    return 'page_title';
  }

  // 2. 페이지 키 메시지 영역 (상단에서 2번째)
  if (row === 2) {
    return 'key_message';
  }

  // 3. 페이지 컨텐츠 영역 (나머지: 3~8행)
  return 'main_content';
}

/**
 * 슬라이드 영역 정보 생성
 */
export function getSlideArea(
  leftPx: number,
  topPx: number,
  slideWidthPx: number = 960.17,
  slideHeightPx: number = 720.0
): SlideArea {
  const rowHeight = slideHeightPx / 8;
  const colWidth = slideWidthPx / 14;

  // floor+1 with clamping to avoid 0-index when px is 0
  let row = Math.floor(topPx / rowHeight) + 1;
  row = Math.max(1, Math.min(8, row));
  let col = Math.floor(leftPx / colWidth) + 1;
  col = Math.max(1, Math.min(14, col));
  const type = classifyContentArea(leftPx, topPx, slideWidthPx, slideHeightPx);

  return { row, col, type };
}

/**
 * 영역별 배경색 클래스 반환 (UI 표시용)
 */
export function getAreaColorClass(areaType: ContentAreaType): string {
  switch (areaType) {
    case 'page_title':
      return 'bg-blue-50 border-blue-200 text-blue-800';
    case 'key_message':
      return 'bg-green-50 border-green-200 text-green-800';
    case 'main_content':
      return 'bg-yellow-50 border-yellow-200 text-yellow-800';
    default:
      return 'bg-gray-50 border-gray-200 text-gray-800';
  }
}

/**
 * 슬라이드 타입별 배경색 클래스 반환
 */
export function getSlideTypeColorClass(slideType: SlideType): string {
  switch (slideType) {
    case 'title':
      return 'bg-purple-50 border-purple-200 text-purple-800';
    case 'toc':
      return 'bg-indigo-50 border-indigo-200 text-indigo-800';
    case 'content':
      return 'bg-blue-50 border-blue-200 text-blue-800';
    case 'ending':
      return 'bg-pink-50 border-pink-200 text-pink-800';
    default:
      return 'bg-gray-50 border-gray-200 text-gray-800';
  }
}
