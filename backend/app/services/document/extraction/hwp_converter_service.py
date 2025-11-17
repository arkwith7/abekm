"""
HWP 파일 변환 서비스
LibreOffice를 사용하여 HWP 파일을 PDF나 DOCX로 변환 후 텍스트 추출
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

class HWPConverterService:
    """HWP 파일 변환 서비스"""
    
    def __init__(self):
        self.libreoffice_path = self._find_libreoffice()
        self.supported_formats = ['.hwp', '.hwpx']
    
    def _find_libreoffice(self) -> Optional[str]:
        """LibreOffice 실행 파일 경로 찾기"""
        possible_paths = [
            '/usr/bin/libreoffice',
            '/usr/bin/soffice',
            '/opt/libreoffice/program/soffice',
            '/Applications/LibreOffice.app/Contents/MacOS/soffice',  # macOS
            'C:\\Program Files\\LibreOffice\\program\\soffice.exe',  # Windows
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"LibreOffice found at: {path}")
                return path
        
        logger.warning("LibreOffice not found. HWP conversion will be limited.")
        return None
    
    async def convert_hwp_to_pdf(self, hwp_file_path: str, output_dir: str = None) -> Optional[str]:
        """HWP 파일을 PDF로 변환"""
        if not self.libreoffice_path:
            logger.error("LibreOffice not available for HWP conversion")
            return None
        
        try:
            hwp_path = Path(hwp_file_path)
            if not hwp_path.exists():
                logger.error(f"HWP file not found: {hwp_file_path}")
                return None
            
            # 출력 디렉토리 설정
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            
            output_path = Path(output_dir) / f"{hwp_path.stem}.pdf"
            
            # LibreOffice 변환 명령
            cmd = [
                self.libreoffice_path,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', output_dir,
                str(hwp_path)
            ]
            
            logger.info(f"Converting HWP to PDF: {hwp_path.name}")
            
            # 비동기 실행
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"HWP to PDF conversion successful: {output_path}")
                return str(output_path)
            else:
                logger.error(f"HWP conversion failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"HWP conversion error: {e}")
            return None
    
    async def convert_hwp_to_docx(self, hwp_file_path: str, output_dir: str = None) -> Optional[str]:
        """HWP 파일을 DOCX로 변환"""
        if not self.libreoffice_path:
            logger.error("LibreOffice not available for HWP conversion")
            return None
        
        try:
            hwp_path = Path(hwp_file_path)
            if not hwp_path.exists():
                logger.error(f"HWP file not found: {hwp_file_path}")
                return None
            
            # 출력 디렉토리 설정
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            
            output_path = Path(output_dir) / f"{hwp_path.stem}.docx"
            
            # LibreOffice 변환 명령
            cmd = [
                self.libreoffice_path,
                '--headless',
                '--convert-to', 'docx',
                '--outdir', output_dir,
                str(hwp_path)
            ]
            
            logger.info(f"Converting HWP to DOCX: {hwp_path.name}")
            
            # 비동기 실행
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"HWP to DOCX conversion successful: {output_path}")
                return str(output_path)
            else:
                logger.error(f"HWP conversion failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"HWP conversion error: {e}")
            return None
    
    async def extract_text_from_hwp(self, hwp_file_path: str) -> Dict[str, Any]:
        """HWP 파일에서 텍스트 추출 (변환 후 추출)"""
        result = {
            'success': False,
            'text': '',
            'metadata': {
                'original_file': hwp_file_path,
                'conversion_method': 'libreoffice',
                'char_count': 0
            },
            'error': None
        }
        
        try:
            # 1단계: HWP를 DOCX로 변환
            docx_path = await self.convert_hwp_to_docx(hwp_file_path)
            
            if docx_path and Path(docx_path).exists():
                # 2단계: DOCX에서 텍스트 추출
                from .text_extractor_service import TextExtractorService
                extractor = TextExtractorService()
                docx_result = await extractor.extract_text_from_file(docx_path)
                
                if docx_result['success']:
                    result['success'] = True
                    result['text'] = docx_result['text']
                    result['metadata'].update({
                        'converted_file': docx_path,
                        'char_count': len(docx_result['text']),
                        'extraction_note': 'HWP → DOCX → 텍스트 추출 완료'
                    })
                    
                    # 임시 파일 정리
                    try:
                        os.remove(docx_path)
                    except:
                        pass
                else:
                    result['error'] = f"DOCX 텍스트 추출 실패: {docx_result.get('error', 'Unknown error')}"
            else:
                # LibreOffice 변환 실패 시 기본 방식 시도
                result = await self._fallback_hwp_extraction(hwp_file_path)
                
        except Exception as e:
            logger.error(f"HWP 텍스트 추출 실패: {e}")
            result['error'] = str(e)
        
        return result
    
    async def _fallback_hwp_extraction(self, hwp_file_path: str) -> Dict[str, Any]:
        """기본 HWP 추출 방식 (LibreOffice 실패 시)"""
        result = {
            'success': False,
            'text': '',
            'metadata': {
                'original_file': hwp_file_path,
                'conversion_method': 'fallback_olefile',
                'char_count': 0
            },
            'error': None
        }
        
        try:
            # 기존의 olefile 방식 사용
            import olefile
            ole = olefile.OleFileIO(hwp_file_path)
            
            if ole.exists('PrvText'):
                raw = ole.openstream('PrvText').read()
                try:
                    text = raw.decode('utf-16le')
                except Exception:
                    text = raw.decode('cp949', errors='ignore')
                
                result['success'] = True
                result['text'] = text.strip()
                result['metadata'].update({
                    'extraction_method': 'olefile-PrvText',
                    'char_count': len(result['text']),
                    'extraction_note': 'HWP 기본 텍스트 추출 완료'
                })
            else:
                result['error'] = "PrvText 스트림을 찾을 수 없습니다"
                
        except Exception as e:
            result['error'] = f"기본 HWP 추출 실패: {str(e)}"
        
        return result
    
    def is_hwp_file(self, file_path: str) -> bool:
        """파일이 HWP 형식인지 확인"""
        ext = Path(file_path).suffix.lower()
        return ext in self.supported_formats
    
    def get_conversion_status(self) -> Dict[str, Any]:
        """변환 서비스 상태 확인"""
        return {
            'libreoffice_available': self.libreoffice_path is not None,
            'libreoffice_path': self.libreoffice_path,
            'supported_formats': self.supported_formats,
            'conversion_methods': ['pdf', 'docx', 'fallback_olefile']
        }

# 전역 인스턴스
hwp_converter_service = HWPConverterService()
