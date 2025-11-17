import {
    BarChart3,
    Eye,
    EyeOff,
    Image as ImageIcon,
    Move3d,
    Palette,
    Plus,
    RotateCcw,
    Square,
    Table,
    Trash2,
    Type
} from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { TextBoxMapping } from '../../types/presentation';
import { getSlideArea } from '../../utils/slideClassification';

// 테이블 데이터 타입 정의
interface TableData {
    headers: string[];
    rows: string[][];
}

// 백엔드 테이블 데이터를 TableData 형식으로 변환하는 함수
const convertBackendTableData = (backendData: any): TableData => {
    if (!backendData || !Array.isArray(backendData.data)) {
        return {
            headers: ['열1', '열2'],
            rows: [['', '']]
        };
    }

    const data = backendData.data;
    if (data.length === 0) {
        return {
            headers: ['열1', '열2'],
            rows: [['', '']]
        };
    }

    // 첫 번째 행을 헤더로 사용
    const headers = data[0].map((cell: string, index: number) =>
        cell.trim() || `열${index + 1}`
    );

    // 나머지 행들을 데이터로 사용
    const rows = data.length > 1 ? data.slice(1) : [new Array(headers.length).fill('')];

    return { headers, rows };
};

// 텍스트에서 테이블 데이터 추출하는 함수
const extractTableDataFromText = (text: string): TableData => {
    const lines = text.split('\n').filter(line => line.trim());

    // 간단한 테이블 파싱 (| 구분자 사용)
    const tableLines = lines.filter(line => line.includes('|'));

    if (tableLines.length === 0) {
        // | 구분자가 없으면 탭이나 공백으로 구분 시도
        const firstLine = lines[0] || '';
        if (firstLine.includes('\t')) {
            const headers = firstLine.split('\t').map(h => h.trim());
            const rows = lines.slice(1).map(line =>
                line.split('\t').map(cell => cell.trim())
            );
            return { headers, rows };
        } else {
            // 기본값: 첫 번째 줄을 헤더로, 나머지를 데이터로
            return {
                headers: ['항목', '값'],
                rows: lines.map(line => ['', line])
            };
        }
    }

    const headers = tableLines[0]
        .split('|')
        .map(h => h.trim())
        .filter(h => h);

    const rows = tableLines.slice(1)
        .filter(line => !line.includes('---')) // 구분선 제거
        .map(line =>
            line.split('|')
                .map(cell => cell.trim())
                .filter(cell => cell)
        );

    return { headers, rows };
};

// TableEditor 컴포넌트
interface TableEditorProps {
    tableData: TableData;
    onTableDataChange: (newTableData: TableData) => void;
}

const TableEditor: React.FC<TableEditorProps> = ({ tableData, onTableDataChange }) => {
    const [localTableData, setLocalTableData] = useState<TableData>(
        tableData || { headers: ['열1', '열2'], rows: [['', '']] }
    );

    useEffect(() => {
        if (tableData) {
            console.log('📊 TableEditor: 새로운 tableData 수신:', tableData);
            setLocalTableData(tableData);
        }
    }, [tableData]);

    const updateTableData = (newData: TableData) => {
        console.log('🔧 updateTableData 호출:', newData);
        setLocalTableData(newData);
        onTableDataChange(newData);
    };

    const updateHeader = (index: number, value: string) => {
        console.log('📝 updateHeader:', index, value);
        const newHeaders = [...localTableData.headers];
        newHeaders[index] = value;
        updateTableData({ ...localTableData, headers: newHeaders });
    };

    const updateCell = (rowIndex: number, colIndex: number, value: string) => {
        console.log('📝 updateCell:', rowIndex, colIndex, value);
        const newRows = [...localTableData.rows];
        if (!newRows[rowIndex]) {
            newRows[rowIndex] = new Array(localTableData.headers.length).fill('');
        }
        newRows[rowIndex] = [...newRows[rowIndex]];
        newRows[rowIndex][colIndex] = value;
        updateTableData({ ...localTableData, rows: newRows });
    };

    const addColumn = () => {
        console.log('➕ addColumn 호출');
        const newHeaders = [...localTableData.headers, `열${localTableData.headers.length + 1}`];
        const newRows = localTableData.rows.map(row => [...row, '']);
        updateTableData({ headers: newHeaders, rows: newRows });
    };

    const removeColumn = (index: number) => {
        console.log('🗑️ removeColumn 호출:', index);
        if (localTableData.headers.length <= 1) {
            console.log('❌ 마지막 열이라 삭제 불가');
            return;
        }

        const newHeaders = localTableData.headers.filter((_, i) => i !== index);
        const newRows = localTableData.rows.map(row => row.filter((_, i) => i !== index));
        updateTableData({ headers: newHeaders, rows: newRows });
    };

    const addRow = () => {
        console.log('➕ addRow 호출');
        const newRow = new Array(localTableData.headers.length).fill('');
        const newRows = [...localTableData.rows, newRow];
        updateTableData({ ...localTableData, rows: newRows });
    };

    const removeRow = (index: number) => {
        console.log('🗑️ removeRow 호출:', index);
        if (localTableData.rows.length <= 1) {
            console.log('❌ 마지막 행이라 삭제 불가');
            return;
        }

        const newRows = localTableData.rows.filter((_, i) => i !== index);
        updateTableData({ ...localTableData, rows: newRows });
    };

    return (
        <div className="table-editor" style={{ pointerEvents: 'auto' }}>
            <div className="overflow-x-auto">
                <table className="min-w-full border-collapse border border-gray-300">
                    <thead>
                        <tr>
                            {localTableData.headers.map((header, index) => (
                                <th key={index} className="border border-gray-300 p-1 bg-gray-50">
                                    <div className="flex items-center gap-1">
                                        <input
                                            type="text"
                                            value={header}
                                            onClick={(e) => e.stopPropagation()}
                                            onChange={(e) => updateHeader(index, e.target.value)}
                                            className="w-full text-xs p-1 border-0 bg-transparent font-medium"
                                            placeholder={`헤더 ${index + 1}`}
                                        />
                                        <button
                                            type="button"
                                            onClick={() => removeColumn(index)}
                                            className="text-red-500 hover:text-red-700 p-1"
                                            title="열 삭제"
                                        >
                                            <Trash2 className="h-3 w-3" />
                                        </button>
                                    </div>
                                </th>
                            ))}
                            <th className="border border-gray-300 p-1 bg-gray-50">
                                <button
                                    type="button"
                                    onMouseDown={(e) => e.stopPropagation()}
                                    onClick={addColumn}
                                    className="text-blue-500 hover:text-blue-700 p-1"
                                    title="열 추가"
                                >
                                    <Plus className="h-3 w-3" />
                                </button>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {localTableData.rows.map((row, rowIndex) => (
                            <tr key={rowIndex}>
                                {row.map((cell, colIndex) => (
                                    <td key={colIndex} className="border border-gray-300 p-1">
                                        <input
                                            type="text"
                                            value={cell}
                                            onClick={(e) => e.stopPropagation()}
                                            onChange={(e) => updateCell(rowIndex, colIndex, e.target.value)}
                                            className="w-full text-xs p-1 border-0 bg-transparent"
                                            placeholder={`데이터 ${rowIndex + 1}-${colIndex + 1}`}
                                        />
                                    </td>
                                ))}
                                <td className="border border-gray-300 p-1">
                                    <button
                                        type="button"
                                        onMouseDown={(e) => e.stopPropagation()}
                                        onClick={() => removeRow(rowIndex)}
                                        className="text-red-500 hover:text-red-700 p-1"
                                        title="행 삭제"
                                    >
                                        <Trash2 className="h-3 w-3" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                        <tr>
                            <td colSpan={localTableData.headers.length + 1} className="border border-gray-300 p-1 text-center">
                                <button
                                    type="button"
                                    onMouseDown={(e) => e.stopPropagation()}
                                    onClick={addRow}
                                    className="text-blue-500 hover:text-blue-700 p-1"
                                    title="행 추가"
                                >
                                    <Plus className="h-3 w-3" /> 행 추가
                                </button>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div className="mt-2 text-xs text-gray-500">
                현재 테이블: {localTableData.headers.length}열 × {localTableData.rows.length}행
                <div className="mt-1">
                    디버그: headers={JSON.stringify(localTableData.headers.slice(0, 2))}
                </div>
            </div>
        </div>
    );
};

// 확장된 타입 정의
export type PPTObjectType =
    | 'textbox'
    | 'image'
    | 'shape'
    | 'chart'
    | 'table'
    | 'diagram'
    | 'icon'
    | 'logo'
    | 'background';

export type ObjectAction =
    | 'keep_original'    // 원본 유지
    | 'replace_content'  // 내용 교체
    | 'hide_object';     // 오브젝트 제거

export interface PPTObjectMapping {
    slideIndex: number;
    elementId: string;
    objectType: PPTObjectType;
    action: ObjectAction;
    isEnabled: boolean;

    // 원본 정보
    originalContent?: string;
    originalStyle?: Record<string, any>;
    originalPosition?: { x: number; y: number; width: number; height: number };

    // 새로운 정보
    newContent?: string;
    newImageUrl?: string;
    newStyle?: Record<string, any>;
    newPosition?: { x: number; y: number; width: number; height: number };

    // 메타데이터
    metadata?: Record<string, any>;
}

interface Props {
    slideIndex: number;
    slideData: any; // 슬라이드 데이터
    contentSegments: any[]; // 컨텐츠 세그먼트
    mappings: TextBoxMapping[]; // 기존 TextBoxMapping 타입 사용
    onMappingChange: (mappings: TextBoxMapping[]) => void; // 기존 핸들러 타입 유지
    // 🆕 확장된 매핑 전달 (테이블 메타데이터 포함)
    onPPTMappingsChange?: (pptMappings: PPTObjectMapping[]) => void;
    className?: string;
    // 기존 TextBoxMappingEditor와의 호환성을 위한 props
    selectedSegment?: any;
    selectedTextBox?: any;
    onTextBoxClick?: (elementId: string) => void;
    onClearMapping?: (elementId: string) => void;
}

const PPTObjectMappingEditor: React.FC<Props> = ({
    slideIndex,
    slideData,
    contentSegments,
    mappings,
    onMappingChange,
    onPPTMappingsChange,
    className = '',
    // 기존 호환성 props
    selectedSegment,
    selectedTextBox,
    onTextBoxClick,
    onClearMapping
}) => {
    const [selectedObjectType, setSelectedObjectType] = useState<PPTObjectType | 'all'>('all');
    const [expandedElements, setExpandedElements] = useState<Set<string>>(new Set());

    // 로컬 매핑 상태 추가
    const [localMappings, setLocalMappings] = useState<PPTObjectMapping[]>([]);

    // 초기 로딩시 및 부모 변경 시 매핑 동기화 (기존 로컬 메타데이터 보존)
    useEffect(() => {
        const pptMappings = convertToPPTObjectMapping(mappings);
        setLocalMappings((prev) => {
            if (!prev || prev.length === 0) return pptMappings;

            // 동일 elementId/slideIndex 기준으로 병합하여 로컬의 metadata/tableData와 변경사항 보존
            const merged = pptMappings.map((m) => {
                const exist = prev.find(
                    (p) => p.slideIndex === m.slideIndex && p.elementId === m.elementId
                );
                if (!exist) return m;
                return {
                    ...m,
                    // 로컬 편집 내용 우선
                    action: exist.action ?? m.action,
                    newContent: exist.newContent ?? m.newContent,
                    isEnabled: exist.isEnabled ?? m.isEnabled,
                    metadata: exist.metadata || m.metadata,
                };
            });

            // prev에만 존재하는 항목 유지
            const prevOnly = prev.filter(
                (p) => !merged.some((m) => m.slideIndex === p.slideIndex && m.elementId === p.elementId)
            );
            return [...merged, ...prevOnly];
        });
    }, [mappings]);

    // 기존 TextBoxMapping을 PPTObjectMapping으로 변환
    const convertToPPTObjectMapping = (textBoxMappings: TextBoxMapping[]): PPTObjectMapping[] => {
        return textBoxMappings.map(mapping => {
            // 기존 매핑에서 objectType이 있으면 사용, 없으면 elementType 기반으로 추론
            let objectType: PPTObjectType = 'textbox';
            if ('objectType' in mapping && mapping.objectType) {
                objectType = mapping.objectType as PPTObjectType;
            } else if (mapping.elementType === 'table') {
                objectType = 'table';
            } else if (mapping.elementType?.toLowerCase().includes('image')) {
                objectType = 'image';
            } else if (mapping.elementType?.toLowerCase().includes('shape')) {
                objectType = 'shape';
            }

            return {
                slideIndex: mapping.slideIndex,
                elementId: mapping.elementId,
                objectType: objectType,
                action: mapping.action || (mapping.contentSource === 'keep_original' ? 'keep_original' as ObjectAction : 'replace_content' as ObjectAction),
                isEnabled: mapping.isEnabled !== undefined ? mapping.isEnabled : true,
                originalContent: mapping.originalContent,
                newContent: mapping.assignedContent,
                metadata: mapping.metadata || {
                    elementType: mapping.elementType,
                    contentSource: mapping.contentSource,
                    position: mapping.position
                }
            };
        });
    };

    // PPTObjectMapping을 기존 TextBoxMapping으로 변환 (개선된 버전)
    const convertToTextBoxMapping = (pptMappings: PPTObjectMapping[]): TextBoxMapping[] => {
        // 모든 타입의 오브젝트를 TextBoxMapping 형식으로 변환 (하위 호환성)
        return pptMappings.map(mapping => ({
            slideIndex: mapping.slideIndex,
            elementId: mapping.elementId,
            elementType: mapping.objectType, // 실제 오브젝트 타입 사용
            originalContent: mapping.originalContent,
            assignedContent: mapping.newContent || mapping.originalContent, // 변경된 내용이 있으면 사용
            contentSource: mapping.action === 'keep_original' ? 'keep_original' : 'ai_answer',
            position: mapping.metadata?.position || 'unknown',
            // 액션 정보 보존 (중요!)
            action: mapping.action,
            // 🆕 백엔드 호환성을 위해 PPT 매핑 필드들 추가
            objectType: mapping.objectType,
            isEnabled: mapping.isEnabled,
            metadata: mapping.metadata
        }));
    };

    // 현재 매핑을 로컬 상태에서 가져오기
    const currentPPTMappings = localMappings;

    // 매핑 변경 핸들러 (로컬 상태 업데이트 후 부모에 전달)
    const handlePPTMappingChange = (newMappings: PPTObjectMapping[]) => {
        console.log('🔄 handlePPTMappingChange:', newMappings.map(m => `${m.elementId}:${m.action}`));
        setLocalMappings(newMappings);
        // 기존 TextBoxMapping 형식으로 변환하여 부모에 전달
        const textBoxMappings = convertToTextBoxMapping(newMappings);
        onMappingChange(textBoxMappings);
        // 확장된 매핑도 함께 전달 (테이블 등 비-텍스트박스용)
        if (onPPTMappingsChange) {
            onPPTMappingsChange(newMappings);
        }
    };

    // 오브젝트 타입별 아이콘
    const getObjectIcon = (type: PPTObjectType) => {
        const iconMap = {
            textbox: <Type className="h-4 w-4" />,
            image: <ImageIcon className="h-4 w-4" />,
            shape: <Square className="h-4 w-4" />,
            chart: <BarChart3 className="h-4 w-4" />,
            table: <Table className="h-4 w-4" />,
            diagram: <Move3d className="h-4 w-4" />,
            icon: <Palette className="h-4 w-4" />,
            logo: <Palette className="h-4 w-4" />,
            background: <Square className="h-4 w-4" />
        };
        return iconMap[type] || <Square className="h-4 w-4" />;
    };

    // PPT 타입을 프론트엔드 타입으로 변환하는 함수
    const mapPPTTypeToObjectType = (pptType: string): PPTObjectType => {
        const typeMap: Record<string, PPTObjectType> = {
            'TEXT_BOX': 'textbox',
            'textbox': 'textbox', // 소문자 버전도 지원
            'AUTO_SHAPE': 'shape',
            'LINE': 'shape',
            'PICTURE': 'image',
            'image': 'image', // 소문자 버전도 지원
            'TABLE': 'table',
            'table': 'table', // 소문자 버전도 지원
            'CHART': 'chart',
            'chart': 'chart', // 소문자 버전도 지원
            'GROUP': 'shape', // 그룹도 도형으로 분류
        };

        return typeMap[pptType] || 'shape'; // 기본값은 shape
    };

    // 슬라이드의 모든 오브젝트 분류 (elements + shapes 병합)
    // 1) elements 기준 정규화 (텍스트박스 등)
    const elementObjects = (slideData.elements || []).map((element: any, index: number) => {
        const mappedType = mapPPTTypeToObjectType(element.type);

        // 테이블 오브젝트의 경우 테이블 데이터 초기화
        let tableData = null;
        if (mappedType === 'table') {
            if (element.data && Array.isArray(element.data)) {
                // 백엔드에서 추출된 테이블 데이터가 있는 경우
                tableData = convertBackendTableData(element);
            } else if (element.content && element.content.includes('Table')) {
                // 기본 테이블 데이터 (백엔드 형식 기반)
                tableData = {
                    headers: ['항목', '내용', '비고'],
                    rows: [
                        ['데이터 1', '설명 1', '비고 1'],
                        ['데이터 2', '설명 2', '비고 2']
                    ]
                };
            } else {
                // 완전히 기본 테이블 데이터
                tableData = {
                    headers: ['열1', '열2', '열3'],
                    rows: [
                        ['데이터 1-1', '데이터 1-2', '데이터 1-3'],
                        ['데이터 2-1', '데이터 2-2', '데이터 2-3']
                    ]
                };
            }
        }

        return {
            ...element,
            id: element.id || `${element.type}-${slideIndex}-${index}`,
            objectType: mappedType,
            displayName: `${mappedType} #${index + 1}`,
            originalType: element.type,
            tableData
        };
    });

    // 2) shapes 중 elements에 없는 것들 추가 (중복 방지)
    const elementIds = new Set(elementObjects.map((e: any) => e.id));
    const shapeObjects = (slideData.shapes || [])
        .filter((s: any) => s && s.name && !elementIds.has(s.name))
        .map((shape: any, idx: number) => {
            const mappedType = mapPPTTypeToObjectType(shape.type);
            const id = shape.name || `${shape.type}-${slideIndex}-shape-${idx}`;
            const position = {
                left: typeof shape.left_px === 'number' ? shape.left_px : shape.position?.left,
                top: typeof shape.top_px === 'number' ? shape.top_px : shape.position?.top,
                width: typeof shape.width_px === 'number' ? shape.width_px : shape.position?.width,
                height: typeof shape.height_px === 'number' ? shape.height_px : shape.position?.height,
            };
            return {
                ...shape,
                id,
                objectType: mappedType,
                displayName: `${mappedType} #${elementObjects.length + idx + 1}`,
                originalType: shape.type,
                position,
                content: shape?.text?.raw || shape?.name || '',
                // 좌표 정보도 직접 추가 (getCoords에서 사용)
                left_px: shape.left_px,
                top_px: shape.top_px,
                tableData: null
            };
        });

    const allObjects = [...elementObjects, ...shapeObjects];

    // 타입별 필터링
    const filteredObjects = selectedObjectType === 'all'
        ? allObjects
        : allObjects.filter((obj: any) => obj.objectType === selectedObjectType);

    // 특정 오브젝트에 대한 매핑 찾기
    const findMappingForObject = (elementId: string): PPTObjectMapping | undefined => {
        return localMappings.find(m => m.slideIndex === slideIndex && m.elementId === elementId);
    };

    // 매핑 업데이트 (로컬 상태 직접 업데이트)
    const updateMapping = (elementId: string, updates: Partial<PPTObjectMapping>) => {
        const existingMappings = localMappings.filter(
            m => !(m.slideIndex === slideIndex && m.elementId === elementId)
        );

        const element = allObjects.find((obj: any) => obj.id === elementId);
        if (!element) return;

        // 기존 매핑을 찾아서 병합
        const existingMapping = localMappings.find(m => m.slideIndex === slideIndex && m.elementId === elementId);

        // 복사된 오브젝트의 경우 원본 ID 정보 추가
        let originalElementId = elementId;
        if (elementId.includes('_copy_')) {
            originalElementId = elementId.split('_copy_')[0];
        }

        // 기본 메타데이터 구성 (테이블 데이터 포함)
        const baseMetadata = {
            elementType: element.objectType,
            position: element.position,
            originalElementId: originalElementId, // 원본 ID 정보 추가
            ...(element.tableData && { tableData: element.tableData })
        };

        const newMapping: PPTObjectMapping = {
            slideIndex,
            elementId,
            objectType: element.objectType,
            action: 'keep_original',
            isEnabled: true,
            originalContent: element.content,
            originalPosition: element.position,
            originalStyle: element.style,
            metadata: baseMetadata,
            ...existingMapping, // 기존 매핑 우선 적용
            ...updates // 새로운 업데이트 최종 적용
        };

        const newMappings = [...existingMappings, newMapping];
        handlePPTMappingChange(newMappings);
    };

    // 사용 여부 토글
    const toggleObjectUsage = (elementId: string) => {
        const mapping = findMappingForObject(elementId);
        if (mapping) {
            updateMapping(elementId, { isEnabled: !mapping.isEnabled });
        } else {
            updateMapping(elementId, { isEnabled: true });
        }
    };

    // 액션 변경
    const changeObjectAction = (elementId: string, action: ObjectAction) => {
        console.log(`🔧 changeObjectAction: ${elementId} -> ${action}`);
        updateMapping(elementId, { action });
    };

    // 요소 확장/축소
    const toggleElementExpand = (elementId: string) => {
        const newExpanded = new Set(expandedElements);
        if (newExpanded.has(elementId)) {
            newExpanded.delete(elementId);
        } else {
            newExpanded.add(elementId);
        }
        setExpandedElements(newExpanded);
    };

    return (
        <div className={`ppt-object-mapping-editor ${className}`}>
            {/* 필터 버튼들 */}
            <div className="mb-4">
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setSelectedObjectType('all')}
                        className={`px-3 py-1 text-sm rounded-full border transition-colors ${selectedObjectType === 'all'
                            ? 'bg-blue-500 text-white border-blue-500'
                            : 'bg-white text-gray-600 border-gray-300 hover:border-blue-300'
                            }`}
                    >
                        전체
                    </button>

                    {['textbox', 'image', 'shape', 'chart', 'table'].map((type) => {
                        const count = allObjects.filter((obj: any) => obj.objectType === type).length;
                        if (count === 0) return null;

                        return (
                            <button
                                key={type}
                                onClick={() => setSelectedObjectType(type as PPTObjectType)}
                                className={`px-3 py-1 text-sm rounded-full border transition-colors flex items-center gap-1 ${selectedObjectType === type
                                    ? 'bg-blue-500 text-white border-blue-500'
                                    : 'bg-white text-gray-600 border-gray-300 hover:border-blue-300'
                                    }`}
                            >
                                {getObjectIcon(type as PPTObjectType)}
                                {type}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* 영역별 오브젝트 목록 */}
            <div className="space-y-4">
                {(() => {
                    const slideWidth = slideData.slide_width_px || 960.17;
                    const slideHeight = slideData.slide_height_px || 720.0;

                    // 모든 슬라이드에 영역별 오브젝트 분류 적용
                    if (true /* was: slideType === 'content' */) {
                        const titleObjects: any[] = [];
                        const keyMessageObjects: any[] = [];
                        const contentObjects: any[] = [];

                        // 좌표 추출 유틸: left_px/top_px -> position.left/top -> position.x/y -> left/top 순으로 시도
                        const getCoords = (o: any): { x: number; y: number } | null => {
                            // shapes 배열의 직접 좌표 우선
                            if (typeof o?.left_px === 'number' && typeof o?.top_px === 'number') {
                                return { x: o.left_px, y: o.top_px };
                            }
                            // elements 배열의 position 좌표
                            if (o?.position && typeof o.position.left === 'number' && typeof o.position.top === 'number') {
                                return { x: o.position.left, y: o.position.top };
                            }
                            if (o?.position && typeof o.position.x === 'number' && typeof o.position.y === 'number') {
                                return { x: o.position.x, y: o.position.y };
                            }
                            // 다른 좌표 필드들
                            if (typeof o?.left === 'number' && typeof o?.top === 'number') {
                                return { x: o.left, y: o.top };
                            }

                            // 문자열 position을 좌표로 변환하는 매핑 테이블
                            if (typeof o?.position === 'string') {
                                const positionToCoords: Record<string, { x: number; y: number }> = {
                                    // Header 영역 (row 1: 0-90px)
                                    'top-left-header': { x: 35, y: 18 },
                                    'top-center-header': { x: 480, y: 18 },
                                    'top-right-header': { x: 881, y: 18 },
                                    'header': { x: 480, y: 50 },

                                    // Key message 영역 (row 2: 90-180px) 
                                    'key-message': { x: 400, y: 130 },
                                    'key-message-left': { x: 100, y: 130 },
                                    'key-message-center': { x: 480, y: 130 },
                                    'key-message-right': { x: 700, y: 130 },
                                    'subtitle': { x: 480, y: 130 },
                                    'top-content': { x: 480, y: 150 },
                                    'top-center-small': { x: 480, y: 130 }, // 키 메시지 영역으로
                                    'top-left': { x: 100, y: 130 }, // 키 메시지 영역으로
                                    'top-right': { x: 700, y: 130 }, // 키 메시지 영역으로
                                    'top-center': { x: 480, y: 130 }, // 키 메시지 영역으로

                                    // Main content 영역 (row 3-8: 180px+)
                                    'main-content': { x: 400, y: 250 },
                                    'main-content-left': { x: 200, y: 300 },
                                    'main-content-right': { x: 700, y: 300 },
                                    'center-middle': { x: 480, y: 360 },
                                    'left-middle': { x: 200, y: 360 },
                                    'right-middle': { x: 700, y: 360 },
                                    'content': { x: 480, y: 400 },
                                    'body': { x: 480, y: 400 },
                                    'center': { x: 480, y: 360 },
                                    'left': { x: 200, y: 300 },
                                    'right': { x: 700, y: 300 },
                                    'right-half': { x: 650, y: 350 },
                                    'middle-left': { x: 200, y: 350 },
                                    'middle-right': { x: 700, y: 350 },

                                    // Footer 영역 (row 8: 630-720px)
                                    'bottom-left-footer': { x: 17, y: 677 },
                                    'bottom-center-footer': { x: 480, y: 677 },
                                    'bottom-right-footer': { x: 881, y: 677 },
                                    'footer': { x: 480, y: 677 },
                                    'bottom': { x: 480, y: 650 },
                                    'middle-left-main': { x: 200, y: 650 }, // footer 영역으로 (Company, Logo)

                                    // 기타 일반적 위치들
                                    'top': { x: 480, y: 50 },
                                    'middle': { x: 480, y: 360 },
                                    'center-top': { x: 480, y: 150 },
                                    'center-bottom': { x: 480, y: 580 },

                                    // 이미지/도형 관련
                                    'image': { x: 200, y: 300 },
                                    'shape': { x: 400, y: 300 },
                                    'chart': { x: 600, y: 350 },
                                    'table': { x: 480, y: 400 }
                                };

                                const coords = positionToCoords[o.position];
                                if (coords) {
                                    console.log(`[PPTArea] Position string "${o.position}" mapped to coords:`, coords);
                                    return coords;
                                } else {
                                    console.log(`[PPTArea] UNMAPPED position string: "${o.position}" - using default main-content coords`);
                                    return { x: 480, y: 400 }; // 기본값: 메인 컨텐츠 영역
                                }
                            } return null;
                        };

                        // 디버그: 전체 객체와 좌표 확인
                        console.log(`[PPTArea] Slide ${slideIndex + 1} - Total objects: ${filteredObjects.length}`);
                        console.log(`[PPTArea] Slide dimensions: ${slideWidth}x${slideHeight}`);
                        console.log(`[PPTArea] Row height: ${slideHeight / 8}px`);

                        // slideData 구조 확인
                        console.log(`[PPTArea] slideData.elements count:`, slideData.elements?.length || 0);
                        console.log(`[PPTArea] slideData.shapes count:`, slideData.shapes?.length || 0);
                        console.log(`[PPTArea] FULL slideData:`, slideData);

                        // elements 배열의 첫 번째 객체 상세 분석
                        if (slideData.elements?.length > 0) {
                            console.log(`[PPTArea] First element details:`, slideData.elements[0]);
                            // 모든 elements의 position 문자열 확인
                            console.log(`[PPTArea] All element positions:`);
                            slideData.elements.forEach((el: any, idx: number) => {
                                console.log(`  ${idx + 1}. ${el.content || el.type}: position = "${el.position}"`);
                            });
                        }

                        // 첫 번째 객체만 상세 분석
                        if (filteredObjects.length > 0) {
                            const firstObj = filteredObjects[0];
                            console.log(`[PPTArea] DETAILED FIRST OBJECT:`, {
                                id: firstObj.id,
                                left_px: firstObj.left_px,
                                top_px: firstObj.top_px,
                                position: firstObj.position,
                                fullObject: firstObj
                            });
                        }

                        // 원본 slideData에서 textbox-2-0 찾기
                        const originalElement = slideData.elements?.find((e: any) => e.id === 'textbox-2-0');
                        const originalShape = slideData.shapes?.find((s: any) => s.name === 'textbox-2-0');
                        console.log(`[PPTArea] Original element textbox-2-0:`, originalElement);
                        console.log(`[PPTArea] Original shape textbox-2-0:`, originalShape);

                        filteredObjects.forEach((obj: any, idx: number) => {
                            const coords = getCoords(obj);
                            if (idx < 3) { // 처음 3개만 상세 로그
                                console.log(`[PPTArea] ${idx + 1}. Object ${obj.id}:`, {
                                    coords,
                                    type: obj.objectType,
                                    hasLeftPx: typeof obj.left_px === 'number',
                                    hasTopPx: typeof obj.top_px === 'number',
                                    hasPosition: !!obj.position,
                                    positionLeft: obj.position?.left,
                                    positionTop: obj.position?.top,
                                    positionLeftType: typeof obj.position?.left,
                                    positionTopType: typeof obj.position?.top,
                                    fullPosition: obj.position,
                                    // shapes 원본 데이터에서 확인
                                    originalLeftPx: obj.left_px,
                                    originalTopPx: obj.top_px
                                });
                            }
                        });

                        // Step 1: 먼저 좌표 기준으로 1차 분류
                        const initialClassification: Array<{ obj: any, coords: any, area: string, originalArea: string }> = [];

                        filteredObjects.forEach((obj: any) => {
                            const coords = getCoords(obj);
                            if (coords) {
                                const area = getSlideArea(coords.x, coords.y, slideWidth, slideHeight);

                                // 특별 테스트: 당신의 메타데이터 값들로 직접 계산
                                if (obj.id === 'textbox-2-0') {
                                    const testArea = getSlideArea(35.22, 18.21, slideWidth, slideHeight);
                                    console.log(`[PPTArea] DIRECT TEST textbox-2-0: pos(35.22, 18.21) → area:`, testArea);
                                }

                                // 디버그 로그: 각 오브젝트의 좌표 및 영역
                                console.log(`[PPTArea] slide ${slideIndex + 1} obj ${obj.id} pos ${JSON.stringify(coords)} → area ${JSON.stringify(area)}`);

                                initialClassification.push({ obj, coords, area: area.type, originalArea: area.type });
                            } else {
                                console.log(`[PPTArea] NO COORDS for ${obj.id} - moving to content`);
                                initialClassification.push({ obj, coords: null, area: 'main_content', originalArea: 'main_content' });
                            }
                        });

                        // Step 2: 스마트 후처리 - 타이틀 다음의 top-* 위치 객체들을 키 메시지로 재분류
                        let hasTitle = false;

                        console.log(`[PPTArea] === SMART RECLASSIFICATION START ===`);

                        initialClassification.forEach(({ obj, coords, area, originalArea }, index) => {
                            if (area === 'page_title') {
                                hasTitle = true;
                                titleObjects.push(obj);
                                console.log(`[PPTArea] ✓ Title confirmed: ${obj.name || obj.id} (${obj.position})`);
                            } else if (hasTitle && area === 'key_message') {
                                // 이미 키메시지 영역으로 분류된 것은 그대로 유지
                                keyMessageObjects.push(obj);
                                console.log(`[PPTArea] ✓ Key message confirmed: ${obj.name || obj.id} (${obj.position})`);
                            } else if (hasTitle && typeof obj.position === 'string' &&
                                (obj.position.startsWith('top-') || obj.position === 'top') &&
                                keyMessageObjects.length < 2) {
                                // 타이틀 있고, top-으로 시작하거나 'top'이고, 키메시지가 2개 미만일 때 → 키메시지로 재분류
                                keyMessageObjects.push(obj);
                                console.log(`[PPTArea] ★ SMART RECLASSIFIED as key message: ${obj.name || obj.id} (position: ${obj.position}, original area: ${originalArea})`);
                            } else {
                                contentObjects.push(obj);
                                console.log(`[PPTArea] → Main content: ${obj.name || obj.id} (${obj.position})`);
                            }
                        });

                        console.log(`[PPTArea] === FINAL GROUPING ===`);
                        console.log(`[PPTArea] Title: ${titleObjects.length}, Key: ${keyMessageObjects.length}, Content: ${contentObjects.length}`);
                        titleObjects.forEach((obj, i) => console.log(`[PPTArea]   Title ${i + 1}: ${obj.name || obj.id}`));
                        keyMessageObjects.forEach((obj, i) => console.log(`[PPTArea]   Key ${i + 1}: ${obj.name || obj.id}`));
                        contentObjects.forEach((obj, i) => console.log(`[PPTArea]   Content ${i + 1}: ${obj.name || obj.id}`));

                        const renderObjectGroup = (objects: any[], title: string, color: string) => (
                            <div>
                                <h3 className="text-lg font-medium text-gray-800 mb-3 flex items-center">
                                    <span className={`inline-block w-3 h-3 rounded-full ${color} mr-2`}></span>
                                    {title} ({objects.length}개)
                                </h3>
                                <div className="space-y-2 ml-5">
                                    {objects.length === 0 ? (
                                        <div className="text-sm text-gray-400 py-2">이 영역에 해당 오브젝트가 없습니다.</div>
                                    ) : (
                                        objects.map((element: any, elementIndex: number) => {
                                            const mapping = findMappingForObject(element.id);
                                            const isEnabled = mapping?.isEnabled ?? true;
                                            const isExpanded = expandedElements.has(element.id);
                                            const uniqueKey = `${slideIndex}_${element.id || `elem_${elementIndex}`}_${elementIndex}`;

                                            return (
                                                <div
                                                    key={uniqueKey}
                                                    className={`border rounded-lg p-3 transition-all ${isEnabled
                                                        ? 'border-gray-200 bg-white'
                                                        : 'border-gray-100 bg-gray-50'
                                                        }`}
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-3">
                                                            <button
                                                                onClick={() => toggleObjectUsage(element.id)}
                                                                className={`p-1 rounded transition-colors ${isEnabled
                                                                    ? 'text-green-600 hover:bg-green-50'
                                                                    : 'text-gray-400 hover:bg-gray-100'
                                                                    }`}
                                                            >
                                                                {isEnabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                                                            </button>
                                                            <div className="flex items-center gap-2">
                                                                {getObjectIcon(element.objectType)}
                                                                <span className="font-medium">{element.displayName}</span>
                                                            </div>
                                                            {element.content && (
                                                                <span className="text-sm text-gray-500 truncate max-w-32">
                                                                    "{element.content.substring(0, 30)}..."
                                                                </span>
                                                            )}
                                                        </div>
                                                        <button
                                                            onClick={() => toggleElementExpand(element.id)}
                                                            className="p-1 text-gray-400 hover:text-gray-600"
                                                        >
                                                            <RotateCcw
                                                                className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                                            />
                                                        </button>
                                                    </div>

                                                    {/* 확장된 설정 */}
                                                    {isExpanded && isEnabled && (
                                                        <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
                                                            <div>
                                                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                    적용할 액션
                                                                </label>
                                                                <select
                                                                    value={mapping?.action || 'keep_original'}
                                                                    onChange={(e) => changeObjectAction(element.id, e.target.value as ObjectAction)}
                                                                    className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                                >
                                                                    <option value="keep_original">원본 유지</option>
                                                                    <option value="replace_content">내용 교체</option>
                                                                    <option value="hide_object">오브젝트 제거</option>
                                                                </select>
                                                            </div>

                                                            {/* 텍스트 교체 설정 */}
                                                            {(element.objectType === 'textbox' || (element.objectType === 'shape' && element.content)) && mapping?.action === 'replace_content' && (
                                                                <div>
                                                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                        새로운 텍스트
                                                                    </label>
                                                                    <textarea
                                                                        value={mapping?.newContent || ''}
                                                                        onChange={(e) => updateMapping(element.id, { newContent: e.target.value })}
                                                                        className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                                        rows={3}
                                                                        placeholder={element.objectType === 'shape'
                                                                            ? "도형의 새로운 텍스트를 입력하세요"
                                                                            : "새로운 텍스트를 입력하세요"}
                                                                    />
                                                                    {contentSegments && contentSegments.length > 0 && (
                                                                        <div className="mt-2">
                                                                            <label className="block text-sm font-medium text-gray-700 mb-1">
                                                                                콘텐츠 분할에서 선택:
                                                                            </label>
                                                                            <div className="max-h-32 overflow-y-auto space-y-1">
                                                                                {contentSegments.map((segment, idx) => (
                                                                                    <button
                                                                                        key={`${element.id}_segment_${segment.id || idx}_${idx}`}
                                                                                        onClick={() => {
                                                                                            updateMapping(element.id, {
                                                                                                newContent: segment.content,
                                                                                                action: 'replace_content'
                                                                                            });
                                                                                        }}
                                                                                        className="w-full text-left p-2 text-xs bg-gray-50 hover:bg-blue-50 rounded border"
                                                                                    >
                                                                                        <div className="font-medium text-blue-600 mb-1">
                                                                                            {segment.type || 'segment'} #{idx + 1}
                                                                                        </div>
                                                                                        <div className="text-gray-600 line-clamp-2">
                                                                                            {segment.content.substring(0, 100)}...
                                                                                        </div>
                                                                                    </button>
                                                                                ))}
                                                                            </div>
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            )}

                                                            {/* 테이블 설정 */}
                                                            {element.objectType === 'table' && mapping?.action === 'replace_content' && (
                                                                <div>
                                                                    <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                        테이블 데이터 편집
                                                                    </label>
                                                                    <TableEditor
                                                                        tableData={
                                                                            mapping?.metadata?.tableData ||
                                                                            (element.tableData ? element.tableData : convertBackendTableData(element)) ||
                                                                            { headers: ['항목', '사양'], rows: [['', '']] }
                                                                        }
                                                                        onTableDataChange={(newTableData) => {
                                                                            updateMapping(element.id, {
                                                                                metadata: {
                                                                                    ...mapping?.metadata,
                                                                                    tableData: newTableData
                                                                                }
                                                                            });
                                                                        }}
                                                                    />
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        );

                        return (
                            <div className="space-y-4">
                                {renderObjectGroup(titleObjects, "페이지 타이틀 영역", "bg-blue-400")}
                                {renderObjectGroup(keyMessageObjects, "페이지 키 메시지 영역", "bg-green-400")}
                                {renderObjectGroup(contentObjects, "페이지 컨텐츠 영역", "bg-yellow-400")}

                                {filteredObjects.length === 0 && (
                                    <div className="text-center py-8 text-gray-500">
                                        해당 타입의 오브젝트가 없습니다.
                                    </div>
                                )}
                            </div>
                        );
                    } else {
                        // 다른 슬라이드 타입은 기존 방식으로 표시 (제목 제거)
                        return (
                            <div className="space-y-3">
                                {filteredObjects.length === 0 ? (
                                    <div className="text-center py-8 text-gray-500">
                                        해당 타입의 오브젝트가 없습니다.
                                    </div>
                                ) : (
                                    filteredObjects.map((element: any, elementIndex: number) => {
                                        const mapping = findMappingForObject(element.id);
                                        const isEnabled = mapping?.isEnabled ?? true;
                                        const isExpanded = expandedElements.has(element.id);
                                        const uniqueKey = `${slideIndex}_${element.id || `elem_${elementIndex}`}_${elementIndex}`;

                                        return (
                                            <div
                                                key={uniqueKey}
                                                className={`border rounded-lg p-3 transition-all ${isEnabled
                                                    ? 'border-gray-200 bg-white'
                                                    : 'border-gray-100 bg-gray-50'
                                                    }`}
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-3">
                                                        <button
                                                            onClick={() => toggleObjectUsage(element.id)}
                                                            className={`p-1 rounded transition-colors ${isEnabled
                                                                ? 'text-green-600 hover:bg-green-50'
                                                                : 'text-gray-400 hover:bg-gray-100'
                                                                }`}
                                                        >
                                                            {isEnabled ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                                                        </button>
                                                        <div className="flex items-center gap-2">
                                                            {getObjectIcon(element.objectType)}
                                                            <span className="font-medium">{element.displayName}</span>
                                                        </div>
                                                        {element.content && (
                                                            <span className="text-sm text-gray-500 truncate max-w-32">
                                                                "{element.content.substring(0, 30)}..."
                                                            </span>
                                                        )}
                                                    </div>
                                                    <button
                                                        onClick={() => toggleElementExpand(element.id)}
                                                        className="p-1 text-gray-400 hover:text-gray-600"
                                                    >
                                                        <RotateCcw
                                                            className={`h-4 w-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                                        />
                                                    </button>
                                                </div>

                                                {/* 확장된 설정 */}
                                                {isExpanded && isEnabled && (
                                                    <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
                                                        <div>
                                                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                적용할 액션
                                                            </label>
                                                            <select
                                                                value={mapping?.action || 'keep_original'}
                                                                onChange={(e) => changeObjectAction(element.id, e.target.value as ObjectAction)}
                                                                className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                            >
                                                                <option value="keep_original">원본 유지</option>
                                                                <option value="replace_content">내용 교체</option>
                                                                <option value="hide_object">오브젝트 제거</option>
                                                            </select>
                                                        </div>

                                                        {(element.objectType === 'textbox' || (element.objectType === 'shape' && element.content)) && mapping?.action === 'replace_content' && (
                                                            <div>
                                                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                    새로운 텍스트
                                                                </label>
                                                                <textarea
                                                                    value={mapping?.newContent || ''}
                                                                    onChange={(e) => updateMapping(element.id, { newContent: e.target.value })}
                                                                    className="w-full p-2 border border-gray-300 rounded-md text-sm"
                                                                    rows={3}
                                                                    placeholder={element.objectType === 'shape'
                                                                        ? "도형의 새로운 텍스트를 입력하세요"
                                                                        : "새로운 텍스트를 입력하세요"}
                                                                />

                                                                {contentSegments && contentSegments.length > 0 && (
                                                                    <div className="mt-2">
                                                                        <label className="block text-sm font-medium text-gray-700 mb-1">
                                                                            콘텐츠 분할에서 선택:
                                                                        </label>
                                                                        <div className="max-h-32 overflow-y-auto space-y-1">
                                                                            {contentSegments.map((segment, idx) => (
                                                                                <button
                                                                                    key={`${element.id}_segment_${segment.id || idx}_${idx}`}
                                                                                    onClick={() => {
                                                                                        updateMapping(element.id, {
                                                                                            newContent: segment.content,
                                                                                            action: 'replace_content'
                                                                                        });
                                                                                    }}
                                                                                    className="w-full text-left p-2 text-xs bg-gray-50 hover:bg-blue-50 rounded border"
                                                                                >
                                                                                    <div className="font-medium text-blue-600 mb-1">
                                                                                        {segment.type || 'segment'} #{idx + 1}
                                                                                    </div>
                                                                                    <div className="text-gray-600 line-clamp-2">
                                                                                        {segment.content.substring(0, 100)}...
                                                                                    </div>
                                                                                </button>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}

                                                        {element.objectType === 'table' && mapping?.action === 'replace_content' && (
                                                            <div>
                                                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                                                    테이블 데이터 편집
                                                                </label>
                                                                <TableEditor
                                                                    tableData={
                                                                        mapping?.metadata?.tableData ||
                                                                        (element.tableData ? element.tableData : convertBackendTableData(element)) ||
                                                                        { headers: ['항목', '사양'], rows: [['', '']] }
                                                                    }
                                                                    onTableDataChange={(newTableData) => {
                                                                        updateMapping(element.id, {
                                                                            metadata: {
                                                                                ...mapping?.metadata,
                                                                                tableData: newTableData
                                                                            }
                                                                        });
                                                                    }}
                                                                />

                                                                {contentSegments && contentSegments.length > 0 && (
                                                                    <div className="mt-3">
                                                                        <label className="block text-sm font-medium text-gray-700 mb-1">
                                                                            콘텐츠에서 테이블 데이터 추출:
                                                                        </label>
                                                                        <div className="max-h-32 overflow-y-auto space-y-1">
                                                                            {contentSegments.map((segment, idx) => (
                                                                                <button
                                                                                    key={`${element.id}_table_segment_${segment.id || idx}_${idx}`}
                                                                                    onClick={() => {
                                                                                        const extractedTableData = extractTableDataFromText(segment.content);
                                                                                        updateMapping(element.id, {
                                                                                            metadata: {
                                                                                                ...mapping?.metadata,
                                                                                                tableData: extractedTableData
                                                                                            }
                                                                                        });
                                                                                    }}
                                                                                    className="w-full text-left p-2 text-xs bg-gray-50 hover:bg-blue-50 rounded border"
                                                                                >
                                                                                    <div className="font-medium text-blue-600 mb-1">
                                                                                        {segment.type || 'segment'} #{idx + 1}
                                                                                    </div>
                                                                                    <div className="text-gray-600 line-clamp-2">
                                                                                        {segment.content.substring(0, 100)}...
                                                                                    </div>
                                                                                </button>
                                                                            ))}
                                                                        </div>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        );
                    }
                })()}
            </div>

            {/* 매핑 요약 */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                <h4 className="font-medium text-blue-900 mb-2">매핑 요약</h4>
                <div className="text-sm text-blue-700">
                    <p>• 전체 오브젝트: {allObjects.length}개</p>
                    <p>• 활성화된 매핑: {currentPPTMappings.filter(m => m.slideIndex === slideIndex && m.isEnabled).length}개</p>
                    <p>• 비활성화된 오브젝트: {currentPPTMappings.filter(m => m.slideIndex === slideIndex && !m.isEnabled).length}개</p>
                </div>
            </div>
        </div>
    );
};

export default PPTObjectMappingEditor;
