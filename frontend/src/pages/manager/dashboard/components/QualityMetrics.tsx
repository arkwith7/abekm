import { AlertTriangle, ArrowRight, BarChart3 } from 'lucide-react';
import React from 'react';
import { Link } from 'react-router-dom';
import { QualityMetric } from '../../../../types/manager.types';

interface QualityMetricsProps {
    metrics: QualityMetric[];
}

export const QualityMetrics: React.FC<QualityMetricsProps> = ({ metrics }) => {
    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
                <h3 className="text-lg font-medium text-gray-900">문서 품질 현황</h3>
                <Link
                    to="/manager/analytics"
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center"
                >
                    상세 분석
                    <ArrowRight className="w-4 h-4 ml-1" />
                </Link>
            </div>
            <div className="p-6">
                {metrics.length === 0 ? (
                    <div className="text-center py-4">
                        <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-2" />
                        <p className="text-gray-500">품질 데이터가 없습니다.</p>
                    </div>
                ) : (
                    <div className="space-y-4">
                        {metrics.map((metric) => (
                            <div key={metric.document_id} className="flex items-center justify-between">
                                <div className="flex-1">
                                    <h4 className="font-medium text-gray-900 truncate">{metric.document_title}</h4>
                                    <div className="flex items-center space-x-4 mt-1">
                                        <span className="text-sm text-gray-500">
                                            평점: {metric.average_rating.toFixed(1)}
                                        </span>
                                        <span className="text-sm text-gray-500">
                                            조회: {metric.view_count}
                                        </span>
                                        <span className="text-sm text-gray-500">
                                            품질: {metric.quality_score.toFixed(1)}
                                        </span>
                                    </div>
                                </div>
                                {metric.issues.length > 0 && (
                                    <AlertTriangle className="w-5 h-5 text-yellow-500" />
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};
