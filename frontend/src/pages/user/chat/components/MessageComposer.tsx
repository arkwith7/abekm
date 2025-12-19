import {
  ArrowUp,
  ChevronDown,
  ChevronUp,
  File as FileIcon,
  Globe,
  LayoutTemplate,
  Paperclip,
  Plus,
  Radio,
  Search,
  Settings2,
  Square,
  Trash2,
  X
} from 'lucide-react';
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from 'react';
import TextareaAutosize from 'react-textarea-autosize';
import { useRealtimeSTT } from '../../../../services/realtimeSTT';
import { AttachmentCategory } from '../types/chat.types';

interface MessageComposerProps {
  onSendMessage: (message: string, files?: File[], tool?: string) => Promise<void> | void;
  onStopStreaming?: () => void;
  isLoading: boolean;
  placeholder?: string;
  onRealtimeSupportChange?: (supported: boolean) => void;
  ragState?: {
    isActive: boolean;
    isCollapsed: boolean;
    selectedCount: number;
    onToggleDetails: () => void;
    onClearDocuments: () => void;
    documents: Array<{ id: string; name: string; fileType?: string }>;
    onOpenDocument: (id: string) => void;
  };
}

type FileDraft = {
  id: string;
  file: File;
  category: AttachmentCategory;
  previewUrl?: string;
};

const getAttachmentCategory = (file: File): AttachmentCategory => {
  if (file.type.startsWith('image/')) return 'image';
  if (file.type.startsWith('audio/')) return 'audio';
  return 'document';
};

const createFileDraft = (file: File): FileDraft => {
  const id = `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  const category = getAttachmentCategory(file);
  const previewUrl = category === 'image' ? URL.createObjectURL(file) : undefined;

  return { id, file, category, previewUrl };
};

const formatFileSize = (size: number) => {
  if (size < 1024) return `${size}B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
  return `${(size / (1024 * 1024)).toFixed(1)}MB`;
};

type ToolType = 'ppt' | 'web-search' | 'deep-research' | 'patent';

interface ToolConfig {
  id: ToolType;
  name: string;
  icon: React.ElementType;
  colorClass: string;
  bgClass: string;
  textClass: string;
  iconBgClass: string;
}

const TOOLS: Record<ToolType, ToolConfig> = {
  'ppt': {
    id: 'ppt',
    name: 'PPT 에이전트',
    icon: LayoutTemplate,
    colorClass: 'text-orange-600',
    bgClass: 'bg-orange-50',
    textClass: 'text-orange-700',
    iconBgClass: 'bg-orange-100'
  },
  'web-search': {
    id: 'web-search',
    name: '웹 검색',
    icon: Globe,
    colorClass: 'text-blue-600',
    bgClass: 'bg-blue-50',
    textClass: 'text-blue-700',
    iconBgClass: 'bg-blue-100'
  },
  'patent': {
    id: 'patent',
    name: '특허 분석',
    icon: FileIcon,
    colorClass: 'text-teal-600',
    bgClass: 'bg-teal-50',
    textClass: 'text-teal-700',
    iconBgClass: 'bg-teal-100'
  },
  'deep-research': {
    id: 'deep-research',
    name: 'Deep Research',
    icon: Search,
    colorClass: 'text-purple-600',
    bgClass: 'bg-purple-50',
    textClass: 'text-purple-700',
    iconBgClass: 'bg-purple-100'
  }
};

const MessageComposer: React.FC<MessageComposerProps> = ({
  onSendMessage,
  onStopStreaming,
  isLoading,
  placeholder = '메시지를 입력하세요...',
  onRealtimeSupportChange,
  ragState
}) => {
  const [message, setMessage] = useState('');
  const [fileDrafts, setFileDrafts] = useState<FileDraft[]>([]);
  const [isDraggingFile, setDraggingFile] = useState(false);
  const [isToolMenuOpen, setIsToolMenuOpen] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [sttLanguage, setSttLanguage] = useState('ko-KR');
  const [isSTTPreparing, setIsSTTPreparing] = useState(false);
  const [selectedTool, setSelectedTool] = useState<ToolType | null>(null);

  const toolMenuButtonRef = useRef<HTMLButtonElement>(null);
  const toolMenuPopupRef = useRef<HTMLDivElement>(null);

  // 🆕 실시간 STT Hook
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const menuPopupRef = useRef<HTMLDivElement>(null);
  const ragDocuments = useMemo(() => ragState?.documents ?? [], [ragState?.documents]);

  // 🆕 실시간 STT Hook
  const {
    isRecording: isRealtimeRecording,
    interimText: realtimeInterimText,
    finalText: realtimeFinalText,
    isSupported: isRealtimeSupported,
    startRecording: startRealtimeSTT,
    stopRecording: stopRealtimeSTT,
    reset: resetRealtimeSTT
  } = useRealtimeSTT();

  const cleanupPreviews = useCallback((drafts: FileDraft[]) => {
    drafts.forEach(draft => {
      if (draft.previewUrl) {
        URL.revokeObjectURL(draft.previewUrl);
      }
    });
  }, []);

  useEffect(() => {
    return () => {
      cleanupPreviews(fileDrafts);
    };
  }, [fileDrafts, cleanupPreviews]);

  // TextareaAutosize를 사용하므로 수동 높이 조절 불필요

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  const handleSubmit = async () => {
    const trimmed = message.trim();
    const files = fileDrafts.map(draft => draft.file);

    if (!trimmed && !files.length) {
      return;
    }

    // 🆕 실시간 STT 중지 (메시지 전송 시)
    if (isRealtimeRecording) {
      stopRealtimeSTT();
    }

    await onSendMessage(trimmed, files, selectedTool || undefined);

    setMessage('');
    cleanupPreviews(fileDrafts);
    setFileDrafts([]);
    setSelectedTool(null); // 🆕 전송 후 도구 선택 초기화
  };

  // 🆕 실시간 텍스트 동기화
  useEffect(() => {
    if (realtimeFinalText || realtimeInterimText) {
      const combinedText = (realtimeFinalText + ' ' + realtimeInterimText).trim();
      setMessage(combinedText);
    }
  }, [realtimeFinalText, realtimeInterimText]);

  useEffect(() => {
    if (onRealtimeSupportChange) {
      onRealtimeSupportChange(isRealtimeSupported);
    }
  }, [isRealtimeSupported, onRealtimeSupportChange]);

  const handleStartRealtimeSTT = async () => {
    if (!isRealtimeSupported) {
      alert('현재 브라우저에서는 실시간 음성인식을 사용할 수 없습니다. 최신 Chrome/Edge를 사용해주세요.');
      return;
    }

    console.log('🎙️ [MessageComposer] 실시간 음성인식 시작 - 언어:', sttLanguage);

    // 준비 중 상태 표시
    setIsSTTPreparing(true);
    setIsMenuOpen(false); // 메뉴 닫기

    try {
      resetRealtimeSTT();
      setMessage(''); // 기존 텍스트 초기화

      // STT 준비 완료 대기
      const success = await startRealtimeSTT(sttLanguage);

      if (!success) {
        console.error('❌ [MessageComposer] STT 시작 실패');
        alert('실시간 음성인식을 시작할 수 없습니다. 마이크 권한을 확인해주세요.');
        return;
      }

      console.log('✅ [MessageComposer] STT 준비 완료 - 마이크 아이콘 표시');
    } catch (error) {
      console.error('❌ [MessageComposer] STT 시작 중 오류:', error);
    } finally {
      // 준비 완료 (성공/실패 모두 준비 상태 해제)
      setIsSTTPreparing(false);
    }
  };



  const handleFilesSelected = (input?: FileList | File[] | null) => {
    if (!input) return;
    const filesArray = Array.isArray(input) ? input : Array.from(input);
    if (!filesArray.length) {
      return;
    }

    // 파일 크기 제한 체크 (3MB)
    const MAX_FILE_SIZE = 3 * 1024 * 1024;
    const oversizedFiles = filesArray.filter(f => f.size > MAX_FILE_SIZE);

    if (oversizedFiles.length > 0) {
      const fileList = oversizedFiles.map(f =>
        `• ${f.name} (${(f.size / (1024 * 1024)).toFixed(1)}MB)`
      ).join('\n');

      alert(`⚠️ 파일 크기 제한 초과\n\n다음 파일이 너무 큽니다:\n${fileList}\n\n채팅에서는 3MB 이하의 파일만 첨부 가능합니다.\n큰 파일은 '문서 컨테이너' 메뉴에서 업로드해주세요.`);
      return;
    }

    const drafts = filesArray.map(createFileDraft);
    setFileDrafts(prev => [...prev, ...drafts]);
  };

  const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    handleFilesSelected(event.target.files);
    if (event.target.value) {
      event.target.value = '';
    }
  };

  const handlePaste = (event: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const { items } = event.clipboardData;
    if (!items?.length) return;
    const newFiles: File[] = [];

    Array.from(items).forEach(item => {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) {
          newFiles.push(file);
        }
      }
    });

    if (newFiles.length) {
      event.preventDefault();
      handleFilesSelected(newFiles);
    }
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDraggingFile(false);
    handleFilesSelected(event.dataTransfer.files);
  };

  const handleDragOver = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!isDraggingFile) {
      setDraggingFile(true);
    }
  };

  const handleDragLeave = (event: React.DragEvent<HTMLDivElement>) => {
    if (!dropZoneRef.current?.contains(event.relatedTarget as Node)) {
      setDraggingFile(false);
    }
  };

  const removeFileDraft = (id: string) => {
    const removed = fileDrafts.find(d => d.id === id);
    if (removed?.previewUrl) {
      URL.revokeObjectURL(removed.previewUrl);
    }
    setFileDrafts(prev => prev.filter(d => d.id !== id));
  };

  const clearDrafts = () => {
    cleanupPreviews(fileDrafts);
    setFileDrafts([]);
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (isRealtimeRecording) {
          stopRealtimeSTT();
        } else if (isDraggingFile) {
          setDraggingFile(false);
        } else if (isMenuOpen) {
          setIsMenuOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isRealtimeRecording, isDraggingFile, isMenuOpen, stopRealtimeSTT]);

  // 팝업 메뉴 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isMenuOpen &&
        menuButtonRef.current &&
        !menuButtonRef.current.contains(event.target as Node) &&
        menuPopupRef.current &&
        !menuPopupRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
      }
      if (
        isToolMenuOpen &&
        toolMenuButtonRef.current &&
        !toolMenuButtonRef.current.contains(event.target as Node) &&
        toolMenuPopupRef.current &&
        !toolMenuPopupRef.current.contains(event.target as Node)
      ) {
        setIsToolMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isMenuOpen, isToolMenuOpen]);

  return (
    <div
      ref={dropZoneRef}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      className={`mx-auto max-w-4xl rounded-3xl border bg-white shadow-lg transition-all ${isDraggingFile ? 'border-blue-400 ring-2 ring-blue-200' : 'border-gray-200'
        }`}
    >
      <div className="border-b border-gray-100 px-3 py-2 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-600">
        {ragState?.isActive ? (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={ragState.onToggleDetails}
              className="inline-flex items-center gap-1 rounded-full bg-green-50 px-2 py-0.5 font-medium text-green-700 border border-green-200 hover:bg-green-100"
            >
              <span>RAG</span>
              <span>{ragState.selectedCount > 0 ? `${ragState.selectedCount}개 문서` : '전체'}</span>
              {ragState.isCollapsed ? <ChevronDown className="h-3 w-3" /> : <ChevronUp className="h-3 w-3" />}
            </button>
            {ragState.selectedCount > 0 && (
              <button
                type="button"
                onClick={ragState.onClearDocuments}
                className="text-blue-600 hover:text-blue-800 px-2 py-0.5"
              >
                전체로
              </button>
            )}
          </div>
        ) : (
          <div className="text-gray-500">
            첨부 파일을 드래그하거나 메시지를 입력해 주세요.
          </div>
        )}
        {fileDrafts.length > 0 && (
          <button
            type="button"
            onClick={clearDrafts}
            className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2 py-0.5 text-gray-500 hover:border-red-300 hover:text-red-500"
          >
            <Trash2 className="h-3 w-3" />
            <span>초기화</span>
          </button>
        )}
      </div>

      {ragState?.isActive && !ragState.isCollapsed && (
        <div className="border-b border-green-100 bg-green-50/80 px-3 py-2 space-y-1 text-xs text-green-800">
          {ragDocuments.length > 0 ? (
            ragDocuments.slice(0, 5).map((doc) => (
              <div key={doc.id} className="flex items-center justify-between gap-2">
                <span className="truncate">📄 {doc.name}</span>
                <button
                  type="button"
                  onClick={() => ragState.onOpenDocument(doc.id)}
                  className="text-green-600 hover:text-green-800"
                >
                  열기
                </button>
              </div>
            ))
          ) : (
            <div>선택된 문서가 없습니다.</div>
          )}
          {ragDocuments.length > 5 && (
            <div className="text-[11px] text-green-600">+ {ragDocuments.length - 5}개 더 선택됨</div>
          )}
        </div>
      )}

      {fileDrafts.length > 0 && (
        <div className="px-4 pt-3">
          <div className="mb-2 flex items-center justify-between text-xs font-medium text-gray-600">
            <span>첨부 {fileDrafts.length}개</span>
            {fileDrafts.length > 0 && (
              <button
                type="button"
                onClick={clearDrafts}
                className="text-xs text-gray-400 hover:text-red-500"
              >
                첨부 모두 제거
              </button>
            )}
          </div>
          <div className="max-h-24 overflow-y-auto pr-1 flex flex-wrap gap-2">
            {fileDrafts.map(draft => (
              <div
                key={draft.id}
                className="flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700"
              >
                {draft.category === 'image' ? (
                  <img
                    src={draft.previewUrl}
                    alt={draft.file.name}
                    className="h-10 w-10 rounded object-cover"
                  />
                ) : (
                  <FileIcon className="h-6 w-6 text-blue-400" />
                )}
                <div className="flex flex-col">
                  <span className="max-w-[160px] truncate">{draft.file.name}</span>
                  <span className="text-[10px] text-blue-500">{formatFileSize(draft.file.size)}</span>
                </div>
                <button
                  type="button"
                  onClick={() => removeFileDraft(draft.id)}
                  className="text-blue-500 hover:text-red-500"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}

          </div>
        </div>
      )}

      <div className="px-4 pb-3 pt-2.5">
        {!isRealtimeSupported && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-700">
            <Radio className="h-4 w-4" />
            <span>현재 브라우저에서는 실시간 음성인식이 제한됩니다. 최신 Chrome/Edge 또는 모바일 앱을 이용하세요.</span>
          </div>
        )}



        {/* 🆕 STT 준비 중 상태 표시 */}
        {isSTTPreparing && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-600">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-amber-600 border-t-transparent"></div>
            <span className="font-medium">음성인식 준비 중...</span>
          </div>
        )}

        {/* 🆕 실시간 STT 상태 표시 */}
        {!isSTTPreparing && isRealtimeRecording && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm text-blue-600">
            <Radio className="h-4 w-4 animate-pulse" />
            <span className="font-medium">말씀하세요...</span>
            {realtimeInterimText && (
              <span className="text-gray-500 italic">"{realtimeInterimText}"</span>
            )}
            <button
              type="button"
              onClick={stopRealtimeSTT}
              className="ml-auto rounded-md px-2 py-1 text-xs text-blue-600 hover:bg-blue-100"
            >
              중지
            </button>
          </div>
        )}

        {/* 메인 입력 영역 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.doc,.docx,.hwp,.hwpx,.ppt,.pptx,.xls,.xlsx,.txt,.md,image/*,audio/*"
          onChange={handleFileInputChange}
        />

        <div className="flex flex-col gap-1.5">
          {/* 1줄: 텍스트 입력 영역 (전체 폭) */}
          <div className="w-full">
            <TextareaAutosize
              ref={textareaRef as any}
              value={message}
              onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setMessage(e.target.value)}
              onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit();
                }
              }}
              onPaste={handlePaste}
              placeholder={`${placeholder} (Shift+Enter 줄바꿈, Ctrl+V 붙여넣기)`}
              minRows={1}
              maxRows={6}
              className="w-full resize-none rounded-2xl border-0 bg-transparent px-4 py-2.5 text-[15px] text-gray-800 placeholder-gray-400 focus:outline-none"
              style={{ overflow: 'hidden' }}
              disabled={isLoading}
            />
          </div>

          {/* 2줄: 버튼 영역 (좌측 + 버튼, 우측 전송 버튼) */}
          <div className="flex items-center justify-between">
            {/* 좌측: + 버튼 (팝업 메뉴) */}
            <div className="relative flex items-center gap-2">
              <button
                ref={menuButtonRef}
                type="button"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
                title="첨부 메뉴"
              >
                <Plus className="h-5 w-5" />
              </button>

              {/* 🆕 도구 버튼 */}
              <div className="relative">
                {selectedTool ? (
                  <div className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${TOOLS[selectedTool].bgClass} ${TOOLS[selectedTool].textClass}`}>
                    {React.createElement(TOOLS[selectedTool].icon, { className: `h-4 w-4 ${TOOLS[selectedTool].colorClass}` })}
                    <span>{TOOLS[selectedTool].name}</span>
                    <button
                      type="button"
                      onClick={() => setSelectedTool(null)}
                      className={`ml-1 rounded-full p-0.5 hover:bg-black/5 ${TOOLS[selectedTool].colorClass}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ) : (
                  <button
                    ref={toolMenuButtonRef}
                    type="button"
                    onClick={() => setIsToolMenuOpen(!isToolMenuOpen)}
                    className="flex h-9 items-center gap-1.5 rounded-full bg-gray-100 px-3 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-200 hover:text-gray-800"
                    title="도구 선택"
                  >
                    <Settings2 className="h-4 w-4" />
                    <span>도구</span>
                  </button>
                )}

                {/* 도구 팝업 메뉴 */}
                {isToolMenuOpen && !selectedTool && (
                  <div
                    ref={toolMenuPopupRef}
                    className="absolute bottom-full left-0 mb-2 w-64 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden z-10 p-1"
                  >
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500">에이전트 선택</div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTool('ppt');
                        setIsToolMenuOpen(false);
                      }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-gray-700 rounded-lg transition-colors hover:bg-blue-50 hover:text-blue-700"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100 text-orange-600">
                        <LayoutTemplate className="h-4 w-4" />
                      </div>
                      <div className="flex flex-col items-start">
                        <span className="font-medium">PPT 에이전트</span>
                        <span className="text-xs text-gray-500">발표 자료 자동 생성</span>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTool('web-search');
                        setIsToolMenuOpen(false);
                      }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-gray-700 rounded-lg transition-colors hover:bg-blue-50 hover:text-blue-700"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                        <Globe className="h-4 w-4" />
                      </div>
                      <div className="flex flex-col items-start">
                        <span className="font-medium">웹 검색</span>
                        <span className="text-xs text-gray-500">실시간 인터넷 정보 검색</span>
                      </div>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTool('patent');
                        setIsToolMenuOpen(false);
                      }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-gray-700 rounded-lg transition-colors hover:bg-blue-50 hover:text-blue-700"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-100 text-teal-600">
                        <FileIcon className="h-4 w-4" />
                      </div>
                      <div className="flex flex-col items-start">
                        <span className="font-medium">특허 분석</span>
                        <span className="text-xs text-gray-500">특허 검색 및 경쟁사 비교</span>
                      </div>
                    </button>

                    <div className="my-1 border-t border-gray-100"></div>
                    <div className="px-3 py-2 text-xs font-semibold text-gray-500">실험실 (Labs)</div>

                    <button
                      type="button"
                      onClick={() => {
                        setSelectedTool('deep-research');
                        setIsToolMenuOpen(false);
                      }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-sm text-gray-700 rounded-lg transition-colors hover:bg-blue-50 hover:text-blue-700"
                    >
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100 text-purple-600">
                        <Search className="h-4 w-4" />
                      </div>
                      <div className="flex flex-col items-start">
                        <span className="font-medium">Deep Research</span>
                        <span className="text-xs text-gray-500">심층 분석 및 리포트</span>
                      </div>
                    </button>
                  </div>
                )}
              </div>

              {/* 팝업 메뉴 (기존 + 버튼 메뉴) */}
              {isMenuOpen && (
                <div
                  ref={menuPopupRef}
                  className="absolute bottom-full left-0 mb-2 w-56 rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden z-10"
                >
                  <button
                    type="button"
                    onClick={() => {
                      fileInputRef.current?.click();
                      setIsMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-3 px-4 py-3 text-sm text-gray-700 transition-colors hover:bg-gray-50"
                  >
                    <Paperclip className="h-5 w-5 text-gray-500" />
                    <span>파일 업로드</span>
                  </button>
                  <div className="px-4 py-3 border-b border-gray-100">
                    <div className="flex items-center gap-3 mb-2">
                      <Radio className="h-5 w-5 text-blue-500" />
                      <span className="text-sm font-medium text-gray-700">실시간 음성인식</span>
                    </div>
                    <div className="ml-8">
                      <select
                        value={sttLanguage}
                        onChange={(e) => setSttLanguage(e.target.value)}
                        disabled={!isRealtimeSupported}
                        className="w-full px-3 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <option value="ko-KR">🇰🇷 한국어</option>
                        <option value="en-US">🇺🇸 영어 (미국)</option>
                        <option value="ja-JP">🇯🇵 일본어</option>
                        <option value="zh-CN">🇨🇳 중국어 (간체)</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => {
                          handleStartRealtimeSTT();
                          setIsMenuOpen(false);
                        }}
                        disabled={isRealtimeRecording || !isRealtimeSupported}
                        className="mt-2 w-full px-3 py-1.5 text-xs bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isRealtimeSupported ? '시작' : '브라우저에서 지원되지 않습니다'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 우측: 전송 버튼 */}
            <button
              type="button"
              onClick={() => {
                if (isLoading) {
                  onStopStreaming?.();
                } else {
                  void handleSubmit();
                }
              }}
              disabled={isLoading ? !onStopStreaming : (!message.trim() && !fileDrafts.length)}
              className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all ${isLoading
                ? 'bg-gray-400 text-white'
                : message.trim() || fileDrafts.length > 0
                  ? 'bg-blue-600 text-white hover:bg-blue-700'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }`}
              title={isLoading ? '생성 중지' : '전송'}
            >
              {isLoading ? (
                onStopStreaming ? <Square className="h-5 w-5" /> : <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <ArrowUp className="h-5 w-5" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageComposer;

