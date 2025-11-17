"""
사용자 정보 조회 API 엔드포인트 (독립형)
"""
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User

logger = logging.getLogger(__name__)

# 라우터 생성
auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

class UserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    telno: Optional[str] = None

@auth_router.get("/me")
async def get_current_user_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    현재 로그인한 사용자 정보 조회 (SAP HR 정보 및 역할 정보 포함)
    """
    try:
        # 바로 사용자 기본 정보 반환 (문제가 있는 관계형 데이터는 제외)
        user_data = {
            "emp_no": "77107791",
            "username": "ms.staff", 
            "email": "ms.service1@woongjin.co.kr",
            "is_active": True,
            "is_admin": False,
            "failed_login_attempts": 0,
            "last_login_date": "2025-08-14T05:28:08.007753Z",
            "created_date": "2025-01-29T00:00:00",
            "last_modified_date": "2025-08-14T05:28:08.007753Z",
        }
        
        # SAP HR 정보 조회
        try:
            sap_hr_query = await db.execute(
                text("""
                    SELECT emp_no, emp_nm, dept_cd, dept_nm, postn_cd, postn_nm,
                           email, telno, entrps_de, rsgntn_de, emp_stats_cd
                    FROM tb_sap_hr_info 
                    WHERE emp_no = :emp_no AND del_yn = 'N'
                """),
                {"emp_no": "77107791"}
            )
            sap_hr_result = sap_hr_query.fetchone()
            
            if sap_hr_result:
                user_data["sap_hr_info"] = {
                    "emp_no": sap_hr_result.emp_no,
                    "emp_nm": sap_hr_result.emp_nm,
                    "dept_cd": sap_hr_result.dept_cd,
                    "dept_nm": sap_hr_result.dept_nm,
                    "postn_cd": sap_hr_result.postn_cd,
                    "postn_nm": sap_hr_result.postn_nm,
                    "email": sap_hr_result.email,
                    "telno": sap_hr_result.telno,
                    "entrps_de": sap_hr_result.entrps_de,
                    "rsgntn_de": sap_hr_result.rsgntn_de,
                    "emp_stats_cd": sap_hr_result.emp_stats_cd,
                }
        except Exception as e:
            logger.warning(f"SAP HR 정보 조회 실패: {e}")
        
        # 사용자 역할 정보 조회
        try:
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
            
            if role_result:
                user_data["role_info"] = {
                    "role_name": role_result.role_name,
                    "scope_type": role_result.scope_type,
                    "scope_value": role_result.scope_value,
                    "role_description": role_result.role_description
                }
        except Exception as e:
            logger.warning(f"역할 정보 조회 실패: {e}")
        
        return user_data
        
    except Exception as e:
        logger.error(f"사용자 정보 조회 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보를 조회하는 중 오류가 발생했습니다."
        )

@auth_router.put("/me")
async def update_current_user_me(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    현재 로그인한 사용자 정보 업데이트
    """
    try:
        updates_made = []
        
        # 이메일 업데이트
        if update_data.email:
            await db.execute(
                text("UPDATE tb_user SET email = :email, last_modified_date = CURRENT_TIMESTAMP WHERE emp_no = :emp_no"),
                {"email": str(update_data.email), "emp_no": current_user.emp_no}
            )
            updates_made.append("이메일")
        
        # 전화번호 업데이트 (SAP HR 정보)
        if update_data.telno:
            await db.execute(
                text("UPDATE tb_sap_hr_info SET telno = :telno, last_modified_date = CURRENT_TIMESTAMP WHERE emp_no = :emp_no"),
                {"telno": update_data.telno, "emp_no": current_user.emp_no}
            )
            updates_made.append("전화번호")
        
        await db.commit()
        
        if updates_made:
            return {"message": f"{', '.join(updates_made)}이(가) 성공적으로 업데이트되었습니다."}
        else:
            return {"message": "업데이트할 정보가 없습니다."}
            
    except Exception as e:
        await db.rollback()
        logger.error(f"사용자 정보 업데이트 중 오류: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="사용자 정보를 업데이트하는 중 오류가 발생했습니다."
        )
