import {
  ArrowUp,
  ChevronDown,
  ChevronUp,
  File as FileIcon,
  Mic,
  Paperclip,
  Play,
  Plus,
  Square,
  Trash2,
  UploadCloud,
  Volume2,
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
import { AttachmentCategory } from '../types/chat.types';

interface MessageComposerProps {
  onSendMessage: (message: string, files?: File[], voiceBlob?: Blob) => Promise<void> | void;
  onStopStreaming?: () => void;
  isLoading: boolean;
  placeholder?: string;
  onDraftTranscription?: (blob: Blob) => Promise<string>;
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

const MessageComposer: React.FC<MessageComposerProps> = ({
  onSendMessage,
  onStopStreaming,
  isLoading,
  placeholder = '메시지를 입력하세요...',
  onDraftTranscription,
  ragState
}) => {
  const [message, setMessage] = useState('');
  const [fileDrafts, setFileDrafts] = useState<FileDraft[]>([]);
  const [isDraggingFile, setDraggingFile] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceDraft, setVoiceDraft] = useState<Blob | null>(null);
  const [voicePreviewUrl, setVoicePreviewUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const menuPopupRef = useRef<HTMLDivElement>(null);
  const ragDocuments = useMemo(() => ragState?.documents ?? [], [ragState?.documents]);

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
      if (voicePreviewUrl) {
        URL.revokeObjectURL(voicePreviewUrl);
      }
    };
  }, [fileDrafts, cleanupPreviews, voicePreviewUrl]);

  // TextareaAutosize를 사용하므로 수동 높이 조절 불필요

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  const resetRecordingTimer = () => {
    if (recordingTimerRef.current) {
      clearInterval(recordingTimerRef.current);
      recordingTimerRef.current = null;
    }
  };

  const handleSubmit = async () => {
    const trimmed = message.trim();
    const files = fileDrafts.map(draft => draft.file);

    if (!trimmed && !files.length && !voiceDraft) {
      return;
    }

    await onSendMessage(trimmed, files, voiceDraft ?? undefined);

    setMessage('');
    cleanupPreviews(fileDrafts);
    setFileDrafts([]);
    setVoiceDraft(null);
    if (voicePreviewUrl) {
      URL.revokeObjectURL(voicePreviewUrl);
      setVoicePreviewUrl(null);
    }
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      alert('이 브라우저는 음성 녹음을 지원하지 않습니다.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: 'audio/webm' });
        setVoiceDraft(blob);
        const preview = URL.createObjectURL(blob);
        if (voicePreviewUrl) URL.revokeObjectURL(voicePreviewUrl);
        setVoicePreviewUrl(preview);
        stream.getTracks().forEach(track => track.stop());
        resetRecordingTimer();
        setRecordingTime(0);

        if (onDraftTranscription) {
          setTranscribing(true);
          onDraftTranscription(blob)
            .then(text => {
              if (text) {
                setMessage(prev => prev ? `${prev}\n${text}` : text);
              }
            })
            .catch(err => {
              console.warn('음성 초안 변환 실패', err);
            })
            .finally(() => setTranscribing(false));
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setRecordingTime(0);
      recordingTimerRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('음성 녹음 시작 실패:', error);
      alert('마이크 권한을 확인해주세요.');
    }
  };

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    mediaRecorderRef.current = null;
    resetRecordingTimer();
  }, []);

  const removeVoiceDraft = () => {
    setVoiceDraft(null);
    if (voicePreviewUrl) {
      URL.revokeObjectURL(voicePreviewUrl);
      setVoicePreviewUrl(null);
    }
  };

  const handleFilesSelected = (input?: FileList | File[] | null) => {
    if (!input) return;
    const filesArray = Array.isArray(input) ? input : Array.from(input);
    if (!filesArray.length) {
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
        if (isRecording) {
          stopRecording();
        } else if (isDraggingFile) {
          setDraggingFile(false);
        } else if (isMenuOpen) {
          setIsMenuOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isRecording, isDraggingFile, isMenuOpen, stopRecording]);

  // 팝업 메뉴 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isMenuOpen &&
        menuPopupRef.current &&
        menuButtonRef.current &&
        !menuPopupRef.current.contains(event.target as Node) &&
        !menuButtonRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMenuOpen]);

  const recordingLabel = useMemo(() => {
    const minutes = Math.floor(recordingTime / 60);
    const seconds = recordingTime % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, [recordingTime]);

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
        {(fileDrafts.length > 0 || voiceDraft) && (
          <button
            type="button"
            onClick={() => {
              clearDrafts();
              removeVoiceDraft();
            }}
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

      {(fileDrafts.length > 0 || voiceDraft) && (
        <div className="px-4 pt-3">
          <div className="mb-2 flex items-center justify-between text-xs font-medium text-gray-600">
            <span>첨부 {fileDrafts.length + (voiceDraft ? 1 : 0)}개</span>
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
            {voiceDraft && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                <Volume2 className="h-5 w-5 text-amber-500" />
                <span>음성 초안 {formatFileSize(voiceDraft.size)}</span>
                {voicePreviewUrl && (
                  <audio controls src={voicePreviewUrl} className="h-8" />
                )}
                <button
                  type="button"
                  onClick={removeVoiceDraft}
                  className="text-amber-500 hover:text-red-500"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="px-4 pb-3 pt-2.5">
        {/* 녹음 상태 표시 */}
        {isRecording && (
          <div className="mb-3 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-600">
            <Play className="h-4 w-4 animate-pulse" />
            <span className="font-medium">녹음 중... {recordingLabel}</span>
            <button
              type="button"
              onClick={stopRecording}
              className="ml-auto rounded-md px-2 py-1 text-xs text-red-600 hover:bg-red-100"
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
          accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,image/*,audio/*"
          onChange={handleFileInputChange}
        />

        <div className="flex flex-col gap-1.5">
          {/* 1줄: 텍스트 입력 영역 (전체 폭) */}
          <div className="w-full">
            <TextareaAutosize
              ref={textareaRef as any}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
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
            {transcribing && (
              <div className="mt-1 flex items-center gap-1.5 px-4 text-xs text-amber-600">
                <UploadCloud className="h-3.5 w-3.5 animate-pulse" />
                <span>음성 텍스트 변환 중...</span>
              </div>
            )}
          </div>

          {/* 2줄: 버튼 영역 (좌측 + 버튼, 우측 전송 버튼) */}
          <div className="flex items-center justify-between">
            {/* 좌측: + 버튼 (팝업 메뉴) */}
            <div className="relative">
              <button
                ref={menuButtonRef}
                type="button"
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-700"
                title="도구 메뉴"
              >
                <Plus className="h-5 w-5" />
              </button>

              {/* 팝업 메뉴 */}
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
                  <button
                    type="button"
                    onClick={() => {
                      startRecording();
                      setIsMenuOpen(false);
                    }}
                    disabled={isRecording}
                    className="flex w-full items-center gap-3 px-4 py-3 text-sm text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Mic className="h-5 w-5 text-gray-500" />
                    <span>음성으로 입력 (STT)</span>
                  </button>
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
              disabled={isLoading ? !onStopStreaming : (!message.trim() && !fileDrafts.length && !voiceDraft)}
              className={`flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all ${isLoading
                ? 'bg-gray-400 text-white'
                : message.trim() || fileDrafts.length > 0 || voiceDraft
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

