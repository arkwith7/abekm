#!/usr/bin/env python3
"""
RAG 채팅 시스템 자동화 테스트 및 통계 분석 시스템
"""

import pandas as pd
import numpy as np
import json
import requests
import time
from datetime import datetime
from typing import Dict, List, Tuple, Any
import os
import asyncio
import aiohttp
from dataclasses import dataclass
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns


@dataclass
class TestResult:
    """테스트 결과를 저장하는 데이터 클래스"""
    question: str
    category: str
    api_type: str
    expected_has_reference: bool
    expected_reference_file: str
    expected_answer_type: str
    
    # 실제 결과
    actual_response: str
    actual_has_reference: bool
    actual_reference_files: List[str]
    response_time: float
    
    # 평가 결과
    reference_accuracy: bool  # 참고자료 유무 정확성
    content_relevance_score: float  # 내용 관련성 점수 (0-1)
    answer_type_correct: bool  # 답변 유형 정확성
    overall_score: float  # 종합 점수


class RAGChatTester:
    """RAG 채팅 시스템 자동화 테스터"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = f"test_session_{int(time.time())}"
        self.test_results: List[TestResult] = []
    
    async def send_chat_message(self, message: str, api_type: str = "general") -> Dict:
        """채팅 메시지 전송 및 응답 받기"""
        
        if api_type == "ppt":
            url = f"{self.base_url}/api/v1/chat/stream"
        else:
            url = f"{self.base_url}/api/v1/chat/message"
        
        payload = {
            "message": message,
            "session_id": self.session_id,
            "top_k": 10
        }
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        response_time = time.time() - start_time
                        
                        return {
                            "success": True,
                            "response": result,
                            "response_time": response_time
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"HTTP {response.status}",
                            "response_time": time.time() - start_time
                        }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response_time": time.time() - start_time
            }
    
    def extract_references_from_response(self, response_data: Dict) -> Tuple[bool, List[str]]:
        """응답에서 참고자료 정보 추출"""
        
        references = []
        has_reference = False
        
        try:
            # 응답 구조에 따라 참고자료 추출
            if "references" in response_data:
                references = response_data["references"]
                has_reference = len(references) > 0
            elif "search_results" in response_data:
                search_results = response_data["search_results"]
                if search_results and len(search_results) > 0:
                    has_reference = True
                    references = [result.get("metadata", {}).get("filename", "") 
                                for result in search_results]
            elif "message" in response_data:
                # 메시지 내용에서 참고자료 언급 확인
                message = response_data["message"]
                if "참고자료" in message or "문서" in message or "파일" in message:
                    has_reference = True
                    
        except Exception as e:
            print(f"참고자료 추출 오류: {e}")
        
        return has_reference, references
    
    def evaluate_content_relevance(self, question: str, response: str, keywords: str) -> float:
        """내용 관련성 평가 (0-1 점수)"""
        
        if not response:
            return 0.0
        
        keywords_list = [k.strip() for k in keywords.split(",") if k.strip()]
        
        # 키워드 포함 여부 확인
        response_lower = response.lower()
        keyword_matches = sum(1 for keyword in keywords_list 
                            if keyword.lower() in response_lower)
        
        keyword_score = keyword_matches / len(keywords_list) if keywords_list else 0
        
        # 응답 길이 점수 (너무 짧으면 감점)
        length_score = min(len(response.split()) / 20, 1.0)  # 20단어 이상이면 만점
        
        # "죄송합니다", "찾을 수 없습니다" 등의 부정적 응답 감점
        negative_patterns = ["죄송", "찾을 수 없", "없습니다", "모르겠", "확인할 수 없"]
        negative_penalty = sum(1 for pattern in negative_patterns 
                             if pattern in response_lower) * 0.2
        
        # 종합 점수
        relevance_score = (keyword_score * 0.6 + length_score * 0.4) - negative_penalty
        
        return max(0.0, min(1.0, relevance_score))
    
    def evaluate_answer_type(self, expected_type: str, response: str) -> bool:
        """답변 유형 정확성 평가"""
        
        response_lower = response.lower()
        
        type_patterns = {
            "확인": ["있습니다", "존재합니다", "확인", "찾았습니다"],
            "설명": ["설명", "다음과 같", "대해서", "관련하여", "특징"],
            "PPT 생성": ["ppt", "프레젠테이션", "슬라이드", "생성", "만들"],
            "자료 없음 안내": ["죄송", "찾을 수 없", "없습니다", "자료가 없"]
        }
        
        if expected_type in type_patterns:
            patterns = type_patterns[expected_type]
            return any(pattern in response_lower for pattern in patterns)
        
        return True  # 기본값
    
    async def run_single_test(self, test_case: Dict) -> TestResult:
        """단일 테스트 케이스 실행"""
        
        print(f"테스트 중: {test_case['question'][:50]}...")
        
        # API 호출
        api_result = await self.send_chat_message(
            test_case["question"], 
            test_case["api_type"]
        )
        
        if not api_result["success"]:
            # 실패한 경우
            return TestResult(
                question=test_case["question"],
                category=test_case["category"],
                api_type=test_case["api_type"],
                expected_has_reference=test_case["expected_has_reference"],
                expected_reference_file=test_case["expected_reference_file"],
                expected_answer_type=test_case["expected_answer_type"],
                actual_response=f"API 오류: {api_result['error']}",
                actual_has_reference=False,
                actual_reference_files=[],
                response_time=api_result["response_time"],
                reference_accuracy=False,
                content_relevance_score=0.0,
                answer_type_correct=False,
                overall_score=0.0
            )
        
        # 응답 분석
        response_data = api_result["response"]
        actual_response = str(response_data.get("message", ""))
        
        # 참고자료 추출
        actual_has_reference, actual_reference_files = self.extract_references_from_response(response_data)
        
        # 평가 수행
        reference_accuracy = (actual_has_reference == test_case["expected_has_reference"])
        
        content_relevance_score = self.evaluate_content_relevance(
            test_case["question"], 
            actual_response, 
            test_case["keywords"]
        )
        
        answer_type_correct = self.evaluate_answer_type(
            test_case["expected_answer_type"], 
            actual_response
        )
        
        # 종합 점수 계산
        overall_score = (
            reference_accuracy * 0.4 +           # 참고자료 정확성 40%
            content_relevance_score * 0.4 +      # 내용 관련성 40%
            answer_type_correct * 0.2             # 답변 유형 20%
        )
        
        return TestResult(
            question=test_case["question"],
            category=test_case["category"],
            api_type=test_case["api_type"],
            expected_has_reference=test_case["expected_has_reference"],
            expected_reference_file=test_case["expected_reference_file"],
            expected_answer_type=test_case["expected_answer_type"],
            actual_response=actual_response,
            actual_has_reference=actual_has_reference,
            actual_reference_files=actual_reference_files,
            response_time=api_result["response_time"],
            reference_accuracy=reference_accuracy,
            content_relevance_score=content_relevance_score,
            answer_type_correct=answer_type_correct,
            overall_score=overall_score
        )
    
    async def run_all_tests(self, ground_truth_file: str, max_tests: int = None) -> List[TestResult]:
        """모든 테스트 케이스 실행"""
        
        # 그라운드 트루스 로드
        df = pd.read_csv(ground_truth_file)
        
        if max_tests:
            df = df.head(max_tests)
        
        print(f"📊 총 {len(df)}개 테스트 케이스 실행 시작...")
        
        results = []
        
        for idx, row in df.iterrows():
            try:
                result = await self.run_single_test(row.to_dict())
                results.append(result)
                
                # 진행률 표시
                if (idx + 1) % 10 == 0:
                    print(f"진행률: {idx + 1}/{len(df)} ({(idx + 1)/len(df)*100:.1f}%)")
                
                # API 부하 방지를 위한 지연
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"테스트 {idx + 1} 실행 오류: {e}")
                continue
        
        self.test_results = results
        return results


class TestResultAnalyzer:
    """테스트 결과 분석 및 통계 생성"""
    
    def __init__(self, test_results: List[TestResult]):
        self.test_results = test_results
        self.df = self.results_to_dataframe()
    
    def results_to_dataframe(self) -> pd.DataFrame:
        """테스트 결과를 DataFrame으로 변환"""
        
        data = []
        for result in self.test_results:
            data.append({
                "question": result.question,
                "category": result.category,
                "api_type": result.api_type,
                "expected_has_reference": result.expected_has_reference,
                "actual_has_reference": result.actual_has_reference,
                "reference_accuracy": result.reference_accuracy,
                "content_relevance_score": result.content_relevance_score,
                "answer_type_correct": result.answer_type_correct,
                "overall_score": result.overall_score,
                "response_time": result.response_time,
                "actual_response": result.actual_response[:200] + "..." if len(result.actual_response) > 200 else result.actual_response
            })
        
        return pd.DataFrame(data)
    
    def calculate_statistics(self) -> Dict:
        """통계 분석 수행"""
        
        stats_result = {
            "총_테스트_수": len(self.test_results),
            "전체_평균_점수": self.df["overall_score"].mean(),
            "참고자료_정확도": self.df["reference_accuracy"].mean(),
            "내용_관련성_평균": self.df["content_relevance_score"].mean(),
            "답변_유형_정확도": self.df["answer_type_correct"].mean(),
            "평균_응답_시간": self.df["response_time"].mean(),
            
            # 카테고리별 통계
            "카테고리별_성능": {},
            "API_타입별_성능": {},
            
            # 통계적 유의성 검정
            "통계_검정_결과": {}
        }
        
        # 카테고리별 분석
        for category in self.df["category"].unique():
            category_data = self.df[self.df["category"] == category]
            stats_result["카테고리별_성능"][category] = {
                "테스트_수": len(category_data),
                "평균_점수": category_data["overall_score"].mean(),
                "참고자료_정확도": category_data["reference_accuracy"].mean(),
                "내용_관련성": category_data["content_relevance_score"].mean()
            }
        
        # API 타입별 분석
        for api_type in self.df["api_type"].unique():
            api_data = self.df[self.df["api_type"] == api_type]
            stats_result["API_타입별_성능"][api_type] = {
                "테스트_수": len(api_data),
                "평균_점수": api_data["overall_score"].mean(),
                "참고자료_정확도": api_data["reference_accuracy"].mean(),
                "내용_관련성": api_data["content_relevance_score"].mean()
            }
        
        # 통계적 유의성 검정
        if len(self.df["category"].unique()) > 1:
            # 카테고리 간 성능 차이 ANOVA 테스트
            categories = [group["overall_score"].values 
                         for name, group in self.df.groupby("category")]
            
            if len(categories) > 1 and all(len(cat) > 1 for cat in categories):
                f_stat, p_value = stats.f_oneway(*categories)
                stats_result["통계_검정_결과"]["카테고리_간_차이"] = {
                    "F_통계량": f_stat,
                    "p_값": p_value,
                    "유의미함": p_value < 0.05
                }
        
        return stats_result
    
    def generate_report(self, output_dir: str = "/home/admin/wkms-aws/jupyter_notebook/data/test_results/rag_chat") -> str:
        """종합 리포트 생성"""
        
        # 통계 분석
        stats = self.calculate_statistics()
        
        # 리포트 생성
        report = {
            "테스트_실행_정보": {
                "실행_시간": datetime.now().isoformat(),
                "총_테스트_케이스": len(self.test_results),
                "성공_케이스": sum(1 for r in self.test_results if r.overall_score > 0.6),
                "실패_케이스": sum(1 for r in self.test_results if r.overall_score <= 0.6)
            },
            "성능_지표": stats,
            "상세_결과": self.df.to_dict('records')
        }
        
        # JSON 리포트 저장
        report_file = os.path.join(output_dir, "rag_test_report.json")
        with open(report_file, "w", encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        # CSV 리포트 저장
        csv_file = os.path.join(output_dir, "rag_test_results.csv")
        self.df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        # 요약 리포트 생성
        summary_file = os.path.join(output_dir, "rag_test_summary.md")
        self.generate_markdown_summary(summary_file, stats)
        
        return report_file
    
    def generate_markdown_summary(self, file_path: str, stats: Dict):
        """마크다운 요약 리포트 생성"""
        
        with open(file_path, "w", encoding='utf-8') as f:
            f.write("# RAG 채팅 시스템 테스트 결과 리포트\n\n")
            f.write(f"**생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## 📊 전체 성능 요약\n\n")
            f.write(f"- **총 테스트 케이스**: {stats['총_테스트_수']}개\n")
            f.write(f"- **전체 평균 점수**: {stats['전체_평균_점수']:.3f}\n")
            f.write(f"- **참고자료 정확도**: {stats['참고자료_정확도']:.3f}\n")
            f.write(f"- **내용 관련성**: {stats['내용_관련성_평균']:.3f}\n")
            f.write(f"- **답변 유형 정확도**: {stats['답변_유형_정확도']:.3f}\n")
            f.write(f"- **평균 응답 시간**: {stats['평균_응답_시간']:.2f}초\n\n")
            
            f.write("## 📈 카테고리별 성능\n\n")
            for category, perf in stats['카테고리별_성능'].items():
                f.write(f"### {category}\n")
                f.write(f"- 테스트 수: {perf['테스트_수']}개\n")
                f.write(f"- 평균 점수: {perf['평균_점수']:.3f}\n")
                f.write(f"- 참고자료 정확도: {perf['참고자료_정확도']:.3f}\n")
                f.write(f"- 내용 관련성: {perf['내용_관련성']:.3f}\n\n")
            
            f.write("## 🔧 API 타입별 성능\n\n")
            for api_type, perf in stats['API_타입별_성능'].items():
                f.write(f"### {api_type.upper()}\n")
                f.write(f"- 테스트 수: {perf['테스트_수']}개\n")
                f.write(f"- 평균 점수: {perf['평균_점수']:.3f}\n")
                f.write(f"- 참고자료 정확도: {perf['참고자료_정확도']:.3f}\n")
                f.write(f"- 내용 관련성: {perf['내용_관련성']:.3f}\n\n")
            
            # 통계적 유의성
            if "통계_검정_결과" in stats and stats["통계_검정_결과"]:
                f.write("## 📐 통계적 유의성 검정\n\n")
                for test_name, result in stats["통계_검정_결과"].items():
                    f.write(f"### {test_name}\n")
                    f.write(f"- F 통계량: {result['F_통계량']:.4f}\n")
                    f.write(f"- p-값: {result['p_값']:.4f}\n")
                    f.write(f"- 유의미함: {'예' if result['유의미함'] else '아니오'}\n\n")


async def main():
    """메인 실행 함수"""
    
    print("🚀 RAG 채팅 시스템 자동화 테스트를 시작합니다...\n")
    
    # 테스터 초기화
    tester = RAGChatTester("http://localhost:8000")
    
    # 테스트 실행 (처음에는 작은 샘플로 테스트)
    ground_truth_file = "/home/admin/wkms-aws/jupyter_notebook/data/ground_truth/ground_truth_criteria.csv"
    
    if not os.path.exists(ground_truth_file):
        print(f"❌ 그라운드 트루스 파일을 찾을 수 없습니다: {ground_truth_file}")
        return
    
    # 샘플 테스트 (전체의 10% 또는 최대 20개)
    df_sample = pd.read_csv(ground_truth_file)
    sample_size = min(20, max(3, len(df_sample) // 10))
    
    print(f"📝 샘플 테스트 실행: {sample_size}개 케이스")
    
    try:
        results = await tester.run_all_tests(ground_truth_file, max_tests=sample_size)
        
        print(f"\n✅ 테스트 완료: {len(results)}개 결과")
        
        # 결과 분석
        analyzer = TestResultAnalyzer(results)
        report_file = analyzer.generate_report()
        
        print(f"📊 테스트 리포트가 생성되었습니다:")
        print(f"- JSON 리포트: {report_file}")
        print(f"- CSV 결과: /home/admin/wkms-aws/jupyter_notebook/data/test_results/rag_chat/rag_test_results.csv")
        print(f"- 요약 리포트: /home/admin/wkms-aws/jupyter_notebook/data/test_results/rag_chat/rag_test_summary.md")
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류: {e}")
        print("💡 백엔드 서버가 실행 중인지 확인해주세요 (http://localhost:8000)")


if __name__ == "__main__":
    asyncio.run(main())