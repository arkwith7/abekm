"""
사용자 관리 서비스
JWT 인증 및 SAP 인사 정보 동기화 포함
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_, func, select
from fastapi import HTTPException, status

from app.models import User, TbSapHrInfo
from app.schemas.user_schemas import (
    UserCreate, UserUpdate, UserPasswordChange, UserSearchParams,
    SapHrInfoCreate, SapHrInfoUpdate, UserListResponse,
    SapSyncRequest, SapSyncResponse
)
from app.core.security import AuthUtils, SecurityUtils, PasswordPolicy

class UserService:
    """사용자 관리 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """사용자 ID로 사용자 조회"""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """사용자명으로 사용자 조회"""
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_emp_no(self, emp_no: str) -> Optional[User]:
        """사번으로 사용자 조회"""
        query = select(User).where(User.emp_no == emp_no)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_document_by_id(self, document_id: str, user_id: int) -> Optional[dict]:
        """문서 ID로 문서 조회 (AsyncSession 버전)"""
        print(f"=== get_document_by_id 시작 ===")
        print(f"document_id: {document_id}, user_id: {user_id}")
        
        try:
            from app.models import TbFileBssInfo, TbFileDtlInfo
            from sqlalchemy.orm import outerjoin
            from sqlalchemy import select, and_
            import os
            
            # 문서 ID를 숫자로 변환
            try:
                file_bss_info_sno = int(document_id)
                print(f"변환된 file_bss_info_sno: {file_bss_info_sno}")
            except ValueError:
                print(f"document_id 변환 실패: {document_id}")
                return None
            
            # 파일 기본 정보와 상세 정보 JOIN하여 조회
            query = select(TbFileBssInfo, TbFileDtlInfo).select_from(
                outerjoin(TbFileBssInfo, TbFileDtlInfo, 
                         TbFileBssInfo.file_dtl_info_sno == TbFileDtlInfo.file_dtl_info_sno)
            ).where(TbFileBssInfo.file_bss_info_sno == file_bss_info_sno)
            
            print(f"SQL 쿼리 실행 중...")
            result = await self.db.execute(query)
            row = result.first()
            
            if not row:
                print(f"데이터베이스에서 문서를 찾을 수 없음: {file_bss_info_sno}")
                return None
            
            file_bss_info, file_dtl_info = row
            print(f"데이터베이스 조회 결과:")
            print(f"  - file_bss_info.path: {file_bss_info.path}")
            print(f"  - file_bss_info.file_psl_nm: {file_bss_info.file_psl_nm}")
            print(f"  - file_bss_info.file_lgc_nm: {file_bss_info.file_lgc_nm}")
            print(f"  - file_bss_info.file_extsn: {file_bss_info.file_extsn}")
            if file_dtl_info:
                print(f"  - file_dtl_info.sj: {file_dtl_info.sj}")
                print(f"  - file_dtl_info.file_sz: {file_dtl_info.file_sz}")
            else:
                print(f"  - file_dtl_info: None")
            
            # 권한 확인 로직 구현
            print(f"권한 확인 중...")
            print(f"  - user_id: {user_id}")
            print(f"  - knowledge_container_id: {file_bss_info.knowledge_container_id}")
            print(f"  - owner_emp_no: {file_bss_info.owner_emp_no}")
            
            # 사용자 정보 조회
            from app.models import User
            user_query = select(User).where(User.id == user_id)
            user_result = await self.db.execute(user_query)
            user = user_result.scalars().first()
            
            if not user:
                print(f"❌ 사용자를 찾을 수 없음: {user_id}")
                return None
            
            print(f"  - user.emp_no: {user.emp_no}")
            print(f"  - user.is_admin: {user.is_admin}")
            
            # 권한 확인
            has_permission = False
            
            # 1. 시스템 관리자는 모든 파일 접근 가능
            if user.is_admin:
                print(f"  ✅ 시스템 관리자 권한으로 접근 허용")
                has_permission = True
            
            # 2. 파일 소유자는 접근 가능
            elif user.emp_no == file_bss_info.owner_emp_no:
                print(f"  ✅ 파일 소유자로 접근 허용")
                has_permission = True
            
            # 3. 컨테이너 권한 확인
            elif file_bss_info.knowledge_container_id:
                from app.models import TbUserPermissions
                perm_query = select(TbUserPermissions).where(
                    and_(
                        TbUserPermissions.user_emp_no == user.emp_no,
                        TbUserPermissions.container_id == file_bss_info.knowledge_container_id,
                        TbUserPermissions.is_active == True
                    )
                )
                perm_result = await self.db.execute(perm_query)
                permission = perm_result.scalars().first()
                
                if permission:
                    print(f"  ✅ 컨테이너 권한으로 접근 허용: {permission.role_id}")
                    has_permission = True
                else:
                    print(f"  ❌ 컨테이너 권한 없음")
            
            # 4. 개발 모드에서는 HR001 사용자에게 모든 파일 접근 허용
            if not has_permission and user.emp_no == "HR001":
                print(f"  ✅ 개발 모드: HR001 사용자 특별 권한으로 접근 허용")
                has_permission = True
            
            if not has_permission:
                print(f"❌ 권한 확인 실패 - 접근 거부")
                return None
            
            print(f"✅ 권한 확인 완료")
            
            # 파일 경로 구성 분석
            if not file_bss_info:
                print("file_bss_info가 없음")
                return None
                
            if not file_bss_info.path:
                print("file_bss_info.path가 없음")
                return None
            
            # 경로 분석 - path가 이미 전체 경로인지 확인
            base_path = file_bss_info.path
            physical_filename = file_bss_info.file_psl_nm
            
            print(f"경로 분석:")
            print(f"  - base_path: {base_path}")
            print(f"  - physical_filename: {physical_filename}")
            
            # path가 이미 물리 파일명을 포함하는지 확인
            if physical_filename and physical_filename in base_path:
                # path가 이미 전체 경로인 경우
                file_path = base_path
                print(f"  - path가 이미 전체 경로를 포함: {file_path}")
            elif physical_filename:
                # path와 물리 파일명을 결합
                file_path = os.path.join(base_path, physical_filename)
                print(f"  - path와 filename 결합: {file_path}")
            else:
                print("  - physical_filename이 없음")
                return None
            
            # 절대 경로로 변환 (백엔드 기준)
            if not os.path.isabs(file_path):
                backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # backend 디렉토리
                absolute_path = os.path.join(backend_dir, file_path)
                print(f"  - 상대경로를 절대경로로 변환: {file_path} -> {absolute_path}")
                file_path = absolute_path
            
            # 파일 존재 여부 확인
            print(f"파일 존재 여부 확인: {file_path}")
            if os.path.exists(file_path):
                print(f"  ✅ 파일 존재함")
            else:
                print(f"  ❌ 파일 존재하지 않음")
                # 가능한 대안 경로들 확인
                alternative_paths = [
                    base_path,  # path만 사용
                    os.path.join("uploads", physical_filename) if physical_filename else None,  # uploads/filename
                    os.path.join(backend_dir, "uploads", physical_filename) if physical_filename else None,  # 절대경로 uploads/filename
                ]
                
                print(f"대안 경로들 확인:")
                for alt_path in alternative_paths:
                    if alt_path and os.path.exists(alt_path):
                        print(f"  ✅ 대안 경로 발견: {alt_path}")
                        file_path = alt_path
                        break
                    elif alt_path:
                        print(f"  ❌ 대안 경로 없음: {alt_path}")
            
            result_data = {
                'id': str(file_bss_info.file_bss_info_sno),
                'title': file_dtl_info.sj if file_dtl_info and file_dtl_info.sj else file_bss_info.file_lgc_nm,
                'file_name': file_bss_info.file_lgc_nm,  # 논리 파일명
                'file_path': file_path,
                'file_size': file_dtl_info.file_sz if file_dtl_info else None,
                'file_extension': file_bss_info.file_extsn,
                'created_at': file_bss_info.created_date,
                'updated_at': file_bss_info.last_modified_date
            }
            
            print(f"최종 반환 데이터:")
            print(f"  - id: {result_data['id']}")
            print(f"  - title: {result_data['title']}")
            print(f"  - file_name: {result_data['file_name']}")
            print(f"  - file_path: {result_data['file_path']}")
            print(f"  - file_extension: {result_data['file_extension']}")
            print(f"=== get_document_by_id 완료 ===")
            
            return result_data
            
        except Exception as e:
            print(f"❌ get_document_by_id 오류: {e}")
            import traceback
            print(f"상세 오류:")
            traceback.print_exc()
            return None
    
    async def increment_download_count(self, document_id: str) -> bool:
        """다운로드 수 증가 (AsyncSession 버전)"""
        try:
            from app.models import TbFileBssInfo
            from sqlalchemy import update, func
            
            file_bss_info_sno = int(document_id)
            
            stmt = update(TbFileBssInfo).where(
                TbFileBssInfo.file_bss_info_sno == file_bss_info_sno
            ).values(
                access_count=TbFileBssInfo.access_count + 1,  # 실제 컬럼명 사용
                last_modified_date=func.now()  # 실제 컬럼명 사용
            )
            
            await self.db.execute(stmt)
            await self.db.commit()
            return True
            
        except Exception as e:
            print(f"Error incrementing download count: {e}")
            return False
    
    async def create_user(self, user_data: UserCreate, created_by: Optional[str] = None) -> User:
        """새 사용자 생성"""
        # 중복 검증
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 사용자명입니다"
            )
        
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 이메일입니다"
            )
        
        existing_emp_no = await self.get_user_by_emp_no(user_data.emp_no)
        if existing_emp_no:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 사번입니다"
            )
        
        # SAP 인사 정보 확인
        sap_query = select(TbSapHrInfo).where(TbSapHrInfo.EMP_NO == user_data.emp_no)
        sap_result = await self.db.execute(sap_query)
        sap_hr_info = sap_result.scalar_one_or_none()
        
        if not sap_hr_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SAP 인사 정보에 해당 사번이 존재하지 않습니다"
            )
        
        # 비밀번호 정책 검증
        is_valid, errors = PasswordPolicy.validate_password(user_data.password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=". ".join(errors)
            )
        
        # 사용자 생성
        db_user = User(
            username=user_data.username,
            email=user_data.email,
            emp_no=user_data.emp_no,
            password_hash=AuthUtils.get_password_hash(user_data.password),
            is_admin=user_data.is_admin,
            password_changed_at=datetime.now(timezone.utc),
            created_by=created_by
        )
        
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        
        return db_user

# 추가 서비스 클래스들은 별도 파일로 분리 예정
