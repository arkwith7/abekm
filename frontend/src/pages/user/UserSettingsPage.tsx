import {
    Bell,
    Layout,
    Palette,
    Settings,
    Shield
} from 'lucide-react';
import React, { useState } from 'react';
import TemplateManagement from './TemplateManagement';

// 설정 탭 타입
type SettingsTab = 'templates' | 'notifications' | 'appearance' | 'privacy';

interface TabItem {
    id: SettingsTab;
    name: string;
    icon: React.ComponentType<{ className?: string }>;
    description: string;
}

const settingsTabs: TabItem[] = [
    {
        id: 'templates',
        name: 'PPT 템플릿',
        icon: Layout,
        description: '프레젠테이션 템플릿 관리'
    },
    {
        id: 'notifications',
        name: '알림 설정',
        icon: Bell,
        description: '알림 및 이메일 설정'
    },
    {
        id: 'appearance',
        name: '화면 설정',
        icon: Palette,
        description: '테마 및 표시 설정'
    },
    {
        id: 'privacy',
        name: '개인정보',
        icon: Shield,
        description: '개인정보 및 보안 설정'
    }
];

export const UserSettingsPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState<SettingsTab>('templates');

    const renderTabContent = () => {
        switch (activeTab) {
            case 'templates':
                return <TemplateManagement />;

            case 'notifications':
                return (
                    <div className="p-6">
                        <h2 className="text-xl font-semibold text-gray-900 mb-4">알림 설정</h2>
                        <div className="bg-white rounded-lg border border-gray-200 p-6">
                            <p className="text-gray-500 text-center py-8">
                                알림 설정 기능은 준비 중입니다.
                            </p>
                        </div>
                    </div>
                );

            case 'appearance':
                return (
                    <div className="p-6">
                        <h2 className="text-xl font-semibold text-gray-900 mb-4">화면 설정</h2>
                        <div className="bg-white rounded-lg border border-gray-200 p-6">
                            <p className="text-gray-500 text-center py-8">
                                화면 설정 기능은 준비 중입니다.
                            </p>
                        </div>
                    </div>
                );

            case 'privacy':
                return (
                    <div className="p-6">
                        <h2 className="text-xl font-semibold text-gray-900 mb-4">개인정보 설정</h2>
                        <div className="bg-white rounded-lg border border-gray-200 p-6">
                            <p className="text-gray-500 text-center py-8">
                                개인정보 설정 기능은 준비 중입니다.
                            </p>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            {/* 페이지 헤더 */}
            <div className="bg-white border-b border-gray-200">
                <div className="px-6 py-4">
                    <div className="flex items-center space-x-3">
                        <Settings className="w-6 h-6 text-gray-600" />
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900">설정</h1>
                            <p className="text-sm text-gray-500">개인 환경설정을 관리합니다</p>
                        </div>
                    </div>
                </div>
            </div>

            <div className="flex">
                {/* 사이드 탭 네비게이션 */}
                <div className="w-64 bg-white border-r border-gray-200 min-h-[calc(100vh-130px)]">
                    <nav className="p-4 space-y-1">
                        {settingsTabs.map((tab) => {
                            const Icon = tab.icon;
                            const isActive = activeTab === tab.id;

                            return (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors text-left ${isActive
                                            ? 'bg-blue-50 text-blue-700 border-l-4 border-blue-600'
                                            : 'text-gray-600 hover:bg-gray-50'
                                        }`}
                                >
                                    <Icon className={`w-5 h-5 ${isActive ? 'text-blue-600' : 'text-gray-400'}`} />
                                    <div>
                                        <div className={`font-medium ${isActive ? 'text-blue-700' : 'text-gray-900'}`}>
                                            {tab.name}
                                        </div>
                                        <div className="text-xs text-gray-500">{tab.description}</div>
                                    </div>
                                </button>
                            );
                        })}
                    </nav>
                </div>

                {/* 콘텐츠 영역 */}
                <div className="flex-1 overflow-auto">
                    {renderTabContent()}
                </div>
            </div>
        </div>
    );
};

export default UserSettingsPage;
