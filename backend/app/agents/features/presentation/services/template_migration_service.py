"""
템플릿 마이그레이션 서비스
기존에 업로드된 템플릿들을 새로운 콘텐츠 정리 시스템에 맞게 업데이트
"""
import logging
from typing import List, Dict, Any
from pathlib import Path

from .ppt_template_manager import template_manager
from .template_content_cleaner import template_content_cleaner
from .dynamic_template_manager import dynamic_template_manager

logger = logging.getLogger(__name__)

class TemplateMigrationService:
    """템플릿 마이그레이션 서비스"""
    
    def __init__(self):
        self.template_manager = template_manager
        self.content_cleaner = template_content_cleaner
        self.dynamic_manager = dynamic_template_manager
    
    def migrate_existing_templates(self) -> Dict[str, Any]:
        """기존 템플릿들을 새로운 시스템으로 마이그레이션"""
        try:
            logger.info("기존 템플릿 마이그레이션 시작")
            
            # 기존 템플릿 목록 가져오기
            existing_templates = self.template_manager.list_templates()
            
            migration_results = {
                "total": len(existing_templates),
                "migrated": 0,
                "failed": 0,
                "skipped": 0,
                "details": []
            }
            
            for template in existing_templates:
                template_id = template.get('id')
                template_name = template.get('name', 'Unknown')
                
                try:
                    result = self._migrate_single_template(template_id, template)
                    if result['success']:
                        migration_results['migrated'] += 1
                    elif result['skipped']:
                        migration_results['skipped'] += 1
                    else:
                        migration_results['failed'] += 1
                    
                    migration_results['details'].append({
                        'template_id': template_id,
                        'name': template_name,
                        'result': result
                    })
                    
                except Exception as e:
                    logger.error(f"템플릿 {template_id} 마이그레이션 실패: {e}")
                    migration_results['failed'] += 1
                    migration_results['details'].append({
                        'template_id': template_id,
                        'name': template_name,
                        'result': {'success': False, 'error': str(e)}
                    })
            
            logger.info(f"템플릿 마이그레이션 완료: {migration_results['migrated']}개 성공, "
                       f"{migration_results['failed']}개 실패, {migration_results['skipped']}개 스킵")
            
            return migration_results
            
        except Exception as e:
            logger.error(f"템플릿 마이그레이션 실패: {e}")
            raise
    
    def _migrate_single_template(self, template_id: str, template_info: Dict[str, Any]) -> Dict[str, Any]:
        """개별 템플릿 마이그레이션"""
        try:
            # 템플릿 상세 정보 가져오기
            template_details = self.template_manager.get_template_details(template_id)
            if not template_details:
                return {'success': False, 'skipped': False, 'error': '템플릿 상세 정보 없음'}
            
            # 이미 마이그레이션된 템플릿은 스킵
            if template_details.get('dynamic_template_id') and template_details.get('is_content_cleaned'):
                logger.debug(f"템플릿 {template_id} 이미 마이그레이션됨")
                return {'success': True, 'skipped': True, 'message': '이미 마이그레이션됨'}
            
            # 템플릿 파일 경로 확인
            template_path = template_details.get('path')
            if not template_path or not Path(template_path).exists():
                return {'success': False, 'skipped': False, 'error': '템플릿 파일 없음'}
            
            template_file_path = Path(template_path)
            
            # 1. 콘텐츠 정리
            clean_template_path = template_file_path.parent / f"clean_{template_file_path.name}"
            cleaned_path = self.content_cleaner.clean_template_content(
                str(template_file_path), str(clean_template_path)
            )
            
            # 2. 동적 템플릿 분석
            dynamic_template_id = self.dynamic_manager.register_user_template(
                cleaned_path, template_details.get('name', template_id)
            )
            
            # 3. 콘텐츠 매핑 정보 생성
            content_mapping = self.content_cleaner.create_content_mapping(cleaned_path)
            
            # 4. 기존 템플릿 정보 업데이트
            if hasattr(self.template_manager, '_registry') and template_id in self.template_manager._registry:
                self.template_manager._registry[template_id].update({
                    'dynamic_template_id': dynamic_template_id,
                    'cleaned_template_path': cleaned_path,
                    'content_mapping': content_mapping,
                    'is_content_cleaned': True,
                    'migration_date': self._get_current_timestamp()
                })
            
            logger.info(f"템플릿 {template_id} 마이그레이션 완료: {dynamic_template_id}")
            
            return {
                'success': True,
                'skipped': False,
                'dynamic_template_id': dynamic_template_id,
                'cleaned_path': cleaned_path,
                'content_areas': content_mapping.get('total_content_areas', 0)
            }
            
        except Exception as e:
            logger.error(f"템플릿 {template_id} 마이그레이션 실패: {e}")
            return {'success': False, 'skipped': False, 'error': str(e)}
    
    def _get_current_timestamp(self) -> str:
        """현재 타임스탬프 반환"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def check_migration_status(self) -> Dict[str, Any]:
        """마이그레이션 상태 확인"""
        try:
            templates = self.template_manager.list_templates()
            
            status = {
                "total_templates": len(templates),
                "migrated_templates": 0,
                "unmigrated_templates": 0,
                "migration_details": []
            }
            
            for template in templates:
                template_id = template.get('id')
                details = self.template_manager.get_template_details(template_id)
                
                is_migrated = (
                    details and 
                    details.get('dynamic_template_id') and 
                    details.get('is_content_cleaned')
                )
                
                if is_migrated:
                    status["migrated_templates"] += 1
                else:
                    status["unmigrated_templates"] += 1
                
                status["migration_details"].append({
                    "template_id": template_id,
                    "name": template.get('name', 'Unknown'),
                    "is_migrated": is_migrated,
                    "dynamic_template_id": details.get('dynamic_template_id') if details else None,
                    "content_cleaned": details.get('is_content_cleaned', False) if details else False
                })
            
            return status
            
        except Exception as e:
            logger.error(f"마이그레이션 상태 확인 실패: {e}")
            return {"error": str(e)}


# 전역 인스턴스
template_migration_service = TemplateMigrationService()
