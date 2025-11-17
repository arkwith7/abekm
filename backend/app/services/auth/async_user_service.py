"""
비동기 사용자 관리 서비스
JWT 인증 및 SAP 인사 정보 동기화 포함
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, func, select, update
from fastapi import HTTPException, status

from app.models import User, TbSapHrInfo
from app.schemas.user_schemas import (
    UserCreate, UserUpdate, UserPasswordChange, UserSearchParams,
    SapHrInfoCreate, SapHrInfoUpdate, UserListResponse,
    SapSyncRequest, SapSyncResponse
)
from app.core.security import AuthUtils, SecurityUtils, PasswordPolicy

class AsyncUserService:
    """비동기 사용자 관리 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_id(self, user_id: int, options: Optional[List] = None) -> Optional[User]:
        """사용자 ID로 사용자 조회"""
        query = select(User).where(User.id == user_id)
        if options:
            query = query.options(*options)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_username(self, username: str, options: Optional[List] = None) -> Optional[User]:
        """사용자명으로 사용자 조회"""
        query = select(User).where(User.username == username)
        if options:
            query = query.options(*options)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_user_by_emp_no(self, emp_no: str, options: Optional[List] = None) -> Optional[User]:
        """사번으로 사용자 조회"""
        query = select(User).where(User.emp_no == emp_no)
        if options:
            query = query.options(*options)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_sap_hr_info_by_emp_no(self, emp_no: str) -> Optional[TbSapHrInfo]:
        """사번으로 SAP HR 정보 조회"""
        query = select(TbSapHrInfo).where(TbSapHrInfo.emp_no == emp_no)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate, created_by: Optional[str] = None) -> User:
        """새 사용자 생성 (SAP 정보가 없으면 자동 생성)"""
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
        
        # SAP 인사 정보 확인 및 자동 생성
        sap_query = select(TbSapHrInfo).where(TbSapHrInfo.emp_no == user_data.emp_no)
        sap_result = await self.db.execute(sap_query)
        sap_hr_info = sap_result.scalar_one_or_none()
        
        if not sap_hr_info:
            # SAP 인사 정보가 없으면 기본값으로 생성
            sap_hr_info = TbSapHrInfo(
                emp_no=user_data.emp_no,
                emp_nm=user_data.username,  # 사용자명을 이름으로 사용
                dept_cd="DEPT999",  # 기본 부서 코드
                dept_nm="미배정",  # 기본 부서명
                postn_cd="POS999",  # 기본 직급 코드
                postn_nm="사원",  # 기본 직급명
                email=user_data.email,
                telno="",  # 전화번호 없음
                mbtlno="",  # 휴대폰 없음
                entrps_de=datetime.now(timezone.utc).strftime("%Y%m%d"),  # 입사일: 오늘
                rsgntn_de=None,  # 퇴사일 없음
                emp_stats_cd="ACTIVE",  # 재직 상태
                del_yn="N",  # 삭제 안됨
                created_by=created_by or "SYSTEM",
                created_date=datetime.now(timezone.utc),
                last_modified_by=created_by or "SYSTEM",
                last_modified_date=datetime.now(timezone.utc)
            )
            self.db.add(sap_hr_info)
            await self.db.flush()  # SAP 정보 먼저 저장
        
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
            created_date=datetime.now(timezone.utc),
            last_modified_date=datetime.now(timezone.utc)
        )
        
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        
        return db_user
    
    async def update_user(self, user_id: int, user_data: UserUpdate, updated_by: Optional[str] = None) -> User:
        """사용자 정보 수정"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        # 중복 검증
        if user_data.username and user_data.username != db_user.username:
            existing_user = await self.get_user_by_username(user_data.username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 존재하는 사용자명입니다"
                )
        
        if user_data.email and user_data.email != db_user.email:
            existing_email = await self.get_user_by_email(user_data.email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 존재하는 이메일입니다"
                )
        
        # 업데이트 수행
        update_data = user_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)
        
        db_user.last_modified_by = updated_by
        db_user.last_modified_date = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(db_user)
        
        return db_user
    
    async def change_password(self, user_id: int, password_data: UserPasswordChange, updated_by: Optional[str] = None) -> bool:
        """비밀번호 변경"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        # 현재 비밀번호 검증
        if not AuthUtils.verify_password(password_data.current_password, db_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호가 올바르지 않습니다"
            )
        
        # 새 비밀번호 정책 검증
        is_valid, errors = PasswordPolicy.validate_password(password_data.new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=". ".join(errors)
            )
        
        # 비밀번호 업데이트
        db_user.password_hash = AuthUtils.get_password_hash(password_data.new_password)
        db_user.password_changed_at = datetime.now(timezone.utc)
        db_user.failed_login_attempts = 0
        db_user.account_locked_until = None
        db_user.last_modified_by = updated_by
        db_user.last_modified_date = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return True
    
    async def reset_password(self, user_id: int, new_password: str, updated_by: Optional[str] = None) -> str:
        """비밀번호 리셋 (관리자용)"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        # 새 비밀번호가 제공되지 않으면 임시 비밀번호 생성
        if not new_password:
            new_password = PasswordPolicy.generate_temporary_password()
        
        # 비밀번호 정책 검증
        is_valid, errors = PasswordPolicy.validate_password(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=". ".join(errors)
            )
        
        # 비밀번호 업데이트
        db_user.password_hash = AuthUtils.get_password_hash(new_password)
        db_user.password_changed_at = datetime.now(timezone.utc)
        db_user.failed_login_attempts = 0
        db_user.account_locked_until = None
        db_user.last_modified_by = updated_by
        db_user.last_modified_date = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return new_password
    
    async def authenticate_user(self, emp_no: str, password: str, options: Optional[List] = None) -> Optional[User]:
        """사용자 인증 - 사번과 비밀번호로 인증"""
        user = await self.get_user_by_emp_no(emp_no, options=options)
        if not user:
            return None
        
        # 계정 잠금 상태 확인
        if SecurityUtils.is_account_locked(user.failed_login_attempts, user.account_locked_until):
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"계정이 잠겨있습니다. {SecurityUtils.LOCKOUT_DURATION_MINUTES}분 후 다시 시도해주세요."
            )
        
        # 비활성 계정 확인
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="비활성화된 계정입니다"
            )
        
        # 비밀번호 검증
        if not AuthUtils.verify_password(password, user.password_hash):
            # 로그인 실패 횟수 증가
            user.failed_login_attempts += 1
            
            # 최대 시도 횟수 도달 시 계정 잠금
            if user.failed_login_attempts >= SecurityUtils.MAX_LOGIN_ATTEMPTS:
                user.account_locked_until = SecurityUtils.get_lockout_time()
            
            await self.db.commit()
            return None
        
        # 로그인 성공 시 실패 횟수 리셋 및 로그인 시간 업데이트
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.last_login = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return user
    
    async def search_users(self, search_params: UserSearchParams) -> Tuple[List[UserListResponse], int]:
        """사용자 검색 및 페이징"""
        # 기본 쿼리 - SAP HR 정보를 항상 조인
        query = select(User).options(selectinload(User.sap_hr_info))
        query = query.outerjoin(TbSapHrInfo, User.emp_no == TbSapHrInfo.emp_no)
        
        count_query = select(func.count(User.id))
        count_query = count_query.outerjoin(TbSapHrInfo, User.emp_no == TbSapHrInfo.emp_no)
        
        # 검색 조건 적용
        conditions = []
        
        if search_params.search:
            search_term = f"%{search_params.search}%"
            # User 테이블과 SAP HR 정보에서 검색
            search_conditions = or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term),
                User.emp_no.ilike(search_term),
                TbSapHrInfo.emp_nm.ilike(search_term),
                TbSapHrInfo.dept_nm.ilike(search_term)
            )
            conditions.append(search_conditions)
        
        # 부서 필터
        if search_params.dept_cd:
            conditions.append(TbSapHrInfo.dept_cd == search_params.dept_cd)
        
        # 부서명 필터
        if search_params.dept_nm:
            conditions.append(TbSapHrInfo.dept_nm.ilike(f"%{search_params.dept_nm}%"))
        
        # 직급 코드 필터
        if search_params.postn_cd:
            conditions.append(TbSapHrInfo.postn_cd == search_params.postn_cd)
        
        # 직급명 필터
        if search_params.postn_nm:
            conditions.append(TbSapHrInfo.postn_nm.ilike(f"%{search_params.postn_nm}%"))
        
        # 활성화 상태 필터
        if search_params.is_active is not None:
            conditions.append(User.is_active == search_params.is_active)
        
        # 관리자 여부 필터
        if search_params.is_admin is not None:
            conditions.append(User.is_admin == search_params.is_admin)
        
        # 조건 적용
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # 전체 개수 조회
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # 페이징 적용
        offset = (search_params.page - 1) * search_params.size
        query = query.order_by(User.created_date.desc()).offset(offset).limit(search_params.size)
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        # 응답 형태로 변환
        user_responses = []
        for user in users:
            # 역할 결정: is_admin이 True면 ADMIN, 아니면 USER
            role = "ADMIN" if user.is_admin else "USER"
            
            user_response = UserListResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                emp_no=user.emp_no,
                is_active=user.is_active,
                is_admin=user.is_admin,
                last_login=user.last_login,
                emp_name=user.sap_hr_info.emp_nm if user.sap_hr_info else None,
                dept_name=user.sap_hr_info.dept_nm if user.sap_hr_info else None,
                position_name=user.sap_hr_info.postn_nm if user.sap_hr_info else None,
                role=role
            )
            user_responses.append(user_response)
        
        return user_responses, total
    
    async def delete_user(self, user_id: int, deleted_by: Optional[str] = None) -> bool:
        """사용자 삭제 (비활성화)"""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="사용자를 찾을 수 없습니다"
            )
        
        # 물리적 삭제 대신 비활성화
        db_user.is_active = False
        db_user.last_modified_date = datetime.now(timezone.utc)
        
        await self.db.commit()
        
        return True
    
    async def bulk_delete_users(self, user_ids: List[int]) -> Tuple[int, int, List[str]]:
        """일괄 사용자 삭제 (비활성화)"""
        processed = 0
        failed = 0
        errors = []
        
        for user_id in user_ids:
            try:
                db_user = await self.get_user_by_id(user_id)
                if not db_user:
                    errors.append(f"사용자 ID {user_id}를 찾을 수 없습니다")
                    failed += 1
                    continue
                
                db_user.is_active = False
                db_user.last_modified_date = datetime.now(timezone.utc)
                processed += 1
            except Exception as e:
                errors.append(f"사용자 ID {user_id} 삭제 실패: {str(e)}")
                failed += 1
        
        await self.db.commit()
        return processed, failed, errors
    
    async def bulk_update_role(self, user_ids: List[int], is_admin: bool) -> Tuple[int, int, List[str]]:
        """일괄 사용자 권한 변경"""
        processed = 0
        failed = 0
        errors = []
        
        for user_id in user_ids:
            try:
                db_user = await self.get_user_by_id(user_id)
                if not db_user:
                    errors.append(f"사용자 ID {user_id}를 찾을 수 없습니다")
                    failed += 1
                    continue
                
                db_user.is_admin = is_admin
                db_user.last_modified_date = datetime.now(timezone.utc)
                processed += 1
            except Exception as e:
                errors.append(f"사용자 ID {user_id} 권한 변경 실패: {str(e)}")
                failed += 1
        
        await self.db.commit()
        return processed, failed, errors
    
    async def get_all_departments(self) -> List[dict]:
        """모든 부서 목록 조회"""
        query = select(TbSapHrInfo.dept_cd, TbSapHrInfo.dept_nm).distinct().where(
            TbSapHrInfo.dept_cd.isnot(None),
            TbSapHrInfo.del_yn == 'N'
        ).order_by(TbSapHrInfo.dept_nm)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [{"code": row[0], "name": row[1]} for row in rows]
    
    async def get_all_positions(self) -> List[dict]:
        """모든 직급 목록 조회"""
        query = select(TbSapHrInfo.postn_cd, TbSapHrInfo.postn_nm).distinct().where(
            TbSapHrInfo.postn_cd.isnot(None),
            TbSapHrInfo.del_yn == 'N'
        ).order_by(TbSapHrInfo.postn_nm)
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [{"code": row[0], "name": row[1]} for row in rows]

class AsyncSapHrService:
    """SAP 인사 정보 관리 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_sap_hr_info(self, emp_no: str) -> Optional[TbSapHrInfo]:
        """SAP 인사 정보 조회"""
        query = select(TbSapHrInfo).where(TbSapHrInfo.emp_no == emp_no)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_sap_hr_info(self, sap_data: SapHrInfoCreate, created_by: Optional[str] = None) -> TbSapHrInfo:
        """SAP 인사 정보 생성"""
        # 중복 검증
        existing_sap = await self.get_sap_hr_info(sap_data.emp_no)
        if existing_sap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 존재하는 사번입니다"
            )
        
        # SAP 인사 정보 생성
        db_sap = TbSapHrInfo(
            **sap_data.dict(),
            created_by=created_by
        )
        
        self.db.add(db_sap)
        await self.db.commit()
        await self.db.refresh(db_sap)
        
        return db_sap
    
    async def update_sap_hr_info(self, emp_no: str, sap_data: SapHrInfoUpdate, updated_by: Optional[str] = None) -> TbSapHrInfo:
        """SAP 인사 정보 수정"""
        db_sap = await self.get_sap_hr_info(emp_no)
        if not db_sap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="SAP 인사 정보를 찾을 수 없습니다"
            )
        
        # 업데이트 수행
        update_data = sap_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_sap, key, value)
        
        db_sap.LAST_MODIFIED_BY = updated_by
        db_sap.LAST_MODIFIED_DATE = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(db_sap)
        
        return db_sap
    
    async def sync_with_users(self, sync_request: SapSyncRequest, synced_by: Optional[str] = None) -> SapSyncResponse:
        """SAP 인사 정보와 User 테이블 동기화"""
        synced_count = 0
        created_users = 0
        updated_users = 0
        deactivated_users = 0
        errors = []
        
        try:
            # SAP 인사 정보에서 활성 사용자 목록 조회
            sap_query = select(TbSapHrInfo).where(TbSapHrInfo.del_yn == 'N')
            
            if not sync_request.sync_inactive:
                # 재직자만 동기화 (퇴사일이 없거나 미래인 경우)
                current_date = datetime.now().strftime('%Y%m%d')
                sap_query = sap_query.where(
                    or_(
                        TbSapHrInfo.rsgntn_de.is_(None),
                        TbSapHrInfo.rsgntn_de == '',
                        TbSapHrInfo.rsgntn_de > current_date
                    )
                )
            
            sap_result = await self.db.execute(sap_query)
            sap_users = sap_result.scalars().all()
            
            for sap_user in sap_users:
                try:
                    # 기존 User 계정 확인
                    user_query = select(User).where(User.emp_no == sap_user.emp_no)
                    user_result = await self.db.execute(user_query)
                    existing_user = user_result.scalar_one_or_none()
                    
                    if existing_user:
                        # 기존 사용자 정보 업데이트
                        if sap_user.email and existing_user.email != sap_user.email:
                            # 이메일 중복 확인
                            email_query = select(User).where(
                                and_(User.email == sap_user.email, User.emp_no != sap_user.emp_no)
                            )
                            email_result = await self.db.execute(email_query)
                            email_conflict = email_result.scalar_one_or_none()
                            
                            if not email_conflict:
                                existing_user.email = sap_user.email
                        
                        # 퇴사자 계정 비활성화
                        if sap_user.rsgntn_de and sap_user.rsgntn_de <= datetime.now().strftime('%Y%m%d'):
                            if existing_user.is_active:
                                existing_user.is_active = False
                                deactivated_users += 1
                        else:
                            # 재직자 계정 활성화
                            if not existing_user.is_active and sync_request.force_sync:
                                existing_user.is_active = True
                        
                        existing_user.last_modified_by = synced_by
                        existing_user.last_modified_date = datetime.now(timezone.utc)
                        updated_users += 1
                        
                    else:
                        # 새 사용자 계정 생성 (force_sync 옵션이 있을 때만)
                        if sync_request.force_sync and sap_user.email:
                            # 임시 비밀번호 생성
                            temp_password = PasswordPolicy.generate_temporary_password()
                            
                            # username 생성 (사번 기반)
                            username = sap_user.emp_no
                            
                            new_user = User(
                                username=username,
                                email=sap_user.email,
                                emp_no=sap_user.emp_no,
                                password_hash=AuthUtils.get_password_hash(temp_password),
                                is_active=True,
                                password_changed_at=datetime.now(timezone.utc),
                                created_by=synced_by
                            )
                            
                            self.db.add(new_user)
                            created_users += 1
                    
                    synced_count += 1
                    
                except Exception as e:
                    errors.append(f"사번 {sap_user.EMP_NO} 동기화 실패: {str(e)}")
            
            await self.db.commit()
            
            return SapSyncResponse(
                success=True,
                message="SAP 인사 정보 동기화가 완료되었습니다",
                synced_count=synced_count,
                created_users=created_users,
                updated_users=updated_users,
                deactivated_users=deactivated_users,
                errors=errors
            )
            
        except Exception as e:
            await self.db.rollback()
            return SapSyncResponse(
                success=False,
                message=f"동기화 중 오류가 발생했습니다: {str(e)}",
                synced_count=0,
                created_users=0,
                updated_users=0,
                deactivated_users=0,
                errors=[str(e)]
            )
