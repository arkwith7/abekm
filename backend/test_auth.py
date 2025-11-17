#!/usr/bin/env python3
"""
JWT 인증 시스템 테스트 스크립트
"""
import asyncio
import asyncpg
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, insert

# 프로젝트 경로 설정
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.file_models import User, TbSapHrInfo
from app.core.security import AuthUtils, PasswordPolicy
from app.core.config import settings

async def create_test_sap_user():
    """테스트용 SAP 사용자 생성"""
    DATABASE_URL = settings.database_url
    engine = create_async_engine(DATABASE_URL)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # 기존 테스트 사용자 확인
        existing_sap = await session.execute(
            select(TbSapHrInfo).where(TbSapHrInfo.emp_no == "ADMIN001")
        )
        if existing_sap.scalar_one_or_none():
            print("✅ 테스트 SAP 사용자가 이미 존재합니다.")
            return

        # 테스트 SAP 사용자 생성
        test_sap_user = TbSapHrInfo(
            emp_no="ADMIN001",
            emp_nm="시스템관리자",
            dept_cd="IT001",
            dept_nm="정보기술팀",
            postn_cd="MGR001",
            postn_nm="팀장",
            email="admin@wkms.com",
            telno="02-1234-5678",
            mbtlno="010-1234-5678",
            entrps_de="20240101",
            emp_stats_cd="1",
            del_yn="N",
            created_by="SYSTEM"
        )
        
        session.add(test_sap_user)
        await session.commit()
        print("✅ 테스트 SAP 사용자 생성 완료: ADMIN001")

async def create_admin_user():
    """관리자 계정 생성"""
    DATABASE_URL = settings.database_url
    engine = create_async_engine(DATABASE_URL)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        # 기존 관리자 확인
        existing_admin = await session.execute(
            select(User).where(User.username == "admin")
        )
        if existing_admin.scalar_one_or_none():
            print("✅ 관리자 계정이 이미 존재합니다.")
            return

        # 관리자 계정 생성
        admin_password = "Admin123!@#"
        
        admin_user = User(
            emp_no="ADMIN001",
            username="admin",
            email="admin@wkms.com",
            password_hash=AuthUtils.get_password_hash(admin_password),
            is_active=True,
            is_admin=True,
            password_changed_at=datetime.now(timezone.utc),
            created_by="SYSTEM"
        )
        
        session.add(admin_user)
        await session.commit()
        
        print(f"✅ 관리자 계정 생성 완료!")
        print(f"   사용자명: admin")
        print(f"   비밀번호: {admin_password}")
        print(f"   이메일: admin@wkms.com")

async def test_jwt_auth():
    """JWT 인증 테스트"""
    try:
        # 토큰 생성 테스트
        user_data = {
            "user_id": 1,
            "username": "admin",
            "emp_no": "ADMIN001",
            "is_admin": True
        }
        
        access_token = AuthUtils.create_access_token(data=user_data)
        print(f"✅ JWT 토큰 생성 성공")
        print(f"   토큰: {access_token[:50]}...")
        
        # 토큰 검증 테스트
        from fastapi import HTTPException
        try:
            token_data = AuthUtils.verify_token(access_token)
            print(f"✅ JWT 토큰 검증 성공")
            print(f"   사용자 ID: {token_data.user_id}")
            print(f"   사용자명: {token_data.username}")
            print(f"   관리자 권한: {token_data.is_admin}")
        except HTTPException as e:
            print(f"❌ 토큰 검증 실패: {e.detail}")
        
        # 비밀번호 검증 테스트
        test_password = "Admin123!@#"
        password_hash = AuthUtils.get_password_hash(test_password)
        is_valid = AuthUtils.verify_password(test_password, password_hash)
        print(f"✅ 비밀번호 해싱/검증 성공: {is_valid}")
        
        # 비밀번호 정책 테스트
        is_policy_valid, errors = PasswordPolicy.validate_password(test_password)
        print(f"✅ 비밀번호 정책 검증: {is_policy_valid}")
        if errors:
            print(f"   오류: {', '.join(errors)}")
            
    except Exception as e:
        print(f"❌ JWT 인증 테스트 실패: {e}")

async def test_database_connection():
    """데이터베이스 연결 테스트"""
    try:
        DATABASE_URL = settings.database_url
        engine = create_async_engine(DATABASE_URL)
        
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            # User 테이블 조회
            users_result = await session.execute(select(User))
            users = users_result.scalars().all()
            print(f"✅ 데이터베이스 연결 성공")
            print(f"   등록된 사용자 수: {len(users)}")
            
            # SAP HR 정보 조회
            sap_result = await session.execute(select(TbSapHrInfo).limit(5))
            sap_users = sap_result.scalars().all()
            print(f"   SAP 인사정보 수: {len(sap_users)}")
            
            for user in users:
                print(f"   - {user.username} ({user.emp_no}) - 관리자: {user.is_admin}")
                
    except Exception as e:
        print(f"❌ 데이터베이스 연결 테스트 실패: {e}")

async def main():
    """메인 테스트 함수"""
    print("🚀 WKMS JWT 인증 시스템 테스트 시작")
    print("=" * 50)
    
    try:
        # 1. 데이터베이스 연결 테스트
        print("\n📊 데이터베이스 연결 테스트")
        await test_database_connection()
        
        # 2. 테스트 SAP 사용자 생성
        print("\n👤 테스트 SAP 사용자 생성")
        await create_test_sap_user()
        
        # 3. 관리자 계정 생성
        print("\n🔐 관리자 계정 생성")
        await create_admin_user()
        
        # 4. JWT 인증 테스트
        print("\n🔑 JWT 인증 시스템 테스트")
        await test_jwt_auth()
        
        print("\n" + "=" * 50)
        print("✅ 모든 테스트 완료!")
        print("\n📋 다음 단계:")
        print("   1. API 서버 실행: uvicorn app.main:app --reload")
        print("   2. API 문서 확인: http://localhost:8000/docs")
        print("   3. 로그인 테스트: POST /auth/login")
        print("   4. 사용자 관리: /users/* 엔드포인트")
        
    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
