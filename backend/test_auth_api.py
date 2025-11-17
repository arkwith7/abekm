"""
간단한 사용자 정보 조회 API 테스트
"""
import asyncio
from app.core.database import get_async_session_local
from sqlalchemy import text

async def test_api():
    async_session_local = get_async_session_local()
    async with async_session_local() as db:
        try:
            # 기본 사용자 정보 조회
            user_query = await db.execute(
                text("SELECT emp_no, username, email, is_active, is_admin FROM tb_user WHERE emp_no = :emp_no"),
                {"emp_no": "77107791"}
            )
            user_result = user_query.fetchone()
            print("User result:", user_result)
            
            # SAP HR 정보 조회
            sap_hr_query = await db.execute(
                text("""
                    SELECT emp_no, emp_nm, dept_cd, dept_nm, postn_cd, postn_nm,
                           email, telno, entrps_de, emp_stats_cd
                    FROM tb_sap_hr_info 
                    WHERE emp_no = :emp_no AND del_yn = 'N'
                """),
                {"emp_no": "77107791"}
            )
            sap_hr_result = sap_hr_query.fetchone()
            print("SAP HR result:", sap_hr_result)
            
            # 역할 정보 조회
            role_query = await db.execute(
                text("""
                    SELECT role_name, scope_type, scope_value, role_description
                    FROM tb_user_roles 
                    WHERE user_emp_no = :emp_no AND is_active = true
                    ORDER BY role_level ASC
                    LIMIT 1
                """),
                {"emp_no": "77107791"}
            )
            role_result = role_query.fetchone()
            print("Role result:", role_result)
            
        except Exception as e:
            print(f"오류: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
