import React, { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { Download, Maximize2, Minimize2, X, ZoomIn, ZoomOut } from 'lucide-react';

interface ChatAssetViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  assetUrl: string | null;
  fileName?: string | null;
}

const ChatAssetViewerModal: React.FC<ChatAssetViewerModalProps> = ({
  isOpen,
  onClose,
  assetUrl,
  fileName
}) => {
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [zoom, setZoom] = useState(100);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const resolvedName = useMemo(() => {
    if (fileName && fileName.trim()) return fileName;
    if (!assetUrl) return '첨부파일';
    try {
      const u = new URL(assetUrl, window.location.origin);
      const last = u.pathname.split('/').pop() || '첨부파일';
      return decodeURIComponent(last);
    } catch {
      const last = assetUrl.split('/').pop() || '첨부파일';
      return last;
    }
  }, [assetUrl, fileName]);

  useEffect(() => {
    if (!isOpen || !assetUrl) return;

    const token =
      localStorage.getItem('ABEKM_token') ||
      localStorage.getItem('access_token') ||
      localStorage.getItem('token');

    setIsLoading(true);
    setError(null);
    setContent('');
    setZoom(100);
    setIsFullscreen(false);

    fetch(assetUrl, {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined
    })
      .then(async (res) => {
        if (!res.ok) {
          const text = await res.text().catch(() => '');
          throw new Error(text || `HTTP ${res.status}`);
        }
        return res.text();
      })
      .then((text) => {
        setContent(text);
      })
      .catch((e: any) => {
        setError(e?.message || '파일을 불러올 수 없습니다.');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [isOpen, assetUrl]);

  if (!isOpen || !assetUrl) return null;

  const handleZoomIn = () => setZoom((z) => Math.min(z + 10, 180));
  const handleZoomOut = () => setZoom((z) => Math.max(z - 10, 80));
  const handleToggleFullscreen = () => setIsFullscreen((v) => !v);

  const handleSaveAs = async () => {
    if (!assetUrl) return;

    const token =
      localStorage.getItem('ABEKM_token') ||
      localStorage.getItem('access_token') ||
      localStorage.getItem('token');

    const suggestedName = resolvedName || '첨부파일';
    const ext = suggestedName.includes('.') ? suggestedName.split('.').pop()!.toLowerCase() : '';
    const mime =
      ext === 'md' ? 'text/markdown' :
      ext === 'txt' ? 'text/plain' :
      ext === 'log' ? 'text/plain' :
      'application/octet-stream';

    const fetchBlob = async (): Promise<Blob> => {
      const res = await fetch(assetUrl, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(text || `HTTP ${res.status}`);
      }
      return await res.blob();
    };

    // Prefer File System Access API when available (enables Save As dialog w/ directory selection)
    const showSaveFilePicker = (window as any).showSaveFilePicker as
      | undefined
      | ((options?: any) => Promise<any>);

    if (showSaveFilePicker) {
      try {
        const pickerOpts = {
          suggestedName,
          types: [
            {
              description: '파일',
              accept: { [mime]: ext ? [`.${ext}`] : ['.*'] }
            }
          ],
          excludeAcceptAllOption: false
        };

        const handle = await showSaveFilePicker(pickerOpts);
        const blob = await fetchBlob();
        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
        return;
      } catch (e) {
        // User cancelled or picker failed → fallback
      }
    }

    // Fallback: classic download (browser will show save prompt depending on settings)
    try {
      const blob = await fetchBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = suggestedName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: any) {
      setError(e?.message || '다운로드에 실패했습니다.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div
        className={
          isFullscreen
            ? 'relative w-screen h-screen bg-white shadow-lg overflow-hidden'
            : 'relative w-[min(960px,calc(100vw-2rem))] h-[min(80vh,calc(100vh-6rem))] bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden'
        }
      >
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
          <div className="text-sm font-medium text-gray-800 truncate">{resolvedName}</div>
          <div className="flex items-center gap-2">
            <button
              className="inline-flex items-center gap-1.5 px-2 py-1.5 text-xs rounded-md border border-gray-200 bg-white hover:bg-gray-50"
              onClick={handleZoomOut}
              title="축소"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <div className="text-xs text-gray-600 min-w-[48px] text-center">{zoom}%</div>
            <button
              className="inline-flex items-center gap-1.5 px-2 py-1.5 text-xs rounded-md border border-gray-200 bg-white hover:bg-gray-50"
              onClick={handleZoomIn}
              title="확대"
            >
              <ZoomIn className="w-4 h-4" />
            </button>

            <button
              className="inline-flex items-center gap-1.5 px-2 py-1.5 text-xs rounded-md border border-gray-200 bg-white hover:bg-gray-50"
              onClick={handleToggleFullscreen}
              title={isFullscreen ? '전체화면 해제' : '전체화면'}
            >
              {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
            </button>

            <button
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md border border-gray-200 bg-white hover:bg-gray-50"
              onClick={handleSaveAs}
              title="다른 이름으로 저장"
            >
              <Download className="w-4 h-4" />
              다운로드
            </button>
            <button
              className="p-1.5 rounded-md hover:bg-gray-100"
              onClick={onClose}
              title="닫기"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="h-[calc(100%-42px)] overflow-y-auto p-4">
          {isLoading && (
            <div className="text-sm text-gray-500">파일을 불러오는 중...</div>
          )}
          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
              ❌ {error}
            </div>
          )}
          {!isLoading && !error && (
            <div
              className="prose prose-sm max-w-none text-left prose-headings:text-left prose-p:text-left prose-li:text-left prose-th:text-left prose-td:text-left"
              style={{ fontSize: `${(14 * zoom) / 100}px` }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} skipHtml>
                {content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatAssetViewerModal;
