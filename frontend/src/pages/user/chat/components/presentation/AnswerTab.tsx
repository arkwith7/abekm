import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface AnswerTabProps {
    sourceContent?: string;
}

const AnswerTab: React.FC<AnswerTabProps> = ({ sourceContent }) => {
    const formattedAnswer = sourceContent
        ?.replace(/\\n\\n/g, '\n\n')  // \\n\\n을 실제 줄바꿈으로 변환
        ?.replace(/\\n/g, '\n')      // \\n을 실제 줄바꿈으로 변환
        ?.replace(/\n{3,}/g, '\n\n'); // 3개 이상의 연속된 줄바꿈을 2개로 제한

    return (
        <div className="prose prose-sm max-w-none dark:prose-invert text-left">
            {formattedAnswer ? (
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        code({ node, inline, className, children, ...props }) {
                            return !inline ? (
                                <pre className="bg-gray-900 text-gray-100 rounded-lg p-3 overflow-auto text-xs">
                                    <code className={className}>{children}</code>
                                </pre>
                            ) : (
                                <code className="bg-gray-100 px-1.5 py-0.5 rounded text-[0.75rem] font-mono" {...props}>
                                    {children}
                                </code>
                            );
                        },
                        h1: ({ children }) => (
                            <h1 className="text-lg font-bold mb-3 text-gray-800 border-b border-gray-200 pb-2">
                                {children}
                            </h1>
                        ),
                        h2: ({ children }) => (
                            <h2 className="text-base font-semibold mb-2 text-gray-800">
                                {children}
                            </h2>
                        ),
                        h3: ({ children }) => (
                            <h3 className="text-sm font-medium mb-2 text-gray-700">
                                {children}
                            </h3>
                        ),
                        p: ({ children }) => (
                            <p className="text-xs leading-relaxed mb-3 text-gray-700">
                                {children}
                            </p>
                        ),
                        ul: ({ children }) => (
                            <ul className="text-xs space-y-1 mb-3 ml-4 list-disc text-gray-700">
                                {children}
                            </ul>
                        ),
                        ol: ({ children }) => (
                            <ol className="text-xs space-y-1 mb-3 ml-4 list-decimal text-gray-700">
                                {children}
                            </ol>
                        ),
                        li: ({ children }) => (
                            <li className="text-xs leading-relaxed">
                                {children}
                            </li>
                        ),
                        blockquote: ({ children }) => (
                            <blockquote className="border-l-4 border-gray-300 pl-3 italic text-xs text-gray-600 my-3">
                                {children}
                            </blockquote>
                        ),
                        table: ({ children }) => (
                            <div className="overflow-x-auto mb-3">
                                <table className="min-w-full text-xs border border-gray-200">
                                    {children}
                                </table>
                            </div>
                        ),
                        thead: ({ children }) => (
                            <thead className="bg-gray-50">
                                {children}
                            </thead>
                        ),
                        th: ({ children }) => (
                            <th className="px-2 py-1 text-left font-medium text-gray-700 border-b border-gray-200">
                                {children}
                            </th>
                        ),
                        td: ({ children }) => (
                            <td className="px-2 py-1 text-gray-600 border-b border-gray-100">
                                {children}
                            </td>
                        ),
                    }}
                >
                    {formattedAnswer}
                </ReactMarkdown>
            ) : (
                <div className="text-xs text-gray-500 italic">
                    원본 AI 답변 내용이 없습니다.
                </div>
            )}
        </div>
    );
};

export default AnswerTab;
