import { ArrowLeft, ArrowRight, Check, CheckCircle, Download, Edit3, Loader2, RefreshCw, Sparkles, Trash2, X } from 'lucide-react';
import React, { useCallback, useEffect, useRef, useState } from 'react';

// ============================================
// 타입 정의
// ============================================

type ModalStep = 'setup' | 'generating_content' | 'editor' | 'generating_ppt' | 'preview';

// 위자드 단계 정의
const WIZARD_STEPS = [
    { id: 'setup', label: '템플릿 선택', number: 1 },
    { id: 'editor', label: '내용 편집', number: 2 },
    { id: 'preview', label: 'PPT 미리보기', number: 3 },
] as const;

interface TemplateInfo {
    id: string;
    name: string;
    description?: string;
    thumbnail_url?: string;
    slide_count?: number;
    is_default?: boolean;
}

interface SlideElement {
    id: string;
    text: string;
    role?: string;
    original_text?: string;
    metadata?: {
        tableData?: {
            headers?: string[];
            rows?: string[][];
        };
        [key: string]: any;
    };
}

interface SlideContent {
    index: number;
    role: string;
    elements: SlideElement[];
    note?: string;
}

interface Props {
    open: boolean;
    onClose: () => void;
    initialOutline?: any;
    onConfirm: (outline: any) => void;
    sourceContent?: string;
    loading?: boolean;
    templates?: TemplateInfo[];
    selectedTemplateId?: string | null | undefined;
    onTemplateChange?: (id: string) => void;
    sessionId?: string;  // 채팅 세션 ID (RAG 컨텍스트 수집용)
    containerIds?: string[];  // 선택된 문서 컨테이너 IDs
}

// ============================================
// 메인 컴포넌트
// ============================================

const PresentationOutlineModal: React.FC<Props> = ({
    open,
    onClose,
    onConfirm,
    sourceContent,
    templates = [],
    selectedTemplateId,
    onTemplateChange,
    sessionId,
    containerIds
}) => {
    // ============================================
    // 상태 관리
    // ============================================

    const [currentStep, setCurrentStep] = useState<ModalStep>('setup');
    const [allTemplates, setAllTemplates] = useState<TemplateInfo[]>([]);
    const [localSelectedTemplateId, setLocalSelectedTemplateId] = useState<string | null>(null);
    // userTopic 상태 제거 - sourceContent(채팅 원본 질의)만 사용

    // 🔧 중복 요청 방지 및 컴포넌트 마운트 상태 추적
    const [isGenerating, setIsGenerating] = useState<boolean>(false);
    const isGeneratingRef = useRef<boolean>(false);  // 🔧 비동기 호출 중 정확한 상태 추적
    const isMountedRef = useRef<boolean>(true);
    const abortControllerRef = useRef<AbortController | null>(null);

    // 🆕 AI 사고 과정 (추론 단계) 표시
    interface ReasoningStep {
        id: string;
        message: string;
        status: 'pending' | 'in_progress' | 'completed' | 'error';
    }
    const [reasoningSteps, setReasoningSteps] = useState<ReasoningStep[]>([]);

    // 편집 데이터
    const [slidesContent, setSlidesContent] = useState<SlideContent[]>([]);
    const [currentSlideIndex, setCurrentSlideIndex] = useState<number>(0);

    // 미리보기용 썸네일
    const [slideThumbnails, setSlideThumbnails] = useState<string[]>([]);

    // 결과물
    const [generatedPptFilename, setGeneratedPptFilename] = useState<string | null>(null);
    const [googlePreviewUrl, setGooglePreviewUrl] = useState<string | null>(null);
    const [directDownloadUrl, setDirectDownloadUrl] = useState<string | null>(null);

    const [error, setError] = useState<string | null>(null);
    const [loadingMessage, setLoadingMessage] = useState<string>("");

    // ============================================
    // 초기화 및 정리
    // ============================================

    // 🔧 컴포넌트 마운트/언마운트 추적
    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
            // 진행 중인 요청 취소
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
                abortControllerRef.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (templates && templates.length > 0) {
            setAllTemplates(templates);
        }
    }, [templates]);

    useEffect(() => {
        if (selectedTemplateId) {
            setLocalSelectedTemplateId(selectedTemplateId);
        }
    }, [selectedTemplateId]);

    useEffect(() => {
        if (open) {
            setCurrentStep('setup');
            setError(null);
            setSlidesContent([]);
            setIsGenerating(false);  // 🔧 생성 상태 초기화
            isGeneratingRef.current = false;  // 🔧 ref도 초기화
            // sourceContent(채팅 원본 질의)는 props에서 직접 사용

            // 템플릿 로드 (allTemplates가 비어있을 때만)
            loadTemplates();
        } else {
            // 🔧 모달이 닫힐 때 진행 중인 요청 취소
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
                abortControllerRef.current = null;
            }
            isGeneratingRef.current = false;  // 🔧 ref도 초기화
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    // ============================================
    // API 호출
    // ============================================

    const loadTemplates = async () => {
        try {
            const response = await fetch('/api/v1/agent/presentation/templates', {
                headers: { 'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}` }
            });
            if (response.ok) {
                const data = await response.json();
                if (isMountedRef.current) {
                    setAllTemplates(data.templates || []);
                }
            }
        } catch (error) {
            console.error('템플릿 로드 실패:', error);
        }
    };

    const loadThumbnails = async (templateId: string) => {
        try {
            const response = await fetch(
                `/api/v1/agent/presentation/templates/${encodeURIComponent(templateId)}/thumbnails`,
                { headers: { 'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}` } }
            );
            if (response.ok) {
                const data = await response.json();
                const urls = (data.thumbnails || []).map((_: any, idx: number) =>
                    `/api/v1/agent/presentation/templates/${encodeURIComponent(templateId)}/thumbnails/${idx}`
                );
                setSlideThumbnails(urls);
            }
        } catch (e) {
            console.error("썸네일 로드 실패", e);
        }
    };

    // Step 1 -> 2: 콘텐츠 생성
    const handleGenerateContent = useCallback(async () => {
        // 🔧 중복 클릭 방지 (state와 ref 모두 체크)
        if (isGenerating || isGeneratingRef.current) {
            console.log("⏳ 이미 생성 중입니다... (state:", isGenerating, ", ref:", isGeneratingRef.current, ")");
            return;
        }

        if (!localSelectedTemplateId) {
            setError("템플릿을 선택해주세요.");
            return;
        }
        // ⚠️ 원본 채팅 질의문(sourceContent) 사용 - 텍스트 영역 수정 내용 무시
        const originalQuery = sourceContent?.trim();
        if (!originalQuery) {
            setError("채팅에서 프레젠테이션 요청이 필요합니다.");
            return;
        }

        // 🔧 이전 요청이 있으면 취소
        if (abortControllerRef.current) {
            console.log("🛑 이전 요청 취소");
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        // 🔧 즉시 ref 설정 (state 업데이트 전에 중복 방지)
        isGeneratingRef.current = true;
        setIsGenerating(true);
        setCurrentStep('generating_content');
        setLoadingMessage("AI가 관련 문서를 검색하고 맞춤형 콘텐츠를 생성하고 있습니다... (최대 2분 소요)");
        setError(null);

        // 🆕 AI 사고 과정 초기화
        setReasoningSteps([
            { id: 'analyze', message: '🔍 템플릿 구조를 분석하고 있습니다...', status: 'in_progress' },
            { id: 'search', message: '📚 관련 문서를 검색하고 있습니다...', status: 'pending' },
            { id: 'generate', message: '✍️ PPT 콘텐츠를 생성하고 있습니다...', status: 'pending' },
            { id: 'match', message: '🧩 슬라이드 매칭을 진행하고 있습니다...', status: 'pending' },
            { id: 'finalize', message: '✅ 콘텐츠 매핑을 완료하고 있습니다...', status: 'pending' },
        ]);

        // 🔧 새 AbortController 생성 및 저장
        const controller = new AbortController();
        abortControllerRef.current = controller;
        let timeoutId: NodeJS.Timeout | null = null;

        // 🆕 추론 단계 업데이트 헬퍼 함수 (ID 기반)
        const updateReasoningStep = (stepId: string, status: 'in_progress' | 'completed' | 'error') => {
            if (!isMountedRef.current) return;
            setReasoningSteps(prev => prev.map(step => {
                if (step.id === stepId) return { ...step, status };
                return step;
            }));
        };

        const completeStepAndStartNext = (currentId: string, nextId: string) => {
            if (!isMountedRef.current) return;
            setReasoningSteps(prev => prev.map(step => {
                if (step.id === currentId) return { ...step, status: 'completed' };
                if (step.id === nextId) return { ...step, status: 'in_progress' };
                return step;
            }));
        };

        // 🔧 재시도 로직을 위한 내부 함수
        const attemptFetch = async (retryCount: number = 0): Promise<Response> => {
            const MAX_RETRIES = 2;

            try {
                console.log(`🚀 콘텐츠 생성 API 호출 (시도 ${retryCount + 1}/${MAX_RETRIES + 1}):`, localSelectedTemplateId);

                const response = await fetch(`/api/v1/agent/presentation/templates/${encodeURIComponent(localSelectedTemplateId)}/generate-content`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
                        'Connection': 'keep-alive'  // 🔧 연결 유지
                    },
                    body: JSON.stringify({
                        user_query: originalQuery,  // 원본 채팅 질의문만 사용
                        context: "",  // context는 비워둠 (RAG에서 수집)
                        session_id: sessionId,  // 채팅 컨텍스트 활용
                        container_ids: containerIds,  // RAG 검색 범위
                        use_rag: true  // Agentic AI: RAG 검색 활성화
                    }),
                    signal: controller.signal,
                    keepalive: true  // 🔧 연결 유지
                });

                return response;
            } catch (fetchError: any) {
                // 🔧 네트워크 오류 시 재시도 (AbortError 제외)
                if (fetchError.name !== 'AbortError' && retryCount < MAX_RETRIES) {
                    console.warn(`⚠️ 네트워크 오류, ${retryCount + 2}번째 시도 예정...`, fetchError.message);
                    // 잠시 대기 후 재시도
                    await new Promise(resolve => setTimeout(resolve, 2000));
                    return attemptFetch(retryCount + 1);
                }
                throw fetchError;
            }
        };

        try {
            // 썸네일 미리 로드 (비동기, 실패해도 계속 진행)
            loadThumbnails(localSelectedTemplateId).catch(console.warn);

            // 🔧 타임아웃 설정 (180초로 증가 - LLM 호출이 오래 걸릴 수 있음)
            timeoutId = setTimeout(() => {
                console.warn("⏰ 요청 타임아웃 (180초)");
                controller.abort();
            }, 180000);

            // 🆕 Step 1 완료, Step 2 시작
            completeStepAndStartNext('analyze', 'search');

            // ⚠️ 재시도 로직 포함된 fetch 호출
            const response = await attemptFetch();

            // 🆕 Step 2 완료, Step 3 시작
            completeStepAndStartNext('search', 'generate');

            // 🔧 타임아웃 해제
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            console.log("📥 API 응답 수신:", response.status, response.statusText);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = errorData.detail || `서버 오류 (${response.status}): 콘텐츠 생성에 실패했습니다.`;
                throw new Error(errorMsg);
            }

            const data = await response.json();
            console.log("✅ 콘텐츠 생성 완료:", data.slides?.length, "슬라이드");

            // 🆕 Step 3 완료, Step 4 시작
            completeStepAndStartNext('generate', 'match');

            // 🔧 컴포넌트가 언마운트되었으면 상태 업데이트 안 함
            if (!isMountedRef.current) {
                console.log("⚠️ 컴포넌트가 언마운트됨, 상태 업데이트 스킵");
                return;
            }

            // 슬라이드 콘텐츠 검증
            if (!data.slides || data.slides.length === 0) {
                throw new Error("AI가 콘텐츠를 생성하지 못했습니다. 주제를 더 구체적으로 입력해주세요.");
            }

            // 🆕 Step 4 완료, Step 5 시작
            completeStepAndStartNext('match', 'finalize');

            // 잠시 후 모든 단계 완료
            setTimeout(() => {
                if (isMountedRef.current) {
                    setReasoningSteps(prev => prev.map(step => ({ ...step, status: 'completed' })));
                }
            }, 500);

            setSlidesContent(data.slides);
            setCurrentStep('editor');
        } catch (e: any) {
            console.error("❌ 콘텐츠 생성 오류:", e);
            console.error("  - 오류 이름:", e.name);
            console.error("  - 오류 메시지:", e.message);
            console.error("  - 오류 스택:", e.stack);

            // 🆕 현재 진행 중인 단계를 에러로 표시
            setReasoningSteps(prev => prev.map(step => {
                if (step.status === 'in_progress') return { ...step, status: 'error' };
                return step;
            }));

            // 🔧 타임아웃 정리
            if (timeoutId) {
                clearTimeout(timeoutId);
            }

            // 🔧 컴포넌트가 언마운트되었으면 상태 업데이트 안 함
            if (!isMountedRef.current) {
                return;
            }

            // 🔧 에러 유형별 사용자 친화적 메시지
            let userMessage: string;
            if (e.name === 'AbortError') {
                userMessage = "요청이 취소되었거나 시간이 초과되었습니다. 다시 시도해주세요.";
            } else if (e.message === 'Failed to fetch' || e.message?.includes('ERR_EMPTY_RESPONSE')) {
                userMessage = "서버 응답을 받지 못했습니다. AI 처리에 시간이 오래 걸릴 수 있으니 잠시 후 다시 시도해주세요.";
            } else if (e.message?.includes('NetworkError') || e.message?.includes('network')) {
                userMessage = "네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.";
            } else {
                userMessage = e.message || "콘텐츠 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.";
            }

            setError(userMessage);
            setCurrentStep('setup');
        } finally {
            // 🔧 생성 상태 해제 (ref와 state 모두)
            isGeneratingRef.current = false;
            if (isMountedRef.current) {
                setIsGenerating(false);
            }
            // 🔧 AbortController 참조 정리
            if (abortControllerRef.current === controller) {
                abortControllerRef.current = null;
            }
        }
    }, [isGenerating, localSelectedTemplateId, sourceContent, sessionId, containerIds]);

    // Step 3 -> 4: PPT 생성
    const handleBuildPPT = async () => {
        setCurrentStep('generating_ppt');
        setLoadingMessage("편집된 내용을 바탕으로 PPT 파일을 생성하고 있습니다...");
        setError(null);

        try {
            const response = await fetch(`/api/v1/agent/presentation/templates/${encodeURIComponent(localSelectedTemplateId!)}/build-from-data`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`
                },
                body: JSON.stringify({
                    slides: slidesContent,
                    output_filename: (sourceContent || '프레젠테이션').slice(0, 30).replace(/[\\/:*?"<>|]/g, '_')
                })
            });

            if (!response.ok) throw new Error("PPT 생성 실패");

            const data = await response.json();
            // generatedPptUrl은 사용되지 않으므로 저장하지 않음
            setGeneratedPptFilename(data.file_name || "presentation.pptx");

            // 미리보기 URL 로드
            await loadPreviewUrl(data.file_name || "presentation.pptx");

            setCurrentStep('preview');
        } catch (e: any) {
            setError(e.message || "PPT 생성 중 오류가 발생했습니다.");
            setCurrentStep('editor');
        }
    };

    const loadPreviewUrl = async (filename: string) => {
        try {
            const response = await fetch(
                `/api/v1/agent/presentation/preview-url/${encodeURIComponent(filename)}`,
                { headers: { 'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}` } }
            );
            if (response.ok) {
                const data = await response.json();
                // previewUrl은 googlePreviewUrl로 통합됨
                setGooglePreviewUrl(data.google_preview_url || data.preview_url);
                setDirectDownloadUrl(data.direct_url);
            }
        } catch (e) {
            console.error("미리보기 URL 로드 실패", e);
        }
    };

    // ============================================
    // UI 렌더링
    // ============================================

    // 1. 설정 화면 (템플릿 선택 + 주제 입력)
    const renderSetup = () => (
        <div className="flex flex-col h-full">
            {/* 스크롤 가능한 컨텐츠 영역 */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                <div>
                    <h3 className="text-lg font-semibold mb-2 flex items-center gap-2">
                        <span className="w-6 h-6 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">1</span>
                        템플릿 선택
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4 p-2 border rounded-lg bg-gray-50">
                        {allTemplates.map(tpl => (
                            <div
                                key={tpl.id}
                                onClick={() => {
                                    setLocalSelectedTemplateId(tpl.id);
                                    onTemplateChange?.(tpl.id);
                                }}
                                className={`cursor-pointer border-2 rounded-lg p-2 hover:bg-white transition-all bg-white ${localSelectedTemplateId === tpl.id ? 'border-blue-500 ring-2 ring-blue-200 bg-blue-50' : 'border-gray-200 hover:border-gray-300'}`}
                            >
                                <div className="aspect-video bg-gray-200 rounded mb-2 overflow-hidden">
                                    {tpl.thumbnail_url ? (
                                        <img src={tpl.thumbnail_url} alt={tpl.name} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-gray-400 text-xs">No Image</div>
                                    )}
                                </div>
                                <div className="text-sm font-medium truncate text-center">{tpl.name}</div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* 안내 메시지 */}
                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                        <div className="p-2 bg-blue-100 rounded-full">
                            <Sparkles className="text-blue-600" size={20} />
                        </div>
                        <div>
                            <p className="text-blue-800 font-medium mb-1">원본 요청 내용</p>
                            <p className="text-blue-700 text-sm">
                                "{sourceContent || '(채팅에서 요청 내용이 전달됩니다)'}"
                            </p>
                            <p className="text-blue-500 text-xs mt-2">
                                AI가 위 요청과 선택한 템플릿을 기반으로 프레젠테이션 초안을 자동 생성합니다.
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* 고정된 하단 액션 바 */}
            <div className="border-t bg-gray-50 px-6 py-4 flex justify-between items-center">
                <button
                    onClick={onClose}
                    className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
                >
                    취소
                </button>
                <button
                    onClick={handleGenerateContent}
                    disabled={!localSelectedTemplateId || !sourceContent?.trim() || isGenerating}
                    className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg transition-all"
                >
                    {isGenerating ? (
                        <>
                            <Loader2 size={20} className="animate-spin" />
                            AI 초안 생성 중...
                        </>
                    ) : (
                        <>
                            <Sparkles size={20} />
                            다음: AI 초안 생성
                            <ArrowRight size={18} />
                        </>
                    )}
                </button>
            </div>
        </div>
    );

    // 2. 에디터 화면 (슬라이드별 편집)
    const renderEditor = () => {
        const currentSlide = slidesContent[currentSlideIndex];
        const currentThumbnail = slideThumbnails[currentSlideIndex];

        return (
            <div className="flex h-full">
                {/* 좌측: 슬라이드 목록 */}
                <div className="w-64 border-r bg-gray-50 flex flex-col">
                    <div className="p-4 border-b font-semibold text-gray-700">슬라이드 목록</div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {slidesContent.map((slide, idx) => (
                            <div
                                key={idx}
                                onClick={() => setCurrentSlideIndex(idx)}
                                className={`p-2 rounded cursor-pointer flex items-center gap-3 transition-colors ${currentSlideIndex === idx ? 'bg-white shadow ring-1 ring-blue-500' : 'hover:bg-gray-200'}`}
                            >
                                <div className="w-6 h-6 flex items-center justify-center bg-gray-300 rounded text-xs font-bold text-gray-600">
                                    {slide.index}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="text-xs font-medium text-gray-500 uppercase">{slide.role}</div>
                                    <div className="text-sm truncate text-gray-800">
                                        {slide.elements.find(e => e.role?.includes('title'))?.text || `Slide ${slide.index}`}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* 우측: 편집 영역 */}
                <div className="flex-1 flex flex-col h-full overflow-hidden">
                    {/* 상단: 썸네일 미리보기 (참고용) */}
                    <div className="h-48 bg-gray-100 border-b flex items-center justify-center p-4 relative">
                        {currentThumbnail ? (
                            <img src={currentThumbnail} alt={`Slide ${currentSlide?.index}`} className="h-full object-contain shadow-lg" />
                        ) : (
                            <div className="text-gray-400">미리보기 없음</div>
                        )}
                        <div className="absolute bottom-2 right-2 bg-black/50 text-white text-xs px-2 py-1 rounded">
                            템플릿 레이아웃 참고용
                        </div>
                    </div>

                    {/* 하단: 폼 입력 */}
                    <div className="flex-1 overflow-y-auto p-6">
                        <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                            <Edit3 size={18} />
                            슬라이드 {currentSlide?.index} 내용 편집
                            <span className="text-sm font-normal text-gray-500">
                                ({currentSlide?.role || 'content'})
                            </span>
                        </h3>

                        {(!currentSlide?.elements || currentSlide.elements.length === 0) ? (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                                <p className="text-yellow-700 mb-2">
                                    이 슬라이드에는 편집 가능한 텍스트 요소가 감지되지 않았습니다.
                                </p>
                                <p className="text-sm text-yellow-600">
                                    템플릿의 이미지나 도형 요소는 자동으로 유지됩니다.
                                    다른 슬라이드에서 콘텐츠를 편집하세요.
                                </p>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                {currentSlide?.elements.map((element, elIdx) => (
                                    <div key={element.id} className="bg-white p-4 rounded-lg border shadow-sm hover:shadow-md transition-shadow">
                                        <div className="flex justify-between items-center mb-2">
                                            <label className="text-sm font-medium text-gray-600 flex items-center gap-2">
                                                <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">{element.id}</span>
                                                {element.role || 'Text Element'}
                                            </label>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={() => {
                                                        const newSlides = [...slidesContent];
                                                        newSlides[currentSlideIndex].elements[elIdx].text = ""; // Clear text effectively removes it
                                                        setSlidesContent(newSlides);
                                                    }}
                                                    className="text-gray-400 hover:text-red-500 p-1"
                                                    title="내용 지우기"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            </div>
                                        </div>
                                        <textarea
                                            className="w-full p-3 border rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[80px]"
                                            value={element.text}
                                            onChange={(e) => {
                                                const newSlides = [...slidesContent];
                                                newSlides[currentSlideIndex].elements[elIdx].text = e.target.value;
                                                setSlidesContent(newSlides);
                                            }}
                                            placeholder="(내용 없음)"
                                        />
                                        {element.original_text && (
                                            <div className="mt-1 text-xs text-gray-400 truncate">
                                                원본: {element.original_text}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* 하단 액션바 - 고정 */}
                    <div className="p-4 border-t bg-gray-50 flex justify-between items-center">
                        <button
                            onClick={() => setCurrentStep('setup')}
                            className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg flex items-center gap-2 transition-colors"
                        >
                            <ArrowLeft size={16} /> 이전: 템플릿 선택
                        </button>
                        <div className="flex gap-3">
                            <button
                                onClick={handleGenerateContent}
                                className="px-4 py-2 text-blue-600 border border-blue-300 bg-blue-50 hover:bg-blue-100 rounded-lg flex items-center gap-2 transition-colors"
                            >
                                <RefreshCw size={16} /> AI 다시 생성
                            </button>
                            <button
                                onClick={handleBuildPPT}
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 shadow-lg transition-all"
                            >
                                <CheckCircle size={18} /> 다음: PPT 생성
                                <ArrowRight size={16} />
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    // 3. 미리보기 화면
    const renderPreview = () => (
        <div className="flex flex-col h-full">
            {/* 미리보기 영역 */}
            <div className="flex-1 bg-gray-100 relative overflow-hidden">
                {googlePreviewUrl ? (
                    <iframe
                        src={googlePreviewUrl}
                        className="w-full h-full border-0"
                        title="PPT Preview"
                    />
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-3">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                        <span>미리보기를 불러오는 중...</span>
                    </div>
                )}
            </div>

            {/* 고정된 하단 액션 바 */}
            <div className="p-4 bg-gray-50 border-t flex justify-between items-center">
                <button
                    onClick={() => setCurrentStep('editor')}
                    className="px-4 py-2 text-gray-600 hover:bg-gray-200 rounded-lg flex items-center gap-2 transition-colors"
                >
                    <ArrowLeft size={16} /> 이전: 내용 편집
                </button>
                <div className="flex gap-3">
                    {directDownloadUrl && (
                        <a
                            href={directDownloadUrl}
                            download={generatedPptFilename || "presentation.pptx"}
                            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2 shadow-lg transition-all"
                        >
                            <Download size={18} /> PPT 다운로드
                        </a>
                    )}
                    <button
                        onClick={onClose}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 shadow-lg transition-all"
                    >
                        <Check size={18} /> 완료
                    </button>
                </div>
            </div>
        </div>
    );

    // 로딩 화면
    const renderLoading = () => (
        <div className="flex flex-col items-center justify-center h-full space-y-6 p-8">
            {/* 메인 로딩 표시 */}
            <div className="flex flex-col items-center space-y-3">
                <Loader2 className="w-12 h-12 text-blue-500 animate-spin" />
                <div className="text-lg font-medium text-gray-700">{loadingMessage}</div>
            </div>

            {/* AI 사고 과정 표시 */}
            {reasoningSteps.length > 0 && (
                <div className="w-full max-w-md bg-gray-50 rounded-xl p-4 border border-gray-200">
                    <div className="flex items-center gap-2 mb-3 pb-2 border-b border-gray-200">
                        <span className="text-lg">🧠</span>
                        <span className="text-sm font-semibold text-gray-700">AI 사고 과정</span>
                    </div>
                    <div className="space-y-2">
                        {reasoningSteps.map((step) => (
                            <div
                                key={step.id}
                                className={`flex items-start gap-2 p-2 rounded-lg transition-all ${step.status === 'in_progress'
                                    ? 'bg-blue-50 border border-blue-200'
                                    : step.status === 'completed'
                                        ? 'bg-green-50 border border-green-200'
                                        : step.status === 'error'
                                            ? 'bg-red-50 border border-red-200'
                                            : 'bg-gray-100 border border-gray-200'
                                    }`}
                            >
                                <div className="flex-shrink-0 mt-0.5">
                                    {step.status === 'in_progress' && (
                                        <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
                                    )}
                                    {step.status === 'completed' && (
                                        <Check className="w-4 h-4 text-green-600" />
                                    )}
                                    {step.status === 'error' && (
                                        <X className="w-4 h-4 text-red-600" />
                                    )}
                                    {step.status === 'pending' && (
                                        <div className="w-4 h-4 rounded-full border-2 border-gray-300" />
                                    )}
                                </div>
                                <span className={`text-sm ${step.status === 'in_progress'
                                    ? 'text-blue-700 font-medium'
                                    : step.status === 'completed'
                                        ? 'text-green-700'
                                        : step.status === 'error'
                                            ? 'text-red-700'
                                            : 'text-gray-500'
                                    }`}>
                                    {step.message}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {reasoningSteps.length === 0 && (
                <div className="text-sm text-gray-500">잠시만 기다려주세요...</div>
            )}
        </div>
    );

    // 현재 위자드 단계 번호 계산
    const getCurrentWizardStep = (): number => {
        if (currentStep === 'setup' || currentStep === 'generating_content') return 1;
        if (currentStep === 'editor') return 2;
        if (currentStep === 'preview' || currentStep === 'generating_ppt') return 3;
        return 1;
    };

    // 위자드 진행 표시기
    const renderWizardProgress = () => {
        const currentWizardStep = getCurrentWizardStep();

        return (
            <div className="flex items-center gap-2">
                {WIZARD_STEPS.map((step, idx) => (
                    <React.Fragment key={step.id}>
                        <div className="flex items-center gap-2">
                            <div
                                className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold transition-all
                                    ${currentWizardStep > step.number
                                        ? 'bg-green-500 text-white'
                                        : currentWizardStep === step.number
                                            ? 'bg-blue-600 text-white ring-2 ring-blue-300'
                                            : 'bg-gray-200 text-gray-500'
                                    }`}
                            >
                                {currentWizardStep > step.number ? <Check size={14} /> : step.number}
                            </div>
                            <span className={`text-sm hidden sm:inline ${currentWizardStep === step.number ? 'font-semibold text-blue-600' : 'text-gray-500'}`}>
                                {step.label}
                            </span>
                        </div>
                        {idx < WIZARD_STEPS.length - 1 && (
                            <div className={`w-8 h-0.5 ${currentWizardStep > step.number ? 'bg-green-500' : 'bg-gray-200'}`} />
                        )}
                    </React.Fragment>
                ))}
            </div>
        );
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="bg-white rounded-xl shadow-2xl w-full max-w-6xl h-[85vh] flex flex-col overflow-hidden">
                {/* 헤더: 좌측 타이틀 + 위자드 진행 표시 */}
                <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
                    <div className="flex items-center gap-4">
                        <h2 className="text-lg font-bold flex items-center gap-2 text-gray-800">
                            <Sparkles className="text-blue-500" size={22} />
                            AI 프레젠테이션
                        </h2>
                        <div className="h-6 w-px bg-gray-300" />
                        {renderWizardProgress()}
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-200 rounded-full transition-colors"
                        title="닫기"
                    >
                        <X size={20} className="text-gray-500" />
                    </button>
                </div>

                {/* 에러 메시지 */}
                {error && (
                    <div className="mx-6 mt-4 bg-red-50 text-red-600 p-3 rounded-lg border border-red-200 flex justify-between items-center">
                        <span>{error}</span>
                        <button onClick={() => setError(null)} className="hover:bg-red-100 p-1 rounded">
                            <X size={16} />
                        </button>
                    </div>
                )}

                {/* 메인 컨텐츠 - 스크롤 가능 영역 */}
                <div className="flex-1 overflow-hidden flex flex-col">
                    {(currentStep === 'generating_content' || currentStep === 'generating_ppt') ? (
                        <div className="flex-1">{renderLoading()}</div>
                    ) : currentStep === 'setup' ? (
                        renderSetup()
                    ) : currentStep === 'editor' ? (
                        renderEditor()
                    ) : currentStep === 'preview' ? (
                        renderPreview()
                    ) : null}
                </div>
            </div>
        </div>
    );
};

export default PresentationOutlineModal;
