import { Search } from 'lucide-react';
import React from 'react';

interface PermissionFiltersProps {
    searchTerm: string;
    setSearchTerm: (value: string) => void;
    selectedDepartment: string;
    setSelectedDepartment: (value: string) => void;
    selectedContainer: string;
    setSelectedContainer: (value: string) => void;
    departments: string[];
    containers: Array<{ id: string; name: string }>;
}

export const PermissionFilters: React.FC<PermissionFiltersProps> = ({
    searchTerm,
    setSearchTerm,
    selectedDepartment,
    setSelectedDepartment,
    selectedContainer,
    setSelectedContainer,
    departments,
    containers
}) => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                    <input
                        type="text"
                        placeholder="이름 또는 사번으로 검색"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                </div>
                <select
                    value={selectedContainer}
                    onChange={(e) => setSelectedContainer(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">모든 지식컨테이너</option>
                    {containers.map((container) => (
                        <option key={container.id} value={container.id}>
                            {container.name}
                        </option>
                    ))}
                </select>
                <select
                    value={selectedDepartment}
                    onChange={(e) => setSelectedDepartment(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    <option value="">모든 부서</option>
                    {departments.map((dept) => (
                        <option key={dept} value={dept}>
                            {dept}
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
};
