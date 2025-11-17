"""
간단한 사용자 정보 API 테스트
"""
from fastapi import APIRouter
from typing import Dict, Any

# 라우터 생성
test_auth_router = APIRouter(prefix="/api/v1/test", tags=["Test"])

@test_auth_router.get("/user")
async def get_test_user() -> Dict[str, Any]:
    """
    테스트용 사용자 정보 반환
    """
    return {
        "emp_no": "77107791",
        "username": "ms.staff",
        "email": "ms.service1@woongjin.co.kr",
        "is_active": True,
        "is_admin": False,
        "failed_login_attempts": 0,
        "last_login_date": "2025-08-14T05:28:08.007753Z",
        "created_date": "2025-01-29T00:00:00",
        "last_modified_date": "2025-08-14T05:28:08.007753Z",
        "sap_hr_info": {
            "emp_no": "77107791",
            "emp_nm": "홍길동",
            "dept_cd": "MSS100",
            "dept_nm": "MS서비스팀",
            "postn_cd": "MGR006",
            "postn_nm": "팀원",
            "email": "ms.service1@woongjin.co.kr",
            "telno": "02-1234-5684",
            "entrps_de": "20200215",
            "emp_stats_cd": "ACTIVE"
        }
    }
