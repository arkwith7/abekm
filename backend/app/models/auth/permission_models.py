"""
WKMS 권한 관리 모델
Phase 1 Database Schema 기반 SQLAlchemy 모델 구현
"""
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, BigInteger, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class TbKnowledgeContainers(Base):
    """지식 컨테이너 테이블 - 계층형 조직 구조 및 지식 분류 관리"""
    __tablename__ = "tb_knowledge_containers"
    
    # 기본 정보
    container_id = Column(String(50), primary_key=True, comment="컨테이너 ID")
    container_name = Column(String(200), nullable=False, comment="컨테이너 명")
    parent_container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=True, comment="상위 컨테이너 ID")
    
    # 조직 구조
    container_type = Column(String(20), nullable=False, default='department', comment="컨테이너 유형 (company/division/department/team)")
    sap_org_code = Column(String(20), nullable=True, comment="SAP 조직 코드")
    sap_cost_center = Column(String(20), nullable=True, comment="SAP 코스트 센터")
    org_level = Column(Integer, nullable=False, default=1, comment="조직 레벨 (1=ROOT, 2=DIVISION, 3=DEPARTMENT, 4=TEAM)")
    org_path = Column(Text, nullable=True, comment="조직 경로 (/ROOT/DIVISION/DEPARTMENT/TEAM)")
    
    # 지식 분류
    description = Column(Text, nullable=True, comment="컨테이너 설명")
    knowledge_category = Column(String(50), nullable=True, comment="주요 지식 분야")
    
    # 접근 제어
    access_level = Column(String(20), nullable=False, default='internal', comment="접근 수준 (public/internal/restricted/confidential)")
    default_permission = Column(String(20), nullable=False, default='VIEWER', comment="기본 권한 레벨")
    
    # 권한 상속
    inherit_parent_permissions = Column(Boolean, nullable=False, default=True, comment="상위 컨테이너 권한 상속 여부")
    permission_inheritance_type = Column(String(20), nullable=False, default='additive', comment="권한 상속 방식 (additive/override)")
    
    # 권한 관리
    container_owner = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="컨테이너 소유자 (ADMIN 권한)")
    permission_managers = Column(ARRAY(String(20)), nullable=True, comment="권한 관리자 목록")
    
    # 승인 워크플로우
    auto_assign_by_org = Column(Boolean, nullable=False, default=True, comment="조직도 기반 자동 권한 할당")
    require_approval_for_access = Column(Boolean, nullable=False, default=False, comment="접근 시 승인 필요")
    approval_workflow_enabled = Column(Boolean, nullable=False, default=False, comment="권한 요청 승인 워크플로우")
    approvers = Column(ARRAY(String(20)), nullable=True, comment="승인자 목록")
    
    # 상태 관리
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 통계 정보
    document_count = Column(Integer, nullable=False, default=0, comment="문서 수")
    total_knowledge_size = Column(BigInteger, nullable=False, default=0, comment="총 지식 크기 (bytes)")
    last_knowledge_update = Column(DateTime(timezone=True), nullable=True, comment="마지막 지식 업데이트")
    user_count = Column(Integer, nullable=False, default=0, comment="접근 권한이 있는 사용자 수")
    permission_request_count = Column(Integer, nullable=False, default=0, comment="권한 요청 건수")
    last_permission_update = Column(DateTime(timezone=True), nullable=True, comment="마지막 권한 변경 시간")
    
    # 시스템 필드
    created_by = Column(String(20), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    last_modified_by = Column(String(20), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="최종 수정일")
    
    # 관계 정의
    parent_container = relationship("TbKnowledgeContainers", remote_side=[container_id], back_populates="child_containers")
    child_containers = relationship("TbKnowledgeContainers", back_populates="parent_container")
    owner = relationship("TbSapHrInfo", foreign_keys=[container_owner])
    user_permissions = relationship("TbUserPermissions", back_populates="knowledge_container")
    permission_requests = relationship("TbPermissionRequests", back_populates="knowledge_container")
    permission_audit_logs = relationship("TbPermissionAuditLog", back_populates="knowledge_container")
    search_documents = relationship("TbDocumentSearchIndex", back_populates="container")


class TbUserRoles(Base):
    """사용자 역할 테이블 - 4단계 RBAC 시스템"""
    __tablename__ = "tb_user_roles"
    
    # 기본 정보
    role_id = Column(Integer, primary_key=True, autoincrement=True, comment="역할 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="사용자 사번")
    role_name = Column(String(20), nullable=False, comment="역할명 (ADMIN/MANAGER/EDITOR/VIEWER)")
    role_level = Column(Integer, nullable=False, comment="역할 레벨 (1=ADMIN, 2=MANAGER, 3=EDITOR, 4=VIEWER)")
    
    # 역할 범위
    scope_type = Column(String(20), nullable=False, default='global', comment="역할 범위 (global/container/department)")
    scope_value = Column(String(50), nullable=True, comment="범위 값 (container_id 또는 dept_code)")
    
    # 역할 설명
    role_description = Column(Text, nullable=True, comment="역할 설명")
    
    # 권한 설정
    permissions = Column(JSONB, nullable=True, comment="세부 권한 설정 (JSON)")
    
    # 유효 기간
    valid_from = Column(DateTime(timezone=True), nullable=True, comment="역할 유효 시작일")
    valid_until = Column(DateTime(timezone=True), nullable=True, comment="역할 유효 종료일")
    
    # 상태 관리
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    
    # 승인 정보
    assigned_by = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="역할 할당자")
    assigned_date = Column(DateTime(timezone=True), nullable=True, comment="역할 할당일")
    approval_required = Column(Boolean, nullable=False, default=False, comment="승인 필요 여부")
    approved_by = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="승인자")
    approved_date = Column(DateTime(timezone=True), nullable=True, comment="승인일")
    
    # 시스템 필드
    created_by = Column(String(20), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    last_modified_by = Column(String(20), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="최종 수정일")
    
    # 관계 정의
    user = relationship("TbSapHrInfo", foreign_keys=[user_emp_no])
    assigner = relationship("TbSapHrInfo", foreign_keys=[assigned_by])
    approver = relationship("TbSapHrInfo", foreign_keys=[approved_by])


class TbUserPermissions(Base):
    """사용자 권한 테이블 - 실제 데이터베이스 스키마에 맞춘 모델"""
    __tablename__ = "tb_user_permissions"
    
    # 기본 정보
    permission_id = Column(Integer, primary_key=True, autoincrement=True, comment="권한 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="사용자 사번")
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="컨테이너 ID")
    
    # 권한 정보 (실제 데이터베이스 스키마)
    role_id = Column(String(20), nullable=False, comment="역할 ID")
    permission_type = Column(String(20), nullable=False, comment="권한 유형")
    access_scope = Column(String(20), nullable=False, comment="접근 범위")

    # NOTE: 레거시 코드 호환을 위한 alias (과거 'permission_level' 컬럼 사용)
    # 실제 물리 컬럼은 role_id 만 존재하며, permission_level 참조는 role_id 로 매핑한다.
    from sqlalchemy.orm import synonym  # local import to avoid circular issues on module load
    permission_level = synonym('role_id')  # type: ignore
    
    # 권한 출처
    permission_source = Column(String(30), nullable=False, comment="권한 출처")
    source_container_id = Column(String(50), nullable=True, comment="권한 출처 컨테이너 ID")
    sap_role = Column(String(50), nullable=True, comment="SAP 역할")
    
    # 제한 사항
    restricted_categories = Column(ARRAY(Integer), nullable=True, comment="제한 카테고리")
    time_restriction = Column(JSONB, nullable=True, comment="시간 제한")
    ip_restriction = Column(ARRAY(String(50)), nullable=True, comment="IP 제한")
    
    # 권한 부여 정보
    granted_by = Column(String(20), nullable=True, comment="권한 부여자")
    granted_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="권한 부여일")
    expires_date = Column(DateTime(timezone=True), nullable=True, comment="만료일")
    
    # 상태 관리
    is_active = Column(Boolean, nullable=False, comment="활성화 여부")
    
    # 사용 통계
    last_accessed_date = Column(DateTime(timezone=True), nullable=True, comment="마지막 접근일")
    access_count = Column(Integer, nullable=False, comment="접근 횟수")
    
    # 관계 정의
    user = relationship("TbSapHrInfo", foreign_keys=[user_emp_no])
    knowledge_container = relationship("TbKnowledgeContainers", back_populates="user_permissions")


class TbPermissionRequests(Base):
    """권한 요청 테이블 - 실제 데이터베이스 스키마에 맞춘 모델"""
    __tablename__ = "tb_permission_requests"
    
    # 기본 정보
    request_id = Column(Integer, primary_key=True, autoincrement=True, comment="요청 ID")
    requester_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="요청자 사번")
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="컨테이너 ID")
    
    # 요청 내용 (실제 데이터베이스 스키마)
    requested_permission = Column(String(20), nullable=False, comment="요청 권한")
    current_permission = Column(String(20), nullable=True, comment="현재 권한")
    
    # 요청 사유 (실제 데이터베이스 스키마)
    justification = Column(Text, nullable=False, comment="요청 사유")
    business_need = Column(Text, nullable=True, comment="업무 필요성")
    requested_duration = Column(String(50), nullable=True, comment="요청 기간")
    temp_end_date = Column(DateTime(timezone=True), nullable=True, comment="임시 종료일")
    
    # 요청 상태
    request_status = Column(String(20), nullable=False, comment="요청 상태")
    priority_level = Column(String(10), nullable=False, comment="우선순위")
    
    # 승인 정보 (실제 데이터베이스 스키마)
    approver_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="승인자 사번")
    approval_date = Column(DateTime(timezone=True), nullable=True, comment="승인일")
    approval_comment = Column(Text, nullable=True, comment="승인 의견")
    rejection_reason = Column(Text, nullable=True, comment="거부 사유")
    
    # 자동 처리
    auto_approved = Column(Boolean, nullable=False, comment="자동 승인 여부")
    notification_sent = Column(Boolean, nullable=False, comment="알림 발송 여부")
    
    # 메타데이터
    request_metadata = Column(JSONB, nullable=True, comment="요청 메타데이터")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="요청일")
    last_modified_date = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="최종 수정일")
    
    # 관계 정의
    requester = relationship("TbSapHrInfo", foreign_keys=[requester_emp_no])
    knowledge_container = relationship("TbKnowledgeContainers", back_populates="permission_requests")
    approver = relationship("TbSapHrInfo", foreign_keys=[approver_emp_no])


class TbPermissionAuditLog(Base):
    """권한 감사 로그 테이블 - 보안 및 컴플라이언스"""
    __tablename__ = "tb_permission_audit_log"
    
    # 기본 정보
    audit_id = Column(Integer, primary_key=True, autoincrement=True, comment="감사 로그 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="작업 수행자 사번")
    target_user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="대상 사용자 사번")
    
    # 대상 리소스
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=True, comment="대상 컨테이너 ID")
    file_id = Column(Integer, ForeignKey('tb_file_bss_info.file_bss_info_sno'), nullable=True, comment="대상 파일 ID")
    
    # 작업 정보
    action_type = Column(String(30), nullable=False, comment="작업 유형 (grant/revoke/modify/access/approve/reject)")
    resource_type = Column(String(20), nullable=False, comment="리소스 유형 (container/file/role/permission)")
    
    # 변경 내용
    old_permission = Column(String(20), nullable=True, comment="이전 권한")
    new_permission = Column(String(20), nullable=True, comment="새 권한")
    
    # 작업 결과
    action_result = Column(String(20), nullable=False, comment="작업 결과 (success/failure/partial)")
    failure_reason = Column(Text, nullable=True, comment="실패 사유")
    
    # 요청 정보
    ip_address = Column(String(45), nullable=True, comment="IP 주소")
    user_agent = Column(Text, nullable=True, comment="사용자 에이전트")
    session_id = Column(String(100), nullable=True, comment="세션 ID")
    request_path = Column(String(200), nullable=True, comment="요청 경로")
    request_method = Column(String(10), nullable=True, comment="HTTP 메소드")
    
    # 추가 정보
    additional_data = Column(JSONB, nullable=True, comment="추가 데이터 (JSON)")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="로그 생성일")
    
    # 관계 정의
    user = relationship("TbSapHrInfo", foreign_keys=[user_emp_no])
    target_user = relationship("TbSapHrInfo", foreign_keys=[target_user_emp_no])
    knowledge_container = relationship("TbKnowledgeContainers", back_populates="permission_audit_logs")


# =============================================================================
# 📋 추가 모델들 (서비스 호환성)
# =============================================================================

# 기존 코드와의 호환성을 위한 별칭
TbPermissionRequestInfo = TbPermissionRequests
TbKnowledgeContainerInfo = TbKnowledgeContainers


class TbPermissionManagementInfo(Base):
    """권한 관리 정보 테이블"""
    __tablename__ = "tb_permission_management_info"
    
    # 기본 정보
    management_id = Column(Integer, primary_key=True, autoincrement=True, comment="관리 ID")
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="컨테이너 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="사용자 사번")
    
    # 권한 정보
    permission_level = Column(String(20), nullable=False, comment="권한 레벨")
    permission_source = Column(String(30), nullable=False, default='manual', comment="권한 출처")
    is_inherited = Column(Boolean, nullable=False, default=False, comment="상속 권한 여부")
    
    # 유효성
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 상태")
    valid_from = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="유효 시작일")
    valid_until = Column(DateTime(timezone=True), nullable=True, comment="유효 종료일")
    
    # 관리자 정보
    granted_by = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="권한 부여자")
    granted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="권한 부여일")
    revoked_by = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=True, comment="권한 취소자")
    revoked_at = Column(DateTime(timezone=True), nullable=True, comment="권한 취소일")
    
    # 메타데이터
    metadata_json = Column(JSONB, nullable=True, comment="추가 메타데이터")
    
    # 시스템 필드
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성일")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="수정일")
    
    # 관계 정의
    user = relationship("TbSapHrInfo", foreign_keys=[user_emp_no])
    container = relationship("TbKnowledgeContainers")
    granter = relationship("TbSapHrInfo", foreign_keys=[granted_by])
    revoker = relationship("TbSapHrInfo", foreign_keys=[revoked_by])


class TbUserPermissionView(Base):
    """사용자 권한 뷰 - 권한 조회 최적화"""
    __tablename__ = "tb_user_permission_view"
    
    # 복합 키
    view_id = Column(Integer, primary_key=True, autoincrement=True, comment="뷰 ID")
    user_emp_no = Column(String(20), ForeignKey('tb_sap_hr_info.emp_no'), nullable=False, comment="사용자 사번")
    container_id = Column(String(50), ForeignKey('tb_knowledge_containers.container_id'), nullable=False, comment="컨테이너 ID")
    
    # 권한 정보
    permission_level = Column(String(20), nullable=False, comment="최종 권한 레벨")
    effective_permission = Column(String(20), nullable=False, comment="실제 적용 권한")
    permission_source = Column(String(30), nullable=False, comment="권한 출처")
    
    # 계층 정보
    is_inherited = Column(Boolean, nullable=False, default=False, comment="상속 권한 여부")
    inheritance_path = Column(Text, nullable=True, comment="상속 경로")
    
    # 컨테이너 정보
    container_name = Column(String(200), nullable=False, comment="컨테이너 명")
    container_type = Column(String(20), nullable=False, comment="컨테이너 유형")
    access_level = Column(String(20), nullable=False, comment="접근 수준")
    
    # 사용자 정보
    user_name = Column(String(100), nullable=False, comment="사용자 명")
    department_name = Column(String(200), nullable=True, comment="부서명")
    
    # 유효성
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 상태")
    valid_until = Column(DateTime(timezone=True), nullable=True, comment="유효 종료일")
    
    # 시스템 필드
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment="최종 업데이트")
    
    # 관계 정의
    user = relationship("TbSapHrInfo", foreign_keys=[user_emp_no])
    container = relationship("TbKnowledgeContainers")


class TbAutoApprovalRules(Base):
    """자동 승인 규칙 - 권한 요청 자동 승인 조건"""
    __tablename__ = "tb_auto_approval_rules"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(50), unique=True, nullable=False, comment="규칙 ID")
    
    # 규칙 정보
    rule_name = Column(String(200), nullable=False, comment="규칙 이름")
    description = Column(Text, nullable=True, comment="규칙 설명")
    is_active = Column(Boolean, server_default='true', nullable=False, comment="활성 상태")
    priority = Column(Integer, server_default='0', nullable=False, comment="우선순위 (높을수록 먼저 적용)")
    
    # 조건
    conditions = Column(JSONB, nullable=False, comment="승인 조건 (JSON)")
    
    # 작업
    action = Column(String(50), server_default='auto_approve', nullable=False, comment="작업 (auto_approve, require_approval)")
    
    # 생성 정보
    created_by = Column(String(20), ForeignKey('tb_user.emp_no', ondelete='SET NULL'), nullable=True, comment="생성자 사번")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="생성 일시")
    updated_at = Column(DateTime(timezone=True), nullable=True, comment="수정 일시")
    
    # 관계 정의
    creator = relationship("User", foreign_keys=[created_by])
