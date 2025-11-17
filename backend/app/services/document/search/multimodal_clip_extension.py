"""멀티모달 CLIP 검색 확장 모듈

MultimodalSearchService에 CLIP 기반 검색 기능 추가
"""

# 이 파일의 내용을 multimodal_search_service.py의 MultimodalSearchService 클래스에 추가합니다

async def search_multimodal_clip(
    self,
    query: str,
    session: AsyncSession,
    query_type: str = "text",  # "text" or "image"
    top_k: int = 10,
    container_ids: Optional[List[str]] = None,
    file_ids: Optional[List[int]] = None,
    similarity_threshold: float = 0.3,
    modality_filter: Optional[str] = None  # "text", "image", None (모두)
) -> List[Dict[str, Any]]:
    """CLIP 기반 멀티모달 검색
    
    Args:
        query: 검색 쿼리 (텍스트) 또는 이미지 경로
        session: DB 세션
        query_type: "text" (텍스트 쿼리) 또는 "image" (이미지 쿼리)
        top_k: 반환할 최대 결과 수
        container_ids: 필터링할 컨테이너 ID 목록
        file_ids: 필터링할 파일 ID 목록
        similarity_threshold: 최소 유사도 임계값
        modality_filter: 검색할 모달리티 필터 (text/image/None)
        
    Returns:
        검색 결과 리스트
    """
    if not image_embedding_service or not image_embedding_service.use_azure_clip:
        logger.warning("CLIP 서비스가 설정되지 않았습니다. 일반 검색으로 대체합니다.")
        return await self.search_similar_chunks(
            query, session, top_k, container_ids, file_ids, similarity_threshold
        )
    
    try:
        # 1. 쿼리 CLIP 임베딩 생성
        if query_type == "text":
            query_embedding = await image_embedding_service.generate_text_embedding(query)
        else:  # image
            query_embedding = await image_embedding_service.generate_image_embedding(image_path=query)
        
        if not query_embedding:
            logger.warning("쿼리 CLIP 임베딩 생성 실패")
            return []
        
        # 2. 차원 조정 (512d)
        clip_dim = 512
        if len(query_embedding) < clip_dim:
            query_embedding = query_embedding + [0.0] * (clip_dim - len(query_embedding))
        elif len(query_embedding) > clip_dim:
            query_embedding = query_embedding[:clip_dim]
        
        # 3. pgvector 검색 쿼리 구성 (clip_vector 사용)
        vector_literal = "[" + ",".join(map(str, query_embedding)) + "]"
        
        # 기본 검색 쿼리
        base_query = f"""
        SELECT 
            de.embedding_id,
            dc.chunk_id,
            dc.file_bss_info_sno,
            dc.chunk_index,
            dc.content_text,
            dc.token_count,
            dc.modality,
            fbf.file_lgc_nm as file_name,
            fbf.knowledge_container_id,
            de.clip_vector <=> '{vector_literal}'::vector(512) as distance
        FROM doc_embedding de
        JOIN doc_chunk dc ON de.chunk_id = dc.chunk_id
        JOIN tb_file_bss_info fbf ON dc.file_bss_info_sno = fbf.file_bss_info_sno
        WHERE fbf.del_yn = 'N'
          AND de.clip_vector IS NOT NULL
        """
        
        # 필터 조건 추가
        conditions = []
        
        if modality_filter:
            conditions.append(f"dc.modality = '{modality_filter}'")
        
        if container_ids:
            container_filter = "'" + "','".join(container_ids) + "'"
            conditions.append(f"fbf.knowledge_container_id IN ({container_filter})")
        
        if file_ids:
            file_filter = ",".join(map(str, file_ids))
            conditions.append(f"dc.file_bss_info_sno IN ({file_filter})")
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # 정렬 및 제한
        base_query += f"""
        ORDER BY distance ASC
        LIMIT {top_k}
        """
        
        # 4. 쿼리 실행
        result = await session.execute(text(base_query))
        rows = result.fetchall()
        
        # 5. 결과 포맷팅
        search_results = []
        for row in rows:
            similarity_score = 1.0 - float(row.distance)  # 거리를 유사도로 변환
            
            if similarity_score < similarity_threshold:
                continue
            
            search_results.append({
                "chunk_id": row.chunk_id,
                "embedding_id": row.embedding_id,
                "file_id": row.file_bss_info_sno,
                "chunk_index": row.chunk_index,
                "content": row.content_text,
                "token_count": row.token_count,
                "modality": row.modality,
                "file_name": row.file_name,
                "container_id": row.knowledge_container_id,
                "similarity_score": similarity_score,
                "distance": float(row.distance),
                "search_type": "clip_multimodal"
            })
        
        logger.info(f"CLIP 멀티모달 검색 완료: {len(search_results)}개 결과 (임계값: {similarity_threshold})")
        return search_results
        
    except Exception as e:
        logger.error(f"CLIP 멀티모달 검색 실패: {e}")
        return []

async def search_hybrid(
    self,
    query_text: str,
    session: AsyncSession,
    top_k: int = 20,
    container_ids: Optional[List[str]] = None,
    file_ids: Optional[List[int]] = None,
    text_weight: float = 0.6,
    clip_weight: float = 0.4,
    similarity_threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """하이브리드 검색 (텍스트 + CLIP)
    
    Args:
        query_text: 검색 쿼리
        session: DB 세션
        top_k: 반환할 최대 결과 수
        container_ids: 필터링할 컨테이너 ID 목록
        file_ids: 필터링할 파일 ID 목록
        text_weight: 텍스트 검색 가중치 (기본 0.6)
        clip_weight: CLIP 검색 가중치 (기본 0.4)
        similarity_threshold: 최소 유사도 임계값
        
    Returns:
        검색 결과 리스트 (점수 기반 정렬)
    """
    try:
        # 1. 텍스트 검색
        text_results = await self.search_similar_chunks(
            query_text, session, top_k * 2, 
            container_ids, file_ids, 0.0  # 임계값 없이 모두 가져오기
        )
        
        # 2. CLIP 검색
        clip_results = []
        if image_embedding_service and image_embedding_service.use_azure_clip:
            clip_results = await self.search_multimodal_clip(
                query_text, session, "text", top_k * 2,
                container_ids, file_ids, 0.0, None
            )
        
        # 3. 점수 정규화 및 결합
        chunk_scores: Dict[int, Dict[str, Any]] = {}
        
        # 텍스트 검색 결과 처리
        for result in text_results:
            chunk_id = result["chunk_id"]
            text_score = result["similarity_score"] * text_weight
            chunk_scores[chunk_id] = {
                **result,
                "text_score": text_score,
                "clip_score": 0.0,
                "hybrid_score": text_score
            }
        
        # CLIP 검색 결과 처리
        for result in clip_results:
            chunk_id = result["chunk_id"]
            clip_score = result["similarity_score"] * clip_weight
            
            if chunk_id in chunk_scores:
                # 기존 결과에 CLIP 점수 추가
                chunk_scores[chunk_id]["clip_score"] = clip_score
                chunk_scores[chunk_id]["hybrid_score"] += clip_score
            else:
                # CLIP 결과만 있는 경우
                chunk_scores[chunk_id] = {
                    **result,
                    "text_score": 0.0,
                    "clip_score": clip_score,
                    "hybrid_score": clip_score
                }
        
        # 4. 하이브리드 점수로 정렬
        hybrid_results = sorted(
            chunk_scores.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True
        )
        
        # 5. 임계값 필터링 및 top_k 제한
        final_results = [
            r for r in hybrid_results 
            if r["hybrid_score"] >= similarity_threshold
        ][:top_k]
        
        logger.info(f"하이브리드 검색 완료: {len(final_results)}개 결과 (text: {len(text_results)}, clip: {len(clip_results)})")
        return final_results
        
    except Exception as e:
        logger.error(f"하이브리드 검색 실패: {e}")
        return []
