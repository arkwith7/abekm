import { AlertCircle } from 'lucide-react';
import React from 'react';

interface ErrorAlertProps {
    message: string;
    onClose: () => void;
}

export const ErrorAlert: React.FC<ErrorAlertProps> = ({ message, onClose }) => {
    return (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
                <h3 className="text-sm font-medium text-red-800">오류가 발생했습니다</h3>
                <p className="mt-1 text-sm text-red-700">{message}</p>
            </div>
            <button
                onClick={onClose}
                className="text-red-600 hover:text-red-800 text-lg font-bold"
            >
                ✕
            </button>
        </div>
    );
};
