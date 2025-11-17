import { AlertTriangle, Globe, Lock, Plus, Search, Trash2, Users, X } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import {
    createDocumentAccessRule,
    deleteDocumentAccessRule,
    getDocumentAccessRules,
    searchUsersForPermissions
} from '../../../../services/managerService';
import type {
    AccessibleDocument,
    AccessLevel,
    AccessRuleCreateRequest,
    DocumentAccessRule,
    PermissionLevel,
    RuleType
} from '../../../../types/manager.types';

interface AccessControlModalProps {
    document: AccessibleDocument;
    isOpen: boolean;
    onClose: () => void;
    onSuccess?: () => void;
}

interface UserSearchResult {
    emp_no: string;
    emp_nm: string;
    dept_nm?: string;
    position?: string;
}

export const AccessControlModal: React.FC<AccessControlModalProps> = ({
    document,
    isOpen,
    onClose,
    onSuccess
}) => {
    const [accessLevel, setAccessLevel] = useState<AccessLevel>(document.access_level);
    const [rules, setRules] = useState<DocumentAccessRule[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // RESTRICTED 규칙 추가 폼
    const [showAddRule, setShowAddRule] = useState(false);
    const [ruleType, setRuleType] = useState<RuleType>('user');
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState<UserSearchResult[]>([]);
    const [selectedTarget, setSelectedTarget] = useState('');
    const [permissionLevel, setPermissionLevel] = useState<PermissionLevel>('view');
    const [departmentInput, setDepartmentInput] = useState('');

    // 접근 규칙 로드
    const loadAccessRules = useCallback(async () => {
        try {
            setIsLoading(true);
            const data = await getDocumentAccessRules(document.file_bss_info_sno);
            setRules(data);

            // 현재 접근 레벨 업데이트
            if (data.length > 0) {
                setAccessLevel(data[0].access_level);
            }
        } catch (err) {
            console.error('Failed to load access rules:', err);
            setError('접근 규칙을 불러오는데 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    }, [document.file_bss_info_sno]);

    useEffect(() => {
        if (isOpen) {
            loadAccessRules();
        }
    }, [isOpen, loadAccessRules]);

    // 사용자 검색
    const handleUserSearch = async (query: string) => {
        setSearchQuery(query);

        if (query.length < 2) {
            setSearchResults([]);
            return;
        }

        try {
            const response = await searchUsersForPermissions(query);
            // UserQuickSearchItem을 UserSearchResult로 매핑
            const mappedResults: UserSearchResult[] = (response.users || []).map(user => ({
                emp_no: user.emp_no,
                emp_nm: user.name || user.username || user.emp_no,
                dept_nm: user.department,
                position: user.position
            }));
            setSearchResults(mappedResults);
        } catch (err) {
            console.error('Failed to search users:', err);
        }
    };

    // 접근 레벨 변경
    const handleAccessLevelChange = async (newLevel: AccessLevel) => {
        try {
            setIsLoading(true);
            setError(null);

            // PUBLIC이나 PRIVATE로 변경하는 경우
            if (newLevel === 'public' || newLevel === 'private') {
                // 기존 규칙 모두 삭제
                await Promise.all(rules.map(rule => deleteDocumentAccessRule(rule.rule_id)));

                // 새 규칙 생성
                await createDocumentAccessRule(document.file_bss_info_sno, {
                    access_level: newLevel,
                    is_inherited: 'N'
                });
            }

            setAccessLevel(newLevel);
            await loadAccessRules();

            if (onSuccess) {
                onSuccess();
            }
        } catch (err) {
            console.error('Failed to change access level:', err);
            setError('접근 레벨 변경에 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    };

    // 규칙 추가
    const handleAddRule = async () => {
        try {
            setIsLoading(true);
            setError(null);

            let targetId = '';

            if (ruleType === 'user') {
                if (!selectedTarget) {
                    setError('사용자를 선택해주세요.');
                    return;
                }
                targetId = selectedTarget;
            } else {
                if (!departmentInput) {
                    setError('부서명을 입력해주세요.');
                    return;
                }
                targetId = departmentInput;
            }

            const ruleData: AccessRuleCreateRequest = {
                access_level: 'restricted',
                rule_type: ruleType,
                target_id: targetId,
                permission_level: permissionLevel,
                is_inherited: 'N'
            };

            await createDocumentAccessRule(document.file_bss_info_sno, ruleData);

            // 폼 초기화
            setShowAddRule(false);
            setSearchQuery('');
            setSearchResults([]);
            setSelectedTarget('');
            setDepartmentInput('');
            setPermissionLevel('view');

            await loadAccessRules();

            if (onSuccess) {
                onSuccess();
            }
        } catch (err) {
            console.error('Failed to add rule:', err);
            setError('규칙 추가에 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    };

    // 규칙 삭제
    const handleDeleteRule = async (ruleId: number) => {
        if (!window.confirm('이 규칙을 삭제하시겠습니까?')) {
            return;
        }

        try {
            setIsLoading(true);
            setError(null);

            await deleteDocumentAccessRule(ruleId);
            await loadAccessRules();

            if (onSuccess) {
                onSuccess();
            }
        } catch (err) {
            console.error('Failed to delete rule:', err);
            setError('규칙 삭제에 실패했습니다.');
        } finally {
            setIsLoading(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
                {/* 헤더 */}
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <h2 className="text-xl font-semibold text-gray-900">문서 접근 권한 설정</h2>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-600"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {/* 문서 정보 */}
                <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
                    <div className="text-sm text-gray-600">문서명</div>
                    <div className="text-base font-medium text-gray-900">{document.file_lgc_nm}</div>
                    <div className="text-xs text-gray-500 mt-1">{document.file_psl_nm}</div>
                </div>

                {/* 내용 */}
                <div className="px-6 py-6 overflow-y-auto max-h-[60vh]">
                    {error && (
                        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-md flex items-start">
                            <AlertTriangle className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
                            <p className="text-sm text-red-800">{error}</p>
                        </div>
                    )}

                    {/* 접근 레벨 선택 */}
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-3">
                            접근 레벨
                        </label>
                        <div className="grid grid-cols-3 gap-4">
                            <button
                                onClick={() => handleAccessLevelChange('public')}
                                disabled={isLoading}
                                className={`p-4 border-2 rounded-lg text-center transition-colors ${accessLevel === 'public'
                                        ? 'border-green-500 bg-green-50'
                                        : 'border-gray-200 hover:border-green-300'
                                    }`}
                            >
                                <Globe className={`w-8 h-8 mx-auto mb-2 ${accessLevel === 'public' ? 'text-green-600' : 'text-gray-400'
                                    }`} />
                                <div className="font-medium">공개</div>
                                <div className="text-xs text-gray-500 mt-1">모든 사용자</div>
                            </button>

                            <button
                                onClick={() => handleAccessLevelChange('restricted')}
                                disabled={isLoading}
                                className={`p-4 border-2 rounded-lg text-center transition-colors ${accessLevel === 'restricted'
                                        ? 'border-yellow-500 bg-yellow-50'
                                        : 'border-gray-200 hover:border-yellow-300'
                                    }`}
                            >
                                <Users className={`w-8 h-8 mx-auto mb-2 ${accessLevel === 'restricted' ? 'text-yellow-600' : 'text-gray-400'
                                    }`} />
                                <div className="font-medium">제한</div>
                                <div className="text-xs text-gray-500 mt-1">특정 사용자/부서</div>
                            </button>

                            <button
                                onClick={() => handleAccessLevelChange('private')}
                                disabled={isLoading}
                                className={`p-4 border-2 rounded-lg text-center transition-colors ${accessLevel === 'private'
                                        ? 'border-red-500 bg-red-50'
                                        : 'border-gray-200 hover:border-red-300'
                                    }`}
                            >
                                <Lock className={`w-8 h-8 mx-auto mb-2 ${accessLevel === 'private' ? 'text-red-600' : 'text-gray-400'
                                    }`} />
                                <div className="font-medium">비공개</div>
                                <div className="text-xs text-gray-500 mt-1">관리자만</div>
                            </button>
                        </div>
                    </div>

                    {/* RESTRICTED 규칙 관리 */}
                    {accessLevel === 'restricted' && (
                        <div className="border-t border-gray-200 pt-6">
                            <div className="flex items-center justify-between mb-4">
                                <h3 className="text-sm font-medium text-gray-700">접근 허용 대상</h3>
                                <button
                                    onClick={() => setShowAddRule(!showAddRule)}
                                    disabled={isLoading}
                                    className="flex items-center px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
                                >
                                    <Plus className="w-4 h-4 mr-1" />
                                    규칙 추가
                                </button>
                            </div>

                            {/* 규칙 추가 폼 */}
                            {showAddRule && (
                                <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
                                    <div className="grid grid-cols-2 gap-4 mb-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                타입
                                            </label>
                                            <select
                                                value={ruleType}
                                                onChange={(e) => setRuleType(e.target.value as RuleType)}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                                            >
                                                <option value="user">개별 사용자</option>
                                                <option value="department">부서 전체</option>
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                권한 레벨
                                            </label>
                                            <select
                                                value={permissionLevel}
                                                onChange={(e) => setPermissionLevel(e.target.value as PermissionLevel)}
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                                            >
                                                <option value="view">조회만</option>
                                                <option value="download">다운로드 가능</option>
                                                <option value="edit">편집 가능</option>
                                            </select>
                                        </div>
                                    </div>

                                    {ruleType === 'user' ? (
                                        <div className="mb-4">
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                사용자 검색
                                            </label>
                                            <div className="relative">
                                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                                                <input
                                                    type="text"
                                                    value={searchQuery}
                                                    onChange={(e) => handleUserSearch(e.target.value)}
                                                    placeholder="이름 또는 사번으로 검색..."
                                                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md"
                                                />
                                            </div>
                                            {searchResults.length > 0 && (
                                                <div className="mt-2 max-h-48 overflow-y-auto border border-gray-200 rounded-md">
                                                    {searchResults.map((user) => (
                                                        <button
                                                            key={user.emp_no}
                                                            onClick={() => {
                                                                setSelectedTarget(user.emp_no);
                                                                setSearchQuery(user.emp_nm);
                                                                setSearchResults([]);
                                                            }}
                                                            className="w-full px-4 py-2 text-left hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                                                        >
                                                            <div className="font-medium">{user.emp_nm}</div>
                                                            <div className="text-sm text-gray-500">
                                                                {user.emp_no} | {user.dept_nm || '부서 없음'}
                                                            </div>
                                                        </button>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div className="mb-4">
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                부서명
                                            </label>
                                            <input
                                                type="text"
                                                value={departmentInput}
                                                onChange={(e) => setDepartmentInput(e.target.value)}
                                                placeholder="예: HR부서"
                                                className="w-full px-3 py-2 border border-gray-300 rounded-md"
                                            />
                                        </div>
                                    )}

                                    <div className="flex justify-end space-x-2">
                                        <button
                                            onClick={() => setShowAddRule(false)}
                                            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                                        >
                                            취소
                                        </button>
                                        <button
                                            onClick={handleAddRule}
                                            disabled={isLoading}
                                            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50"
                                        >
                                            추가
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* 현재 규칙 목록 */}
                            <div className="space-y-2">
                                {rules.filter(r => r.access_level === 'restricted').map((rule) => (
                                    <div
                                        key={rule.rule_id}
                                        className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-md"
                                    >
                                        <div className="flex-1">
                                            <div className="flex items-center">
                                                {rule.rule_type === 'user' ? (
                                                    <Users className="w-4 h-4 text-gray-400 mr-2" />
                                                ) : (
                                                    <Globe className="w-4 h-4 text-gray-400 mr-2" />
                                                )}
                                                <span className="font-medium">{rule.target_id}</span>
                                                <span className="ml-2 text-sm text-gray-500">
                                                    ({rule.rule_type === 'user' ? '사용자' : '부서'})
                                                </span>
                                            </div>
                                            <div className="text-sm text-gray-600 mt-1">
                                                권한: {rule.permission_level}
                                            </div>
                                        </div>
                                        <button
                                            onClick={() => handleDeleteRule(rule.rule_id)}
                                            disabled={isLoading}
                                            className="text-red-600 hover:text-red-800 disabled:opacity-50"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                ))}
                                {rules.filter(r => r.access_level === 'restricted').length === 0 && (
                                    <p className="text-sm text-gray-500 text-center py-4">
                                        아직 규칙이 없습니다. 규칙을 추가해주세요.
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {/* 푸터 */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        닫기
                    </button>
                </div>
            </div>
        </div>
    );
};
