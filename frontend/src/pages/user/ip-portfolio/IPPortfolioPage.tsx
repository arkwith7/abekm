import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ipPortfolioService, IpcTreeNode, PatentCardDto } from '../../../services/ipPortfolioService';

type NodeState = Record<string, boolean>;

const flattenFirstNodeCode = (nodes: IpcTreeNode[]): string | null => {
  for (const n of nodes) {
    if (n.code) return n.code;
  }
  return null;
};

const IPPortfolioPage: React.FC = () => {
  const [tree, setTree] = useState<IpcTreeNode[]>([]);
  const [expanded, setExpanded] = useState<NodeState>({});
  const [selectedIpc, setSelectedIpc] = useState<string | null>(null);

  const [stats, setStats] = useState<any>(null);
  const [patents, setPatents] = useState<PatentCardDto[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);

  const [loadingTree, setLoadingTree] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pageSize = 20;

  const toggleNode = useCallback((code: string) => {
    setExpanded((prev) => ({ ...prev, [code]: !prev[code] }));
  }, []);

  const selectNode = useCallback((code: string) => {
    setSelectedIpc(code);
    setPage(1);
  }, []);

  const loadTree = useCallback(async () => {
    setLoadingTree(true);
    setError(null);
    try {
      const nodes = await ipPortfolioService.getIpcTree(false);
      setTree(nodes);
      const first = flattenFirstNodeCode(nodes);
      if (first) {
        setSelectedIpc((prev) => prev ?? first);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'IPC 트리를 불러오지 못했습니다.');
    } finally {
      setLoadingTree(false);
    }
  }, []);

  const loadContent = useCallback(async () => {
    if (!selectedIpc) return;

    setLoadingContent(true);
    setError(null);
    try {
      const [statsRes, patentsRes] = await Promise.all([
        ipPortfolioService.getDashboardStats(selectedIpc, true),
        ipPortfolioService.listPatents({ ipcCode: selectedIpc, includeChildren: true, page, pageSize }),
      ]);

      setStats(statsRes);
      setPatents(patentsRes.items);
      setTotal(patentsRes.total);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? '데이터를 불러오지 못했습니다.');
    } finally {
      setLoadingContent(false);
    }
  }, [page, pageSize, selectedIpc]);

  useEffect(() => {
    loadTree();
  }, [loadTree]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(total / pageSize));
  }, [total, pageSize]);

  const renderNode = (node: IpcTreeNode, depth: number) => {
    const hasChildren = !!node.children?.length;
    const isExpanded = !!expanded[node.code];
    const isSelected = selectedIpc === node.code;

    return (
      <div key={node.code} className="select-none">
        <div
          className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer ${isSelected ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-100 text-gray-700'}`}
          style={{ paddingLeft: `${8 + depth * 12}px` }}
          onClick={() => selectNode(node.code)}
        >
          <button
            type="button"
            className={`w-5 h-5 flex items-center justify-center rounded ${hasChildren ? 'hover:bg-gray-200' : 'opacity-0 pointer-events-none'}`}
            onClick={(e) => {
              e.stopPropagation();
              if (hasChildren) toggleNode(node.code);
            }}
            aria-label="toggle"
          >
            <span className="text-xs">{hasChildren ? (isExpanded ? '▾' : '▸') : ''}</span>
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{node.code}</div>
            {node.description_ko ? (
              <div className="text-xs text-gray-500 truncate">{node.description_ko}</div>
            ) : null}
          </div>
        </div>

        {hasChildren && isExpanded ? (
          <div>
            {node.children.map((c) => renderNode(c, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  };

  return (
    <div className="h-full flex">
      <aside className="w-80 border-r border-gray-200 bg-gray-50">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-sm font-semibold text-gray-900">IPC 트리</h2>
          <p className="text-xs text-gray-500 mt-1">권한 범위 내 IPC만 표시됩니다.</p>
        </div>

        <div className="p-2 overflow-auto h-[calc(100%-73px)]">
          {loadingTree ? (
            <div className="p-4 text-sm text-gray-500">불러오는 중...</div>
          ) : tree.length ? (
            tree.map((n) => renderNode(n, 0))
          ) : (
            <div className="p-4 text-sm text-gray-500">표시할 IPC가 없습니다.</div>
          )}
        </div>
      </aside>

      <main className="flex-1 p-6 overflow-auto">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">IP 포트폴리오</h1>
            <div className="text-sm text-gray-500 mt-1">선택 IPC: {selectedIpc ?? '-'}</div>
          </div>
        </div>

        {error ? (
          <div className="mt-4 p-3 rounded border border-red-200 bg-red-50 text-sm text-red-700">{error}</div>
        ) : null}

        <section className="mt-6">
          <h2 className="text-sm font-semibold text-gray-900">대시보드 통계</h2>
          <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-4 rounded border border-gray-200 bg-white">
              <div className="text-xs text-gray-500">총 특허</div>
              <div className="text-2xl font-bold text-gray-900">{stats?.total_patents ?? (loadingContent ? '-' : 0)}</div>
            </div>
            <div className="p-4 rounded border border-gray-200 bg-white">
              <div className="text-xs text-gray-500">상태 Top</div>
              <div className="mt-2 space-y-1">
                {(stats?.by_patent_status ?? []).slice(0, 3).map((x: any) => (
                  <div key={x.patent_status} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{x.patent_status}</span>
                    <span className="text-gray-900 font-medium">{x.count}</span>
                  </div>
                ))}
                {!loadingContent && (stats?.by_patent_status ?? []).length === 0 ? (
                  <div className="text-sm text-gray-500">데이터 없음</div>
                ) : null}
              </div>
            </div>
            <div className="p-4 rounded border border-gray-200 bg-white">
              <div className="text-xs text-gray-500">IPC 섹션 Top</div>
              <div className="mt-2 space-y-1">
                {(stats?.by_ipc_section ?? []).slice(0, 3).map((x: any) => (
                  <div key={x.primary_ipc_section} className="flex items-center justify-between text-sm">
                    <span className="text-gray-700">{x.primary_ipc_section}</span>
                    <span className="text-gray-900 font-medium">{x.count}</span>
                  </div>
                ))}
                {!loadingContent && (stats?.by_ipc_section ?? []).length === 0 ? (
                  <div className="text-sm text-gray-500">데이터 없음</div>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-8">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-900">특허</h2>
            <div className="text-sm text-gray-500">총 {total.toLocaleString()}건</div>
          </div>

          <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3">
            {loadingContent ? (
              <div className="p-4 text-sm text-gray-500">불러오는 중...</div>
            ) : patents.length ? (
              patents.map((p) => (
                <div key={p.metadata_id} className="p-4 rounded border border-gray-200 bg-white">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-gray-900 truncate">{p.application_number}</div>
                      <div className="text-xs text-gray-500 mt-1 truncate">{p.applicant ?? '출원인 정보 없음'}</div>
                    </div>
                    <div className="text-xs text-gray-600 whitespace-nowrap">
                      {p.patent_status ?? p.legal_status ?? 'UNKNOWN'}
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    {p.main_ipc_code ? (
                      <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">{p.main_ipc_code}</span>
                    ) : null}
                    {p.primary_ipc_section ? (
                      <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">{p.primary_ipc_section}</span>
                    ) : null}
                  </div>

                  {p.abstract ? (
                    <div className="mt-3 text-sm text-gray-700 line-clamp-3">{p.abstract}</div>
                  ) : (
                    <div className="mt-3 text-sm text-gray-400">초록 정보 없음</div>
                  )}
                </div>
              ))
            ) : (
              <div className="p-4 text-sm text-gray-500">표시할 특허가 없습니다.</div>
            )}
          </div>

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              className="px-3 py-2 text-sm rounded border border-gray-200 bg-white text-gray-700 disabled:opacity-50"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || loadingContent}
            >
              이전
            </button>
            <div className="text-sm text-gray-600">
              {page} / {totalPages}
            </div>
            <button
              type="button"
              className="px-3 py-2 text-sm rounded border border-gray-200 bg-white text-gray-700 disabled:opacity-50"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || loadingContent}
            >
              다음
            </button>
          </div>
        </section>
      </main>
    </div>
  );
};

export default IPPortfolioPage;
