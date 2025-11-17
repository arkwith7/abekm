#!/usr/bin/env python3
"""
WKMS 테스트 시스템 설정 및 검증 스크립트

새로 정리된 디렉토리 구조를 검증하고 초기 설정을 수행합니다.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 현재 스크립트 위치 기준으로 프로젝트 루트 설정
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
JUPYTER_DIR = SCRIPT_DIR  # jupyter_notebook 디렉토리가 현재 디렉토리


def check_directory_structure():
    """디렉토리 구조 검증"""
    
    print("🔍 디렉토리 구조 검증 중...")
    
    required_dirs = [
        "tests/rag_chat",
        "tests/document_processing", 
        "tests/hybrid_search",
        "data/ground_truth",
        "data/test_results/rag_chat",
        "data/sample_documents",
        "utils",
        "config"
    ]
    
    missing_dirs = []
    existing_dirs = []
    
    for dir_path in required_dirs:
        full_path = JUPYTER_DIR / dir_path
        if full_path.exists():
            existing_dirs.append(dir_path)
        else:
            missing_dirs.append(dir_path)
    
    print(f"✅ 존재하는 디렉토리: {len(existing_dirs)}개")
    for dir_path in existing_dirs:
        print(f"   - {dir_path}")
    
    if missing_dirs:
        print(f"❌ 누락된 디렉토리: {len(missing_dirs)}개")
        for dir_path in missing_dirs:
            print(f"   - {dir_path}")
            # 누락된 디렉토리 생성
            (JUPYTER_DIR / dir_path).mkdir(parents=True, exist_ok=True)
            print(f"   ✅ 생성 완료: {dir_path}")
        return False  # 디렉토리를 새로 생성했으므로 False 반환
    
    return True


def check_required_files():
    """필수 파일 존재 여부 확인"""
    
    print("\n📄 필수 파일 확인 중...")
    
    required_files = [
        "utils/analyze_uploads_documents.py",
        "utils/common_test_utils.py", 
        "tests/rag_chat/automated_rag_tester.py",
        "config/test_config.yaml",
        "data/ground_truth/ground_truth_criteria.csv"
    ]
    
    missing_files = []
    existing_files = []
    
    for file_path in required_files:
        full_path = JUPYTER_DIR / file_path
        if full_path.exists():
            existing_files.append(file_path)
            # 파일 크기 확인
            file_size = full_path.stat().st_size
            print(f"   ✅ {file_path} ({file_size:,} bytes)")
        else:
            missing_files.append(file_path)
            print(f"   ❌ {file_path}")
    
    if missing_files:
        print(f"\n⚠️  누락된 파일 {len(missing_files)}개를 수동으로 생성해야 합니다.")
        return False
    
    return True


def check_ground_truth_data():
    """그라운드 트루스 데이터 검증"""
    
    print("\n🎯 그라운드 트루스 데이터 검증 중...")
    
    gt_file = JUPYTER_DIR / "data/ground_truth/ground_truth_criteria.csv"
    
    if not gt_file.exists():
        print("❌ 그라운드 트루스 파일이 없습니다.")
        return False
    
    try:
        import pandas as pd
        df = pd.read_csv(gt_file)
        
        print(f"   📊 총 테스트 케이스: {len(df)}개")
        
        # 카테고리별 분포
        category_counts = df['category'].value_counts()
        print("   📈 카테고리별 분포:")
        for category, count in category_counts.items():
            print(f"      - {category}: {count}개")
        
        # 필수 컬럼 확인
        required_columns = ["question", "category", "expected_has_reference"]
        missing_columns = set(required_columns) - set(df.columns)
        
        if missing_columns:
            print(f"   ❌ 누락된 컬럼: {missing_columns}")
            return False
        
        print("   ✅ 그라운드 트루스 데이터가 유효합니다.")
        return True
        
    except Exception as e:
        print(f"   ❌ 그라운드 트루스 검증 실패: {e}")
        return False


def create_test_report():
    """시스템 상태 리포트 생성"""
    
    print("\n📋 시스템 상태 리포트 생성 중...")
    
    report = {
        "validation_date": datetime.now().isoformat(),
        "project_root": str(PROJECT_ROOT),
        "jupyter_directory": str(JUPYTER_DIR),
        "structure_validation": {
            "directories_checked": True,
            "files_checked": True,
            "ground_truth_validated": True
        },
        "statistics": {
            "total_test_cases": 0,
            "categories": {},
            "file_sizes": {}
        },
        "next_steps": [
            "RAG 채팅 테스트 실행: cd tests/rag_chat && python automated_rag_tester.py",
            "문서 분석 업데이트: cd utils && python analyze_uploads_documents.py",
            "설정 파일 커스터마이징: config/test_config.yaml 수정"
        ]
    }
    
    # 통계 정보 수집
    try:
        import pandas as pd
        gt_file = JUPYTER_DIR / "data/ground_truth/ground_truth_criteria.csv"
        if gt_file.exists():
            df = pd.read_csv(gt_file)
            report["statistics"]["total_test_cases"] = len(df)
            report["statistics"]["categories"] = df['category'].value_counts().to_dict()
    except:
        pass
    
    # 파일 크기 정보
    important_files = [
        "utils/analyze_uploads_documents.py",
        "utils/common_test_utils.py",
        "tests/rag_chat/automated_rag_tester.py",
        "data/ground_truth/ground_truth_criteria.csv"
    ]
    
    for file_path in important_files:
        full_path = JUPYTER_DIR / file_path
        if full_path.exists():
            report["statistics"]["file_sizes"][file_path] = full_path.stat().st_size
    
    # 리포트 저장
    report_file = JUPYTER_DIR / "system_validation_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"   ✅ 시스템 리포트 저장: {report_file}")
    return report


def display_usage_guide():
    """사용 가이드 출력"""
    
    print("\n🚀 WKMS 테스트 시스템 사용 가이드")
    print("=" * 50)
    
    print("\n📁 디렉토리 구조:")
    print("   jupyter_notebook/")
    print("   ├── tests/rag_chat/           # RAG 채팅 테스트")
    print("   ├── data/ground_truth/        # 그라운드 트루스 데이터")
    print("   ├── data/test_results/        # 테스트 결과")
    print("   ├── utils/                    # 공통 유틸리티")
    print("   └── config/                   # 설정 파일")
    
    print("\n🔧 주요 명령어:")
    print("   # RAG 채팅 테스트 실행")
    print("   cd jupyter_notebook/tests/rag_chat")
    print("   python automated_rag_tester.py")
    
    print("\n   # 문서 분석 및 그라운드 트루스 재생성")
    print("   cd jupyter_notebook/utils")
    print("   python analyze_uploads_documents.py")
    
    print("\n   # 시스템 상태 재검증")
    print("   cd jupyter_notebook")
    print("   python validate_system.py")
    
    print("\n📊 생성되는 결과 파일:")
    print("   - data/test_results/rag_chat/rag_test_report.json")
    print("   - data/test_results/rag_chat/rag_test_results.csv")
    print("   - data/test_results/rag_chat/rag_test_summary.md")
    
    print("\n⚙️  설정 커스터마이징:")
    print("   config/test_config.yaml 파일을 수정하여 다양한 설정 조정 가능")
    
    print("\n📈 성능 모니터링:")
    print("   - 전체 평균 점수: 0.75 이상 목표")
    print("   - 참고자료 정확도: 0.85 이상 목표")  
    print("   - 평균 응답 시간: 2.0초 이하 목표")


def main():
    """메인 실행 함수"""
    
    print("🧪 WKMS 테스트 시스템 검증 시작")
    print("=" * 50)
    
    # 1. 디렉토리 구조 검증
    dirs_ok = check_directory_structure()
    
    # 2. 필수 파일 확인
    files_ok = check_required_files()
    
    # 3. 그라운드 트루스 데이터 검증
    data_ok = check_ground_truth_data()
    
    # 4. 리포트 생성
    report = create_test_report()
    
    # 5. 결과 요약
    print("\n" + "=" * 50)
    print("📋 검증 결과 요약")
    print("=" * 50)
    
    if dirs_ok and files_ok and data_ok:
        print("✅ 모든 검증을 통과했습니다!")
        print("🎉 WKMS 테스트 시스템이 정상적으로 구성되었습니다.")
        
        # 6. 사용 가이드 출력
        display_usage_guide()
        
    else:
        print("❌ 일부 검증에 실패했습니다.")
        print("💡 위의 오류 메시지를 확인하고 누락된 파일을 생성해주세요.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())