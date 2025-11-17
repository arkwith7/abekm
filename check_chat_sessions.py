"""
채팅 세션 데이터 확인 스크립트
"""
import asyncio
from sqlalchemy import select, func
from backend.app.core.database import get_db, async_session_maker
from backend.app.models.chat.chat_models import TbChatSessions

async def check_sessions():
    async with async_session_maker() as db:
        # 전체 세션 수 확인
        total_count_result = await db.execute(
            select(func.count(TbChatSessions.session_id))
        )
        total_count = total_count_result.scalar()
        print(f"전체 채팅 세션 수: {total_count}")
        
        # 최근 5개 세션 조회
        query = (
            select(TbChatSessions)
            .order_by(TbChatSessions.created_date.desc())
            .limit(5)
        )
        result = await db.execute(query)
        sessions = result.scalars().all()
        
        print(f"\n최근 세션 목록:")
        for session in sessions:
            print(f"  - session_id: {session.session_id}")
            print(f"    user_emp_no: {session.user_emp_no}")
            print(f"    created_date: {session.created_date}")
            print(f"    is_active: {session.is_active}")
            print()
        
        # 특정 사용자(77107791)의 세션 조회
        user_query = (
            select(TbChatSessions)
            .where(TbChatSessions.user_emp_no == '77107791')
            .order_by(TbChatSessions.created_date.desc())
        )
        user_result = await db.execute(user_query)
        user_sessions = user_result.scalars().all()
        
        print(f"\n사용자 77107791의 세션 수: {len(user_sessions)}")
        for session in user_sessions:
            print(f"  - {session.session_id}: {session.created_date}")

if __name__ == "__main__":
    asyncio.run(check_sessions())
