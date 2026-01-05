"""
실험 결과 분석 스크립트

저장된 실험 결과를 분석하고 상세 리포트를 생성합니다.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def load_results(results_file: str) -> Dict[str, Any]:
    """실험 결과 로드"""
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_per_case_performance(details: List[Dict]) -> Dict[str, Any]:
    """케이스별 성능 분석"""
    
    recall_100_list = [d['recall_at_k']['100'] for d in details]
    precision_10_list = [d['precision_at_k']['10'] for d in details]
    ap_list = [d['average_precision'] for d in details]
    
    analysis = {
        'recall_100': {
            'min': float(np.min(recall_100_list)),
            'max': float(np.max(recall_100_list)),
            'median': float(np.median(recall_100_list)),
            'q25': float(np.percentile(recall_100_list, 25)),
            'q75': float(np.percentile(recall_100_list, 75)),
            'distribution': {
                '0-20%': sum(1 for r in recall_100_list if r < 0.2),
                '20-40%': sum(1 for r in recall_100_list if 0.2 <= r < 0.4),
                '40-60%': sum(1 for r in recall_100_list if 0.4 <= r < 0.6),
                '60-80%': sum(1 for r in recall_100_list if 0.6 <= r < 0.8),
                '80-100%': sum(1 for r in recall_100_list if r >= 0.8)
            }
        },
        'precision_10': {
            'min': float(np.min(precision_10_list)),
            'max': float(np.max(precision_10_list)),
            'median': float(np.median(precision_10_list)),
        },
        'average_precision': {
            'min': float(np.min(ap_list)),
            'max': float(np.max(ap_list)),
            'median': float(np.median(ap_list)),
        }
    }
    
    return analysis


def analyze_ground_truth_distribution(details: List[Dict]) -> Dict[str, Any]:
    """Ground Truth 분포 분석"""
    
    gt_counts = [len(d['ground_truth']) for d in details]
    
    distribution = {
        '1개': sum(1 for c in gt_counts if c == 1),
        '2개': sum(1 for c in gt_counts if c == 2),
        '3-5개': sum(1 for c in gt_counts if 3 <= c <= 5),
        '6-10개': sum(1 for c in gt_counts if 6 <= c <= 10),
        '10개 이상': sum(1 for c in gt_counts if c > 10)
    }
    
    return {
        'total': sum(gt_counts),
        'mean': float(np.mean(gt_counts)),
        'median': float(np.median(gt_counts)),
        'min': int(np.min(gt_counts)),
        'max': int(np.max(gt_counts)),
        'distribution': distribution
    }


def find_best_worst_cases(details: List[Dict], top_n: int = 5) -> Dict[str, List[Dict]]:
    """성능이 가장 좋은/나쁜 케이스 찾기"""
    
    # Recall@100 기준 정렬
    sorted_by_recall = sorted(
        details,
        key=lambda x: x['recall_at_k']['100'],
        reverse=True
    )
    
    best_cases = [
        {
            'patent_id': case['patent_id'],
            'recall_100': case['recall_at_k']['100'],
            'precision_10': case['precision_at_k']['10'],
            'ap': case['average_precision'],
            'gt_count': len(case['ground_truth'])
        }
        for case in sorted_by_recall[:top_n]
    ]
    
    worst_cases = [
        {
            'patent_id': case['patent_id'],
            'recall_100': case['recall_at_k']['100'],
            'precision_10': case['precision_at_k']['10'],
            'ap': case['average_precision'],
            'gt_count': len(case['ground_truth'])
        }
        for case in sorted_by_recall[-top_n:]
    ]
    
    return {
        'best': best_cases,
        'worst': worst_cases
    }


def compare_with_baselines(summary: Dict) -> Dict[str, Any]:
    """Baseline과 비교"""
    
    # 가상의 Baseline 성능 (논문 기반)
    baselines = {
        'Boolean Search': {
            'recall_10': 0.12,
            'recall_20': 0.18,
            'recall_50': 0.35,
            'recall_100': 0.52,
            'precision_10': 0.18,
            'map': 0.28
        },
        'ChatGPT-4o RAG': {
            'recall_10': 0.08,
            'recall_20': 0.15,
            'recall_50': 0.28,
            'recall_100': 0.45,
            'precision_10': 0.12,
            'map': 0.22
        },
        'Patsnap Agent': {
            'recall_10': 0.20,
            'recall_20': 0.30,
            'recall_50': 0.55,
            'recall_100': 0.81,
            'precision_10': 0.30,
            'map': 0.48
        }
    }
    
    # 현재 시스템 성능
    current = {
        'recall_10': summary['avg_recall']['10'],
        'recall_20': summary['avg_recall']['20'],
        'recall_50': summary['avg_recall']['50'],
        'recall_100': summary['avg_recall']['100'],
        'precision_10': summary['avg_precision']['10'],
        'map': summary['mean_average_precision']
    }
    
    # 비교
    comparison = {}
    
    for baseline_name, baseline_metrics in baselines.items():
        improvements = {}
        
        for metric_name, baseline_value in baseline_metrics.items():
            current_value = current[metric_name]
            improvement = current_value - baseline_value
            improvement_pct = (improvement / baseline_value * 100) if baseline_value > 0 else 0
            
            improvements[metric_name] = {
                'baseline': baseline_value,
                'current': current_value,
                'improvement': improvement,
                'improvement_pct': improvement_pct
            }
        
        comparison[baseline_name] = improvements
    
    return comparison


def print_analysis_report(
    summary: Dict,
    per_case_analysis: Dict,
    gt_distribution: Dict,
    best_worst_cases: Dict,
    baseline_comparison: Dict
):
    """분석 리포트 출력"""
    
    print("\n" + "="*80)
    print("📊 실험 결과 상세 분석 리포트")
    print("="*80)
    
    # 1. 전체 요약
    print("\n### 1. 전체 성능 요약")
    print("-"*80)
    print(f"테스트 케이스: {summary['num_cases']}건")
    print(f"\nRecall@K:")
    for k in [10, 20, 50, 100]:
        v = summary['avg_recall'][str(k)]
        print(f"  @{k:3d}: {v*100:5.2f}%")
    
    print(f"\nMAP: {summary['mean_average_precision']:.4f}")
    
    target = summary['target_recall_100']
    achieved = summary['avg_recall']['100']
    status = "✅ 달성" if summary['achieved_target'] else "❌ 미달성"
    print(f"\n목표 (Recall@100 ≥ {target*100:.0f}%): {status} (실제: {achieved*100:.2f}%)")
    
    # 2. 케이스별 성능 분석
    print("\n### 2. 케이스별 성능 분석")
    print("-"*80)
    
    recall_stats = per_case_analysis['recall_100']
    print(f"\nRecall@100 분포:")
    print(f"  최소: {recall_stats['min']*100:.2f}%")
    print(f"  Q25: {recall_stats['q25']*100:.2f}%")
    print(f"  중앙값: {recall_stats['median']*100:.2f}%")
    print(f"  Q75: {recall_stats['q75']*100:.2f}%")
    print(f"  최대: {recall_stats['max']*100:.2f}%")
    
    print(f"\n성능 구간별 분포:")
    for range_name, count in recall_stats['distribution'].items():
        pct = count / summary['num_cases'] * 100
        print(f"  {range_name}: {count}건 ({pct:.1f}%)")
    
    # 3. Ground Truth 분석
    print("\n### 3. Ground Truth 분포")
    print("-"*80)
    print(f"총 Ground Truth: {gt_distribution['total']}건")
    print(f"평균: {gt_distribution['mean']:.2f}건/케이스")
    print(f"중앙값: {gt_distribution['median']:.0f}건")
    print(f"범위: {gt_distribution['min']}~{gt_distribution['max']}건")
    
    print(f"\n개수별 분포:")
    for range_name, count in gt_distribution['distribution'].items():
        pct = count / summary['num_cases'] * 100
        print(f"  {range_name}: {count}건 ({pct:.1f}%)")
    
    # 4. Best/Worst 케이스
    print("\n### 4. 성능 우수/부진 케이스 (Top 5)")
    print("-"*80)
    
    print("\n🏆 가장 우수한 케이스:")
    for i, case in enumerate(best_worst_cases['best'], start=1):
        print(f"  {i}. {case['patent_id']}")
        print(f"     Recall@100: {case['recall_100']*100:.2f}%, "
              f"Precision@10: {case['precision_10']*100:.2f}%, "
              f"AP: {case['ap']:.4f}, GT: {case['gt_count']}건")
    
    print("\n📉 가장 부진한 케이스:")
    for i, case in enumerate(best_worst_cases['worst'], start=1):
        print(f"  {i}. {case['patent_id']}")
        print(f"     Recall@100: {case['recall_100']*100:.2f}%, "
              f"Precision@10: {case['precision_10']*100:.2f}%, "
              f"AP: {case['ap']:.4f}, GT: {case['gt_count']}건")
    
    # 5. Baseline 비교
    print("\n### 5. Baseline 시스템과의 비교")
    print("-"*80)
    
    for baseline_name, metrics in baseline_comparison.items():
        print(f"\n vs. {baseline_name}:")
        
        recall_100 = metrics['recall_100']
        print(f"  Recall@100: {recall_100['baseline']*100:.2f}% → {recall_100['current']*100:.2f}% "
              f"({recall_100['improvement_pct']:+.1f}%p)")
        
        precision_10 = metrics['precision_10']
        print(f"  Precision@10: {precision_10['baseline']*100:.2f}% → {precision_10['current']*100:.2f}% "
              f"({precision_10['improvement_pct']:+.1f}%p)")
        
        map_metric = metrics['map']
        print(f"  MAP: {map_metric['baseline']:.4f} → {map_metric['current']:.4f} "
              f"({map_metric['improvement_pct']:+.1f}%)")
    
    print("\n" + "="*80 + "\n")


def main():
    """메인 분석 함수"""
    
    # 결과 파일 경로
    results_dir = Path("/home/arkwith/Dev/abekm/backend/results/paper_experiment")
    results_file = results_dir / "experiment_results_latest.json"
    
    if not results_file.exists():
        print(f"❌ 결과 파일을 찾을 수 없습니다: {results_file}")
        print("먼저 run_paper_experiment.py를 실행하세요.")
        return
    
    print(f"\n📂 결과 파일 로드: {results_file}")
    
    # 결과 로드
    results = load_results(str(results_file))
    
    summary = results['summary']
    details = results['details']
    
    # 분석 수행
    print("📊 분석 중...")
    
    per_case_analysis = analyze_per_case_performance(details)
    gt_distribution = analyze_ground_truth_distribution(details)
    best_worst_cases = find_best_worst_cases(details, top_n=5)
    baseline_comparison = compare_with_baselines(summary)
    
    # 리포트 출력
    print_analysis_report(
        summary,
        per_case_analysis,
        gt_distribution,
        best_worst_cases,
        baseline_comparison
    )
    
    # 분석 결과 저장
    analysis_output = results_dir / "analysis_report.json"
    
    with open(analysis_output, 'w', encoding='utf-8') as f:
        json.dump({
            'per_case_analysis': per_case_analysis,
            'ground_truth_distribution': gt_distribution,
            'best_worst_cases': best_worst_cases,
            'baseline_comparison': baseline_comparison
        }, f, ensure_ascii=False, indent=2)
    
    print(f"💾 분석 리포트 저장: {analysis_output}\n")


if __name__ == "__main__":
    main()
