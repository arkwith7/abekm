"""
WKMS 사용자 및 인사 정보 모델
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Index, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base


class TbSapHrInfo(Base):
    """SAP 인사 정보 테이블"""
    __tablename__ = "tb_sap_hr_info"
    
    # 기본 정보
    emp_no = Column(String(20), primary_key=True, comment="사번")
    emp_nm = Column(String(100), nullable=False, comment="직원명")
    
    # 조직 정보
    dept_cd = Column(String(20), nullable=True, comment="부서 코드")
    dept_nm = Column(String(100), nullable=True, comment="부서명")
    postn_cd = Column(String(20), nullable=True, comment="직급 코드")
    postn_nm = Column(String(100), nullable=True, comment="직급명")
    
    # 연락처 정보
    email = Column(String(200), nullable=True, comment="이메일")
    telno = Column(String(20), nullable=True, comment="전화번호")
    mbtlno = Column(String(20), nullable=True, comment="휴대폰번호")
    
    # 입사/퇴사 정보
    entrps_de = Column(String(8), nullable=True, comment="입사일 (YYYYMMDD)")
    rsgntn_de = Column(String(8), nullable=True, comment="퇴사일 (YYYYMMDD)")
    emp_stats_cd = Column(String(10), nullable=True, comment="재직 상태")
    
    # 삭제 여부
    del_yn = Column(String(1), nullable=False, default='N', comment="삭제 여부")
    
    # 시스템 필드
    created_by = Column(String(50), nullable=True, comment="생성자")
    created_date = Column(DateTime(timezone=True), nullable=True, comment="생성일")
    last_modified_by = Column(String(50), nullable=True, comment="최종 수정자")
    last_modified_date = Column(DateTime(timezone=True), nullable=True, comment="최종 수정일")
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_tb_sap_hr_info_dept_cd', 'dept_cd'),
        Index('idx_tb_sap_hr_info_email', 'email'),
        Index('idx_tb_sap_hr_info_emp_stats_cd', 'emp_stats_cd'),
        Index('idx_tb_sap_hr_info_del_yn', 'del_yn'),
    )


class User(Base):
    """WKMS 사용자 모델 (FastAPI Users 호환)"""
    __tablename__ = "tb_user"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, autoincrement=True)
    emp_no = Column(String(20), nullable=False, unique=True, comment="사번")
    username = Column(String(50), nullable=False, comment="사용자명")
    email = Column(String(200), nullable=False, unique=True, comment="이메일")
    password_hash = Column(String(255), nullable=False, comment="해시된 비밀번호")
    
    # 상태 정보
    is_active = Column(Boolean, nullable=False, default=True, comment="활성화 여부")
    is_admin = Column(Boolean, nullable=False, default=False, comment="관리자 여부")
    
    # 로그인 정보
    last_login = Column(DateTime(timezone=True), nullable=True, comment="마지막 로그인 날짜")
    failed_login_attempts = Column(Integer, nullable=False, default=0, comment="로그인 실패 횟수")
    account_locked_until = Column(DateTime(timezone=True), nullable=True, comment="계정 잠금 해제 시간")
    
    # 시스템 필드
    created_date = Column(DateTime(timezone=True), nullable=False, comment="생성일")
    last_modified_date = Column(DateTime(timezone=True), nullable=False, comment="최종 수정일")
    
    # 관계 정의
    sap_hr_info = relationship(
        "TbSapHrInfo",
        primaryjoin="User.emp_no == TbSapHrInfo.emp_no",
        foreign_keys=[emp_no],
        uselist=False,
        lazy="select"
    )
    
    # FastAPI Users 호환성을 위한 프로퍼티들
    @property
    def name(self) -> str:
        """이름 (SAP HR 정보에서 가져오기)"""
        return self.sap_hr_info.emp_nm if self.sap_hr_info else self.username
    
    @property
    def hashed_password(self) -> str:
        """FastAPI Users 호환성"""
        return self.password_hash
    
    @hashed_password.setter
    def hashed_password(self, value: str):
        """FastAPI Users 호환성"""
        self.password_hash = value
    
    @property
    def is_superuser(self) -> bool:
        """FastAPI Users 호환성"""
        return self.is_admin
    
    @is_superuser.setter
    def is_superuser(self, value: bool):
        """FastAPI Users 호환성"""
        self.is_admin = value
    
    @property
    def is_verified(self) -> bool:
        """FastAPI Users 호환성 - 항상 True로 설정"""
        return True
    
    @property
    def department(self) -> str:
        """부서명 (SAP HR 정보에서 가져오기)"""
        return self.sap_hr_info.dept_nm if self.sap_hr_info else None
    
    @property
    def position(self) -> str:
        """직급 (SAP HR 정보에서 가져오기)"""
        return self.sap_hr_info.postn_nm if self.sap_hr_info else None
    
    # 인덱스 정의
    __table_args__ = (
        Index('idx_tb_user_emp_no', 'emp_no'),
        Index('idx_tb_user_email', 'email'),
        Index('idx_tb_user_is_active', 'is_active'),
    )


class RefreshToken(Base):
    """사용자 Refresh 토큰 저장 및 로테이션 관리 테이블"""
    __tablename__ = "tb_refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("tb_user.id", ondelete="CASCADE"), nullable=False, comment="사용자 ID")
    emp_no = Column(String(20), nullable=False, comment="사번")
    jti = Column(String(64), nullable=False, unique=True, comment="JWT 토큰 ID (고유 식별자)")
    token_hash = Column(String(255), nullable=False, comment="Refresh 토큰 해시값")
    user_agent = Column(Text, nullable=True, comment="사용자 에이전트")
    ip_address = Column(String(45), nullable=True, comment="IP 주소")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="발급 시각")
    expires_at = Column(DateTime(timezone=True), nullable=False, comment="만료 시각")
    rotated_at = Column(DateTime(timezone=True), nullable=True, comment="로테이션(재발급) 시각")
    revoked_at = Column(DateTime(timezone=True), nullable=True, comment="철회 시각")
    revoke_reason = Column(Text, nullable=True, comment="철회 사유")
    is_active = Column(Boolean, nullable=False, default=True, comment="활성 상태")

    __table_args__ = (
        Index('idx_tb_refresh_tokens_emp_no', 'emp_no'),
        Index('idx_tb_refresh_tokens_user_id', 'user_id'),
        Index('idx_tb_refresh_tokens_active', 'is_active'),
        Index('idx_tb_refresh_tokens_expires', 'expires_at'),
    )
