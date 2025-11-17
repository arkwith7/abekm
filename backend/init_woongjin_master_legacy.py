"""WKMS Legacy Initialization Script

이 파일은 새로운 CSV + Alembic 기반 시스템으로 대체되었습니다.
새로운 시스템을 사용해주세요:

1. 완전 초기화: ./init_system_complete.sh
2. 시드 데이터만: python -m data.seeds.run_all_seeders
3. 개별 시더: python -m data.seeds.user_seeder

마이그레이션 가이드:
- CSV 데이터: backend/data/csv/
- 시드 스크립트: backend/data/seeds/
- 문서: backend/data/README.md
"""
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def main():
    """레거시 스크립트 실행 시 안내 메시지 출력"""
    print("=" * 80)
    print("⚠️  WKMS 초기화 시스템이 업그레이드되었습니다!")
    print("=" * 80)
    print()
    print("🔄 이 스크립트는 더 이상 사용되지 않습니다.")
    print("   새로운 CSV + Alembic 기반 시스템을 사용해주세요.")
    print()
    print("🚀 새로운 초기화 방법:")
    print("   1. 완전 초기화:")
    print("      ./init_system_complete.sh")
    print()
    print("   2. 시드 데이터만 로딩:")
    print("      python -m data.seeds.run_all_seeders")
    print()
    print("   3. 개별 데이터 시더:")
    print("      python -m data.seeds.user_seeder      # 사용자")
    print("      python -m data.seeds.hr_seeder        # HR 정보")
    print("      python -m data.seeds.system_seeder    # 시스템 데이터")
    print()
    print("📚 자세한 내용:")
    print("   backend/data/README.md")
    print()
    print("=" * 80)
    
    # 사용자가 강제로 실행하려는 경우 확인
    response = input("그래도 레거시 시스템을 실행하시겠습니까? (y/N): ")
    if response.lower() == 'y':
        print("⚠️  레거시 시스템 실행은 지원하지 않습니다.")
        print("   새로운 시스템으로 마이그레이션해주세요.")
        return 1
    
    print("✅ 새로운 초기화 시스템을 사용해주세요!")
    return 0

if __name__ == "__main__":
    sys.exit(main())