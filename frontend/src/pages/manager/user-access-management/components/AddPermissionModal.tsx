import { Plus, Search, X } from 'lucide-react';
import React, { useState } from 'react';
import { searchUsersForPermissions } from '../../../../services/managerService';

interface AddPermissionModalProps {
    isOpen: boolean;
    onClose: () => void;
    containers: Array<{ id: string; name: string }>;
    onAddPermission: (userId: string, containerId: string, permission: string) => Promise<void>;
}

interface SearchedUser {
    emp_no: string;
    name?: string;
    username?: string;
    department?: string;
    position?: string;
}

export const AddPermissionModal: React.FC<AddPermissionModalProps> = ({
    isOpen,
    onClose,
    containers,
    onAddPermission
}) => {
    const [selectedContainer, setSelectedContainer] = useState('');
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedUser, setSelectedUser] = useState<SearchedUser | null>(null);
    const [selectedPermission, setSelectedPermission] = useState('read');
    const [searchResults, setSearchResults] = useState<SearchedUser[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    const handleSearch = async () => {
        if (!searchTerm.trim()) {
            alert('검색어를 입력해주세요.');
            return;
        }

        setIsSearching(true);
        try {
            console.log('사용자 검색 시작:', searchTerm);
            const response = await searchUsersForPermissions(searchTerm, 1, 50);
            console.log('검색 응답:', response);

            const users: SearchedUser[] = response.users.map((user: any) => ({
                emp_no: user.emp_no,
                name: user.name || user.username,
                username: user.username,
                department: user.department,
                position: user.position
            }));

            console.log('변환된 사용자 목록:', users);
            setSearchResults(users);

            if (users.length === 0) {
                alert('검색 결과가 없습니다. 다른 검색어를 시도해보세요.');
            }
        } catch (error: any) {
            console.error('사용자 검색 실패:', error);
            const errorMessage = error.response?.data?.detail || error.message || '사용자 검색에 실패했습니다.';
            alert(`검색 실패: ${errorMessage}`);
            setSearchResults([]);
        } finally {
            setIsSearching(false);
        }
    };

    const handleSubmit = async () => {
        if (!selectedContainer) {
            alert('지식컨테이너를 선택해주세요.');
            return;
        }
        if (!selectedUser) {
            alert('사용자를 선택해주세요.');
            return;
        }

        try {
            console.log('권한 추가 시도:', {
                user: selectedUser.emp_no,
                container: selectedContainer,
                permission: selectedPermission
            });

            await onAddPermission(selectedUser.emp_no, selectedContainer, selectedPermission);

            console.log('권한 추가 성공');

            // 초기화
            setSelectedContainer('');
            setSearchTerm('');
            setSelectedUser(null);
            setSelectedPermission('read');
            setSearchResults([]);

            // 성공 메시지는 부모 컴포넌트에서 처리하므로 모달만 닫기
            onClose();
        } catch (error: any) {
            console.error('권한 추가 실패:', error);
            const errorMessage = error.response?.data?.detail || error.message || '권한 추가에 실패했습니다.';
            alert(`권한 추가 실패: ${errorMessage}`);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between p-6 border-b border-gray-200">
                    <h2 className="text-xl font-semibold text-gray-900">사용자 권한 추가</h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* 지식컨테이너 선택 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            지식컨테이너 선택 <span className="text-red-500">*</span>
                        </label>
                        <select
                            value={selectedContainer}
                            onChange={(e) => setSelectedContainer(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="">지식컨테이너를 선택하세요</option>
                            {containers.map((container) => (
                                <option key={container.id} value={container.id}>
                                    {container.name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* 사용자 검색 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            사용자 검색 <span className="text-red-500">*</span>
                        </label>
                        <div className="flex space-x-2">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                                <input
                                    type="text"
                                    placeholder="이름, 사번, 부서로 검색"
                                    value={searchTerm}
                                    onChange={(e) => setSearchTerm(e.target.value)}
                                    onKeyPress={(e) => {
                                        if (e.key === 'Enter') handleSearch();
                                    }}
                                    className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                />
                            </div>
                            <button
                                onClick={handleSearch}
                                disabled={isSearching}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400"
                            >
                                {isSearching ? '검색 중...' : '검색'}
                            </button>
                        </div>
                    </div>

                    {/* 검색 결과 */}
                    {searchResults.length > 0 && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">검색 결과</label>
                            <div className="border border-gray-200 rounded-md divide-y divide-gray-200 max-h-60 overflow-y-auto">
                                {searchResults.map((user) => (
                                    <div
                                        key={user.emp_no}
                                        onClick={() => setSelectedUser(user)}
                                        className={`p-3 cursor-pointer hover:bg-gray-50 ${selectedUser?.emp_no === user.emp_no ? 'bg-blue-50 border-l-4 border-blue-500' : ''
                                            }`}
                                    >
                                        <div className="flex items-center justify-between">
                                            <div>
                                                <div className="font-medium text-gray-900">
                                                    {user.name} ({user.emp_no})
                                                </div>
                                                <div className="text-sm text-gray-500">
                                                    {user.department} · {user.position}
                                                </div>
                                            </div>
                                            {selectedUser?.emp_no === user.emp_no && (
                                                <div className="text-blue-600">
                                                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                                        <path
                                                            fillRule="evenodd"
                                                            d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                                                            clipRule="evenodd"
                                                        />
                                                    </svg>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 권한 선택 */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            권한 레벨 선택 <span className="text-red-500">*</span>
                        </label>
                        <select
                            value={selectedPermission}
                            onChange={(e) => setSelectedPermission(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="read">읽기 - 문서 조회, 검색, 다운로드</option>
                            <option value="write">읽기/쓰기 - 읽기 + 문서 업로드, 수정</option>
                            <option value="admin">관리자 - 모든 권한 + 지식컨테이너 관리</option>
                        </select>
                    </div>

                    {/* 선택된 정보 미리보기 */}
                    {selectedUser && selectedContainer && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <h4 className="font-medium text-blue-900 mb-2">선택 정보 확인</h4>
                            <div className="text-sm text-blue-800 space-y-1">
                                <div>
                                    <span className="font-medium">사용자:</span> {selectedUser.name} ({selectedUser.emp_no})
                                </div>
                                <div>
                                    <span className="font-medium">컨테이너:</span>{' '}
                                    {containers.find((c) => c.id === selectedContainer)?.name}
                                </div>
                                <div>
                                    <span className="font-medium">권한:</span>{' '}
                                    {selectedPermission === 'read'
                                        ? '읽기'
                                        : selectedPermission === 'write'
                                            ? '읽기/쓰기'
                                            : '관리자'}
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="flex justify-end space-x-3 p-6 border-t border-gray-200 bg-gray-50">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                    >
                        취소
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={!selectedContainer || !selectedUser}
                        className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center"
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        권한 추가
                    </button>
                </div>
            </div>
        </div>
    );
};
