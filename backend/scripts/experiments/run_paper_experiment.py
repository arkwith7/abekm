"""
논문 실험 실행 스크립트

KIPRIS 데이터셋(100건 샘플)을 사용하여 선행기술 탐지 실험을 수행합니다.

사용법:
    python -m backend.scripts.experiments.run_paper_experiment
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.app.evaluation.prior_art_evaluator import PriorArtEvaluator


def load_sample_dataset(file_path: str) -> List[Dict[str, Any]]:
    """
    실험용 샘플 데이터셋 로드
    
    Args:
        file_path: JSONL 파일 경로
    
    Returns:
        테스트 케이스 리스트
    """
    test_cases = []
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            
            # 데이터 형식 변환
            # paper_eval_sample.jsonl 형식:
            # {"target": {...}, "ground_truth": [...], "dataset_source_path": "..."}
            
            test_case = {
                'patent_id': data['target']['application_number'],
                'title': data['target']['title'],
                'abstract': data['target'].get('abstract', ''),
                'ipc': data['target'].get('ipc', ''),
                'ground_truth': data['ground_truth'],
                # predictions는 나중에 에이전트 실행 후 추가
                'predictions': []
            }
            
            test_cases.append(test_case)
    
    return test_cases


async def run_prior_art_search_mock(
    patent_data: Dict[str, Any],
    top_k: int = 100
) -> List[str]:
    """
    선행기술 검색 실행 (Mock 버전)
    
    실제 에이전트 구현이 완료되면 이 함수를 대체해야 합니다.
    현재는 Ground Truth의 일부 + 랜덤 결과를 반환합니다.
    
    Args:
        patent_data: 특허 데이터
        top_k: 상위 K개 결과
    
    Returns:
        예측 결과 리스트 (특허번호)
    """
    # TODO: 실제 에이전트 호출로 대체
    # from backend.app.agents.prior_art_agent import PriorArtAgent
    # agent = PriorArtAgent()
    # results = await agent.search_prior_art(...)
    
    print(f"  [MOCK] {patent_data['patent_id']} 검색 중...")
    
    # Mock 구현: Ground Truth의 50% + 더미 결과
    ground_truth = patent_data.get('ground_truth', [])
    
    # Ground Truth 중 50% 포함 (Mock 성능: Recall@100 ≈ 50%)
    predictions = ground_truth[:len(ground_truth)//2]
    
    # 더미 결과로 100개 채우기
    dummy_results = [
        f"US2005{str(i).zfill(7)} A1" for i in range(top_k - len(predictions))
    ]
    
    predictions.extend(dummy_results)
    
    await asyncio.sleep(0.1)  # 네트워크 지연 시뮬레이션
    
    return predictions[:top_k]


async def run_experiment_batch(
    test_cases: List[Dict[str, Any]],
    top_k: int = 100
) -> List[Dict[str, Any]]:
    """
    배치 실험 실행
    
    Args:
        test_cases: 테스트 케이스 리스트
        top_k: 상위 K개 결과
    
    Returns:
        예측 결과가 포함된 테스트 케이스 리스트
    """
    results = []
    
    print(f"\n🚀 실험 시작: {len(test_cases)}건")
    print("="*70)
    
    for i, case in enumerate(test_cases, start=1):
        print(f"\n[{i}/{len(test_cases)}] {case['patent_id']}")
        print(f"  제목: {case['title'][:60]}...")
        print(f"  Ground Truth: {len(case['ground_truth'])}건")
        
        # 선행기술 검색 실행
        predictions = await run_prior_art_search_mock(case, top_k=top_k)
        
        # 결과 저장
        result = {
            'patent_id': case['patent_id'],
            'ground_truth': case['ground_truth'],
            'predictions': predictions
        }
        
        results.append(result)
        
        print(f"  Predictions: {len(predictions)}건")
    
    print("\n" + "="*70)
    print("✅ 실험 완료!")
    
    return results


def save_results(
    results: List[Dict[str, Any]],
    summary: Any,
    output_dir: Path
) -> None:
    """
    실험 결과 저장
    
    Args:
        results: 개별 평가 결과
        summary: 평가 요약
        output_dir: 출력 디렉토리
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 타임스탬프
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 전체 결과 (상세)
    results_file = output_dir / f"experiment_results_{timestamp}.json"
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'timestamp': timestamp,
                'num_cases': len(results),
                'k_values': [10, 20, 50, 100]
            },
            'summary': summary.dict(),
            'details': [r.dict() for r in results]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 결과 저장: {results_file}")
    
    # 2. 요약 결과 (간결)
    summary_file = output_dir / f"experiment_summary_{timestamp}.json"
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary.dict(), f, ensure_ascii=False, indent=2)
    
    print(f"💾 요약 저장: {summary_file}")
    
    # 3. 최신 결과 링크 (latest)
    latest_file = output_dir / "experiment_results_latest.json"
    
    with open(latest_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'timestamp': timestamp,
                'num_cases': len(results),
                'k_values': [10, 20, 50, 100]
            },
            'summary': summary.dict(),
            'details': [r.dict() for r in results]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"💾 최신 결과: {latest_file}")


async def main():
    """메인 실험 실행 함수"""
    
    print("\n" + "="*70)
    print("📄 논문 실험: 선행기술 탐지 성능 평가")
    print("="*70)
    
    # 1. 데이터 로드
    data_path = Path("/home/arkwith/Dev/abekm/backend/data/processed/fulltext/paper_eval_sample.jsonl")
    
    if not data_path.exists():
        print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_path}")
        return
    
    print(f"\n📂 데이터 로드: {data_path}")
    test_cases = load_sample_dataset(str(data_path))
    print(f"✅ {len(test_cases)}건 로드 완료")
    
    # 통계 출력
    total_gt = sum(len(case['ground_truth']) for case in test_cases)
    avg_gt = total_gt / len(test_cases) if test_cases else 0
    
    print(f"\n📊 데이터셋 통계:")
    print(f"  - 테스트 케이스: {len(test_cases)}건")
    print(f"  - 총 Ground Truth: {total_gt}건")
    print(f"  - 평균 Ground Truth: {avg_gt:.2f}건/케이스")
    
    # 2. 실험 실행
    results = await run_experiment_batch(test_cases, top_k=100)
    
    # 3. 평가
    print("\n" + "="*70)
    print("📊 평가 중...")
    print("="*70)
    
    evaluator = PriorArtEvaluator(k_values=[10, 20, 50, 100])
    evaluation = evaluator.evaluate_batch(results)
    
    summary = evaluation['summary']
    details = evaluation['details']
    
    # 4. 결과 출력
    evaluator.print_summary(summary)
    
    # 5. 결과 저장
    output_dir = Path("/home/arkwith/Dev/abekm/backend/results/paper_experiment")
    save_results(details, summary, output_dir)
    
    print("\n✅ 실험 완료!\n")


if __name__ == "__main__":
    asyncio.run(main())
