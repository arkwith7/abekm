import axios from 'axios';
import {
    AlertCircle,
    Building,
    Calendar,
    CheckCircle,
    Clock,
    Edit3,
    Mail,
    Phone,
    Save,
    Shield,
    User,
    X
} from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { authService } from '../../services/authService';
import { getApiUrl } from '../../utils/apiConfig';

interface UserInfo {
    emp_no: string;
    username: string;
    email: string;
    is_active: boolean;
    is_admin: boolean;
    failed_login_attempts: number;
    last_login_date?: string;
    created_date: string;
    last_modified_date: string;
    sap_hr_info?: {
        emp_nm: string;
        dept_cd: string;
        dept_nm: string;
        postn_cd: string;
        postn_nm: string;
        telno?: string;
        entrps_de?: string;
        emp_stats_cd: string;
    };
    role_info?: {
        role_name: string;
        scope_type: string;
        scope_value: string;
        role_description: string;
    };
}

interface EditableField {
    key: string;
    label: string;
    value: string;
    type: 'text' | 'email' | 'tel';
    editable: boolean;
}

const UserProfilePage: React.FC = () => {
    const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editableFields, setEditableFields] = useState<EditableField[]>([]);
    const [saveLoading, setSaveLoading] = useState(false);
    const [saveMessage, setSaveMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    const fetchUserInfo = async () => {
        try {
            setLoading(true);
            setError(null);

            // 인증 상태 먼저 체크
            if (!authService.isAuthenticated()) {
                setError('인증이 만료되었습니다. 다시 로그인해주세요.');
                setLoading(false);
                return;
            }

            // 정식 인증된 사용자 정보 API 사용
            const response = await axios.get(`/api/v1/auth/me`, {
                headers: {
                    'Content-Type': 'application/json',
                    'accept': 'application/json'
                }
            });

            if (response.status === 200) {
                const data = response.data;
                setUserInfo(data);

                // 편집 가능한 필드 초기화
                setEditableFields([
                    {
                        key: 'email',
                        label: '이메일',
                        value: data.email || '',
                        type: 'email',
                        editable: true
                    },
                    {
                        key: 'telno',
                        label: '전화번호',
                        value: data.sap_hr_info?.telno || '',
                        type: 'tel',
                        editable: true
                    }
                ]);
            } else {
                setError('사용자 정보를 불러오는데 실패했습니다.');
            }
        } catch (err) {
            console.error('사용자 정보 조회 오류:', err);
            setError('네트워크 오류가 발생했습니다.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchUserInfo();
    }, []);

    const handleEditToggle = () => {
        if (isEditing) {
            // 편집 취소 시 원래 값으로 복원
            setEditableFields(prev => prev.map(field => ({
                ...field,
                value: field.key === 'email' ? userInfo?.email || '' : userInfo?.sap_hr_info?.telno || ''
            })));
        }
        setIsEditing(!isEditing);
        setSaveMessage(null);
    };

    const handleFieldChange = (key: string, value: string) => {
        setEditableFields(prev => prev.map(field =>
            field.key === key ? { ...field, value } : field
        ));
    };

    const handleSave = async () => {
        try {
            setSaveLoading(true);
            setSaveMessage(null);

            const updateData: any = {};
            editableFields.forEach(field => {
                if (field.key === 'email') {
                    updateData.email = field.value;
                } else if (field.key === 'telno') {
                    updateData.telno = field.value;
                }
            });

            const apiBaseUrl = getApiUrl();
            const apiUrl = apiBaseUrl ? `${apiBaseUrl}/api/v1/auth/me` : '/api/v1/auth/me';
            
            const response = await fetch(apiUrl, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('ABEKM_token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
            });

            if (response.status === 401) {
                // 인증 만료 시 로그인 페이지로 리다이렉트
                localStorage.removeItem('ABEKM_token');
                localStorage.removeItem('ABEKM_refresh_token');
                window.dispatchEvent(new Event('session:invalid'));
                window.location.href = '/login';
                return;
            }

            if (response.ok) {
                setSaveMessage({ type: 'success', text: '사용자 정보가 성공적으로 업데이트되었습니다.' });
                setIsEditing(false);
                // 최신 정보 다시 불러오기
                await fetchUserInfo();
            } else {
                const errorData = await response.json();
                setSaveMessage({ type: 'error', text: errorData.detail || '정보 업데이트에 실패했습니다.' });
            }
        } catch (err) {
            console.error('사용자 정보 업데이트 오류:', err);
            setSaveMessage({ type: 'error', text: '네트워크 오류가 발생했습니다.' });
        } finally {
            setSaveLoading(false);
        }
    };

    const formatDate = (dateString?: string) => {
        if (!dateString) return '-';
        try {
            return new Date(dateString).toLocaleDateString('ko-KR', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateString;
        }
    };

    const getRoleDisplayName = (role?: string) => {
        switch (role) {
            case 'ADMIN': return '시스템관리자';
            case 'MANAGER': return '지식관리자';
            case 'USER': return '일반사용자';
            default: return role || '미지정';
        }
    };

    const getStatusColor = (isActive: boolean) => {
        return isActive ? 'text-green-600 bg-green-100' : 'text-red-600 bg-red-100';
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600">사용자 정보를 불러오는 중...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="min-h-screen bg-gray-50 flex items-center justify-center">
                <div className="text-center">
                    <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
                    <h3 className="text-lg font-medium text-gray-900 mb-2">오류 발생</h3>
                    <p className="text-gray-600 mb-4">{error}</p>
                    <button
                        onClick={fetchUserInfo}
                        className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                    >
                        다시 시도
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-4xl mx-auto">
                {/* 헤더 */}
                <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-4">
                            <div className="w-16 h-16 bg-blue-600 rounded-full flex items-center justify-center">
                                <span className="text-white text-2xl font-bold">
                                    {userInfo?.sap_hr_info?.emp_nm?.charAt(0) || userInfo?.username?.charAt(0) || 'U'}
                                </span>
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold text-gray-900">
                                    {userInfo?.sap_hr_info?.emp_nm || userInfo?.username || '사용자'}
                                </h1>
                                <p className="text-gray-600">
                                    {userInfo?.sap_hr_info?.dept_nm || '부서 미지정'} · {userInfo?.sap_hr_info?.postn_nm || '직급 미지정'}
                                </p>
                                <div className="flex items-center mt-2 space-x-2">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(userInfo?.is_active || false)}`}>
                                        {userInfo?.is_active ? '활성' : '비활성'}
                                    </span>
                                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-600">
                                        {getRoleDisplayName(userInfo?.is_admin ? 'ADMIN' : 'USER')}
                                    </span>
                                </div>
                            </div>
                        </div>

                        <div className="flex items-center space-x-2">
                            {saveMessage && (
                                <div className={`flex items-center space-x-1 px-3 py-2 rounded-lg text-sm ${saveMessage.type === 'success'
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-red-100 text-red-700'
                                    }`}>
                                    {saveMessage.type === 'success' ? (
                                        <CheckCircle className="w-4 h-4" />
                                    ) : (
                                        <AlertCircle className="w-4 h-4" />
                                    )}
                                    <span>{saveMessage.text}</span>
                                </div>
                            )}

                            {isEditing ? (
                                <div className="flex space-x-2">
                                    <button
                                        onClick={handleSave}
                                        disabled={saveLoading}
                                        className="flex items-center space-x-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                                    >
                                        <Save className="w-4 h-4" />
                                        <span>{saveLoading ? '저장 중...' : '저장'}</span>
                                    </button>
                                    <button
                                        onClick={handleEditToggle}
                                        className="flex items-center space-x-1 bg-gray-500 text-white px-4 py-2 rounded-lg hover:bg-gray-600 transition-colors"
                                    >
                                        <X className="w-4 h-4" />
                                        <span>취소</span>
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={handleEditToggle}
                                    className="flex items-center space-x-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                                >
                                    <Edit3 className="w-4 h-4" />
                                    <span>편집</span>
                                </button>
                            )}
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* 기본 정보 */}
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <User className="w-5 h-5 mr-2" />
                            기본 정보
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">사원번호</label>
                                <p className="text-gray-900">{userInfo?.emp_no || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">사용자명</label>
                                <p className="text-gray-900">{userInfo?.username || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">이름</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.emp_nm || '-'}</p>
                            </div>

                            {editableFields.map(field => (
                                <div key={field.key}>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">{field.label}</label>
                                    {isEditing && field.editable ? (
                                        <input
                                            type={field.type}
                                            value={field.value}
                                            onChange={(e) => handleFieldChange(field.key, e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                                        />
                                    ) : (
                                        <div className="flex items-center">
                                            {field.key === 'email' && <Mail className="w-4 h-4 mr-2 text-gray-400" />}
                                            {field.key === 'telno' && <Phone className="w-4 h-4 mr-2 text-gray-400" />}
                                            <p className="text-gray-900">{field.value || '-'}</p>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* 조직 정보 */}
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <Building className="w-5 h-5 mr-2" />
                            조직 정보
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">부서코드</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.dept_cd || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">부서명</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.dept_nm || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">직급코드</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.postn_cd || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">직급명</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.postn_nm || '-'}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">입사일</label>
                                <div className="flex items-center">
                                    <Calendar className="w-4 h-4 mr-2 text-gray-400" />
                                    <p className="text-gray-900">{userInfo?.sap_hr_info?.entrps_de || '-'}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 계정 정보 */}
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <Shield className="w-5 h-5 mr-2" />
                            계정 정보
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">계정 상태</label>
                                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(userInfo?.is_active || false)}`}>
                                    {userInfo?.is_active ? '활성' : '비활성'}
                                </span>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">권한</label>
                                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-600">
                                    {getRoleDisplayName(userInfo?.is_admin ? 'ADMIN' : 'USER')}
                                </span>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">로그인 실패 횟수</label>
                                <p className="text-gray-900">{userInfo?.failed_login_attempts || 0}회</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">마지막 로그인</label>
                                <div className="flex items-center">
                                    <Clock className="w-4 h-4 mr-2 text-gray-400" />
                                    <p className="text-gray-900">{formatDate(userInfo?.last_login_date)}</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* 시스템 정보 */}
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <Clock className="w-5 h-5 mr-2" />
                            시스템 정보
                        </h2>

                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">계정 생성일</label>
                                <p className="text-gray-900">{formatDate(userInfo?.created_date)}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">마지막 수정일</label>
                                <p className="text-gray-900">{formatDate(userInfo?.last_modified_date)}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">재직 상태</label>
                                <p className="text-gray-900">{userInfo?.sap_hr_info?.emp_stats_cd || '-'}</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 역할 정보 (있는 경우) */}
                {userInfo?.role_info && (
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mt-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                            <Shield className="w-5 h-5 mr-2" />
                            역할 정보
                        </h2>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">역할명</label>
                                <p className="text-gray-900">{userInfo.role_info.role_name}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">범위 유형</label>
                                <p className="text-gray-900">{userInfo.role_info.scope_type}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">범위 값</label>
                                <p className="text-gray-900">{userInfo.role_info.scope_value}</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">역할 설명</label>
                                <p className="text-gray-900">{userInfo.role_info.role_description}</p>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default UserProfilePage;
