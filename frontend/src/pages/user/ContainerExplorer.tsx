import { Folder, FolderOpen, Lock, Plus, ShieldQuestion, Upload } from 'lucide-react';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useGlobalApp } from '../../contexts/GlobalAppContext';
import { createContainer } from '../../services/managerService';
import { createPermissionRequest } from '../../services/permissionRequestService';
import { getFullContainerHierarchy, getMyDocuments } from '../../services/userService';
import AccessRequestModal from './container-explorer/components/AccessRequestModal';
import SubcontainerCreateForm from './container-explorer/components/SubcontainerCreateForm';

interface ExplorerNode {
    id: string;
    name: string;
    children?: ExplorerNode[];
    permission: 'OWNER' | 'EDITOR' | 'VIEWER' | 'NONE';
    document_count?: number;
}

const ContainerExplorer: React.FC = () => {
    // 🆕 글로벌 상태에서 저장된 상태 복원
    const { state: globalState, actions } = useGlobalApp();
    const savedState = globalState.pageStates?.containerExplorer;

    const [tree, setTree] = useState<ExplorerNode[]>(savedState?.tree || []);
    const [selectedId, setSelectedId] = useState<string | null>(savedState?.selectedId || null);
    const [expanded, setExpanded] = useState<Set<string>>(
        new Set(savedState?.expanded || [])
    );
    const [loading, setLoading] = useState(!savedState?.tree?.length); // 저장된 트리가 있으면 로딩 스킵
    const [docs, setDocs] = useState<any[]>(savedState?.documents || []);

    // 모달 상태
    const [showAccessRequestModal, setShowAccessRequestModal] = useState(false);
    const [showSubcontainerModal, setShowSubcontainerModal] = useState(false);

    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const expandedRef = useRef(expanded);
    const loadingTreeRef = useRef(false); // 🆕 트리 로딩 중복 방지
    const loadingDocsRef = useRef(false); // 🆕 문서 로딩 중복 방지
    const mountedRef = useRef(false); // 🆕 마운트 보호

    // expanded 변경 감지 및 ref 업데이트
    useEffect(() => {
        expandedRef.current = expanded;
    }, [expanded]);

    // 🆕 상태 변경 시 저장 (디바운스)
    useEffect(() => {
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        saveTimeoutRef.current = setTimeout(() => {
            actions.savePageState('containerExplorer', {
                tree,
                selectedId,
                expanded: Array.from(expandedRef.current),
                documents: docs,
                scrollPosition: 0,
                lastLoadTime: Date.now() // 🆕 캐시 타임스탬프 추가
            });
        }, 500);

        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [tree, selectedId, docs]);

    // 전체 트리를 가져와서 각 노드에 권한 정보가 포함되어 있음
    useEffect(() => {
        // 🆕 이미 마운트되었으면 스킵 (Strict Mode 대응)
        if (mountedRef.current) {
            console.log('✅ 이미 마운트됨 - 트리 로드 스킵');
            return;
        }
        mountedRef.current = true;

        // 저장된 트리가 있으면 백엔드 조회 건너뛰기
        if (savedState?.tree?.length) {
            console.log('✅ 저장된 컨테이너 트리 사용 (백엔드 조회 스킵)', {
                노드수: savedState.tree.length,
                선택된ID: savedState.selectedId,
                확장노드수: savedState.expanded?.length || 0
            });
            setLoading(false);
            return;
        }

        const load = async () => {
            // 🆕 이미 로딩 중이면 스킵
            if (loadingTreeRef.current) {
                console.log('⏭️ 트리 로딩 중복 호출 방지');
                return;
            }
            loadingTreeRef.current = true;

            setLoading(true);
            try {
                console.log('🔄 컨테이너 트리 백엔드 조회 시작...');
                // 전체 컨테이너 트리 조회 (각 노드에 permission 포함)
                const response = await getFullContainerHierarchy();

                console.log('📊 전체 컨테이너 트리 (권한 포함):', response);

                if (!response?.success || !response.containers) {
                    setTree([]);
                    return;
                }

                // 응답에 이미 permission이 포함되어 있으므로 그대로 매핑
                const mapTree = (nodes: any[]): ExplorerNode[] => nodes.map((n: any) => ({
                    id: n.id,
                    name: n.name,
                    permission: n.permission || 'NONE', // OWNER, EDITOR, VIEWER, NONE
                    document_count: n.document_count || 0,
                    children: n.children ? mapTree(n.children) : []
                }));

                const mapped = mapTree(response.containers);
                setTree(mapped);

                // 최초 포커스: 접근 가능한 최상위 노드 (또는 첫 번째 노드)
                const findFirstNode = (nodes: ExplorerNode[]): ExplorerNode | null => {
                    if (nodes.length === 0) return null;
                    // 권한이 있는 첫 번째 노드 찾기
                    const q: ExplorerNode[] = [...nodes];
                    while (q.length) {
                        const cur = q.shift()!;
                        if (cur.permission !== 'NONE') return cur;
                        if (cur.children) q.push(...cur.children);
                    }
                    // 권한이 있는 노드가 없으면 첫 번째 노드 선택
                    return nodes[0];
                };

                const first = findFirstNode(mapped);
                if (first) {
                    setSelectedId(first.id);
                    // 경로 확장
                    const expandPath = (nodes: ExplorerNode[], targetId: string, path: string[] = []): string[] | null => {
                        for (const node of nodes) {
                            if (node.id === targetId) return [...path, node.id];
                            if (node.children) {
                                const p = expandPath(node.children, targetId, [...path, node.id]);
                                if (p) return p;
                            }
                        }
                        return null;
                    };
                    const p = expandPath(mapped, first.id) || [];
                    setExpanded(new Set(p));
                }
                console.log('✅ 컨테이너 트리 로드 완료');
            } catch (e) {
                console.error('❌ 컨테이너 탐색 데이터 로드 실패:', e);
                setTree([]);
            } finally {
                setLoading(false);
                loadingTreeRef.current = false;
            }
        };
        load();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // 선택 노드 탐색
    const selectedNode = useMemo(() => {
        const find = (nodes: ExplorerNode[], id: string | null): ExplorerNode | null => {
            if (!id) return null;
            for (const n of nodes) {
                if (n.id === id) return n;
                const c = n.children && n.children.length ? find(n.children, id) : null;
                if (c) return c;
            }
            return null;
        };
        return find(tree, selectedId);
    }, [tree, selectedId]);

    // 노드 클릭
    const handleSelect = (id: string) => setSelectedId(id);
    const toggleExpand = (id: string) => {
        setExpanded(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id); else next.add(id);
            return next;
        });
    };

    // 문서 로드(간단)
    useEffect(() => {
        const loadDocs = async () => {
            if (!selectedId) {
                setDocs([]);
                return;
            }

            // 🆕 저장된 문서가 있고 같은 컨테이너면 캐시 사용
            if (savedState?.documents?.length && savedState.selectedId === selectedId) {
                console.log(`✅ 저장된 문서 사용 (container: ${selectedId})`);
                return;
            }

            // 🆕 이미 로딩 중이면 스킵
            if (loadingDocsRef.current) {
                console.log('⏭️ 문서 로딩 중복 호출 방지');
                return;
            }
            loadingDocsRef.current = true;

            try {
                console.log(`🔄 문서 조회 시작 (container: ${selectedId})`);
                const r = await getMyDocuments({ container_id: selectedId, limit: 10, skip: 0 });
                setDocs(r.documents || []);
                console.log(`✅ 문서 ${r.documents?.length || 0}개 조회 완료`);
            } catch (e) {
                console.error('❌ 문서 조회 실패:', e);
                setDocs([]);
            } finally {
                loadingDocsRef.current = false;
            }
        };
        loadDocs();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedId]);

    // 권한 요청 제출
    const handleAccessRequest = async (data: { reason: string; roleId: string; expiresAt?: string }) => {
        if (!selectedNode) return;

        await createPermissionRequest({
            container_id: selectedNode.id,
            requested_permission_level: data.roleId,  // ✅ 올바른 필드명으로 수정
            request_reason: data.reason               // ✅ 올바른 필드명으로 수정
        });

        alert('권한 요청이 접수되었습니다.');
        setShowAccessRequestModal(false);
    };

    // 하위 컨테이너 생성
    const handleSubcontainerCreate = async (data: { name: string; description: string; inheritPermissions: boolean }) => {
        if (!selectedNode) return;

        await createContainer({
            name: data.name,
            description: data.description,
            parent_id: selectedNode.id
        });

        alert('하위 컨테이너가 생성되었습니다. 새로고침 후 확인하세요.');
        setShowSubcontainerModal(false);

        // TODO: 트리 다시 로드하여 새 컨테이너 반영
    };

    const renderNode = (node: ExplorerNode, level = 0) => {
        const hasChildren = (node.children || []).length > 0;
        const isExpanded = expanded.has(node.id);
        const isSelected = selectedId === node.id;

        return (
            <div key={node.id}>
                <div
                    className={`flex items-center p-2 rounded-md cursor-pointer ${isSelected ? 'bg-blue-100 text-blue-800' : node.permission === 'NONE' ? 'hover:bg-red-50' : 'hover:bg-gray-100'
                        }`}
                    style={{ paddingLeft: `${level * 20 + 8}px` }}
                    onClick={() => handleSelect(node.id)}
                >
                    <div className="w-5 mr-2" onClick={(e) => { e.stopPropagation(); toggleExpand(node.id); }}>
                        {hasChildren ? (isExpanded ? <FolderOpen className="w-4 h-4 text-blue-600" /> : <Folder className="w-4 h-4 text-gray-600" />) : <span />}
                    </div>
                    <div className="flex-1 text-sm">
                        {node.name}
                        {node.permission === 'NONE' && <span className="ml-2 text-xs text-red-500">(접근 불가)</span>}
                    </div>
                    {node.permission === 'NONE' && <Lock className="w-4 h-4 text-red-500" />}
                </div>
                {hasChildren && isExpanded && (
                    <div>
                        {node.children!.map((c) => renderNode(c, level + 1))}
                    </div>
                )}
            </div>
        );
    };

    if (loading) {
        return (
            <div className="min-h-[50vh] flex items-center justify-center text-gray-500">로딩 중...</div>
        );
    }

    return (
        <div className="h-full flex bg-gray-50">
            <div className="w-80 p-4 border-r bg-white overflow-auto">
                <h3 className="text-lg font-medium mb-3">컨테이너 탐색</h3>
                <div className="space-y-1">
                    {tree.map((n) => renderNode(n))}
                </div>
            </div>
            <div className="flex-1 p-6">
                {!selectedNode ? (
                    <div className="text-gray-500">컨테이너를 선택하세요.</div>
                ) : (
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <div className="text-xl font-semibold">{selectedNode.name}</div>
                                <div className="text-sm text-gray-500">컨테이너 ID: {selectedNode.id} · 권한: {selectedNode.permission}</div>
                            </div>
                            <div className="flex gap-2">
                                {selectedNode.permission === 'NONE' ? (
                                    <button
                                        onClick={() => setShowAccessRequestModal(true)}
                                        className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 inline-flex items-center">
                                        <ShieldQuestion className="w-4 h-4 mr-1" /> 권한 요청
                                    </button>
                                ) : (
                                    <>
                                        <button
                                            onClick={() => setShowSubcontainerModal(true)}
                                            className="px-3 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 inline-flex items-center">
                                            <Plus className="w-4 h-4 mr-1" /> 하위 컨테이너 추가
                                        </button>
                                        <button
                                            className="px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 inline-flex items-center"
                                            onClick={() => alert('업로드 모달은 내 지식 화면의 업로드 모달 재사용 권장')}
                                        >
                                            <Upload className="w-4 h-4 mr-1" /> 지식 등록
                                        </button>
                                    </>
                                )}
                            </div>
                        </div>

                        {selectedNode.permission === 'NONE' && (
                            <div className="bg-yellow-50 border border-yellow-200 rounded p-3">
                                <div className="text-sm text-yellow-800 mb-2">
                                    이 컨테이너에 접근하려면 권한 요청이 필요합니다.
                                </div>
                                <div className="text-xs text-gray-600">
                                    '권한 요청' 버튼을 클릭하여 접근 권한을 요청할 수 있습니다.
                                </div>
                            </div>
                        )}

                        <div className="mt-4">
                            <div className="text-lg font-medium mb-2">문서</div>
                            {selectedNode.permission === 'NONE' ? (
                                <div className="text-gray-400 text-sm">접근 권한이 없어 문서를 표시할 수 없습니다.</div>
                            ) : docs.length === 0 ? (
                                <div className="text-gray-400 text-sm">문서가 없습니다.</div>
                            ) : (
                                <ul className="divide-y bg-white rounded border">
                                    {docs.map((d) => (
                                        <li key={d.id || d.file_id} className="p-3 flex items-center justify-between">
                                            <div>
                                                <div className="text-sm font-medium">{d.title || d.file_name}</div>
                                                <div className="text-xs text-gray-500">{d.created_at?.slice(0, 10)}</div>
                                            </div>
                                            <button className="text-blue-600 text-sm hover:underline">열람</button>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* 권한 요청 모달 */}
            {selectedNode && (
                <AccessRequestModal
                    isOpen={showAccessRequestModal}
                    onClose={() => setShowAccessRequestModal(false)}
                    onSubmit={handleAccessRequest}
                    containerName={selectedNode.name}
                />
            )}

            {/* 하위 컨테이너 생성 모달 */}
            {selectedNode && (
                <SubcontainerCreateForm
                    isOpen={showSubcontainerModal}
                    onClose={() => setShowSubcontainerModal(false)}
                    onSubmit={handleSubcontainerCreate}
                    parentContainerName={selectedNode.name}
                />
            )}
        </div>
    );
};

export default ContainerExplorer;
