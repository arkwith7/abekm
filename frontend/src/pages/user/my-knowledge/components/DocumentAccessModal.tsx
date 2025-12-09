import axios from 'axios';
import { Download, Edit2, Eye, Globe, Lock, Users, X } from 'lucide-react';
import React, { useCallback, useEffect, useState } from 'react';
import { getApiUrl } from '../../../../utils/apiConfig';

const getApiBaseUrl = () => {
  const apiUrl = getApiUrl();
  return apiUrl ? `${apiUrl}/api/v1` : '/api/v1';
};

const API_BASE_URL = getApiBaseUrl();

interface AccessRule {
    rule_id: number;
    file_bss_info_sno: number;
    access_level: 'public' | 'restricted' | 'private';
    rule_type?: 'user' | 'department';
    target_id?: string;
    permission_level?: 'view' | 'download' | 'edit';
    is_inherited: string;
    created_by: string;
    created_date: string;
}

interface DocumentAccessModalProps {
    documentId: string;
    documentName: string;
    onClose: () => void;
    onSuccess?: () => void;
}

const DocumentAccessModal: React.FC<DocumentAccessModalProps> = ({
    documentId,
    documentName,
    onClose,
    onSuccess
}) => {
    console.log('[AccessModal] 모달 초기화 - documentId:', documentId, 'documentName:', documentName);

    const [currentRules, setCurrentRules] = useState<AccessRule[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isInitialLoad, setIsInitialLoad] = useState(true); // 🔥 초기 로드 플래그

    // 폼 상태
    const [accessLevel, setAccessLevel] = useState<'public' | 'restricted' | 'private'>('public');
    const [ruleType, setRuleType] = useState<'user' | 'department'>('user');
    const [targetId, setTargetId] = useState('');
    const [permissionLevel, setPermissionLevel] = useState<'view' | 'download' | 'edit'>('view');

    const loadAccessRules = useCallback(async () => {
        console.log('[AccessModal] loadAccessRules 시작 - documentId:', documentId);
        try {
            setIsLoading(true);
            const token = localStorage.getItem('access_token');
            const response = await axios.get(`${API_BASE_URL}/documents/${documentId}/access-rules`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            console.log('[AccessModal] API 응답:', response.data);
            setCurrentRules(response.data);

            // 🔥 초기 로드일 때만 기존 규칙을 폼에 반영
            if (isInitialLoad && response.data.length > 0) {
                const rule = response.data[0];
                console.log('[AccessModal] 기존 규칙 발견 (초기 로드):', rule);
                // 소문자로 변환하여 상태 설정 (백엔드에서 대문자로 올 경우 대비)
                const normalizedLevel = String(rule.access_level).toLowerCase() as 'public' | 'restricted' | 'private';
                console.log('[AccessModal] 정규화된 access_level:', normalizedLevel);
                setAccessLevel(normalizedLevel);
                if (rule.rule_type) {
                    const normalizedRuleType = String(rule.rule_type).toLowerCase() as 'user' | 'department';
                    console.log('[AccessModal] rule_type 설정:', normalizedRuleType);
                    setRuleType(normalizedRuleType);
                }
                if (rule.target_id) {
                    console.log('[AccessModal] target_id 설정:', rule.target_id);
                    setTargetId(rule.target_id);
                }
                if (rule.permission_level) {
                    const normalizedPermLevel = String(rule.permission_level).toLowerCase() as 'view' | 'download' | 'edit';
                    console.log('[AccessModal] permission_level 설정:', normalizedPermLevel);
                    setPermissionLevel(normalizedPermLevel);
                }
            } else if (isInitialLoad && response.data.length === 0) {
                console.log('[AccessModal] 기존 규칙 없음 - 기본값으로 초기화 (초기 로드)');
                // 기존 규칙이 없으면 기본값으로 초기화
                setAccessLevel('public');
                setRuleType('user');
                setTargetId('');
                setPermissionLevel('view');
            } else {
                console.log('[AccessModal] 초기 로드 이후 - 사용자 선택 유지');
            }

            // 초기 로드 플래그 해제
            setIsInitialLoad(false);
        } catch (error) {
            console.error('[AccessModal] 접근 규칙 로드 실패:', error);
        } finally {
            setIsLoading(false);
            console.log('[AccessModal] loadAccessRules 완료');
        }
    }, [documentId, isInitialLoad]);

    useEffect(() => {
        loadAccessRules();
    }, [loadAccessRules]);

    // accessLevel 상태 변경 추적
    useEffect(() => {
        console.log('[AccessModal] ✅ accessLevel 상태 변경됨:', accessLevel);
        console.log('[AccessModal] ✅ restricted 패널 표시 여부:', accessLevel === 'restricted');
    }, [accessLevel]);

    // accessLevel 상태 변경 추적
    useEffect(() => {
        console.log('[AccessModal] accessLevel 상태 변경됨:', accessLevel);
        console.log('[AccessModal] restricted 패널 표시 여부:', accessLevel === 'restricted');
    }, [accessLevel]);

    const handleSave = async () => {
        console.log('[AccessModal] handleSave 시작 - accessLevel:', accessLevel);
        try {
            setIsSaving(true);
            const token = localStorage.getItem('access_token');

            // 기존 규칙 삭제
            console.log('[AccessModal] 기존 규칙 삭제 중:', currentRules.length, '개');
            for (const rule of currentRules) {
                await axios.delete(`${API_BASE_URL}/documents/access-rules/${rule.rule_id}`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
            }

            // 새 규칙 생성
            const payload: any = {
                access_level: accessLevel,
                is_inherited: 'N'
            };

            if (accessLevel === 'restricted') {
                console.log('[AccessModal] 제한 공개 설정 - ruleType:', ruleType, 'targetId:', targetId, 'permissionLevel:', permissionLevel);
                if (!targetId.trim()) {
                    console.log('[AccessModal] 제한 공개 대상 미입력');
                    alert('제한 공개 시 대상을 입력해주세요.');
                    return;
                }
                payload.rule_type = ruleType;
                payload.target_id = targetId.trim();
                payload.permission_level = permissionLevel;
            }

            console.log('[AccessModal] API 호출 payload:', payload);

            await axios.post(`${API_BASE_URL}/documents/${documentId}/access-rules`, payload, {
                headers: { Authorization: `Bearer ${token}` }
            });

            alert('접근 권한이 설정되었습니다.');
            onSuccess?.();
            onClose();
        } catch (error: any) {
            console.error('접근 규칙 저장 실패:', error);
            alert(error.response?.data?.detail || '접근 권한 설정에 실패했습니다.');
        } finally {
            setIsSaving(false);
        }
    };

    console.log('[AccessModal] 현재 렌더링 - accessLevel:', accessLevel, 'isLoading:', isLoading);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                {/* 헤더 */}
                <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between rounded-t-2xl">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">문서 접근 권한 설정</h2>
                        <p className="text-sm text-gray-500 mt-1">{documentName}</p>
                    </div>
                    <button
                        onClick={() => {
                            console.log('[AccessModal] 닫기 버튼 클릭');
                            onClose();
                        }}
                        className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                        <X className="w-5 h-5 text-gray-500" />
                    </button>
                </div>

                {/* 내용 */}
                <div className="px-6 py-6 space-y-6">
                    {isLoading ? (
                        <div className="text-center py-8">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                            <p className="mt-4 text-gray-600">로딩 중...</p>
                        </div>
                    ) : (
                        <>
                            {/* 접근 레벨 선택 */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-3">
                                    접근 레벨
                                </label>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3" role="group" aria-label="접근 레벨 선택">
                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            console.log('[AccessModal] 🔵 공개 버튼 클릭');
                                            console.log('[AccessModal] - 현재 accessLevel:', accessLevel);
                                            setAccessLevel('public');
                                            console.log('[AccessModal] 공개로 변경 완료');
                                        }}
                                        className={`p-4 border-2 rounded-xl transition-colors ${accessLevel === 'public'
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        aria-pressed={accessLevel === 'public'}
                                    >
                                        <Globe className={`w-6 h-6 mx-auto mb-2 ${accessLevel === 'public' ? 'text-blue-600' : 'text-gray-400'
                                            }`} />
                                        <div className="text-sm font-semibold text-gray-900">공개</div>
                                        <div className="text-xs text-gray-500 mt-1">모두 조회 가능</div>
                                    </button>

                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            console.log('[AccessModal] 🟡 제한 버튼 클릭 시작');
                                            console.log('[AccessModal] - 클릭 이벤트:', e.type);
                                            console.log('[AccessModal] - 현재 accessLevel:', accessLevel);
                                            console.log('[AccessModal] - isInitialLoad:', isInitialLoad);
                                            console.log('[AccessModal] - isLoading:', isLoading);

                                            setAccessLevel('restricted');

                                            console.log('[AccessModal] 🟢 setAccessLevel("restricted") 호출 완료');
                                            console.log('[AccessModal] - 다음 렌더링에서 accessLevel === "restricted" 체크 예상');
                                        }}
                                        className={`p-4 border-2 rounded-xl transition-colors ${accessLevel === 'restricted'
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        aria-pressed={accessLevel === 'restricted'}
                                    >
                                        <Users className={`w-6 h-6 mx-auto mb-2 ${accessLevel === 'restricted' ? 'text-blue-600' : 'text-gray-400'
                                            }`} />
                                        <div className="text-sm font-semibold text-gray-900">제한 공개</div>
                                        <div className="text-xs text-gray-500 mt-1">특정 사용자/부서</div>
                                    </button>

                                    <button
                                        type="button"
                                        onClick={(e) => {
                                            console.log('[AccessModal] 🔴 비공개 버튼 클릭');
                                            console.log('[AccessModal] - 현재 accessLevel:', accessLevel);
                                            setAccessLevel('private');
                                            console.log('[AccessModal] 비공개로 변경 완료');
                                        }}
                                        className={`p-4 border-2 rounded-xl transition-colors ${accessLevel === 'private'
                                            ? 'border-blue-500 bg-blue-50'
                                            : 'border-gray-200 hover:border-gray-300'
                                            }`}
                                        aria-pressed={accessLevel === 'private'}
                                    >
                                        <Lock className={`w-6 h-6 mx-auto mb-2 ${accessLevel === 'private' ? 'text-blue-600' : 'text-gray-400'
                                            }`} />
                                        <div className="text-sm font-semibold text-gray-900">비공개</div>
                                        <div className="text-xs text-gray-500 mt-1">관리자만 조회</div>
                                    </button>
                                </div>
                            </div>

                            {/* 제한 공개 상세 설정 */}
                            {(() => {
                                const shouldShow = accessLevel === 'restricted';
                                console.log('[AccessModal] 🔍 제한 패널 표시 체크:', {
                                    accessLevel,
                                    shouldShow,
                                    comparison: `"${accessLevel}" === "restricted"`,
                                    typeOfAccessLevel: typeof accessLevel
                                });
                                return shouldShow;
                            })() && (
                                    <div className="bg-gray-50 rounded-xl p-4 space-y-4">
                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                대상 유형
                                            </label>
                                            <div className="flex gap-3">
                                                <button
                                                    type="button"
                                                    onClick={() => setRuleType('user')}
                                                    className={`flex-1 py-2 px-4 rounded-lg border-2 transition-all ${ruleType === 'user'
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    사용자 (사번)
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setRuleType('department')}
                                                    className={`flex-1 py-2 px-4 rounded-lg border-2 transition-all ${ruleType === 'department'
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    부서
                                                </button>
                                            </div>
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                {ruleType === 'user' ? '사용자 사번' : '부서명'}
                                            </label>
                                            <input
                                                type="text"
                                                value={targetId}
                                                onChange={(e) => setTargetId(e.target.value)}
                                                placeholder={ruleType === 'user' ? '예: MSS001' : '예: MS서비스팀'}
                                                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            />
                                        </div>

                                        <div>
                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                권한 레벨
                                            </label>
                                            <div className="grid grid-cols-3 gap-2">
                                                <button
                                                    type="button"
                                                    onClick={() => setPermissionLevel('view')}
                                                    className={`py-2 px-3 rounded-lg border-2 text-sm transition-all ${permissionLevel === 'view'
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    <Eye className="w-4 h-4 mx-auto mb-1" />
                                                    조회만
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setPermissionLevel('download')}
                                                    className={`py-2 px-3 rounded-lg border-2 text-sm transition-all ${permissionLevel === 'download'
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    <Download className="w-4 h-4 mx-auto mb-1" />
                                                    다운로드
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setPermissionLevel('edit')}
                                                    className={`py-2 px-3 rounded-lg border-2 text-sm transition-all ${permissionLevel === 'edit'
                                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                                        : 'border-gray-200 hover:border-gray-300'
                                                        }`}
                                                >
                                                    <Edit2 className="w-4 h-4 mx-auto mb-1" />
                                                    편집
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                            {/* 안내 메시지 */}
                            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                                <div className="flex">
                                    <div className="flex-shrink-0">
                                        <svg className="h-5 w-5 text-blue-400" fill="currentColor" viewBox="0 0 20 20">
                                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                                        </svg>
                                    </div>
                                    <div className="ml-3">
                                        <h3 className="text-sm font-medium text-blue-800">접근 권한 안내</h3>
                                        <div className="mt-2 text-sm text-blue-700">
                                            <ul className="list-disc list-inside space-y-1">
                                                <li><strong>공개</strong>: 컨테이너 접근 권한이 있는 모든 사용자가 조회 가능</li>
                                                <li><strong>제한 공개</strong>: 지정한 사용자 또는 부서만 조회 가능</li>
                                                <li><strong>비공개</strong>: 본인과 컨테이너 관리자만 조회 가능</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* 푸터 */}
                <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end gap-3 rounded-b-2xl">
                    <button
                        onClick={onClose}
                        disabled={isSaving}
                        className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
                    >
                        취소
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving || isLoading}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {isSaving ? (
                            <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                                저장 중...
                            </>
                        ) : (
                            '저장'
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default DocumentAccessModal;
