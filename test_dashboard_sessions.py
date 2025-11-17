#!/usr/bin/env python3
"""
대시보드 세션 카운트 테스트 스크립트
백엔드 가상환경과 앱 경로를 고려한 테스트
"""
import sys
import os

# 백엔드 앱 경로 추가
sys.path.insert(0, '/home/admin/wkms-aws/backend')

import asyncio
from sqlalchemy import text, select, func
from app.core.database import get_db
from app.models.chat.chat_models import TbChatSessions

async def test_session_count():
    """세션 카운트 테스트"""
    print("=" * 60)
    print("🧪 대시보드 세션 카운트 테스트")
    print("=" * 60)
    
    async for db in get_db():
        try:
            # 1. 전체 세션 수 (Raw SQL)
            print("\n[1] Raw SQL - 전체 세션 수")
            result = await db.execute(text("SELECT COUNT(*) FROM tb_chat_sessions"))
            total = result.scalar()
            print(f"   📊 전체 세션: {total}개")
            
            # 2. ORM으로 전체 세션 수
            print("\n[2] ORM - 전체 세션 수")
            result = await db.execute(
                select(func.count(TbChatSessions.session_id))
            )
            orm_total = result.scalar() or 0
            print(f"   📊 ORM 전체 세션: {orm_total}개")
            
            # 3. 사용자별 세션 수 (Raw SQL)
            print("\n[3] Raw SQL - 사용자별 세션 수")
            result = await db.execute(text("""
                SELECT user_emp_no, COUNT(*) as session_count
                FROM tb_chat_sessions
                GROUP BY user_emp_no
                ORDER BY session_count DESC
            """))
            user_sessions = result.all()
            if user_sessions:
                for row in user_sessions:
                    print(f"   👤 사용자 {row.user_emp_no}: {row.session_count}개")
            else:
                print("   ⚠️ 사용자별 세션 없음")
            
            # 4. 특정 사용자 세션 수 (문자열 비교)
            test_user = "77107791"
            print(f"\n[4] 특정 사용자({test_user}) 세션 수 - 문자열 비교")
            result = await db.execute(
                select(func.count(TbChatSessions.session_id))
                .where(TbChatSessions.user_emp_no == test_user)
            )
            user_count = result.scalar() or 0
            print(f"   📊 사용자 {test_user}: {user_count}개")
            
            # 5. 특정 사용자 세션 수 (정수 비교 - 실패 예상)
            print(f"\n[5] 특정 사용자({test_user}) 세션 수 - 정수 비교 (실패 예상)")
            try:
                result = await db.execute(
                    select(func.count(TbChatSessions.session_id))
                    .where(TbChatSessions.user_emp_no == 77107791)  # 정수로 비교
                )
                user_count_int = result.scalar() or 0
                print(f"   📊 사용자 77107791(정수): {user_count_int}개")
            except Exception as e:
                print(f"   ❌ 에러 발생 (예상됨): {type(e).__name__}")
                print(f"   💡 메시지: {str(e)[:100]}")
            
            # 6. 최근 세션 3개 상세
            print("\n[6] 최근 세션 3개 상세")
            result = await db.execute(text("""
                SELECT session_id, user_emp_no, title, created_date
                FROM tb_chat_sessions
                ORDER BY created_date DESC
                LIMIT 3
            """))
            recent = result.all()
            if recent:
                for idx, row in enumerate(recent, 1):
                    print(f"\n   [{idx}] 세션 ID: {row.session_id}")
                    print(f"       사용자: {row.user_emp_no}")
                    print(f"       제목: {row.title}")
                    print(f"       생성: {row.created_date}")
            else:
                print("   ⚠️ 최근 세션 없음")
            
            # 7. 데이터 타입 확인
            print("\n[7] user_emp_no 컬럼 데이터 타입 확인")
            result = await db.execute(text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_name = 'tb_chat_sessions' AND column_name = 'user_emp_no'
            """))
            col_info = result.first()
            if col_info:
                print(f"   📋 컬럼명: {col_info.column_name}")
                print(f"   📋 데이터 타입: {col_info.data_type}")
                print(f"   📋 최대 길이: {col_info.character_maximum_length}")
            
            print("\n" + "=" * 60)
            print("✅ 테스트 완료")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ 전체 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
        finally:
            break

if __name__ == "__main__":
    asyncio.run(test_session_count())
