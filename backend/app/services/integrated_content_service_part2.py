"""
🔄 통합 콘텐츠 서비스 - 2부: 검색, RAG, 채팅 통합
====================================================

키워드 검색, RAG 시스템, 채팅 세션 관리 구현
"""

    async def _keyword_search_unified(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int
    ) -> List[Dict[str, Any]]:
        """통합 키워드 검색 - vs_doc_contents_index의 텍스트 검색"""
        try:
            keywords = processed_query.get("keywords", [])
            if not keywords:
                keywords = [processed_query["original_text"]]
            
            # 키워드를 PostgreSQL 전문검색 쿼리로 변환
            search_terms = " | ".join(keywords)  # OR 검색
            
            async with self.async_session_local() as session:
                container_filter = "', '".join(container_ids)
                
                query_sql = text(f"""
                    SELECT 
                        v.id as vector_id,
                        v.file_bss_info_sno,
                        v.chunk_text,
                        v.chunk_index,
                        v.chunk_size,
                        v.metadata_json,
                        v.knowledge_container_id,
                        f.file_lgc_nm,
                        f.file_psl_nm,
                        f.path,
                        f.korean_metadata,
                        f.created_at as file_created_at,
                        ts_rank(to_tsvector('korean', v.chunk_text), plainto_tsquery('korean', :search_terms)) as keyword_score
                    FROM vs_doc_contents_index v
                    JOIN tb_file_bss_info f ON v.file_bss_info_sno = f.file_bss_info_sno
                    WHERE v.knowledge_container_id IN ('{container_filter}')
                        AND f.del_yn = 'N'
                        AND to_tsvector('korean', v.chunk_text) @@ plainto_tsquery('korean', :search_terms)
                    ORDER BY keyword_score DESC
                    LIMIT {max_results}
                """)
                
                result = await session.execute(query_sql, {"search_terms": search_terms})
                
                results = []
                for row in result.fetchall():
                    # 메타데이터 파싱
                    metadata = {}
                    if row.metadata_json:
                        try:
                            metadata = json.loads(row.metadata_json)
                        except:
                            pass
                    
                    # 한국어 메타데이터 파싱
                    korean_metadata = {}
                    if row.korean_metadata:
                        try:
                            korean_metadata = json.loads(row.korean_metadata)
                        except:
                            pass
                    
                    results.append({
                        "vector_id": row.vector_id,
                        "file_bss_info_sno": row.file_bss_info_sno,
                        "document_id": f"doc_{row.file_bss_info_sno}_{row.chunk_index}",
                        "title": row.file_lgc_nm or row.file_psl_nm,
                        "content": row.chunk_text,
                        "chunk_index": row.chunk_index,
                        "chunk_size": row.chunk_size,
                        "keyword_score": float(row.keyword_score),
                        "similarity_score": float(row.keyword_score),  # 통일성을 위해 
                        "container_id": row.knowledge_container_id,
                        "file_path": row.path,
                        "metadata": metadata,
                        "korean_metadata": korean_metadata,
                        "file_created_at": row.file_created_at.isoformat() if row.file_created_at else None,
                        "search_method": "keyword"
                    })
                
                logger.info(f"키워드 검색 결과: {len(results)}개")
                return results
                
        except Exception as e:
            logger.error(f"통합 키워드 검색 실패: {str(e)}")
            return []
    
    async def _hybrid_search_unified(
        self,
        processed_query: Dict[str, Any],
        container_ids: List[str],
        max_results: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """통합 하이브리드 검색 - 벡터 + 키워드 결합"""
        try:
            # 병렬로 벡터 검색과 키워드 검색 실행
            import asyncio
            
            vector_results, keyword_results = await asyncio.gather(
                self._vector_search_unified(processed_query, container_ids, max_results * 2, threshold),
                self._keyword_search_unified(processed_query, container_ids, max_results * 2),
                return_exceptions=True
            )
            
            # 결과 통합
            combined_results = {}
            
            # 벡터 검색 결과 처리
            if not isinstance(vector_results, Exception):
                for result in vector_results:
                    doc_id = result["document_id"]
                    result["combined_score"] = result["similarity_score"] * self.vector_weight
                    result["search_methods"] = ["vector"]
                    combined_results[doc_id] = result
            
            # 키워드 검색 결과 처리
            if not isinstance(keyword_results, Exception):
                for result in keyword_results:
                    doc_id = result["document_id"]
                    keyword_contribution = result["keyword_score"] * self.keyword_weight
                    
                    if doc_id in combined_results:
                        # 이미 벡터 검색에서 찾은 문서
                        combined_results[doc_id]["combined_score"] += keyword_contribution
                        combined_results[doc_id]["search_methods"].append("keyword")
                        combined_results[doc_id]["keyword_score"] = result["keyword_score"]
                    else:
                        # 키워드 검색에서만 찾은 문서
                        result["combined_score"] = keyword_contribution
                        result["search_methods"] = ["keyword"]
                        combined_results[doc_id] = result
            
            # 결합 점수로 정렬
            sorted_results = sorted(
                combined_results.values(),
                key=lambda x: x.get("combined_score", 0.0),
                reverse=True
            )
            
            # 점수 정규화
            if sorted_results:
                max_score = max(r.get("combined_score", 0.0) for r in sorted_results)
                if max_score > 0:
                    for result in sorted_results:
                        result["similarity_score"] = result.get("combined_score", 0.0) / max_score
            
            final_results = sorted_results[:max_results]
            
            logger.info(f"하이브리드 검색 결과: {len(final_results)}개")
            return final_results
            
        except Exception as e:
            logger.error(f"통합 하이브리드 검색 실패: {str(e)}")
            return []

    # =========================================================================
    # 💬 3. 통합 RAG 시스템 (Unified RAG System)
    # =========================================================================
    
    async def rag_search_and_context(
        self,
        query: str,
        user_emp_no: str,
        container_ids: Optional[List[str]] = None,
        max_chunks: int = 10,
        similarity_threshold: float = 0.7,
        context_window: int = 4000
    ) -> Dict[str, Any]:
        """
        RAG용 문서 검색 및 컨텍스트 구성
        """
        try:
            # 1. 고품질 벡터 검색 (RAG용 높은 임계값 사용)
            search_results = await self.unified_search(
                query=query,
                user_emp_no=user_emp_no,
                container_ids=container_ids,
                max_results=max_chunks,
                search_type="vector",
                similarity_threshold=similarity_threshold
            )
            
            if not search_results["results"]:
                return {
                    "success": False,
                    "context_text": "",
                    "chunks": [],
                    "total_tokens": 0,
                    "message": "관련 문서를 찾을 수 없습니다"
                }
            
            # 2. 컨텍스트 구성 및 토큰 관리
            context_parts = []
            chunks_used = []
            total_tokens = 0
            
            for i, result in enumerate(search_results["results"]):
                chunk_text = result["content"]
                chunk_tokens = len(chunk_text.split())  # 간단한 토큰 추정
                
                if total_tokens + chunk_tokens > context_window:
                    break
                
                # 컨텍스트 파트 구성
                metadata = result.get("metadata", {})
                source_info = f"출처: {result['title']}"
                if metadata.get("page_number"):
                    source_info += f" (페이지: {metadata['page_number']})"
                
                context_part = f"[문서 {i+1}] {source_info}\n{chunk_text}\n"
                context_parts.append(context_part)
                
                # 사용된 청크 정보
                chunks_used.append({
                    "chunk_id": result["document_id"],
                    "title": result["title"],
                    "content_preview": chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text,
                    "similarity_score": result["similarity_score"],
                    "page_number": metadata.get("page_number"),
                    "file_path": result.get("file_path"),
                    "container_id": result["container_id"]
                })
                
                total_tokens += chunk_tokens
            
            # 3. 최종 컨텍스트 텍스트 구성
            context_text = "\n".join(context_parts)
            
            return {
                "success": True,
                "context_text": context_text,
                "chunks": chunks_used,
                "total_tokens": total_tokens,
                "max_chunks_used": len(chunks_used),
                "similarity_threshold_used": similarity_threshold,
                "search_query": query
            }
            
        except Exception as e:
            logger.error(f"RAG 컨텍스트 구성 실패: {str(e)}")
            return {
                "success": False,
                "context_text": "",
                "chunks": [],
                "total_tokens": 0,
                "error": str(e)
            }

    # =========================================================================
    # 💬 4. 통합 채팅 시스템 (Unified Chat System)
    # =========================================================================
    
    async def create_chat_session(
        self,
        user_emp_no: str,
        session_name: Optional[str] = None,
        container_ids: Optional[List[str]] = None
    ) -> str:
        """새 채팅 세션 생성"""
        try:
            session_id = f"chat_{user_emp_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            async with self.async_session_local() as session:
                query = text("""
                    INSERT INTO tb_chat_history (
                        session_id, user_emp_no, session_name, container_ids_json, 
                        created_at, updated_at, is_active
                    ) VALUES (
                        :session_id, :user_emp_no, :session_name, :container_ids,
                        NOW(), NOW(), true
                    )
                """)
                
                await session.execute(query, {
                    "session_id": session_id,
                    "user_emp_no": user_emp_no,
                    "session_name": session_name or f"채팅 세션 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "container_ids": json.dumps(container_ids) if container_ids else None
                })
                
                await session.commit()
            
            logger.info(f"새 채팅 세션 생성: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"채팅 세션 생성 실패: {str(e)}")
            raise
    
    async def add_chat_message(
        self,
        session_id: str,
        user_emp_no: str,
        question: str,
        answer: str,
        context_chunks: Optional[List[Dict]] = None,
        search_stats: Optional[Dict] = None
    ) -> bool:
        """채팅 메시지 추가"""
        try:
            async with self.async_session_local() as session:
                # 1. 채팅 히스토리에 Q&A 저장
                query = text("""
                    INSERT INTO tb_chat_history (
                        session_id, user_emp_no, question, answer, 
                        context_chunks_json, search_stats_json,
                        created_at, updated_at
                    ) VALUES (
                        :session_id, :user_emp_no, :question, :answer,
                        :context_chunks, :search_stats,
                        NOW(), NOW()
                    )
                """)
                
                await session.execute(query, {
                    "session_id": session_id,
                    "user_emp_no": user_emp_no,
                    "question": question,
                    "answer": answer,
                    "context_chunks": json.dumps(context_chunks) if context_chunks else None,
                    "search_stats": json.dumps(search_stats) if search_stats else None
                })
                
                # 2. 세션 업데이트 시간 갱신
                update_query = text("""
                    UPDATE tb_chat_history 
                    SET updated_at = NOW()
                    WHERE session_id = :session_id AND user_emp_no = :user_emp_no
                        AND question IS NULL AND answer IS NULL
                """)
                
                await session.execute(update_query, {
                    "session_id": session_id,
                    "user_emp_no": user_emp_no
                })
                
                await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"채팅 메시지 저장 실패: {str(e)}")
            return False
    
    async def get_chat_history(
        self,
        session_id: str,
        user_emp_no: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """채팅 히스토리 조회"""
        try:
            async with self.async_session_local() as session:
                query = text("""
                    SELECT 
                        id, session_id, question, answer, 
                        context_chunks_json, search_stats_json,
                        created_at
                    FROM tb_chat_history
                    WHERE session_id = :session_id 
                        AND user_emp_no = :user_emp_no
                        AND question IS NOT NULL
                        AND answer IS NOT NULL
                    ORDER BY created_at ASC
                    LIMIT :limit
                """)
                
                result = await session.execute(query, {
                    "session_id": session_id,
                    "user_emp_no": user_emp_no,
                    "limit": limit
                })
                
                history = []
                for row in result.fetchall():
                    context_chunks = []
                    search_stats = {}
                    
                    if row.context_chunks_json:
                        try:
                            context_chunks = json.loads(row.context_chunks_json)
                        except:
                            pass
                    
                    if row.search_stats_json:
                        try:
                            search_stats = json.loads(row.search_stats_json)
                        except:
                            pass
                    
                    history.append({
                        "id": row.id,
                        "session_id": row.session_id,
                        "question": row.question,
                        "answer": row.answer,
                        "context_chunks": context_chunks,
                        "search_stats": search_stats,
                        "timestamp": row.created_at.isoformat() if row.created_at else None
                    })
                
                return history
                
        except Exception as e:
            logger.error(f"채팅 히스토리 조회 실패: {str(e)}")
            return []
    
    async def get_user_chat_sessions(
        self,
        user_emp_no: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """사용자의 채팅 세션 목록 조회"""
        try:
            async with self.async_session_local() as session:
                query = text("""
                    SELECT DISTINCT
                        session_id, session_name, container_ids_json,
                        MIN(created_at) as first_message,
                        MAX(updated_at) as last_activity,
                        COUNT(CASE WHEN question IS NOT NULL THEN 1 END) as message_count
                    FROM tb_chat_history
                    WHERE user_emp_no = :user_emp_no
                    GROUP BY session_id, session_name, container_ids_json
                    ORDER BY last_activity DESC
                    LIMIT :limit
                """)
                
                result = await session.execute(query, {
                    "user_emp_no": user_emp_no,
                    "limit": limit
                })
                
                sessions = []
                for row in result.fetchall():
                    container_ids = []
                    if row.container_ids_json:
                        try:
                            container_ids = json.loads(row.container_ids_json)
                        except:
                            pass
                    
                    sessions.append({
                        "session_id": row.session_id,
                        "session_name": row.session_name,
                        "container_ids": container_ids,
                        "first_message": row.first_message.isoformat() if row.first_message else None,
                        "last_activity": row.last_activity.isoformat() if row.last_activity else None,
                        "message_count": row.message_count
                    })
                
                return sessions
                
        except Exception as e:
            logger.error(f"채팅 세션 목록 조회 실패: {str(e)}")
            return []

    # =========================================================================
    # 🔧 5. 공통 유틸리티 메서드
    # =========================================================================
    
    async def _get_accessible_containers(
        self,
        user_emp_no: str,
        requested_containers: Optional[List[str]] = None
    ) -> List[str]:
        """사용자가 접근 가능한 컨테이너 목록 조회"""
        try:
            # 권한 서비스 활용 (기존 로직 재사용)
            permission_service = PermissionService(None)  # session은 내부에서 관리
            
            if requested_containers:
                # 요청된 컨테이너 중 접근 가능한 것만 필터링
                accessible = []
                for container_id in requested_containers:
                    # 각 컨테이너에 대한 권한 확인 로직 (간소화)
                    accessible.append(container_id)  # 실제로는 권한 체크 필요
                return accessible
            else:
                # 모든 접근 가능한 컨테이너 반환
                return ["DEFAULT_CONTAINER"]  # 기본 컨테이너
                
        except Exception as e:
            logger.error(f"접근 가능한 컨테이너 조회 실패: {str(e)}")
            return ["DEFAULT_CONTAINER"]
    
    async def _process_search_query(self, query: str) -> Dict[str, Any]:
        """검색 쿼리 전처리"""
        try:
            # 한국어 NLP 처리
            nlp_result = await korean_nlp_service.analyze_text(query)
            
            return {
                "original_text": query,
                "optimized_text": query,  # NLP 결과로 최적화된 쿼리
                "keywords": nlp_result.get("keywords", [query]),
                "entities": nlp_result.get("entities", []),
                "intent": nlp_result.get("intent", "search")
            }
            
        except Exception as e:
            logger.error(f"쿼리 전처리 실패: {str(e)}")
            return {
                "original_text": query,
                "optimized_text": query,
                "keywords": [query],
                "entities": [],
                "intent": "search"
            }
    
    async def _format_search_results_unified(
        self,
        results: List[Dict[str, Any]],
        user_emp_no: str
    ) -> List[Dict[str, Any]]:
        """검색 결과 통일된 포맷으로 변환"""
        formatted_results = []
        
        for result in results:
            # 기본 정보 추출
            formatted_result = {
                "document_id": result["document_id"],
                "title": result["title"],
                "content_preview": result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"],
                "similarity_score": result["similarity_score"],
                "search_methods": result.get("search_methods", []),
                "container_id": result["container_id"],
                "file_path": result.get("file_path"),
                "metadata": {
                    "chunk_index": result.get("chunk_index"),
                    "chunk_size": result.get("chunk_size"),
                    "page_number": result.get("metadata", {}).get("page_number"),
                    "file_created_at": result.get("file_created_at"),
                    "search_timestamp": datetime.now().isoformat()
                }
            }
            
            # 추가 메타데이터
            if result.get("korean_metadata"):
                formatted_result["korean_metadata"] = result["korean_metadata"]
            
            formatted_results.append(formatted_result)
        
        return formatted_results
    
    async def _log_search_activity(
        self,
        user_emp_no: str,
        query: str,
        result_count: int,
        search_type: str
    ) -> None:
        """검색 활동 로그 (선택적)"""
        try:
            # 검색 로그를 별도 테이블에 저장할 수 있음
            logger.info(f"검색 로그: 사용자={user_emp_no}, 쿼리='{query}', 결과={result_count}개, 타입={search_type}")
        except Exception as e:
            logger.error(f"검색 로그 저장 실패: {str(e)}")


# 전역 서비스 인스턴스
integrated_content_service = IntegratedContentService()
