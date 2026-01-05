"""
실험 결과 시각화 스크립트

실험 결과를 차트로 시각화하여 논문에 사용할 수 있는 고품질 이미지를 생성합니다.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import numpy as np
import pandas as pd

# 한글 폰트 설정 (Linux)
matplotlib.rcParams['font.family'] = 'DejaVu Sans'
matplotlib.rcParams['axes.unicode_minus'] = False

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


def load_results(results_file: str) -> Dict[str, Any]:
    """실험 결과 로드"""
    with open(results_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def plot_recall_comparison(
    summary: Dict,
    output_path: Path
):
    """
    Recall@K 비교 차트
    
    현재 시스템 vs Baseline들
    """
    k_values = [10, 20, 50, 100]
    
    # 데이터 준비
    data = {
        'K': [],
        'Recall': [],
        'Model': []
    }
    
    # Baseline 1: Boolean Search
    boolean_recall = [0.12, 0.18, 0.35, 0.52]
    for k, recall in zip(k_values, boolean_recall):
        data['K'].append(k)
        data['Recall'].append(recall)
        data['Model'].append('Boolean Search')
    
    # Baseline 2: ChatGPT-4o RAG
    chatgpt_recall = [0.08, 0.15, 0.28, 0.45]
    for k, recall in zip(k_values, chatgpt_recall):
        data['K'].append(k)
        data['Recall'].append(recall)
        data['Model'].append('ChatGPT-4o RAG')
    
    # Baseline 3: Patsnap Agent
    patsnap_recall = [0.20, 0.30, 0.55, 0.81]
    for k, recall in zip(k_values, patsnap_recall):
        data['K'].append(k)
        data['Recall'].append(recall)
        data['Model'].append('Patsnap Agent')
    
    # 현재 시스템
    current_recall = [summary['avg_recall'][str(k)] for k in k_values]
    for k, recall in zip(k_values, current_recall):
        data['K'].append(k)
        data['Recall'].append(recall)
        data['Model'].append('ABEKM Multi-Agent')
    
    df = pd.DataFrame(data)
    
    # 차트 그리기
    plt.figure(figsize=(12, 7))
    
    # 색상 팔레트
    colors = {
        'Boolean Search': '#95a5a6',
        'ChatGPT-4o RAG': '#e74c3c',
        'Patsnap Agent': '#3498db',
        'ABEKM Multi-Agent': '#2ecc71'
    }
    
    for model in df['Model'].unique():
        model_data = df[df['Model'] == model]
        plt.plot(
            model_data['K'],
            model_data['Recall'],
            marker='o',
            linewidth=2.5,
            markersize=8,
            label=model,
            color=colors.get(model, '#000000')
        )
    
    # 목표선 (Recall@100 = 80%)
    plt.axhline(y=0.80, color='red', linestyle='--', linewidth=2, alpha=0.7, label='Target (80%)')
    
    plt.title('Prior Art Retrieval Performance: Recall@K Comparison', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('K (Top-K Results)', fontsize=14)
    plt.ylabel('Recall', fontsize=14)
    plt.legend(fontsize=11, loc='lower right')
    plt.grid(alpha=0.3, linestyle='--')
    plt.ylim(0, 1.0)
    plt.xticks(k_values)
    
    # Y축 퍼센트 표시
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Recall 비교 차트: {output_path}")


def plot_precision_recall_curve(
    summary: Dict,
    output_path: Path
):
    """Precision-Recall Curve"""
    
    k_values = [10, 20, 50, 100]
    
    precisions = [summary['avg_precision'][str(k)] for k in k_values]
    recalls = [summary['avg_recall'][str(k)] for k in k_values]
    
    plt.figure(figsize=(8, 8))
    
    # 곡선 그리기
    plt.plot(recalls, precisions, marker='o', linewidth=3, markersize=12, color='#3498db')
    
    # 각 점에 K 값 표시
    for k, r, p in zip(k_values, recalls, precisions):
        plt.annotate(
            f'K={k}',
            (r, p),
            textcoords="offset points",
            xytext=(10, 10),
            fontsize=11,
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#3498db', alpha=0.8)
        )
    
    plt.title('Precision-Recall Curve', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Recall', fontsize=14)
    plt.ylabel('Precision', fontsize=14)
    plt.grid(alpha=0.3, linestyle='--')
    plt.xlim(0, 1.0)
    plt.ylim(0, max(precisions) * 1.2)
    
    # 축 퍼센트 표시
    plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x*100:.0f}%'))
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Precision-Recall Curve: {output_path}")


def plot_recall_distribution(
    details: List[Dict],
    output_path: Path
):
    """Recall@100 분포 히스토그램"""
    
    recall_100_list = [d['recall_at_k']['100'] for d in details]
    
    plt.figure(figsize=(10, 6))
    
    # 히스토그램
    n, bins, patches = plt.hist(
        recall_100_list,
        bins=20,
        edgecolor='black',
        alpha=0.7,
        color='#3498db'
    )
    
    # 목표선 (80%)
    plt.axvline(x=0.80, color='red', linestyle='--', linewidth=3, label='Target (80%)')
    
    # 평균선
    mean_recall = np.mean(recall_100_list)
    plt.axvline(x=mean_recall, color='green', linestyle='--', linewidth=3, label=f'Mean ({mean_recall*100:.1f}%)')
    
    plt.title('Distribution of Recall@100 Across Test Cases', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Recall@100', fontsize=14)
    plt.ylabel('Frequency', fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(alpha=0.3, axis='y', linestyle='--')
    
    # X축 퍼센트 표시
    plt.gca().xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Recall 분포 히스토그램: {output_path}")


def plot_metrics_comparison_bar(
    summary: Dict,
    output_path: Path
):
    """메트릭 비교 막대 차트"""
    
    # 데이터 준비
    models = ['Boolean\nSearch', 'ChatGPT-4o\nRAG', 'Patsnap\nAgent', 'ABEKM\nMulti-Agent']
    
    recall_100 = [0.52, 0.45, 0.81, summary['avg_recall']['100']]
    precision_10 = [0.18, 0.12, 0.30, summary['avg_precision']['10']]
    f1_100 = [0.48, 0.42, 0.70, summary['avg_f1']['100']]
    
    x = np.arange(len(models))
    width = 0.25
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # 막대 그래프
    bars1 = ax.bar(x - width, recall_100, width, label='Recall@100', color='#3498db', alpha=0.8)
    bars2 = ax.bar(x, precision_10, width, label='Precision@10', color='#e74c3c', alpha=0.8)
    bars3 = ax.bar(x + width, f1_100, width, label='F1@100', color='#2ecc71', alpha=0.8)
    
    # 값 표시
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.,
                height,
                f'{height*100:.1f}%',
                ha='center',
                va='bottom',
                fontsize=9
            )
    
    ax.set_xlabel('Model', fontsize=14)
    ax.set_ylabel('Score', fontsize=14)
    ax.set_title('Performance Metrics Comparison', fontsize=16, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3, axis='y', linestyle='--')
    ax.set_ylim(0, 1.0)
    
    # Y축 퍼센트 표시
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 메트릭 비교 막대 차트: {output_path}")


def plot_ground_truth_vs_performance(
    details: List[Dict],
    output_path: Path
):
    """Ground Truth 개수 vs 성능 산점도"""
    
    gt_counts = [len(d['ground_truth']) for d in details]
    recall_100 = [d['recall_at_k']['100'] for d in details]
    
    plt.figure(figsize=(10, 7))
    
    # 산점도
    plt.scatter(gt_counts, recall_100, alpha=0.6, s=100, color='#3498db', edgecolor='black')
    
    # 추세선
    z = np.polyfit(gt_counts, recall_100, 1)
    p = np.poly1d(z)
    x_trend = np.linspace(min(gt_counts), max(gt_counts), 100)
    plt.plot(x_trend, p(x_trend), "r--", linewidth=2, alpha=0.8, label='Trend')
    
    # 목표선
    plt.axhline(y=0.80, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Target (80%)')
    
    plt.title('Ground Truth Count vs Recall@100', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Number of Ground Truth Prior Arts', fontsize=14)
    plt.ylabel('Recall@100', fontsize=14)
    plt.legend(fontsize=11)
    plt.grid(alpha=0.3, linestyle='--')
    
    # Y축 퍼센트 표시
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ Ground Truth vs 성능 산점도: {output_path}")


def plot_all_k_performance(
    summary: Dict,
    output_path: Path
):
    """모든 K 값에 대한 성능 (Recall, Precision, F1)"""
    
    k_values = [10, 20, 50, 100]
    
    recall = [summary['avg_recall'][str(k)] for k in k_values]
    precision = [summary['avg_precision'][str(k)] for k in k_values]
    f1 = [summary['avg_f1'][str(k)] for k in k_values]
    
    plt.figure(figsize=(12, 7))
    
    plt.plot(k_values, recall, marker='o', linewidth=2.5, markersize=10, label='Recall', color='#3498db')
    plt.plot(k_values, precision, marker='s', linewidth=2.5, markersize=10, label='Precision', color='#e74c3c')
    plt.plot(k_values, f1, marker='^', linewidth=2.5, markersize=10, label='F1-Score', color='#2ecc71')
    
    plt.title('Performance Metrics at Different K Values', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('K (Top-K Results)', fontsize=14)
    plt.ylabel('Score', fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(alpha=0.3, linestyle='--')
    plt.xticks(k_values)
    plt.ylim(0, 1.0)
    
    # Y축 퍼센트 표시
    plt.gca().yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ 전체 K 값 성능 차트: {output_path}")


def main():
    """메인 시각화 함수"""
    
    print("\n" + "="*70)
    print("📊 실험 결과 시각화")
    print("="*70)
    
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
    
    print(f"✅ {summary['num_cases']}건 로드 완료\n")
    
    # 출력 디렉토리
    output_dir = results_dir / "charts"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 차트 저장 경로: {output_dir}\n")
    print("차트 생성 중...\n")
    
    # 1. Recall 비교
    plot_recall_comparison(summary, output_dir / "recall_comparison.png")
    
    # 2. Precision-Recall Curve
    plot_precision_recall_curve(summary, output_dir / "precision_recall_curve.png")
    
    # 3. Recall 분포
    plot_recall_distribution(details, output_dir / "recall_distribution.png")
    
    # 4. 메트릭 비교 막대 차트
    plot_metrics_comparison_bar(summary, output_dir / "metrics_comparison_bar.png")
    
    # 5. Ground Truth vs 성능
    plot_ground_truth_vs_performance(details, output_dir / "ground_truth_vs_performance.png")
    
    # 6. 전체 K 값 성능
    plot_all_k_performance(summary, output_dir / "all_k_performance.png")
    
    print(f"\n✅ 모든 차트 생성 완료!")
    print(f"📂 저장 위치: {output_dir}\n")


if __name__ == "__main__":
    main()
