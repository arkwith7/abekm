import { Check, Lock, Shield, Users, X } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { searchUsersForPermissions } from '../../../services/managerService';

interface AccessRule {
    type: 'container' | 'department' | 'user';
    targetId: string;
    targetName: string;
    permission: 'view' | 'download' | 'edit';
}

interface DocumentAccessControlModalProps {
    isOpen: boolean;
    onClose: () => void;
    documentId: string;
    documentTitle: string;
    currentContainer: string;
    currentAccessRules?: AccessRule[];
    onSave: (rules: AccessRule[]) => Promise<void>;
}

export const DocumentAccessControlModal: React.FC<DocumentAccessControlModalProps> = ({
    isOpen,
    onClose,
    documentId,
    documentTitle,
    currentContainer,
    currentAccessRules = [],
    onSave
}) => {
    const [accessLevel, setAccessLevel] = useState<'container' | 'restricted' | 'private'>('container');
    const [accessRules, setAccessRules] = useState<AccessRule[]>(currentAccessRules);
    const [searchTerm, setSearchTerm] = useState('');
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [isSearching, setIsSearching] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    useEffect(() => {
        if (currentAccessRules.length === 0) {
            setAccessLevel('container');
        } else {
            setAccessLevel('restricted');
        }
    }, [currentAccessRules]);

    const handleSearch = async () => {
        if (!searchTerm.trim()) return;

        setIsSearching(true);
        try {
            const response = await searchUsersForPermissions(searchTerm, 1, 20);
            setSearchResults(response.users);
        } catch (error) {
            console.error('Failed to search users:', error);
        } finally {
            setIsSearching(false);
        }
    };

    const addUserRule = (user: any) => {
        const newRule: AccessRule = {
            type: 'user',
            targetId: user.emp_no,
            targetName: user.name || user.username,
            permission: 'view'
        };

        if (!accessRules.some(rule => rule.targetId === user.emp_no)) {
            setAccessRules([...accessRules, newRule]);
            setSearchTerm('');
            setSearchResults([]);
        }
    };

    const removeRule = (index: number) => {
        setAccessRules(accessRules.filter((_, i) => i !== index));
    };

    const updateRulePermission = (index: number, permission: 'view' | 'download' | 'edit') => {
        const updated = [...accessRules];
        updated[index].permission = permission;
        setAccessRules(updated);
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            const rulesToSave = accessLevel === 'container' ? [] : accessRules;
            await onSave(rulesToSave);
            onClose();
        } catch (error) {
            console.error('Failed to save access rules:', error);
            alert('권한 설정 저장에 실패했습니다.');
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                {/* 헤더 */}
                <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900 flex items-center">
                            <Shield className="w-6 h-6 mr-2 text-blue-600" />
                            문서 접근 권한 설정
                        </h2>
                        <p className="text-sm text-gray-600 mt-1">{documentTitle}</p>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                {/* 내용 */}
                <div className="flex-1 overflow-y-auto px-6 py-4">
                    {/* 공개 범위 선택 */}
                    <div className="mb-6">
                        <label className="block text-sm font-medium text-gray-700 mb-3">
                            기본 공개 범위
                        </label>
                        <div className="space-y-3">
                            <label className="flex items-start p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                                <input
                                    type="radio"
                                    name="accessLevel"
                                    value="container"
                                    checked={accessLevel === 'container'}
                                    onChange={(e) => setAccessLevel(e.target.value as any)}
                                    className="mt-1 mr-3"
                                />
                                <div className="flex-1">
                                    <div className="flex items-center">
                                        <Users className="w-5 h-5 mr-2 text-green-600" />
                                        <span className="font-medium text-gray-900">컨테이너 전체 공개</span>
                                        <span className="ml-2 px-2 py-0.5 bg-green-100 text-green-800 text-xs rounded-full">
                                            기본
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-600 mt-1">
                                        "{currentContainer}" 컨테이너에 권한이 있는 모든 사용자가 접근 가능합니다.
                                    </p>
                                </div>
                            </label>

                            <label className="flex items-start p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                                <input
                                    type="radio"
                                    name="accessLevel"
                                    value="restricted"
                                    checked={accessLevel === 'restricted'}
                                    onChange={(e) => setAccessLevel(e.target.value as any)}
                                    className="mt-1 mr-3"
                                />
                                <div className="flex-1">
                                    <div className="flex items-center">
                                        <Lock className="w-5 h-5 mr-2 text-orange-600" />
                                        <span className="font-medium text-gray-900">제한된 공개</span>
                                        <span className="ml-2 px-2 py-0.5 bg-orange-100 text-orange-800 text-xs rounded-full">
                                            맞춤 설정
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-600 mt-1">
                                        지정한 사용자, 부서, 또는 다른 컨테이너에만 공개됩니다.
                                    </p>
                                </div>
                            </label>

                            <label className="flex items-start p-4 border-2 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors">
                                <input
                                    type="radio"
                                    name="accessLevel"
                                    value="private"
                                    checked={accessLevel === 'private'}
                                    onChange={(e) => setAccessLevel(e.target.value as any)}
                                    className="mt-1 mr-3"
                                />
                                <div className="flex-1">
                                    <div className="flex items-center">
                                        <Shield className="w-5 h-5 mr-2 text-red-600" />
                                        <span className="font-medium text-gray-900">비공개</span>
                                        <span className="ml-2 px-2 py-0.5 bg-red-100 text-red-800 text-xs rounded-full">
                                            관리자만
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-600 mt-1">
                                        컨테이너 관리자와 문서 작성자만 접근 가능합니다.
                                    </p>
                                </div>
                            </label>
                        </div>
                    </div>

                    {/* 사용자별 권한 설정 (제한된 공개 선택 시) */}
                    {accessLevel === 'restricted' && (
                        <div className="border-t border-gray-200 pt-6">
                            <h3 className="text-sm font-medium text-gray-700 mb-3">추가 접근 허용</h3>

                            {/* 사용자 검색 */}
                            <div className="mb-4">
                                <div className="flex gap-2">
                                    <input
                                        type="text"
                                        value={searchTerm}
                                        onChange={(e) => setSearchTerm(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                                        placeholder="사용자 이름 또는 사번으로 검색..."
                                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                    <button
                                        onClick={handleSearch}
                                        disabled={isSearching || !searchTerm.trim()}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {isSearching ? '검색 중...' : '검색'}
                                    </button>
                                </div>

                                {/* 검색 결과 */}
                                {searchResults.length > 0 && (
                                    <div className="mt-2 border border-gray-200 rounded-md max-h-40 overflow-y-auto">
                                        {searchResults.map((user) => (
                                            <button
                                                key={user.emp_no}
                                                onClick={() => addUserRule(user)}
                                                className="w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center justify-between"
                                            >
                                                <div>
                                                    <div className="font-medium text-gray-900">
                                                        {user.name || user.username}
                                                    </div>
                                                    <div className="text-sm text-gray-500">
                                                        {user.emp_no} • {user.department || '부서 미지정'}
                                                    </div>
                                                </div>
                                                <Check className="w-4 h-4 text-green-600" />
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>

                            {/* 권한 목록 */}
                            <div className="space-y-2">
                                {accessRules.length === 0 ? (
                                    <div className="text-center py-8 text-gray-500 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                                        <Users className="w-12 h-12 mx-auto mb-2 text-gray-400" />
                                        <p>추가된 사용자가 없습니다.</p>
                                        <p className="text-sm mt-1">위에서 사용자를 검색하여 추가하세요.</p>
                                    </div>
                                ) : (
                                    accessRules.map((rule, index) => (
                                        <div
                                            key={index}
                                            className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                                        >
                                            <div className="flex-1">
                                                <div className="font-medium text-gray-900">{rule.targetName}</div>
                                                <div className="text-sm text-gray-500">{rule.targetId}</div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <select
                                                    value={rule.permission}
                                                    onChange={(e) =>
                                                        updateRulePermission(index, e.target.value as any)
                                                    }
                                                    className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                                >
                                                    <option value="view">읽기 전용</option>
                                                    <option value="download">다운로드 가능</option>
                                                    <option value="edit">편집 가능</option>
                                                </select>
                                                <button
                                                    onClick={() => removeRule(index)}
                                                    className="p-1 text-red-600 hover:bg-red-50 rounded"
                                                >
                                                    <X className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    )}

                    {/* 안내 메시지 */}
                    <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <div className="flex">
                            <div className="flex-shrink-0">
                                <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                                    <path
                                        fillRule="evenodd"
                                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                                        clipRule="evenodd"
                                    />
                                </svg>
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-blue-800">권한 설정 안내</h3>
                                <div className="mt-2 text-sm text-blue-700">
                                    <ul className="list-disc list-inside space-y-1">
                                        <li>컨테이너 관리자와 문서 작성자는 항상 접근 가능합니다.</li>
                                        <li>제한된 공개 설정 시 지정된 사용자만 문서를 볼 수 있습니다.</li>
                                        <li>다운로드 권한이 없으면 뷰어로만 볼 수 있습니다.</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 푸터 */}
                <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                        disabled={isSaving}
                    >
                        취소
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
                    >
                        {isSaving ? (
                            <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                저장 중...
                            </>
                        ) : (
                            <>
                                <Check className="w-4 h-4 mr-2" />
                                저장
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};
