import React from 'react';

type Props = {
    html: string;
    title?: string;
};

const HTMLCard: React.FC<Props> = ({ html, title = 'HTML 미리보기' }) => {
    const iframeRef = React.useRef<HTMLIFrameElement | null>(null);
    const [height, setHeight] = React.useState<number>(420);

    // Parsed deck context for pagination
    const [headHtml, setHeadHtml] = React.useState<string>('');
    const [slides, setSlides] = React.useState<Element[]>([]);
    const [index, setIndex] = React.useState<number>(0);

    // Parse slides on html change
    React.useEffect(() => {
        try {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html || '', 'text/html');
            const found = Array.from(doc.querySelectorAll('section.slide'));
            setSlides(found);
            setHeadHtml(doc.head?.innerHTML || '');
            setIndex(0);
        } catch {
            setSlides([]);
            setHeadHtml('');
            setIndex(0);
        }
    }, [html]);

    const canPrev = index > 0;
    const canNext = index + 1 < slides.length;
    const goPrev = React.useCallback(() => setIndex(i => Math.max(0, i - 1)), []);
    const goNext = React.useCallback(() => setIndex(i => Math.min(slides.length - 1, i + 1)), [slides.length]);

    // Compose doc for current slide when slides are found; else show full HTML
    const srcDoc = React.useMemo(() => {
        if (!slides.length) return html;
        const slide = slides[index] as HTMLElement | undefined;
        if (!slide) return html;
        const head = headHtml || '';
        const overrides = `<style>html,body{overflow:hidden!important;margin:0!important;padding:0!important;} .deck{padding:0!important;} section.slide{margin:0!important;}</style>`;
        const body = slide.outerHTML;
        return '<!DOCTYPE html>\n<html lang="ko">\n<head>' + head + overrides + '</head>\n<body>' + body + '</body>\n</html>';
    }, [slides, index, headHtml, html]);

    // Auto-resize after load (requires same-origin in sandbox)
    const onLoad = React.useCallback(() => {
        const ifr = iframeRef.current;
        if (!ifr) return;
        try {
            const doc = ifr.contentDocument || ifr.contentWindow?.document;
            if (!doc) return;
            const body = doc.body;
            // Basic default style for readability (applied only when full doc without slides)
            if (!slides.length) {
                const style = doc.createElement('style');
                style.textContent = `
          :root { color-scheme: light; }
          body { font-family: system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans KR', 'Apple SD Gothic Neo', '맑은 고딕', sans-serif; margin: 16px; color: #1f2937; }
          h1,h2,h3 { margin: 0.6em 0 0.4em; }
          p, li { line-height: 1.5; }
          table { border-collapse: collapse; }
          table, th, td { border: 1px solid #e5e7eb; }
          th, td { padding: 6px 8px; }
          code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace; }
        `;
                doc.head.appendChild(style);
            }
            // Prevent inner scrollbars and margins
            const viewerStyle = doc.createElement('style');
            viewerStyle.textContent = `html,body{overflow:hidden !important;margin:0 !important;padding:0 !important;}`;
            doc.head.appendChild(viewerStyle);

            // Prefer the slide element height instead of document scrollHeight to avoid cumulative growth
            const slideEl = doc.querySelector('section.slide') as HTMLElement | null;
            const getElHeight = (el: HTMLElement | null) => {
                if (!el) return 0;
                const rect = el.getBoundingClientRect();
                return Math.max(rect.height, el.scrollHeight, el.offsetHeight);
            };
            const baseH = Math.max(getElHeight(slideEl), body ? Math.max(body.scrollHeight, body.offsetHeight) : 0);
            const clamp = (h: number) => Math.min(Math.max(Math.round(h), 360), 1600);
            setHeight(clamp(baseH));
            // re-measure after fonts/layout settle
            setTimeout(() => {
                try {
                    const h2 = Math.max(getElHeight(doc.querySelector('section.slide') as HTMLElement | null), body ? Math.max(body.scrollHeight, body.offsetHeight) : 0);
                    setHeight(clamp(h2));
                } catch { }
            }, 60);
        } catch {
            // ignore, keep default height
        }
    }, [slides.length]);

    const openInNewTab = React.useCallback(() => {
        try {
            const blob = new Blob([html], { type: 'text/html;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            window.open(url, '_blank', 'noopener,noreferrer');
            // URL.revokeObjectURL after a delay
            setTimeout(() => URL.revokeObjectURL(url), 60_000);
        } catch (e) {
            console.error('Open HTML failed', e);
        }
    }, [html]);

    // Use srcDoc to avoid data: URL constraints
    return (
        <div className="border rounded-lg overflow-hidden bg-white relative">
            <div className="flex items-center justify-between px-3 py-2 border-b bg-gray-50">
                <div className="text-xs font-medium text-gray-700">{title}</div>
                <div className="flex items-center gap-2">
                    {slides.length > 0 && (
                        <div className="text-[11px] text-gray-500">{index + 1} / {slides.length}</div>
                    )}
                    <button
                        className="px-2 py-1 text-xs rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
                        onClick={openInNewTab}
                        title="새 탭에서 열기"
                    >
                        새 탭에서 열기
                    </button>
                </div>
            </div>
            <div className="relative">
                <iframe
                    ref={iframeRef}
                    title={title}
                    sandbox="allow-same-origin"
                    scrolling="no"
                    // No allow-scripts: blocks inline/event-handler scripts for safety
                    style={{ width: '100%', height: height, border: '0' }}
                    srcDoc={srcDoc}
                    onLoad={onLoad}
                />
                {slides.length > 0 && (
                    <div className="absolute inset-x-0 bottom-2 px-2 flex items-center justify-between pointer-events-none">
                        <button
                            onClick={goPrev}
                            disabled={!canPrev}
                            className={`pointer-events-auto px-2 py-1 rounded text-xs ${canPrev ? 'bg-black/50 text-white hover:bg-black/60' : 'bg-black/10 text-gray-400 cursor-not-allowed'}`}
                        >
                            ◀ 이전
                        </button>
                        <button
                            onClick={goNext}
                            disabled={!canNext}
                            className={`pointer-events-auto px-2 py-1 rounded text-xs ${canNext ? 'bg-black/50 text-white hover:bg-black/60' : 'bg-black/10 text-gray-400 cursor-not-allowed'}`}
                        >
                            다음 ▶
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default HTMLCard;
