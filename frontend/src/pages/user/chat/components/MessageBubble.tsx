import { Bot, Copy, FileText, Paperclip, User } from 'lucide-react';
import React, { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { downloadByUrl } from '../../../../services/userService';
import { getAccessToken } from '../../../../utils/tokenStorage';
import { ChatMessage } from '../types/chat.types';
import HTMLCard from './HTMLCard';
import ReferencePanel from './ReferencePanel';
import PresentationActionBar from './presentation/PresentationActionBar';

interface AttachmentProps {
  id?: string;
  fileName: string;
  downloadUrl?: string;
  previewUrl?: string;
}

const AuthenticatedImageAttachment: React.FC<{
  attachment: AttachmentProps;
  onClick?: () => void;
}> = ({ attachment, onClick }) => {
  const [resolvedUrl, setResolvedUrl] = useState<string | undefined>(() => {
    if (attachment.previewUrl && (attachment.previewUrl.startsWith('blob:') || attachment.previewUrl.startsWith('data:'))) {
      return attachment.previewUrl;
    }
    return undefined;
  });

  useEffect(() => {
    // previewUrl이 있고, blob: 또는 data: 로 시작하는 경우에만 직접 사용 (로컬 미리보기)
    if (attachment.previewUrl && (attachment.previewUrl.startsWith('blob:') || attachment.previewUrl.startsWith('data:'))) {
      setResolvedUrl(attachment.previewUrl);
      return;
    }

    if (!attachment.downloadUrl) {
      return;
    }

    const controller = new AbortController();
    let objectUrl: string | null = null;

    const loadImage = async () => {
      try {
        const token = getAccessToken();
        const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await fetch(attachment.downloadUrl!, {
          headers,
          signal: controller.signal
        });
        if (!response.ok) {
          throw new Error(`이미지 로드 실패: ${response.status}`);
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        setResolvedUrl(objectUrl);
      } catch (error) {
        console.error('이미지 미리보기 로드 실패:', error);
        setResolvedUrl(attachment.downloadUrl);
      }
    };

    loadImage();

    return () => {
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [attachment.downloadUrl, attachment.previewUrl]);

  if (!resolvedUrl) {
    return (
      <div className="w-32 h-32 flex items-center justify-center rounded-lg border border-dashed border-gray-300 text-xs text-gray-400">
        이미지 미리보기 실패
      </div>
    );
  }

  return (
    <img
      src={resolvedUrl}
      alt={attachment.fileName}
      className="w-32 h-32 object-cover rounded-lg border border-gray-200 cursor-pointer hover:border-blue-400 transition-colors"
      onClick={onClick}
    />
  );
};

interface MessageBubbleProps {
  message: ChatMessage;
  onOpenDocument?: (doc: {
    id: string;
    file_name: string;
    file_extension?: string;
    title?: string;
  }) => void;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onOpenDocument }) => {
  const [showReferences, setShowReferences] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showHtmlPreview, setShowHtmlPreview] = useState(true);
  const isUser = message.role === 'user';

  // 🆕 백엔드에서 전달하는 detailed_chunks, context_info 기반 참고자료 체크
  const hasReferences = (
    (message.references && message.references.length > 0) ||
    (message.detailed_chunks && message.detailed_chunks.length > 0) ||
    (message.context_info?.chunks_count && message.context_info.chunks_count > 0)
  );

  // 🆕 첨부 파일 기반 답변 체크
  const hasAttachedFiles = (message as any).attached_files && (message as any).attached_files.length > 0;

  const hasPresentationIntent = !!message.presentation_intent;

  // HTML 응답 감지 (완전한 HTML 문서 기준)
  const content = message.content || '';
  const isLikelyHtml = useMemo(() => {
    const hasHtmlRoot = /<html[\s>]/i.test(content) && /<\/html>/i.test(content);
    const hasDoctype = /<!DOCTYPE\s+html/i.test(content);
    const hasBody = /<body[\s>]/i.test(content) && /<\/body>/i.test(content);
    return (hasHtmlRoot || hasDoctype || hasBody);
  }, [content]);

  // 세션 ID는 상위 훅에서 넘어오지만, 여기서는 링크 삽입만 하고 원클릭은 훅 내 SSE 결과를 그대로 활용
  // 간단하게 sessionId를 전역 훅에서 가져오지 않고, 액션은 호출 측에서 처리하도록 콜백을 구성할 수도 있습니다.
  // 여기서는 별도 훅 인스턴스를 만들지 않고, 프레젠테이션 훅만 세션 ID 필요 시 상위에서 주입하는 구조가 이상적입니다.

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('클립보드 복사 실패:', err);
    }
  };

  const formattedAiContent = useMemo(() => {
    if (!message.content) return '';
    return message.content.trim();
  }, [message.content]); const getAgentBadge = () => {
    if (!message.agent_type || message.agent_type === 'general') return null;

    const agentMap: Record<string, { name: string; icon: string; color: string }> = {
      general: { name: '일반 대화', icon: '💬', color: 'bg-gray-100 text-gray-800' },
      summarizer: { name: '요약 전문가', icon: '📄', color: 'bg-blue-100 text-blue-800' },
      'keyword-extractor': { name: '키워드 추출', icon: '🔍', color: 'bg-green-100 text-green-800' },
      presentation: { name: 'PPT 생성', icon: '📊', color: 'bg-orange-100 text-orange-800' },
      template: { name: '템플릿 생성', icon: '📝', color: 'bg-purple-100 text-purple-800' },
      'knowledge-graph': { name: '지식 그래프', icon: '🧠', color: 'bg-indigo-100 text-indigo-800' },
      analyzer: { name: '분석 전문가', icon: '📈', color: 'bg-pink-100 text-pink-800' },
      insight: { name: '인사이트 도출', icon: '💡', color: 'bg-yellow-100 text-yellow-800' },
      'report-generator': { name: '보고서 생성', icon: '📋', color: 'bg-teal-100 text-teal-800' },
      'script-generator': { name: '스크립트 생성', icon: '🎬', color: 'bg-red-100 text-red-800' },
      'key-points': { name: '핵심 요점', icon: '⭐', color: 'bg-emerald-100 text-emerald-800' }
    };

    const agent = agentMap[message.agent_type];
    if (!agent) return null;

    return (
      <div className={`inline-flex items-center space-x-1 px-2 py-1 rounded-full text-xs font-medium ${agent.color} mb-2`}>
        <span>{agent.icon}</span>
        <span>{agent.name}</span>
      </div>
    );
  };

  // 사용자 메시지의 서브타입에 따른 스타일링
  const getUserMessageStyle = () => {
    if (message.message_subtype === 'selected_documents') {
      return 'bg-white text-gray-900 border border-gray-200 shadow-sm';
    }
    return 'bg-gray-100 text-gray-900 border border-gray-300';
  };

  // PPT 다운로드 링크 전용 메시지인지 여부
  const isPresentationDownload = !isUser && message.message_subtype === 'presentation_download';

  // 선택된 문서 정보 렌더링
  const renderSelectedDocuments = () => {
    if (!message.selected_documents || message.selected_documents.length === 0) {
      return null;
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-3">
          <FileText className="w-4 h-4" />
          <span>선택된 문서 정보:</span>
        </div>
        {message.selected_documents.map((doc, index) => (
          <div key={index} className="flex items-center space-x-3 p-2 bg-gray-50 rounded-lg">
            <div className="flex-shrink-0">
              <FileText className="w-4 h-4 text-gray-500" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-gray-900 truncate">
                {doc.fileName}
              </div>
              <div className="text-xs text-gray-500">
                {doc.fileType.toUpperCase()}
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const formatAttachmentSize = (size: number) => {
    if (!size) return '';
    if (size < 1024) return `${size}B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
    return `${(size / (1024 * 1024)).toFixed(1)}MB`;
  };

  const handleAttachmentDownload = async (attachment: { downloadUrl?: string; fileName: string }) => {
    if (!attachment.downloadUrl) return;
    try {
      await downloadByUrl(attachment.downloadUrl, attachment.fileName);
    } catch (error) {
      console.error('첨부 파일 다운로드 실패:', error);
    }
  };

  const renderAttachments = (isAssistantMessage: boolean) => {
    if (!message.attachments || message.attachments.length === 0) {
      return null;
    }

    // 이미지와 문서 분리
    const imageAttachments = message.attachments.filter(att => att.category === 'image');
    const docAttachments = message.attachments.filter(att => att.category !== 'image');

    return (
      <div className={`mt-3 ${isAssistantMessage ? '' : 'text-left'}`}>
        {/* 🆕 이미지 미리보기 */}
        {imageAttachments.length > 0 && (
          <div className="mb-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              <span>이미지 ({imageAttachments.length})</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {imageAttachments.map((attachment) => (
                <div key={attachment.id} className="relative group">
                  <AuthenticatedImageAttachment
                    attachment={attachment}
                    onClick={() => attachment.downloadUrl && window.open(attachment.downloadUrl, '_blank')}
                  />
                  <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-50 text-white text-xs px-2 py-1 rounded-b-lg truncate opacity-0 group-hover:opacity-100 transition-opacity">
                    {attachment.fileName}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 문서 첨부 파일 */}
        {docAttachments.length > 0 && (
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-2">
              <Paperclip className="w-4 h-4" />
              <span>첨부 파일 ({docAttachments.length})</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {docAttachments.map((attachment) => (
                <button
                  key={attachment.id}
                  type="button"
                  onClick={() => handleAttachmentDownload(attachment)}
                  className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600 hover:border-blue-300 hover:text-blue-600 shadow-sm transition-colors"
                  title={`${attachment.fileName} 다운로드`}
                >
                  <FileText className="w-4 h-4" />
                  <span className="font-medium truncate max-w-[180px]">{attachment.fileName}</span>
                  {attachment.size ? (
                    <span className="text-[10px] text-gray-400">
                      {formatAttachmentSize(attachment.size)}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="w-full px-1">
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
        <div className={`flex ${isUser ? 'flex-row-reverse' : 'flex-row'} items-start w-full`} style={{ marginLeft: '5px', marginRight: '5px' }}>
          {/* 아바타 */}
          <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${isUser ? 'ml-3' : 'mr-3'}`}>
            {isUser ? (
              <div className="w-full h-full bg-gray-300 rounded-full flex items-center justify-center">
                <User className="w-6 h-6 text-gray-600" />
              </div>
            ) : (
              <div className="w-full h-full bg-gradient-to-r from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
                <Bot className="w-6 h-6 text-white" />
              </div>
            )}
          </div>

          {/* 메시지 컨테이너 */}
          <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : 'text-left'}`}>
            {/* 에이전트 배지 (AI 메시지에만) */}
            {!isUser && getAgentBadge() && (
              <div className="mb-2">
                {getAgentBadge()}
              </div>
            )}

            {/* 🆕 답변 근거 표시 (assistant 메시지만) */}
            {!isUser && (hasAttachedFiles || hasReferences) && (
              <div className="mb-2 space-y-1.5">
                {/* 첨부 파일 기반 답변 */}
                {hasAttachedFiles && (
                  <div className="bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-sm inline-block">
                    <div className="flex items-center gap-2 text-blue-800">
                      <Paperclip className="w-4 h-4" />
                      <span className="font-medium">📎 참조 문서:</span>
                    </div>
                    <div className="mt-1 space-y-0.5">
                      {(message as any).attached_files.map((file: any, idx: number) => (
                        <div key={idx} className="text-blue-700 text-xs flex items-center gap-1">
                          <FileText className="w-3 h-3" />
                          <span>{file.file_name}</span>
                          <span className="text-blue-500">({(file.file_size / 1024).toFixed(0)}KB)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {/* 데이터베이스 검색 기반 답변 */}
                {!hasAttachedFiles && hasReferences && (
                  <div className="bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm inline-block">
                    <div className="flex items-center gap-2 text-green-800">
                      <FileText className="w-4 h-4" />
                      <span className="font-medium">🔍 데이터베이스 검색 기반 답변 ({message.context_info?.chunks_count || 0}개 문서)</span>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* 메시지 버블 */}
            <div
              className={`relative px-4 py-2.5 rounded-2xl shadow-sm w-full overflow-hidden ${isUser
                ? getUserMessageStyle()
                : 'bg-white text-gray-900 border border-gray-100'
                }`}
            >
              {/* 메시지 내용 */}
              <div className="text-left">
                {isUser ? (
                  <div className="space-y-3">
                    {/* 선택된 문서 정보 표시 */}
                    {message.message_subtype === 'selected_documents'
                      ? renderSelectedDocuments()
                      : (
                        <div className="whitespace-pre-wrap break-words leading-relaxed">
                          {message.content}
                        </div>
                      )
                    }
                    {renderAttachments(false)}
                  </div>
                ) : (
                  // AI 메시지는 마크다운 또는 HTML 미리보기로 렌더링
                  <div className="w-full text-left break-words overflow-hidden">
                    {isLikelyHtml && showHtmlPreview ? (
                      <div className="mb-3">
                        <HTMLCard html={content} title="HTML 미리보기" />
                      </div>
                    ) : (
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, remarkBreaks]}
                        skipHtml={true}
                        className="text-gray-900 leading-snug text-sm max-w-none"
                        transformLinkUri={(href, children, title) => {
                          // doc-open 스킴은 그대로 유지
                          if (href?.startsWith('doc-open://')) {
                            return href;
                          }
                          // 다른 링크들은 기본 처리
                          return href || '';
                        }}
                        components={{
                          // 커스텀 스타일링 - 시각적 강조 개선
                          p: ({ children }) => (
                            <p className="my-0.5 text-left leading-snug text-gray-800 text-sm">
                              {children}
                            </p>
                          ),
                          h1: ({ children }) => (
                            <h1 className="text-2xl font-bold mb-3 mt-4 text-left text-red-600 border-b-2 border-red-300 pb-2">
                              {children}
                            </h1>
                          ),
                          h2: ({ children }) => (
                            <h2 className="text-xl font-bold mb-2 mt-3 text-left text-blue-600 bg-blue-50 px-2 py-1">
                              {children}
                            </h2>
                          ),
                          h3: ({ children }) => (
                            <h3 className="text-lg font-bold mb-2 mt-3 text-left text-green-600 bg-green-50 px-2 py-1">
                              {children}
                            </h3>
                          ),
                          ul: ({ children }) => (
                            <ul className="list-disc pl-5 my-1 space-y-0.5 text-left">
                              {children}
                            </ul>
                          ),
                          ol: ({ children }) => (
                            <ol className="list-decimal pl-5 my-1 space-y-0.5 text-left">
                              {children}
                            </ol>
                          ),
                          li: ({ children }) => {
                            // 리스트 항목 내부에 자동으로 생성되는 <p>를 제거하여 여백 최소화
                            let content = children as React.ReactNode;
                            if (Array.isArray(children) && children.length === 1) {
                              const only = children[0] as React.ReactElement<any>;
                              if (React.isValidElement(only) && (only.type as any) === 'p') {
                                const inner = (only.props as any)?.children;
                                content = inner ?? content;
                              }
                            }
                            return (
                              <li className="text-left leading-snug text-gray-800 text-sm ml-1">
                                {content}
                              </li>
                            );
                          },
                          strong: ({ children }) => (
                            <strong className="font-bold text-red-600 bg-yellow-100 px-1">
                              {children}
                            </strong>
                          ),
                          em: ({ children }) => (
                            <em className="italic text-gray-800">
                              {children}
                            </em>
                          ),
                          blockquote: ({ children }) => (
                            <blockquote className="border-l-4 border-blue-300 pl-3 pr-2 py-1.5 mb-2 bg-blue-50">
                              <div className="text-gray-800 text-sm leading-snug italic">
                                {children}
                              </div>
                            </blockquote>
                          ),
                          hr: () => (
                            <hr className="my-2 border-gray-300" />
                          ),
                          pre: ({ children }) => (
                            <div className="bg-gray-900 rounded-md p-2.5 mb-2 overflow-x-auto border border-gray-800">
                              <pre className="text-green-400 text-xs font-mono leading-snug">
                                {children}
                              </pre>
                            </div>
                          ),
                          code: ({ children, className }) => {
                            if (className?.includes('language-')) {
                              return (
                                <code className="text-green-400 font-mono text-xs">
                                  {children}
                                </code>
                              );
                            }
                            return (
                              <code className="bg-gray-100 text-red-600 px-1 py-0.5 rounded font-mono text-sm border border-gray-200">
                                {children}
                              </code>
                            );
                          },
                          table: ({ children }) => (
                            <div className="overflow-x-auto mb-3 rounded-md border border-gray-200">
                              <table className="w-full border-collapse text-left bg-white">
                                {children}
                              </table>
                            </div>
                          ),
                          th: ({ children }) => (
                            <th className="border-b border-gray-300 px-2 py-1 font-semibold text-left text-gray-900 text-[12.5px] bg-gray-50">
                              {children}
                            </th>
                          ),
                          td: ({ children }) => (
                            <td className="border-b border-gray-200 px-2 py-1 text-left text-gray-800 text-[12.5px]">
                              {children}
                            </td>
                          ),
                          a: ({ children, href }) => {
                            const isDocOpen = (u: string) => u.startsWith('doc-open://');
                            // 템플릿 모드(URL 템플릿)로 전달된 뷰어 링크인지 판단: fileId= 또는 docId= 파라미터가 존재
                            const isTemplateViewer = (u: string) => /[?&](fileId|docId)=/.test(u);
                            const extractDocId = (u: string): string => {
                              try {
                                const urlObj = new URL(u, window.location.origin);
                                return urlObj.searchParams.get('fileId') || urlObj.searchParams.get('docId') || '';
                              } catch {
                                return '';
                              }
                            };
                            const extractFileNameFromChildren = (): string => {
                              // children 이 문자열/배열 혼합일 수 있으므로 텍스트만 추출
                              const recur = (node: any): string => {
                                if (node == null) return '';
                                if (typeof node === 'string') return node;
                                if (Array.isArray(node)) return node.map(recur).join('');
                                if (typeof node === 'object' && 'props' in node) return recur((node as any).props.children);
                                return '';
                              };
                              return recur(children).trim();
                            };
                            const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
                              if (!href) return;
                              const url = href.toString();

                              // 디버그 로그 추가
                              // 커스텀 문서 오픈 스킴 처리 (doc-open://) → 새 탭 열지 않고 뷰어 오픈
                              if (isDocOpen(url)) {
                                e.preventDefault();
                                try {
                                  const work = url.replace('doc-open://', 'https://placeholder/');
                                  const u = new URL(work);
                                  const docId = u.searchParams.get('docId') || '';
                                  const name = decodeURIComponent(u.searchParams.get('name') || '문서');
                                  const ext = decodeURIComponent(u.searchParams.get('ext') || (name.includes('.') ? name.split('.').pop() || '' : ''));
                                  if (onOpenDocument && docId) {
                                    onOpenDocument({ id: docId, file_name: name, file_extension: ext, title: name });
                                  }
                                } catch (err) {
                                  console.error('❌ doc-open 링크 파싱 실패:', err);
                                }
                                return;
                              }
                              // 템플릿 모드 viewer 링크 (fileId= 또는 docId= 파라미터 포함) 인터셉트
                              if (isTemplateViewer(url)) {
                                const docId = extractDocId(url);
                                if (docId) {
                                  e.preventDefault();
                                  const fileName = extractFileNameFromChildren();
                                  const ext = fileName.includes('.') ? fileName.split('.').pop() || '' : '';
                                  if (onOpenDocument) {
                                    onOpenDocument({ id: docId, file_name: fileName || '문서', file_extension: ext, title: fileName });
                                    return; // 새 탭 열지 않음
                                  }
                                }
                              }
                              // 업로드/다운로드 API 링크는 강제 다운로드 처리
                              if (url.startsWith('/uploads/') || url.startsWith('/api/v1/chat/presentation/download/')) {
                                try {
                                  const text = (children as any)?.toString?.() || undefined;
                                  const fallbackTitle = text?.replace(/[[\]]/g, '') || undefined;
                                  downloadByUrl(url, fallbackTitle, 'pptx');
                                  e.preventDefault();
                                } catch {
                                  // 실패 시 기본 동작(새 탭 열기)
                                }
                              }
                            };
                            const url = href?.toString() || '';
                            const target = (isDocOpen(url) || isTemplateViewer(url)) ? undefined : '_blank';
                            const rel = (isDocOpen(url) || isTemplateViewer(url)) ? undefined : 'noopener noreferrer';

                            // 추가 디버그: href와 URL 상태 로깅
                            return (
                              <a
                                href={href}
                                target={target}
                                rel={rel}
                                onClick={handleClick}
                                className="text-blue-600 hover:text-blue-800 underline font-medium transition-colors duration-200"
                              >
                                {children}
                              </a>
                            );
                          },
                          del: ({ children }) => (
                            <del className="line-through text-gray-500">
                              {children}
                            </del>
                          )
                        }}
                      >
                        {formattedAiContent}
                      </ReactMarkdown>
                    )}
                    {renderAttachments(true)}
                  </div>
                )}
              </div>

              {/* 메시지 액션 바 */}
              <div className={`flex items-center mt-3 pt-2 border-t ${isUser
                ? 'border-gray-200 justify-between'
                : 'border-gray-100 justify-between'
                }`}>
                <span className={`text-xs ${isUser ? 'text-gray-500' : 'text-gray-500'}`}>
                  {formatTime(message.timestamp)}
                </span>

                <div className="flex items-center space-x-2">
                  {/* HTML 미리보기 토글 (AI 메시지에서만) */}
                  {!isUser && isLikelyHtml && (
                    <button
                      onClick={() => setShowHtmlPreview((v) => !v)}
                      className="px-2 py-1.5 rounded-lg text-xs font-medium transition-colors bg-green-50 hover:bg-green-100 text-green-700"
                    >
                      {showHtmlPreview ? '🔎 HTML 숨기기' : '🔎 HTML 보기'}
                    </button>
                  )}
                  {/* 프레젠테이션 모드 버튼 제거 (새 탭 열기와 기능 중복) */}
                  {/* PPT 생성 액션: 어시스턴트 메시지에서 발표자료 의도가 감지될 때 표시 (참고자료 유무와 관계없이) */}
                  {!isUser && !isPresentationDownload && hasPresentationIntent && (
                    <PresentationActionBar
                      sourceMessageId={message.message_id || message.id}
                      sessionId={''}
                      onBuildOneClick={(sourceMessageId, presentationType) => {
                        // 원클릭은 기존 SSE 기반 훅과 충돌을 피하기 위해 앞으로 상위 컴포넌트에서 주입하도록 권장
                        // 임시로 이벤트를 발생시켜 상위 컨테이너가 처리하게 할 수 있습니다.
                        const evt = new CustomEvent('presentation:buildOneClick', {
                          detail: {
                            sourceMessageId: sourceMessageId,
                            presentationType: presentationType
                          }
                        });
                        window.dispatchEvent(evt);
                      }}
                      onOpenOutline={(sourceMessageId, presentationType) => {
                        const evt = new CustomEvent('presentation:openOutline', {
                          detail: {
                            sourceMessageId: sourceMessageId,
                            presentationType: presentationType
                          }
                        });
                        window.dispatchEvent(evt);
                      }}
                    />
                  )}
                  {/* 복사 버튼 (AI 메시지에만) */}
                  {!isUser && (
                    <button
                      onClick={copyToClipboard}
                      className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors group"
                      title="메시지 복사"
                    >
                      <Copy className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
                    </button>
                  )}

                  {/* 참고자료 버튼 */}
                  {hasReferences && (
                    <button
                      onClick={() => setShowReferences(!showReferences)}
                      className="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors bg-blue-50 hover:bg-blue-100 text-blue-700"
                    >
                      📚 참고자료 {message.context_info?.chunks_count || message.detailed_chunks?.length || message.references?.length || 0}개
                      <span className="ml-1">
                        {showReferences ? '▼' : '▶'}
                      </span>
                    </button>
                  )}
                </div>
              </div>

              {/* 복사 성공 표시 */}
              {copied && (
                <div className="absolute -top-8 right-0 bg-gray-800 text-white text-xs px-2 py-1 rounded z-10">
                  복사됨!
                </div>
              )}
            </div>

            {/* 참고자료 패널 */}
            {hasReferences && showReferences && (
              <div className="mt-3 w-full overflow-hidden">
                <ReferencePanel
                  references={message.detailed_chunks || message.references || []}
                  contextInfo={message.context_info}
                  ragStats={message.rag_stats}
                />
              </div>
            )}

            {/* RAG 통계 정보 (개발 모드에서만) */}
            {message.rag_stats && process.env.NODE_ENV === 'development' && (
              <div className="mt-2 p-2 bg-gray-50 rounded-lg text-xs text-gray-500">
                <div className="grid grid-cols-2 gap-2 text-left">
                  <span>Provider: {message.rag_stats.provider || 'N/A'}</span>
                  <span>검색 시간: {
                    message.rag_stats.search_time !== null && message.rag_stats.search_time !== undefined
                      ? `${message.rag_stats.search_time.toFixed(2)}ms`
                      : 'N/A'
                  }</span>
                  <span>청크 수: {message.rag_stats.final_chunks}</span>
                  <span>유사도: {
                    message.rag_stats.avg_similarity !== null && message.rag_stats.avg_similarity !== undefined
                      ? message.rag_stats.avg_similarity.toFixed(3)
                      : 'N/A'
                  }</span>
                  {/* 멀티턴 컨텍스트 정보 */}
                  {(message.rag_stats as any)?.multiturn_context && (
                    <>
                      <span className="col-span-2 font-semibold text-blue-600">🔗 멀티턴 컨텍스트 활용됨</span>
                      <span className="col-span-2">주제 연속성: {
                        (message.rag_stats as any)?.topic_continuity !== null && (message.rag_stats as any)?.topic_continuity !== undefined
                          ? ((message.rag_stats as any).topic_continuity * 100).toFixed(1) + '%'
                          : 'N/A'
                      }</span>
                      {(message.rag_stats as any)?.accumulated_keywords && (message.rag_stats as any).accumulated_keywords.length > 0 && (
                        <span className="col-span-2 text-xs">
                          누적 키워드: {(message.rag_stats as any).accumulated_keywords.slice(0, 3).join(', ')}
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageBubble;