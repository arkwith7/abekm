import React from 'react';
import { useSearchParams } from 'react-router-dom';

// Minimal HTML slide viewer: parses sections and provides navigation (keyboard/buttons)
const HTMLPresentationViewer: React.FC = () => {
    const [params] = useSearchParams();
    const [html, setHtml] = React.useState<string>('');
    const [slides, setSlides] = React.useState<Element[]>([]);
    const [index, setIndex] = React.useState<number>(0);
    const [loading, setLoading] = React.useState<boolean>(true);
    const [error, setError] = React.useState<string>('');

    const msgId = params.get('msgId') || '';
    const htmlUrl = params.get('url') || '';
    const storageKey = params.get('key') || '';

    // Fetch HTML by URL param (simple path). If msgId flow is desired, add API fetch here.
    React.useEffect(() => {
        let cancelled = false;
        async function run() {
            try {
                setLoading(true);
                setError('');
                let content = '';
                if (storageKey) {
                    // Load HTML from localStorage (cross-tab) then fallback to sessionStorage
                    const rawLocal = localStorage.getItem(`html_viewer:${storageKey}`) || '';
                    const rawSession = sessionStorage.getItem(`html_viewer:${storageKey}`) || '';
                    content = rawLocal || rawSession;
                } else if (htmlUrl) {
                    const res = await fetch(htmlUrl, { credentials: 'include' });
                    if (!res.ok) throw new Error(`HTML fetch failed: ${res.status}`);
                    content = await res.text();
                } else {
                    // msgId 기반 서버 조회가 필요하면 이 분기에서 구현
                    content = '';
                }
                if (cancelled) return;
                setHtml(content);
                // Clean up stored HTML after loading to avoid stale storage bloat
                if (storageKey) {
                    try {
                        localStorage.removeItem(`html_viewer:${storageKey}`);
                        sessionStorage.removeItem(`html_viewer:${storageKey}`);
                    } catch { }
                }

                // parse slides
                const parser = new DOMParser();
                const doc = parser.parseFromString(content, 'text/html');
                const found = Array.from(doc.querySelectorAll('section.slide'));
                setSlides(found);
                setIndex(0);
            } catch (e: any) {
                if (!cancelled) setError(e?.message || '로딩 실패');
            } finally {
                if (!cancelled) setLoading(false);
            }
        }
        run();
        return () => {
            cancelled = true;
        };
    }, [htmlUrl, msgId, storageKey]);

    const canPrev = index > 0;
    const canNext = index + 1 < slides.length;

    const goPrev = React.useCallback(() => setIndex(i => Math.max(0, i - 1)), []);
    const goNext = React.useCallback(() => setIndex(i => Math.min(slides.length - 1, i + 1)), [slides.length]);

    // keyboard
    React.useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            // If typing in inputs/textareas/contentEditable, don't hijack keys
            const target = e.target as HTMLElement | null;
            const tag = (target?.tagName || '').toLowerCase();
            const isEditable = !!(target && (tag === 'input' || tag === 'textarea' || target.isContentEditable));
            if (isEditable) return; // let typing work (spaces, arrows)

            if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); goPrev(); }
            if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); goNext(); }
            if (e.key.toLowerCase() === 'f') { document.documentElement.requestFullscreen?.(); }
            if (e.key === 'Home') setIndex(0);
            if (e.key === 'End') setIndex(Math.max(0, slides.length - 1));
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [goPrev, goNext, slides.length]);

    // Render selected slide as raw HTML inside a sandboxed iframe-like container using srcDoc
    const slideHtml = React.useMemo(() => {
        if (!html) return '';
        if (!slides.length) return html; // fallback to full doc
        const wrapper = document.implementation.createHTMLDocument('slide');
        const head = wrapper.head;
        // try to carry styles from original doc
        const orig = new DOMParser().parseFromString(html, 'text/html');
        head.innerHTML = orig.head.innerHTML;
        const body = wrapper.body;
        body.innerHTML = (slides[index] as HTMLElement).outerHTML;
        return `<!DOCTYPE html>\n${wrapper.documentElement.outerHTML}`;
    }, [html, slides, index]);

    // Touch swipe support for mobile
    React.useEffect(() => {
        let startX = 0;
        let startY = 0;
        const onTouchStart = (e: TouchEvent) => {
            const t = e.changedTouches[0];
            startX = t.clientX; startY = t.clientY;
        };
        const onTouchEnd = (e: TouchEvent) => {
            const t = e.changedTouches[0];
            const dx = t.clientX - startX;
            const dy = t.clientY - startY;
            if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
                if (dx < 0) goNext(); else goPrev();
            }
        };
        window.addEventListener('touchstart', onTouchStart, { passive: true });
        window.addEventListener('touchend', onTouchEnd, { passive: true });
        return () => {
            window.removeEventListener('touchstart', onTouchStart as any);
            window.removeEventListener('touchend', onTouchEnd as any);
        };
    }, [goPrev, goNext]);

    if (loading) return <div className="w-full h-screen flex items-center justify-center text-gray-500">로딩중…</div>;
    if (error) return <div className="p-6 text-red-600">에러: {error}</div>;
    if (!html) return <div className="p-6 text-gray-500">표시할 HTML이 없습니다.</div>;

    return (
        <div className="w-screen h-screen bg-black text-white overflow-hidden relative">
            {/* Controls */}
            <div className="absolute top-3 right-3 z-20 flex items-center gap-2">
                <button onClick={() => document.documentElement.requestFullscreen?.()} className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20">전체화면(F)</button>
                <a href={htmlUrl || '#'} target="_blank" rel="noopener noreferrer" className="px-3 py-1.5 text-sm rounded bg-white/10 hover:bg-white/20">원문 열기</a>
            </div>

            {/* Slide stage with left/right nav zones */}
            <div className="w-full h-full grid place-items-center p-6">
                <div className="relative w-[90vw] h-[90vh] bg-white rounded-lg shadow-2xl overflow-hidden">
                    <iframe title="slide" className="w-full h-full border-0" sandbox="allow-same-origin" srcDoc={slideHtml} />
                    {/* Left/right click areas */}
                    <button onClick={goPrev} disabled={!canPrev} className={`absolute inset-y-0 left-0 w-[18%] ${canPrev ? 'hover:bg-black/10' : ''} focus:outline-none`} aria-label="이전" />
                    <button onClick={goNext} disabled={!canNext} className={`absolute inset-y-0 right-0 w-[18%] ${canNext ? 'hover:bg-black/10' : ''} focus:outline-none`} aria-label="다음" />
                    {/* Bottom pager */}
                    <div className="absolute bottom-3 left-0 right-0 flex items-center justify-between px-4">
                        <button onClick={goPrev} disabled={!canPrev} className={`px-4 py-2 rounded ${canPrev ? 'bg-black/50 hover:bg-black/60' : 'bg-black/20 cursor-not-allowed'}`}>◀ 이전</button>
                        <div className="text-sm text-black/80 bg-white/70 px-3 py-1 rounded">{index + 1} / {Math.max(1, slides.length)}</div>
                        <button onClick={goNext} disabled={!canNext} className={`px-4 py-2 rounded ${canNext ? 'bg-black/50 hover:bg-black/60' : 'bg-black/20 cursor-not-allowed'}`}>다음 ▶</button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default HTMLPresentationViewer;
