"""
평가 유틸리티 - 검색 품질 메트릭 계산
"""
from typing import List, Dict, Any
import numpy as np


def calculate_ndcg_at_k(
    retrieved_docs: List[str],
    relevance_judgments: Dict[str, Dict[str, Any]],
    k: int = 10
) -> float:
    """
    nDCG@K 계산
    
    Args:
        retrieved_docs: 검색 결과 문서 ID 리스트 (순위 순서)
        relevance_judgments: {doc_id: {"score": int, "label": str}}
        k: 상위 K개
    
    Returns:
        nDCG@K 점수 (0~1)
    """
    # DCG 계산
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_docs[:k], start=1):
        relevance = relevance_judgments.get(doc_id, {}).get("score", 0)
        dcg += relevance / np.log2(i + 1)
    
    # IDCG 계산 (이상적인 순서)
    ideal_relevances = sorted(
        [j["score"] for j in relevance_judgments.values()],
        reverse=True
    )[:k]
    
    idcg = 0.0
    for i, relevance in enumerate(ideal_relevances, start=1):
        idcg += relevance / np.log2(i + 1)
    
    if idcg == 0:
        return 0.0
    
    return dcg / idcg


def calculate_recall_at_k(
    retrieved_docs: List[str],
    expected_docs: List[str],
    k: int = 10
) -> float:
    """
    Recall@K 계산
    
    Args:
        retrieved_docs: 검색 결과 문서 ID 리스트
        expected_docs: 기대 문서 ID 리스트
        k: 상위 K개
    
    Returns:
        Recall@K (0~1)
    """
    if not expected_docs:
        return 0.0
    
    retrieved_set = set(retrieved_docs[:k])
    expected_set = set(expected_docs)
    
    intersection = retrieved_set & expected_set
    return len(intersection) / len(expected_set)


def calculate_precision_at_k(
    retrieved_docs: List[str],
    expected_docs: List[str],
    k: int = 10
) -> float:
    """
    Precision@K 계산
    """
    if not retrieved_docs[:k]:
        return 0.0
    
    retrieved_set = set(retrieved_docs[:k])
    expected_set = set(expected_docs)
    
    intersection = retrieved_set & expected_set
    return len(intersection) / len(retrieved_set)


def calculate_mrr(
    retrieved_docs: List[str],
    expected_docs: List[str]
) -> float:
    """
    MRR (Mean Reciprocal Rank) 계산
    
    Returns:
        MRR 점수 (0~1)
    """
    expected_set = set(expected_docs)
    
    for i, doc_id in enumerate(retrieved_docs, start=1):
        if doc_id in expected_set:
            return 1.0 / i
    
    return 0.0


def evaluate_query(
    query_data: Dict[str, Any],
    retrieved_docs: List[str]
) -> Dict[str, float]:
    """
    단일 쿼리 평가
    
    Args:
        query_data: Golden dataset의 쿼리 항목
        retrieved_docs: 검색 시스템이 반환한 문서 ID 리스트
    
    Returns:
        메트릭 딕셔너리
    """
    expected_docs = query_data["expected_documents"]
    relevance_judgments = query_data["relevance_judgments"]
    
    return {
        "ndcg@10": calculate_ndcg_at_k(retrieved_docs, relevance_judgments, k=10),
        "recall@10": calculate_recall_at_k(retrieved_docs, expected_docs, k=10),
        "precision@10": calculate_precision_at_k(retrieved_docs, expected_docs, k=10),
        "mrr": calculate_mrr(retrieved_docs, expected_docs)
    }


def aggregate_metrics(
    query_metrics: List[Dict[str, float]]
) -> Dict[str, float]:
    """
    여러 쿼리의 메트릭 집계
    
    Returns:
        평균 메트릭
    """
    if not query_metrics:
        return {}
    
    metric_names = query_metrics[0].keys()
    aggregated = {}
    
    for metric_name in metric_names:
        values = [qm[metric_name] for qm in query_metrics]
        aggregated[f"avg_{metric_name}"] = np.mean(values)
        aggregated[f"std_{metric_name}"] = np.std(values)
    
    return aggregated
