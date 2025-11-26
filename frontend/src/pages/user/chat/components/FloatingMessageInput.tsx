import { ChevronUp, Mic, Paperclip, Send, Square } from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';

interface AgentOption {
  id: string;
  name: string;
  description: string;
  icon: string;
}

interface FloatingMessageInputProps {
  onSendMessage: (message: string, files?: File[], voiceBlob?: Blob) => void;
  onStopStreaming?: () => void;
  isLoading: boolean;
  selectedAgent: string;
  onAgentChange: (agentId: string) => void;
  showAgentSelector: boolean;
  onToggleAgentSelector: (show: boolean) => void;
  placeholder?: string;
}

const FloatingMessageInput: React.FC<FloatingMessageInputProps> = ({
  onSendMessage,
  onStopStreaming,
  isLoading,
  selectedAgent,
  onAgentChange,
  showAgentSelector,
  onToggleAgentSelector,
  placeholder = "메시지를 입력하세요..."
}) => {
  const [message, setMessage] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [recordingTime, setRecordingTime] = useState(0);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // AI 에이전트 옵션들
  const agentOptions: AgentOption[] = [
    {
      id: 'general',
      name: '일반 AI',
      description: '일반적인 질문 답변',
      icon: '🤖'
    },
    {
      id: 'ppt_generator',
      name: 'PPT 생성',
      description: 'PowerPoint 프레젠테이션 생성',
      icon: '📊'
    },
    {
      id: 'document_summary',
      name: '문서 요약',
      description: '문서 내용 요약 및 분석',
      icon: '📋'
    },
    {
      id: 'excel_generator',
      name: '엑셀 생성',
      description: 'Excel 스프레드시트 생성',
      icon: '📈'
    },
    {
      id: 'report_writer',
      name: '보고서 작성',
      description: '전문 보고서 작성',
      icon: '📝'
    },
    {
      id: 'data_analyst',
      name: '데이터 분석',
      description: '데이터 분석 및 시각화',
      icon: '📊'
    }
  ];

  const selectedAgentInfo = agentOptions.find(agent => agent.id === selectedAgent) || agentOptions[0];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if ((message.trim() || selectedFiles.length > 0) && !isLoading) {
      onSendMessage(message.trim(), selectedFiles);
      setMessage('');
      setSelectedFiles([]);
      onToggleAgentSelector(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
    adjustTextareaHeight();
  };

  const adjustTextareaHeight = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setSelectedFiles(prev => [...prev, ...newFiles]);
    }
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const audioChunks: Blob[] = [];

      recorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        onSendMessage('', [], audioBlob);
        stream.getTracks().forEach(track => track.stop());
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setRecordingTime(0);

      recordingIntervalRef.current = setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('음성 녹음 시작 실패:', error);
      alert('음성 녹음을 시작할 수 없습니다. 마이크 권한을 확인해주세요.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      setIsRecording(false);
      setMediaRecorder(null);
      setIsRecording(false);
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };


  useEffect(() => {
    adjustTextareaHeight();
  }, [message]);

  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-40">
      {/* AI 에이전트 선택 패널 */}
      {showAgentSelector && (
        <div className="border-b border-gray-100 bg-gray-50 p-4">
          <div className="max-w-4xl mx-auto">
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
              {agentOptions.map((agent) => (
                <button
                  key={agent.id}
                  className={`relative p-3 border rounded-lg cursor-pointer transition-all ${selectedAgent === agent.id
                    ? 'border-blue-500 bg-blue-50 text-blue-700'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  onClick={() => onAgentChange(agent.id)}
                >
                  <div className="text-center">
                    <div className="text-2xl mb-2">{agent.icon}</div>
                    <div className="text-sm font-medium mb-1">{agent.name}</div>
                    <div className="text-xs text-gray-500 leading-tight">
                      {agent.description}
                    </div>
                  </div>
                  {selectedAgent === agent.id && (
                    <div className="absolute top-2 right-2 w-4 h-4 bg-blue-500 rounded-full flex items-center justify-center">
                      <div className="w-2 h-2 bg-white rounded-full"></div>
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 선택된 파일 목록 */}
      {selectedFiles.length > 0 && (
        <div className="border-b border-gray-100 p-3 bg-blue-50">
          <div className="flex flex-wrap gap-2">
            {selectedFiles.map((file, index) => (
              <div key={index} className="flex items-center space-x-2 bg-blue-100 rounded-lg px-3 py-1">
                <span className="text-sm text-blue-700">{file.name}</span>
                <button
                  onClick={() => removeFile(index)}
                  className="text-blue-500 hover:text-blue-700"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 메시지 입력 폼 */}
      <form onSubmit={handleSubmit} className="flex items-end space-x-3 mx-2">
        {/* AI 에이전트 선택 버튼 */}
        <button
          type="button"
          onClick={() => onToggleAgentSelector(!showAgentSelector)}
          className="flex-shrink-0 flex items-center space-x-2 px-3 py-2 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl hover:from-blue-600 hover:to-purple-700 transition-all shadow-md"
        >
          <span className="text-lg">{selectedAgentInfo.icon}</span>
          <span className="hidden sm:inline text-sm font-medium">{selectedAgentInfo.name}</span>
          <ChevronUp
            className={`w-4 h-4 transition-transform ${showAgentSelector ? 'rotate-180' : ''}`}
          />
        </button>

        {/* 메시지 입력 영역 */}
        <div className="flex-1 relative">
          <div className="flex items-center bg-white border border-gray-100 rounded-xl focus-within:border-blue-300 transition-colors shadow-sm mx-1">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={handleTextareaChange}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isLoading || isRecording}
              rows={1}
              className="flex-1 px-4 py-3 bg-transparent resize-none focus:outline-none disabled:opacity-50"
              style={{ maxHeight: '120px' }}
            />

            <div className="flex items-center space-x-1 px-2">
              {/* 파일 업로드 버튼 */}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".txt,.pdf,.doc,.docx,.hwp,.hwpx,.ppt,.pptx,.xls,.xlsx,.jpg,.jpeg,.png,.gif"
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg transition-colors flex items-center justify-center"
              >
                <Paperclip className="w-5 h-5" />
              </button>

              {/* 음성 녹음 버튼 */}
              <button
                type="button"
                onClick={isRecording ? stopRecording : startRecording}
                disabled={isLoading}
                className={`p-2 rounded-lg transition-all flex items-center justify-center ${isRecording
                  ? 'text-red-600 bg-red-50 animate-pulse'
                  : 'text-gray-400 hover:text-blue-500 hover:bg-blue-50'
                  }`}
              >
                <Mic className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* 녹음 시간 표시 */}
          {isRecording && (
            <div className="absolute top-full mt-2 left-4 text-sm text-red-600 font-mono">
              🔴 녹음 중... {formatTime(recordingTime)}
            </div>
          )}
        </div>

        {/* 전송 버튼 */}
        <button
          type={isLoading ? "button" : "submit"}
          onClick={isLoading && onStopStreaming ? onStopStreaming : undefined}
          disabled={(!message.trim() && selectedFiles.length === 0) || (!isLoading && !onStopStreaming)}
          className="flex-shrink-0 w-12 h-12 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:from-gray-400 disabled:to-gray-500 text-white rounded-xl transition-all flex items-center justify-center shadow-lg transform hover:scale-105 disabled:hover:scale-100"
        >
          {isLoading ? (
            onStopStreaming ? (
              <Square className="w-5 h-5" />
            ) : (
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            )
          ) : (
            <Send className="w-5 h-5" />
          )}
        </button>
      </form>

      {/* 도움말 텍스트 */}
      <div className="text-center py-2 text-xs text-gray-400">
        Shift+Enter로 줄바꿈
      </div>
    </div>
  );
};

export default FloatingMessageInput;
