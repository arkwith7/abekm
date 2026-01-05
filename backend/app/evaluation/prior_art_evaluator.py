"""
선행기술 탐지 평가 프레임워크 (논문 실험용)

이 모듈은 KIPRIS 데이터셋을 사용한 선행기술 탐지 실험의 평가를 담당합니다.
Ground Truth(심사관 인용 선행기술)와 에이전트 예측을 비교하여 성능을 측정합니다.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import numpy as np
from app.evaluation.metrics import (
    calculate_recall_at_k,
    calculate_precision_at_k
)


class EvaluationResult(BaseModel):
    """단일 케이스 평가 결과"""
    patent_id: str = Field(..., description="대상 특허 출원번호")
    ground_truth: List[str] = Field(..., description="Ground Truth 선행기술 리스트")
    predictions: List[str] = Field(..., description="에이전트 예측 결과 리스트")
    recall_at_k: Dict[int, float] = Field(default_factory=dict, description="Recall@K")
    precision_at_k: Dict[int, float] = Field(default_factory=dict, description="Precision@K")
    f1_at_k: Dict[int, float] = Field(default_factory=dict, description="F1-Score@K")
    average_precision: float = Field(0.0, description="Average Precision (AP)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "patent_id": "1020047020979",
                "ground_truth": ["US20050056824 A1", "US20050167836 A1"],
                "predictions": ["US20050056824 A1", "JP2014194966 A", "..."],
                "recall_at_k": {10: 0.5, 20: 0.5, 50: 1.0, 100: 1.0},
                "precision_at_k": {10: 0.1, 20: 0.05, 50: 0.04, 100: 0.02},
                "f1_at_k": {10: 0.167, 20: 0.091, 50: 0.077, 100: 0.039},
                "average_precision": 0.75
            }
        }


class BatchEvaluationSummary(BaseModel):
    """배치 평가 요약"""
    num_cases: int = Field(..., description="평가 케이스 수")
    avg_recall: Dict[int, float] = Field(default_factory=dict, description="평균 Recall@K")
    avg_precision: Dict[int, float] = Field(default_factory=dict, description="평균 Precision@K")
    avg_f1: Dict[int, float] = Field(default_factory=dict, description="평균 F1-Score@K")
    mean_average_precision: float = Field(0.0, description="Mean Average Precision (MAP)")
    
    # 통계
    std_recall: Optional[Dict[int, float]] = Field(default_factory=dict)
    std_precision: Optional[Dict[int, float]] = Field(default_factory=dict)
    std_f1: Optional[Dict[int, float]] = Field(default_factory=dict)
    
    # 목표 달성 여부
    target_recall_100: float = Field(0.80, description="Recall@100 목표치")
    achieved_target: bool = Field(False, description="목표 달성 여부")


class PriorArtEvaluator:
    """선행기술 탐지 평가기"""
    
    def __init__(self, k_values: List[int] = [10, 20, 50, 100]):
        """
        Args:
            k_values: 평가할 K 값 리스트
        """
        self.k_values = k_values
    
    @staticmethod
    def normalize_patent_id(patent_id: str) -> str:
        """
        특허번호 정규화 (비교를 위해)
        
        Examples:
            "US 20050056824 A1" -> "US20050056824A1"
            "JP 2014-194966 A" -> "JP2014194966A"
            "1020047020979" -> "1020047020979"
        """
        # 공백, 하이픈 제거 후 대문자 변환
        return patent_id.replace(' ', '').replace('-', '').upper()
    
    def calculate_recall_at_k_normalized(
        self,
        ground_truth: List[str],
        predictions: List[str],
        k: int
    ) -> float:
        """
        특허번호 정규화 후 Recall@K 계산
        
        Args:
            ground_truth: Ground Truth 선행기술 리스트
            predictions: 에이전트 예측 결과 리스트 (순위 순)
            k: 상위 K개 고려
        
        Returns:
            Recall@K 값 (0.0 ~ 1.0)
        """
        if not ground_truth:
            return 0.0
        
        # 정규화
        gt_normalized = set(self.normalize_patent_id(p) for p in ground_truth)
        pred_normalized = set(self.normalize_patent_id(p) for p in predictions[:k])
        
        # 교집합
        hits = len(gt_normalized & pred_normalized)
        
        return hits / len(ground_truth)
    
    def calculate_precision_at_k_normalized(
        self,
        ground_truth: List[str],
        predictions: List[str],
        k: int
    ) -> float:
        """
        특허번호 정규화 후 Precision@K 계산
        
        Args:
            ground_truth: Ground Truth 선행기술 리스트
            predictions: 에이전트 예측 결과 리스트 (순위 순)
            k: 상위 K개 고려
        
        Returns:
            Precision@K 값 (0.0 ~ 1.0)
        """
        if k == 0:
            return 0.0
        
        # 정규화
        gt_normalized = set(self.normalize_patent_id(p) for p in ground_truth)
        pred_normalized = set(self.normalize_patent_id(p) for p in predictions[:k])
        
        # 교집합
        hits = len(gt_normalized & pred_normalized)
        
        return hits / k
    
    def calculate_f1_at_k(
        self,
        ground_truth: List[str],
        predictions: List[str],
        k: int
    ) -> float:
        """
        F1-Score@K 계산
        
        Args:
            ground_truth: Ground Truth 선행기술 리스트
            predictions: 에이전트 예측 결과 리스트
            k: 상위 K개 고려
        
        Returns:
            F1-Score@K 값 (0.0 ~ 1.0)
        """
        recall = self.calculate_recall_at_k_normalized(ground_truth, predictions, k)
        precision = self.calculate_precision_at_k_normalized(ground_truth, predictions, k)
        
        if recall + precision == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)
    
    def calculate_average_precision(
        self,
        ground_truth: List[str],
        predictions: List[str]
    ) -> float:
        """
        Average Precision (AP) 계산
        
        AP는 순위를 고려한 평가 지표입니다.
        상위에 Ground Truth가 많을수록 높은 점수를 받습니다.
        
        Formula:
            AP = (1 / |GT|) * Σ(Precision@k × rel(k))
            where rel(k) = 1 if k번째 결과가 GT에 포함, else 0
        
        Args:
            ground_truth: Ground Truth 선행기술 리스트
            predictions: 에이전트 예측 결과 리스트 (순위 순)
        
        Returns:
            AP 값 (0.0 ~ 1.0)
        """
        if not ground_truth:
            return 0.0
        
        gt_normalized = set(self.normalize_patent_id(p) for p in ground_truth)
        
        num_hits = 0
        sum_precisions = 0.0
        
        for k, pred in enumerate(predictions, start=1):
            pred_normalized = self.normalize_patent_id(pred)
            
            # GT에 포함되면
            if pred_normalized in gt_normalized:
                num_hits += 1
                precision_at_k = num_hits / k
                sum_precisions += precision_at_k
        
        return sum_precisions / len(ground_truth) if ground_truth else 0.0
    
    def evaluate_single_case(
        self,
        patent_id: str,
        ground_truth: List[str],
        predictions: List[str]
    ) -> EvaluationResult:
        """
        단일 케이스 평가
        
        Args:
            patent_id: 대상 특허 출원번호
            ground_truth: Ground Truth 선행기술 리스트
            predictions: 에이전트 예측 결과 리스트
        
        Returns:
            EvaluationResult 객체
        """
        recall_at_k = {}
        precision_at_k = {}
        f1_at_k = {}
        
        # 각 K 값에 대해 계산
        for k in self.k_values:
            recall_at_k[k] = self.calculate_recall_at_k_normalized(
                ground_truth, predictions, k
            )
            precision_at_k[k] = self.calculate_precision_at_k_normalized(
                ground_truth, predictions, k
            )
            f1_at_k[k] = self.calculate_f1_at_k(
                ground_truth, predictions, k
            )
        
        # Average Precision 계산
        ap = self.calculate_average_precision(ground_truth, predictions)
        
        return EvaluationResult(
            patent_id=patent_id,
            ground_truth=ground_truth,
            predictions=predictions,
            recall_at_k=recall_at_k,
            precision_at_k=precision_at_k,
            f1_at_k=f1_at_k,
            average_precision=ap
        )
    
    def evaluate_batch(
        self,
        test_cases: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        배치 평가 및 통계 계산
        
        Args:
            test_cases: 테스트 케이스 리스트
                형식: [
                    {
                        "patent_id": "1020047020979",
                        "ground_truth": ["US20050056824 A1", ...],
                        "predictions": ["...", ...]
                    },
                    ...
                ]
        
        Returns:
            {
                "summary": BatchEvaluationSummary,
                "details": List[EvaluationResult]
            }
        """
        results = []
        
        # 각 케이스 평가
        for case in test_cases:
            result = self.evaluate_single_case(
                patent_id=case['patent_id'],
                ground_truth=case['ground_truth'],
                predictions=case['predictions']
            )
            results.append(result)
        
        # 통계 계산
        summary = self._calculate_summary(results)
        
        return {
            'summary': summary,
            'details': results
        }
    
    def _calculate_summary(
        self,
        results: List[EvaluationResult]
    ) -> BatchEvaluationSummary:
        """
        배치 평가 요약 통계 계산
        
        Args:
            results: 개별 평가 결과 리스트
        
        Returns:
            BatchEvaluationSummary 객체
        """
        num_cases = len(results)
        
        # 각 메트릭별 평균 및 표준편차
        avg_recall = {}
        avg_precision = {}
        avg_f1 = {}
        std_recall = {}
        std_precision = {}
        std_f1 = {}
        
        for k in self.k_values:
            recall_values = [r.recall_at_k[k] for r in results]
            precision_values = [r.precision_at_k[k] for r in results]
            f1_values = [r.f1_at_k[k] for r in results]
            
            avg_recall[k] = float(np.mean(recall_values))
            avg_precision[k] = float(np.mean(precision_values))
            avg_f1[k] = float(np.mean(f1_values))
            
            std_recall[k] = float(np.std(recall_values))
            std_precision[k] = float(np.std(precision_values))
            std_f1[k] = float(np.std(f1_values))
        
        # MAP 계산
        ap_values = [r.average_precision for r in results]
        mean_average_precision = float(np.mean(ap_values))
        
        # 목표 달성 여부 (Recall@100 >= 80%)
        target_recall_100 = 0.80
        achieved_target = avg_recall.get(100, 0.0) >= target_recall_100
        
        return BatchEvaluationSummary(
            num_cases=num_cases,
            avg_recall=avg_recall,
            avg_precision=avg_precision,
            avg_f1=avg_f1,
            std_recall=std_recall,
            std_precision=std_precision,
            std_f1=std_f1,
            mean_average_precision=mean_average_precision,
            target_recall_100=target_recall_100,
            achieved_target=achieved_target
        )
    
    def print_summary(self, summary: BatchEvaluationSummary) -> None:
        """
        평가 요약 출력 (콘솔)
        
        Args:
            summary: BatchEvaluationSummary 객체
        """
        print("\n" + "="*70)
        print("실험 결과 요약")
        print("="*70)
        
        print(f"\n총 테스트 케이스: {summary.num_cases}건\n")
        
        print("📊 Recall@K:")
        for k in sorted(summary.avg_recall.keys()):
            v = summary.avg_recall[k]
            std = summary.std_recall.get(k, 0.0)
            print(f"  @{k:3d}: {v:.4f} ({v*100:5.2f}%) ± {std:.4f}")
        
        print("\n📊 Precision@K:")
        for k in sorted(summary.avg_precision.keys()):
            v = summary.avg_precision[k]
            std = summary.std_precision.get(k, 0.0)
            print(f"  @{k:3d}: {v:.4f} ({v*100:5.2f}%) ± {std:.4f}")
        
        print("\n📊 F1-Score@K:")
        for k in sorted(summary.avg_f1.keys()):
            v = summary.avg_f1[k]
            std = summary.std_f1.get(k, 0.0)
            print(f"  @{k:3d}: {v:.4f} ± {std:.4f}")
        
        print(f"\n📊 MAP: {summary.mean_average_precision:.4f}")
        
        # 목표 달성 여부
        print("\n" + "="*70)
        print("🎯 목표 달성 여부")
        print("="*70)
        
        recall_100 = summary.avg_recall.get(100, 0.0)
        if summary.achieved_target:
            print(f"✅ Recall@100: {recall_100*100:.2f}% ≥ {summary.target_recall_100*100:.0f}% (목표 달성!)")
        else:
            print(f"❌ Recall@100: {recall_100*100:.2f}% < {summary.target_recall_100*100:.0f}% (목표 미달성)")
        
        print("="*70 + "\n")
