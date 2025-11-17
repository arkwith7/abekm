import pytest
from app.services.document.pipeline.integrated_document_pipeline_service import integrated_pipeline_service

class DummyPreprocessor:
    async def process_document(self, file_path, file_extension, container_id, user_emp_no):
        return {
            'success': True,
            'chunks': ['첫번째 청크 내용', '두번째 청크 내용'],
            'extracted_text': '첫번째 청크 내용\n두번째 청크 내용'
        }

@pytest.mark.asyncio
async def test_pipeline_structure_monkeypatch(monkeypatch):
    # Monkeypatch preprocessing service
    monkeypatch.setattr('app.services.document.pipeline.integrated_document_pipeline_service.document_preprocessing_service', DummyPreprocessor())
    # Monkeypatch korean NLP
    async def fake_analyze_chunk_for_search(text):
        return { 'success': True, 'korean_keywords': ['테스트'], 'pos_tags': [], 'named_entities': [], 'embedding': [0.01]*1024 }
    monkeypatch.setattr('app.services.document.pipeline.integrated_document_pipeline_service.korean_nlp_service.analyze_chunk_for_search', fake_analyze_chunk_for_search)
    # Monkeypatch DB generator to capture added objects without real DB
    added = []
    class DummySession:
        def add(self, obj):
            added.append(obj)
        async def commit(self):
            pass
    async def fake_get_db():
        yield DummySession()
    monkeypatch.setattr('app.services.document.pipeline.integrated_document_pipeline_service.get_db', fake_get_db)

    res = await integrated_pipeline_service.process_document_for_rag(
        file_path='/tmp/test.txt',
        file_name='test.txt',
        container_id='CNT1',
        user_emp_no='U1',
        file_bss_info_sno=123
    )
    assert res['success']
    # Ensure no duplicate VsDocContentsChunks objects per chunk index (expect 2 chunks)
    from app.models import VsDocContentsChunks
    chunk_objs = [o for o in added if isinstance(o, VsDocContentsChunks)]
    assert len(chunk_objs) == 2
