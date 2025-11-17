"""
비동기 백그라운드 작업 모듈
"""
from app.tasks.document_tasks import process_document_async

__all__ = ['process_document_async']
