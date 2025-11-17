#!/usr/bin/env python3
"""
채팅 세션 복원 테스트 스크립트
- 최근 채팅 세션의 참고자료 저장/복원 확인
- detailed_chunks와 selected_documents 검증
"""

import asyncio
import json
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 데이터베이스 연결 설정
DATABASE_URL = "postgresql+asyncpg://wikl_user:wikl_password@localhost:5432/wikl_chat"

async def test_reference_restoration():
    """최근 채팅 세션의 참고자료 복원 테스트"""
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        print("=" * 80)
        print("📊 채팅 세션 참고자료 복원 테스트")
        print("=" * 80)
        print()
        
        # 1. 최근 세션 조회
        query = text("""
            SELECT 
                session_id,
                user_id,
                title,
                referenced_documents,
                created_at
            FROM tb_chat_sessions
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        result = await session.execute(query)
        sessions = result.fetchall()
        
        if not sessions:
            print("❌ 저장된 채팅 세션이 없습니다.")
            return
        
        print(f"✅ 최근 세션 {len(sessions)}개 조회 완료\n")
        
        for idx, sess in enumerate(sessions, 1):
            session_id = sess[0]
            user_id = sess[1]
            title = sess[2]
            referenced_docs = sess[3]
            created_at = sess[4]
            
            print(f"{'='*80}")
            print(f"세션 #{idx}")
            print(f"{'='*80}")
            print(f"📌 세션 ID: {session_id}")
            print(f"👤 사용자 ID: {user_id}")
            print(f"📝 제목: {title}")
            print(f"📅 생성일: {created_at}")
            print(f"📚 참고 문서 수: {len(referenced_docs) if referenced_docs else 0}")
            
            if referenced_docs:
                print(f"\n참고 문서 목록:")
                for doc_id in referenced_docs:
                    print(f"  - 문서 ID: {doc_id}")
            print()
            
            # 2. 해당 세션의 메시지 조회
            msg_query = text("""
                SELECT 
                    message_id,
                    role,
                    LEFT(content, 100) as content_preview,
                    search_results,
                    conversation_context
                FROM tb_chat_history
                WHERE session_id = :session_id
                ORDER BY created_at
            """)
            
            msg_result = await session.execute(msg_query, {"session_id": session_id})
            messages = msg_result.fetchall()
            
            print(f"💬 메시지 수: {len(messages)}")
            print()
            
            for msg_idx, msg in enumerate(messages, 1):
                message_id = msg[0]
                role = msg[1]
                content_preview = msg[2]
                search_results = msg[3]
                conversation_context = msg[4]
                
                print(f"  메시지 #{msg_idx} ({role})")
                print(f"  └─ ID: {message_id}")
                print(f"  └─ 내용 미리보기: {content_preview}...")
                
                # 🆕 detailed_chunks 확인
                if search_results and isinstance(search_results, dict):
                    detailed_chunks = search_results.get('detailed_chunks', [])
                    
                    if detailed_chunks:
                        print(f"  └─ ✅ detailed_chunks: {len(detailed_chunks)}개")
                        
                        for chunk_idx, chunk in enumerate(detailed_chunks[:3], 1):  # 최대 3개만 표시
                            print(f"      Chunk #{chunk_idx}:")
                            print(f"        - 파일명: {chunk.get('file_name', 'N/A')}")
                            print(f"        - 청크 인덱스: {chunk.get('chunk_index', 'N/A')}")
                            print(f"        - 페이지: {chunk.get('page_number', 'N/A')}")
                            print(f"        - 유사도: {chunk.get('similarity_score', 'N/A')}")
                            print(f"        - 검색 타입: {chunk.get('search_type', 'N/A')}")
                            content_preview_chunk = chunk.get('content_preview', '')[:50]
                            print(f"        - 내용: {content_preview_chunk}...")
                        
                        if len(detailed_chunks) > 3:
                            print(f"      ... 외 {len(detailed_chunks) - 3}개")
                    else:
                        print(f"  └─ ⚠️ detailed_chunks 없음")
                
                # 🆕 conversation_context의 selected_documents 확인
                if conversation_context and isinstance(conversation_context, dict):
                    selected_docs = conversation_context.get('selected_documents', [])
                    
                    if selected_docs:
                        print(f"  └─ ✅ selected_documents: {len(selected_docs)}개")
                        for doc in selected_docs[:2]:  # 최대 2개만 표시
                            print(f"      - {doc.get('fileName', 'N/A')} (ID: {doc.get('id', 'N/A')})")
                        if len(selected_docs) > 2:
                            print(f"      ... 외 {len(selected_docs) - 2}개")
                    else:
                        print(f"  └─ ℹ️ selected_documents 없음")
                
                print()
            
            print()
        
        print("=" * 80)
        print("✅ 테스트 완료")
        print("=" * 80)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_reference_restoration())
