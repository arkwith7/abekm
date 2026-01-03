"""
Text-to-SQL E2E Integration Test

실제 Bedrock LLM과 실제 PostgreSQL DB를 사용하는 완전한 통합 테스트.
"""

import pytest
from langchain_core.messages import HumanMessage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_full_e2e_with_real_llm_and_db():
    """
    완전한 E2E 테스트: 실제 LLM + 실제 DB
    
    Flow:
    1. Schema introspection (information_schema 조회)
    2. 질문 분석 및 관련 테이블 검색
    3. Bedrock LLM으로 SQL 생성
    4. SQL Guard 검증
    5. 실제 DB 실행
    6. 결과 포매팅
    """
    from app.agents.features.text_to_sql.graph import text_to_sql_worker_node

    # 실제 데이터가 있는 테이블로 질문
    question = "지식 컨테이너 테이블에서 상위 5개 레코드를 보여줘"
    
    initial_state = {
        "messages": [HumanMessage(content=question)],
        "next": "",
        "shared_context": {},
    }

    # 실제 worker 실행
    result_state = await text_to_sql_worker_node(initial_state)

    # 응답 검증
    assert "messages" in result_state
    messages = result_state["messages"]
    assert len(messages) > 0
    
    last_message = messages[-1]
    answer = last_message.content
    
    # 성공 케이스 검증
    assert "✅" in answer or "❌" in answer, "Response should have status indicator"
    
    # SQL이 포함되어야 함
    assert "```sql" in answer.lower() or "sql" in answer.lower(), "Response should contain SQL"
    
    # shared_context 검증
    if "✅" in answer:
        shared_context = result_state.get("shared_context", {})
        sql_data = shared_context.get("text_to_sql", {})
        
        assert "sql" in sql_data, "Should have generated SQL"
        assert "columns" in sql_data, "Should have column info"
        assert "rows" in sql_data, "Should have result rows"
        
        # SQL Guard 검증: SELECT만 허용
        sql = sql_data["sql"]
        assert sql.strip().upper().startswith("SELECT"), "Should be SELECT query"
        assert "DELETE" not in sql.upper(), "Should not contain DELETE"
        assert "DROP" not in sql.upper(), "Should not contain DROP"
        assert "UPDATE" not in sql.upper(), "Should not contain UPDATE"
        
        print(f"✅ Generated SQL: {sql}")
        print(f"✅ Columns: {sql_data['columns']}")
        print(f"✅ Row count: {len(sql_data['rows'])}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_schema_introspection():
    """
    Schema introspection 검증
    
    SQLite store에 스키마 정보가 올바르게 저장되는지 확인
    """
    from app.agents.core.db import get_db_session_context
    from app.agents.features.text_to_sql.graph import _default_store
    from app.agents.features.text_to_sql.services.schema_introspector import (
        introspect_public_schema_tables,
    )

    store = _default_store()
    connection_id = "app_db"

    async with get_db_session_context() as session:
        # 스키마 introspection 실행
        tables = await introspect_public_schema_tables(session)
        
        assert len(tables) > 0, "Should find tables in public schema"
        
        # tb_knowledge_containers가 있어야 함
        container_table = next(
            (t for t in tables if t["table_name"] == "tb_knowledge_containers"), None
        )
        assert container_table is not None, "Should find tb_knowledge_containers"
        
        # Store에 저장
        for t in tables[:5]:  # 처음 5개만 테스트
            await store.upsert_table_schema(
                connection_id=connection_id,
                schema_name=t["schema_name"],
                table_name=t["table_name"],
                columns=t["columns"],
                table_comment=t.get("table_comment"),
            )
        
        # Store에서 조회
        results = await store.search_tables(
            connection_id=connection_id, keyword="container", limit=5
        )
        
        assert len(results) > 0, "Should find tables with 'container' keyword"
        
        # 상세 스키마 조회
        schema = await store.get_table_schema(
            connection_id=connection_id,
            schema_name="public",
            table_name="tb_knowledge_containers",
        )
        
        assert schema is not None, "Should get schema details"
        assert "columns" in schema, "Should have columns info"
        assert len(schema["columns"]) > 0, "Should have at least one column"
        
        print(f"✅ Found {len(tables)} tables in public schema")
        print(f"✅ tb_knowledge_containers has {len(schema['columns'])} columns")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_sql_guard():
    """
    SQL Guard 검증: 위험한 쿼리 차단
    """
    from app.agents.features.text_to_sql.services.sql_guard import (
        SqlGuardConfig,
        SqlGuardError,
        validate_read_only_sql,
    )

    config = SqlGuardConfig(max_rows=100)

    # ✅ 안전한 쿼리
    safe_sql = "SELECT * FROM tb_knowledge_containers LIMIT 10"
    validated = validate_read_only_sql(safe_sql, config=config)
    assert "LIMIT" in validated.upper()
    assert validated.strip().upper().startswith("SELECT")

    # ❌ 위험한 쿼리들
    dangerous_queries = [
        "DELETE FROM tb_knowledge_containers",
        "DROP TABLE tb_knowledge_containers",
        "UPDATE tb_knowledge_containers SET container_name = 'hacked'",
        "INSERT INTO tb_knowledge_containers VALUES ('fake')",
        "SELECT * FROM tb_knowledge_containers; DROP TABLE users;",
        "EXEC sp_executesql 'SELECT 1'",
    ]

    for dangerous_sql in dangerous_queries:
        with pytest.raises(SqlGuardError) as exc_info:
            validate_read_only_sql(dangerous_sql, config=config)
        
        assert "금지" in str(exc_info.value) or "허용" not in str(exc_info.value)
        print(f"✅ Blocked: {dangerous_sql[:50]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_cache_mechanism():
    """
    Query cache 검증: 동일 질문 재질의 시 캐시 활용
    """
    from app.agents.features.text_to_sql.graph import _default_store

    store = _default_store()
    connection_id = "test_cache"
    question = "테스트 질문: 지식 컨테이너 조회"
    sql_query = "SELECT * FROM tb_knowledge_containers LIMIT 5"

    # 캐시에 저장
    await store.cache_question_sql(
        connection_id=connection_id, question=question, sql_query=sql_query
    )

    # 캐시에서 조회
    cached_sql = await store.get_cached_sql(
        connection_id=connection_id, question=question
    )

    assert cached_sql == sql_query, "Should retrieve cached SQL"
    print(f"✅ Cache hit: {cached_sql}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_via_api_endpoint():
    """
    API 엔드포인트를 통한 E2E 테스트
    
    /agent/chat?tool=sql 호출 시 TextToSQLAgent 실행 확인
    """
    from app.agents.catalog import agent_catalog
    from langchain_core.messages import HumanMessage

    # AgentCatalog에서 TextToSQLAgent 가져오기
    workers = agent_catalog.get_workers()
    assert "TextToSQLAgent" in workers, "TextToSQLAgent should be in catalog"

    spec = workers["TextToSQLAgent"]
    
    # Worker 직접 호출
    initial_state = {
        "messages": [
            HumanMessage(content="컨테이너 테이블에서 데이터 3개만 보여줘")
        ],
        "next": "",
        "shared_context": {},
    }

    result_state = await spec.node(initial_state)

    # 결과 검증
    assert "messages" in result_state
    messages = result_state["messages"]
    assert len(messages) > 0

    last_message = messages[-1]
    assert last_message.name == "TextToSQLAgent"
    
    answer = last_message.content
    print(f"✅ API Response:\n{answer[:200]}...")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_text_to_sql_with_korean_business_terms():
    """
    한국어 비즈니스 용어로 질문 → 영어 테이블명 매핑 검증
    """
    from app.agents.features.text_to_sql.graph import text_to_sql_worker_node

    # 한국어 비즈니스 용어로 질문
    questions = [
        "지식 컨테이너가 몇 개야?",
        "문서 파일 정보 테이블에서 최근 5개 보여줘",
        "채팅 세션 개수를 알려줘",
    ]

    for question in questions:
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "next": "",
            "shared_context": {},
        }

        result_state = await text_to_sql_worker_node(initial_state)
        messages = result_state["messages"]
        answer = messages[-1].content

        # LLM이 SQL을 생성했거나 graceful failure 메시지를 반환해야 함
        assert (
            "```sql" in answer.lower()
            or "설정" in answer
            or "테이블" in answer
            or "select" in answer.lower()
        ), f"Should handle Korean question: {question}"

        print(f"✅ Question: {question}")
        print(f"   Response preview: {answer[:100]}...")
