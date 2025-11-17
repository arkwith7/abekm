#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import asyncio
from app.database import get_db
from sqlalchemy import text

async def check_sessions():
    async for db in get_db():
        try:
            # 세션 수 확인
            result = await db.execute(text("SELECT COUNT(*) FROM tb_chat_sessions WHERE user_emp_no = 'HR001'"))
            session_count = result.scalar()
            print(f"RDB 세션 수: {session_count}")
            
            # 메시지 수 확인
            result = await db.execute(text("SELECT COUNT(*) FROM tb_chat_history WHERE user_emp_no = 'HR001'"))
            message_count = result.scalar()
            print(f"RDB 메시지 수: {message_count}")
            
            # 세션 상세 정보
            result = await db.execute(text("""
                SELECT session_id, session_name, message_count, created_date, last_modified_date 
                FROM tb_chat_sessions 
                WHERE user_emp_no = 'HR001' 
                ORDER BY last_modified_date DESC 
                LIMIT 5
            """))
            sessions = result.fetchall()
            print(f"세션 상세 정보:")
            for session in sessions:
                print(f"  - {session.session_id}: {session.session_name} ({session.message_count}개 메시지)")
                
        except Exception as e:
            print(f"오류 발생: {e}")
        break

if __name__ == "__main__":
    asyncio.run(check_sessions())
