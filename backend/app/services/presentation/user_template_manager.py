"""
사용자별 PPT 템플릿 관리 서비스
각 사용자는 자신만의 템플릿을 업로드하고 관리할 수 있습니다.

디렉토리 구조:
uploads/templates/
├── users/                      # 사용자별 템플릿 디렉토리
│   └── {user_id}/              # 각 사용자의 템플릿 폴더
│       ├── template1.pptx      # 사용자가 업로드한 템플릿
│       ├── template2.pptx
│       ├── config.json         # 사용자 설정 (기본 템플릿 ID 등)
│       └── metadata/           # 템플릿 메타데이터 (자동 생성)
│           ├── template1_metadata.json
│           └── template2_metadata.json
├── thumbnails/                 # 썸네일 캐시 (전역)
└── metadata/                   # 레거시 메타데이터 (참고용)
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from loguru import logger

from .ppt_template_extractor import extract_presentation


class UserTemplateManager:
    """사용자별 템플릿 관리자"""
    
    def __init__(self):
        # 기본 경로 설정
        self.base_dir = Path(__file__).parents[3] / 'uploads' / 'templates'
        self.users_dir = self.base_dir / 'users'
        self.thumbnails_dir = self.base_dir / 'thumbnails'
        
        # 디렉토리 생성
        self.users_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ UserTemplateManager 초기화: users={self.users_dir}")
    
    def _get_user_dir(self, user_id: str) -> Path:
        """사용자별 템플릿 디렉토리 반환 (없으면 생성)"""
        user_dir = self.users_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
    
    def _get_user_config_path(self, user_id: str) -> Path:
        """사용자 설정 파일 경로"""
        return self._get_user_dir(user_id) / 'config.json'
    
    def _load_user_config(self, user_id: str) -> Dict[str, Any]:
        """사용자 설정 로드"""
        config_path = self._get_user_config_path(user_id)
        if config_path.exists():
            try:
                return json.loads(config_path.read_text(encoding='utf-8'))
            except Exception as e:
                logger.warning(f"사용자 설정 로드 실패: {user_id}, {e}")
        return {}
    
    def _save_user_config(self, user_id: str, config: Dict[str, Any]):
        """사용자 설정 저장"""
        config_path = self._get_user_config_path(user_id)
        try:
            config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as e:
            logger.error(f"사용자 설정 저장 실패: {user_id}, {e}")
    
    def _scan_templates_in_dir(self, directory: Path) -> List[Dict[str, Any]]:
        """디렉토리에서 템플릿 스캔"""
        templates = []
        if not directory.exists():
            return templates
        
        for pptx_file in directory.glob('*.pptx'):
            # clean_ 접두사 파일은 스킵 (원본의 정리된 버전)
            if pptx_file.name.startswith('clean_'):
                continue
            
            # _with_ids 파일은 스킵 (내부 처리용 복사본)
            if '_with_ids' in pptx_file.stem:
                continue
                
            template_id = pptx_file.stem.lower().replace(' ', '_')
            template_name = pptx_file.stem.replace('_', ' ').title()
            
            # 메타데이터 파일 확인
            metadata_dir = directory / 'metadata'
            metadata_file = metadata_dir / f"{template_id}_metadata.json"
            
            slide_count = 0
            if metadata_file.exists():
                try:
                    metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                    slide_count = len(metadata.get('slides', []))
                except Exception:
                    pass
            
            templates.append({
                'id': template_id,
                'name': template_name,
                'path': str(pptx_file),
                'type': 'user-uploaded',
                'slideCount': slide_count,
                'thumbnail_url': f'/api/v1/agent/presentation/templates/{template_id}/thumbnails/0',
                'is_user_uploaded': True
            })
        
        return templates
    
    def list_templates_for_user(self, user_id: str) -> Dict[str, Any]:
        """특정 사용자의 템플릿 목록"""
        # 사용자 템플릿 스캔
        user_dir = self._get_user_dir(user_id)
        user_templates = self._scan_templates_in_dir(user_dir)
        
        # 기본 템플릿 ID 가져오기
        user_config = self._load_user_config(user_id)
        default_template_id = user_config.get('default_template_id')
        
        # 기본 템플릿 표시
        for t in user_templates:
            t['isDefault'] = t['id'] == default_template_id
        
        return {
            'success': True,
            'templates': user_templates,
            'built_in': [],  # 공용 템플릿 없음
            'user_uploaded': user_templates,
            'default_template_id': default_template_id
        }
    
    def upload_template(
        self, 
        user_id: str, 
        file_content: bytes, 
        filename: str, 
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """사용자 템플릿 업로드"""
        user_dir = self._get_user_dir(user_id)
        
        # 안전한 파일명 생성
        safe_name = filename.replace('..', '_').replace('/', '_')
        dest_path = user_dir / safe_name
        
        # 파일 저장
        dest_path.write_bytes(file_content)
        logger.info(f"📄 템플릿 업로드: {dest_path} (user={user_id})")
        
        # 템플릿 ID 생성
        template_id = dest_path.stem.lower().replace(' ', '_')
        
        # 메타데이터 추출
        metadata_dir = user_dir / 'metadata'
        metadata_dir.mkdir(exist_ok=True)
        metadata_file = metadata_dir / f"{template_id}_metadata.json"
        
        try:
            extract_presentation(str(dest_path), str(metadata_file))
            logger.info(f"📊 메타데이터 추출 완료: {metadata_file}")
        except Exception as e:
            logger.warning(f"메타데이터 추출 실패: {e}")
        
        # 슬라이드 수 확인
        slide_count = 0
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text(encoding='utf-8'))
                slide_count = len(metadata.get('slides', []))
            except Exception:
                pass
        
        return {
            'id': template_id,
            'name': name or dest_path.stem,
            'path': str(dest_path),
            'type': 'user-uploaded',
            'slideCount': slide_count,
            'is_user_uploaded': True
        }
    
    def delete_template(self, user_id: str, template_id: str) -> bool:
        """사용자 템플릿 삭제"""
        user_dir = self._get_user_dir(user_id)
        
        # 템플릿 파일 찾기
        for pptx_file in user_dir.glob('*.pptx'):
            if pptx_file.stem.lower().replace(' ', '_') == template_id:
                try:
                    # 파일 삭제
                    pptx_file.unlink()
                    logger.info(f"🗑️ 템플릿 삭제: {pptx_file}")
                    
                    # 메타데이터 파일 삭제
                    metadata_dir = user_dir / 'metadata'
                    metadata_file = metadata_dir / f"{template_id}_metadata.json"
                    if metadata_file.exists():
                        metadata_file.unlink()
                    
                    # clean_ 버전도 삭제
                    clean_version = user_dir / f"clean_{pptx_file.name}"
                    if clean_version.exists():
                        clean_version.unlink()
                    
                    # 기본 템플릿이었다면 해제
                    user_config = self._load_user_config(user_id)
                    if user_config.get('default_template_id') == template_id:
                        user_config['default_template_id'] = None
                        self._save_user_config(user_id, user_config)
                    
                    return True
                except Exception as e:
                    logger.error(f"템플릿 삭제 실패: {e}")
                    return False
        
        logger.warning(f"템플릿을 찾을 수 없습니다: {template_id} (user={user_id})")
        return False
    
    def set_default_template(self, user_id: str, template_id: str) -> bool:
        """기본 템플릿 설정"""
        # 템플릿 존재 확인
        templates = self.list_templates_for_user(user_id)
        template_ids = [t['id'] for t in templates['templates']]
        
        if template_id not in template_ids:
            logger.error(f"존재하지 않는 템플릿: {template_id}")
            return False
        
        # 설정 저장
        user_config = self._load_user_config(user_id)
        user_config['default_template_id'] = template_id
        self._save_user_config(user_id, user_config)
        
        logger.info(f"✅ 기본 템플릿 설정: user={user_id}, template={template_id}")
        return True
    
    def get_default_template_id(self, user_id: str) -> Optional[str]:
        """사용자의 기본 템플릿 ID 반환"""
        user_config = self._load_user_config(user_id)
        return user_config.get('default_template_id')
    
    def get_template_path(self, user_id: str, template_id: str) -> Optional[str]:
        """
        템플릿 파일 경로 반환 (원본 파일)
        
        Args:
            user_id: 사용자 ID
            template_id: 템플릿 ID
        """
        user_dir = self._get_user_dir(user_id)
        
        for pptx_file in user_dir.glob('*.pptx'):
            # _with_ids 버전은 건너뛰기
            if '_with_ids' in pptx_file.stem:
                continue
                
            if pptx_file.stem.lower().replace(' ', '_') == template_id:
                return str(pptx_file)
        
        return None
    
    def get_template_metadata(self, user_id: str, template_id: str) -> Optional[Dict[str, Any]]:
        """템플릿 메타데이터 반환"""
        user_dir = self._get_user_dir(user_id)
        metadata_file = user_dir / 'metadata' / f"{template_id}_metadata.json"
        
        if metadata_file.exists():
            try:
                return json.loads(metadata_file.read_text(encoding='utf-8'))
            except Exception as e:
                logger.error(f"메타데이터 로드 실패: {e}")
        
        return None
    
    def get_template_details(self, user_id: str, template_id: str) -> Optional[Dict[str, Any]]:
        """템플릿 상세 정보 (썸네일 포함) 반환"""
        user_dir = self._get_user_dir(user_id)
        
        # 템플릿 파일 찾기
        template_path = None
        template_name = template_id
        for pptx_file in user_dir.glob('*.pptx'):
            if pptx_file.stem.lower().replace(' ', '_') == template_id:
                template_path = str(pptx_file)
                template_name = pptx_file.stem
                break
        
        if not template_path:
            return None
        
        # 메타데이터 로드
        metadata = self.get_template_metadata(user_id, template_id)
        slides = metadata.get('slides', []) if metadata else []
        
        # 썸네일 정보 생성
        thumbnails = []
        for i, slide in enumerate(slides):
            thumbnails.append({
                'index': i,
                'url': f'/api/v1/agent/presentation/templates/{template_id}/thumbnails/{i}',
                'role': slide.get('role', 'content')
            })
        
        return {
            'id': template_id,
            'name': template_name,
            'path': template_path,
            'slideCount': len(slides),
            'thumbnails': thumbnails,
            'metadata': metadata
        }
    
    def find_template_owner(self, template_id: str) -> Optional[str]:
        """템플릿 ID로 소유자 user_id 찾기"""
        if not self.users_dir.exists():
            return None
        
        for user_dir in self.users_dir.iterdir():
            if user_dir.is_dir():
                for pptx_file in user_dir.glob('*.pptx'):
                    if pptx_file.stem.lower().replace(' ', '_') == template_id:
                        return user_dir.name
        
        return None


# 전역 인스턴스
user_template_manager = UserTemplateManager()
