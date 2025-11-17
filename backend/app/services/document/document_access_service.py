"""
문서 접근 제어 서비스
Phase 2: 문서 접근 관리 기능

설계 원칙:
1. 컨테이너 기본 권한 + 문서별 예외 설정
2. 문서가 컨테이너 권한 상속
3. 부서 단위 권한 지원
4. 기존 문서는 컨테이너 권한에 따라 자동 매핑
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete, func
from sqlalchemy.orm import joinedload
from datetime import datetime
import logging

from app.models import TbSapHrInfo
from app.models.document.file_models import TbFileBssInfo
from app.models.document.document_access import (
    TbDocumentAccessRules,
    TbDocumentAccessLog,
    AccessLevel,
    RuleType,
    PermissionLevel
)

logger = logging.getLogger(__name__)


class DocumentAccessService:
    """문서 접근 제어 서비스"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ========== CRUD 기본 함수 ==========
    
    async def create_access_rule(
        self,
        file_bss_info_sno: int,
        access_level: AccessLevel,
        created_by: str,
        rule_type: Optional[RuleType] = None,
        target_id: Optional[str] = None,
        permission_level: Optional[PermissionLevel] = None,
        is_inherited: str = 'N',
        metadata: Optional[Dict[str, Any]] = None
    ) -> TbDocumentAccessRules:
        """
        문서 접근 규칙 생성
        
        Args:
            file_bss_info_sno: 파일 일련번호
            access_level: 접근 레벨 (public/restricted/private)
            created_by: 생성자 사번
            rule_type: 규칙 타입 (user/department) - RESTRICTED일 때 필수
            target_id: 대상 ID (사번 또는 부서명) - RESTRICTED일 때 필수
            permission_level: 권한 레벨 (view/download/edit) - RESTRICTED일 때 필수
            is_inherited: 컨테이너 권한 상속 여부
            metadata: 추가 메타데이터
        """
        try:
            # RESTRICTED인 경우 검증
            if access_level == AccessLevel.RESTRICTED:
                if not rule_type or not target_id or not permission_level:
                    raise ValueError(
                        "RESTRICTED access level requires rule_type, target_id, and permission_level"
                    )
            
            # 규칙 생성
            access_rule = TbDocumentAccessRules(
                file_bss_info_sno=file_bss_info_sno,
                access_level=access_level,
                rule_type=rule_type,
                target_id=target_id,
                permission_level=permission_level,
                is_inherited=is_inherited,
                rule_metadata=metadata,
                created_by=created_by
            )
            
            self.db.add(access_rule)
            await self.db.commit()
            await self.db.refresh(access_rule)
            
            logger.info(
                f"Created access rule {access_rule.rule_id} for document {file_bss_info_sno} "
                f"with level {access_level}"
            )
            
            return access_rule
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to create access rule: {str(e)}")
            raise
    
    async def get_document_access_rules(
        self,
        file_bss_info_sno: int
    ) -> List[TbDocumentAccessRules]:
        """문서의 모든 접근 규칙 조회"""
        try:
            query = select(TbDocumentAccessRules).where(
                TbDocumentAccessRules.file_bss_info_sno == file_bss_info_sno
            ).order_by(TbDocumentAccessRules.created_date.desc())
            
            result = await self.db.execute(query)
            rules = result.scalars().all()
            
            return list(rules)
            
        except Exception as e:
            logger.error(f"Failed to get access rules for document {file_bss_info_sno}: {str(e)}")
            raise
    
    async def get_access_rule_by_id(self, rule_id: int) -> Optional[TbDocumentAccessRules]:
        """특정 접근 규칙 조회"""
        try:
            query = select(TbDocumentAccessRules).where(
                TbDocumentAccessRules.rule_id == rule_id
            )
            
            result = await self.db.execute(query)
            rule = result.scalar_one_or_none()
            
            return rule
            
        except Exception as e:
            logger.error(f"Failed to get access rule {rule_id}: {str(e)}")
            raise
    
    async def update_access_rule(
        self,
        rule_id: int,
        access_level: Optional[AccessLevel] = None,
        rule_type: Optional[RuleType] = None,
        target_id: Optional[str] = None,
        permission_level: Optional[PermissionLevel] = None,
        is_inherited: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        modified_by: Optional[str] = None
    ) -> Optional[TbDocumentAccessRules]:
        """접근 규칙 수정"""
        try:
            rule = await self.get_access_rule_by_id(rule_id)
            if not rule:
                return None
            
            # 업데이트할 필드만 수정
            if access_level is not None:
                rule.access_level = access_level
            if rule_type is not None:
                rule.rule_type = rule_type
            if target_id is not None:
                rule.target_id = target_id
            if permission_level is not None:
                rule.permission_level = permission_level
            if is_inherited is not None:
                rule.is_inherited = is_inherited
            if metadata is not None:
                setattr(rule, 'rule_metadata', metadata)
            if modified_by is not None:
                rule.last_modified_by = modified_by
            
            await self.db.commit()
            await self.db.refresh(rule)
            
            logger.info(f"Updated access rule {rule_id}")
            
            return rule
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update access rule {rule_id}: {str(e)}")
            raise
    
    async def delete_access_rule(self, rule_id: int) -> bool:
        """접근 규칙 삭제"""
        try:
            stmt = delete(TbDocumentAccessRules).where(
                TbDocumentAccessRules.rule_id == rule_id
            )
            
            result = await self.db.execute(stmt)
            await self.db.commit()
            
            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted access rule {rule_id}")
            
            return deleted
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete access rule {rule_id}: {str(e)}")
            raise
    
    # ========== 접근 권한 확인 ==========
    
    async def check_user_document_access(
        self,
        file_bss_info_sno: int,
        user_emp_no: str,
        required_permission: PermissionLevel = PermissionLevel.VIEW
    ) -> bool:
        """
        사용자의 문서 접근 권한 확인
        
        로직:
        1. 문서의 접근 규칙 조회
        2. PUBLIC: 모두 허용
        3. PRIVATE: 관리자만 허용 (추후 관리자 확인 로직 추가)
        4. RESTRICTED: 개별 규칙 확인 (사용자 or 부서)
        """
        try:
            # 문서 정보 및 접근 규칙 조회
            query = select(TbDocumentAccessRules).where(
                TbDocumentAccessRules.file_bss_info_sno == file_bss_info_sno
            )
            
            result = await self.db.execute(query)
            rules = result.scalars().all()
            
            # 규칙이 없으면 PUBLIC으로 간주 (기본값)
            if not rules:
                return True
            
            # 접근 레벨별 확인
            for rule in rules:
                if rule.access_level == AccessLevel.PUBLIC:
                    return True
                
                elif rule.access_level == AccessLevel.PRIVATE:
                    # TODO: 관리자 권한 확인 로직 추가
                    # 현재는 False 반환 (추후 User 모델과 연동)
                    continue
                
                elif rule.access_level == AccessLevel.RESTRICTED:
                    # 사용자별 규칙 확인
                    if rule.rule_type == RuleType.USER and rule.target_id == user_emp_no:
                        if self._check_permission_level(rule.permission_level, required_permission):
                            return True
                    
                    # 부서별 규칙 확인
                    elif rule.rule_type == RuleType.DEPARTMENT:
                        user_dept = await self._get_user_department(user_emp_no)
                        if user_dept and user_dept == rule.target_id:
                            if self._check_permission_level(rule.permission_level, required_permission):
                                return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"Failed to check access for user {user_emp_no} on document {file_bss_info_sno}: {str(e)}"
            )
            # 에러 발생 시 안전을 위해 접근 거부
            return False
    
    def _check_permission_level(
        self,
        granted_permission: PermissionLevel,
        required_permission: PermissionLevel
    ) -> bool:
        """권한 레벨 확인 (계층 구조: EDIT > DOWNLOAD > VIEW)"""
        permission_hierarchy = {
            PermissionLevel.VIEW: 1,
            PermissionLevel.DOWNLOAD: 2,
            PermissionLevel.EDIT: 3
        }
        
        granted_level = permission_hierarchy.get(granted_permission, 0)
        required_level = permission_hierarchy.get(required_permission, 0)
        
        return granted_level >= required_level
    
    async def _get_user_department(self, emp_no: str) -> Optional[str]:
        """사용자 부서명 조회"""
        try:
            query = select(TbSapHrInfo.dept_nm).where(
                TbSapHrInfo.emp_no == emp_no
            )
            
            result = await self.db.execute(query)
            dept_nm = result.scalar_one_or_none()
            
            return dept_nm
            
        except Exception as e:
            logger.error(f"Failed to get department for user {emp_no}: {str(e)}")
            return None
    
    # ========== 접근 가능 문서 목록 ==========
    
    async def get_accessible_documents(
        self,
        user_emp_no: str,
        access_level_filter: Optional[AccessLevel] = None,
        container_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        사용자가 접근 가능한 문서 목록 조회
        
        Args:
            user_emp_no: 사용자 사번
            access_level_filter: 접근 레벨 필터 (선택)
            container_id: 컨테이너 ID 필터 (선택)
            limit: 결과 제한
            offset: 페이지네이션 오프셋
        """
        try:
            # 사용자 부서 조회
            user_dept = await self._get_user_department(user_emp_no)
            
            # 기본 쿼리: 파일 정보 + 접근 규칙 조인
            query = select(
                TbFileBssInfo,
                TbDocumentAccessRules
            ).outerjoin(
                TbDocumentAccessRules,
                TbFileBssInfo.file_bss_info_sno == TbDocumentAccessRules.file_bss_info_sno
            ).where(
                TbFileBssInfo.del_yn == 'N'
            )
            
            # 컨테이너 필터
            if container_id:
                query = query.where(TbFileBssInfo.knowledge_container_id == container_id)
            
            # 접근 레벨 필터
            if access_level_filter:
                query = query.where(
                    or_(
                        TbDocumentAccessRules.access_level == access_level_filter,
                        TbDocumentAccessRules.access_level.is_(None)  # 규칙 없음 = PUBLIC
                    )
                )
            
            # 접근 권한 필터링
            access_conditions = or_(
                # PUBLIC 문서
                TbDocumentAccessRules.access_level == AccessLevel.PUBLIC,
                # 규칙 없는 문서 (기본 PUBLIC)
                TbDocumentAccessRules.access_level.is_(None),
                # RESTRICTED - 사용자별
                and_(
                    TbDocumentAccessRules.access_level == AccessLevel.RESTRICTED,
                    TbDocumentAccessRules.rule_type == RuleType.USER,
                    TbDocumentAccessRules.target_id == user_emp_no
                ),
                # RESTRICTED - 부서별
                and_(
                    TbDocumentAccessRules.access_level == AccessLevel.RESTRICTED,
                    TbDocumentAccessRules.rule_type == RuleType.DEPARTMENT,
                    TbDocumentAccessRules.target_id == user_dept
                ) if user_dept else False
            )
            
            query = query.where(access_conditions)
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            rows = result.all()
            
            # 결과 포맷팅
            documents = []
            for file_info, access_rule in rows:
                doc_data = {
                    'file_bss_info_sno': file_info.file_bss_info_sno,
                    'file_lgc_nm': file_info.file_lgc_nm,
                    'file_psl_nm': file_info.file_psl_nm,
                    'file_extsn': file_info.file_extsn,
                    'knowledge_container_id': file_info.knowledge_container_id,
                    'created_date': file_info.created_date,
                    'access_level': access_rule.access_level if access_rule else AccessLevel.PUBLIC,
                    'permission_level': access_rule.permission_level if access_rule else PermissionLevel.DOWNLOAD,
                    'is_inherited': access_rule.is_inherited if access_rule else 'Y'
                }
                documents.append(doc_data)
            
            return documents
            
        except Exception as e:
            logger.error(f"Failed to get accessible documents for user {user_emp_no}: {str(e)}")
            raise
    
    # ========== 접근 로그 ==========
    
    async def log_document_access(
        self,
        file_bss_info_sno: int,
        user_emp_no: str,
        access_type: str,
        access_granted: bool,
        denial_reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> TbDocumentAccessLog:
        """문서 접근 로그 기록"""
        try:
            access_log = TbDocumentAccessLog(
                file_bss_info_sno=file_bss_info_sno,
                user_emp_no=user_emp_no,
                access_type=access_type,
                access_granted='Y' if access_granted else 'N',
                denial_reason=denial_reason,
                access_metadata=metadata
            )
            
            self.db.add(access_log)
            await self.db.commit()
            await self.db.refresh(access_log)
            
            return access_log
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to log document access: {str(e)}")
            raise
    
    # ========== 컨테이너 기반 자동 설정 ==========
    
    async def set_document_access_from_container(
        self,
        file_bss_info_sno: int,
        created_by: str
    ) -> Optional[TbDocumentAccessRules]:
        """
        컨테이너 권한을 기반으로 문서 접근 레벨 자동 설정
        
        로직:
        1. 문서의 컨테이너 정보 조회
        2. 컨테이너의 permission_level에 따라 access_level 매핑
        3. 접근 규칙 생성 (is_inherited='Y')
        """
        try:
            # 문서 정보 조회
            query = select(TbFileBssInfo).where(
                TbFileBssInfo.file_bss_info_sno == file_bss_info_sno
            )
            
            result = await self.db.execute(query)
            file_info = result.scalar_one_or_none()
            
            if not file_info:
                logger.warning(f"Document {file_bss_info_sno} not found")
                return None
            
            # 컨테이너 권한에 따른 접근 레벨 매핑
            access_level = self._map_container_permission_to_access_level(
                file_info.permission_level
            )
            
            # 접근 규칙 생성
            access_rule = await self.create_access_rule(
                file_bss_info_sno=file_bss_info_sno,
                access_level=access_level,
                created_by=created_by,
                is_inherited='Y',
                metadata={
                    'source': 'container',
                    'container_permission_level': file_info.permission_level
                }
            )
            
            logger.info(
                f"Set document {file_bss_info_sno} access level to {access_level} "
                f"from container permission {file_info.permission_level}"
            )
            
            return access_rule
            
        except Exception as e:
            logger.error(
                f"Failed to set document access from container for {file_bss_info_sno}: {str(e)}"
            )
            raise
    
    def _map_container_permission_to_access_level(
        self,
        container_permission: str
    ) -> AccessLevel:
        """
        컨테이너 권한을 문서 접근 레벨로 매핑
        
        매핑 규칙:
        - PUBLIC, INTERNAL -> PUBLIC
        - RESTRICTED -> RESTRICTED
        - PRIVATE, CONFIDENTIAL -> PRIVATE
        """
        if container_permission in ['PUBLIC', 'INTERNAL']:
            return AccessLevel.PUBLIC
        elif container_permission == 'RESTRICTED':
            return AccessLevel.RESTRICTED
        elif container_permission in ['PRIVATE', 'CONFIDENTIAL']:
            return AccessLevel.PRIVATE
        else:
            # 기본값: PUBLIC
            return AccessLevel.PUBLIC
