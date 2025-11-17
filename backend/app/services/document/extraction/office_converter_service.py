"""
Office 파일을 PDF로 변환하는 서비스
LibreOffice headless 모드를 사용한 변환
"""
import os
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from loguru import logger
import aiofiles


class OfficeConverterService:
    """Office 파일을 PDF로 변환하는 서비스"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.libreoffice_path = self._find_libreoffice()
        
    def _find_libreoffice(self) -> str:
        """LibreOffice 실행 파일 경로 찾기"""
        possible_paths = [
            "/usr/bin/libreoffice",
            "/usr/bin/soffice",
            "/opt/libreoffice/program/soffice",
            "/snap/libreoffice/current/lib/libreoffice/program/soffice",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"LibreOffice found at: {path}")
                return path
                
        # which 명령어로 찾기
        try:
            result = subprocess.run(["which", "libreoffice"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                logger.info(f"LibreOffice found via which: {path}")
                return path
        except subprocess.TimeoutExpired:
            pass
            
        # soffice로 찾기
        try:
            result = subprocess.run(["which", "soffice"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip()
                logger.info(f"soffice found via which: {path}")
                return path
        except subprocess.TimeoutExpired:
            pass
            
        raise FileNotFoundError("LibreOffice not found. Please install LibreOffice.")
    
    async def convert_to_pdf(self, input_file: str, output_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Office 파일을 PDF로 변환
        
        Args:
            input_file: 변환할 입력 파일 경로
            output_dir: 출력 디렉토리 (기본값: temp_dir)
            
        Returns:
            (성공여부, PDF파일경로_또는_오류메시지)
        """
        try:
            input_path = Path(input_file)
            if not input_path.exists():
                return False, f"Input file not found: {input_file}"
            
            # 지원하는 파일 형식 확인
            supported_extensions = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                  '.odt', '.ods', '.odp', '.rtf'}
            if input_path.suffix.lower() not in supported_extensions:
                return False, f"Unsupported file format: {input_path.suffix}"
            
            # 출력 디렉토리 설정
            if output_dir is None:
                output_dir = self.temp_dir
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Converting {input_file} to PDF using LibreOffice")
            
            # LibreOffice headless 모드로 변환
            cmd = [
                self.libreoffice_path,
                "--headless",
                "--invisible",
                "--convert-to", "pdf",
                "--outdir", str(output_path),
                str(input_path)
            ]
            
            logger.debug(f"Running command: {' '.join(cmd)}")
            
            # 한국어 폰트 지원을 위한 환경변수 설정
            env = os.environ.copy()
            env.update({
                'LANG': 'ko_KR.UTF-8',
                'LC_ALL': 'ko_KR.UTF-8',
                'FONTCONFIG_FILE': '/etc/fonts/fonts.conf',
                'FONTCONFIG_PATH': '/etc/fonts/conf.d',
            })
            
            # 비동기로 subprocess 실행
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                logger.error(f"LibreOffice conversion failed: {error_msg}")
                return False, f"Conversion failed: {error_msg}"
            
            # 변환된 PDF 파일 경로 생성
            pdf_filename = input_path.stem + ".pdf"
            pdf_path = output_path / pdf_filename
            
            if pdf_path.exists():
                logger.info(f"Successfully converted to: {pdf_path}")
                return True, str(pdf_path)
            else:
                logger.error(f"PDF file not created: {pdf_path}")
                return False, "PDF file was not created"
                
        except asyncio.TimeoutError:
            logger.error("LibreOffice conversion timed out")
            return False, "Conversion timed out"
        except Exception as e:
            logger.error(f"Error during conversion: {e}")
            return False, f"Conversion error: {str(e)}"
    
    async def convert_and_cache(self, input_file: str, cache_dir: str) -> Tuple[bool, str]:
        """
        Office 파일을 PDF로 변환하고 캐시 디렉토리에 저장
        
        Args:
            input_file: 변환할 입력 파일 경로
            cache_dir: 캐시 디렉토리
            
        Returns:
            (성공여부, PDF파일경로_또는_오류메시지)
        """
        try:
            input_path = Path(input_file)
            cache_path = Path(cache_dir)
            cache_path.mkdir(parents=True, exist_ok=True)
            
            # 캐시된 PDF가 이미 있는지 확인
            pdf_filename = input_path.stem + ".pdf"
            cached_pdf = cache_path / pdf_filename
            
            # 입력 파일이 캐시된 PDF보다 새로운 경우에만 변환
            if cached_pdf.exists():
                input_mtime = input_path.stat().st_mtime
                cached_mtime = cached_pdf.stat().st_mtime
                
                if cached_mtime >= input_mtime:
                    logger.info(f"Using cached PDF: {cached_pdf}")
                    return True, str(cached_pdf)
            
            # 변환 실행
            success, result = await self.convert_to_pdf(input_file, str(cache_path))
            
            if success:
                logger.info(f"PDF cached at: {result}")
            
            return success, result
            
        except Exception as e:
            logger.error(f"Error during convert_and_cache: {e}")
            return False, f"Cache conversion error: {str(e)}"
    
    def is_office_file(self, file_path: str) -> bool:
        """Office 파일인지 확인"""
        path = Path(file_path)
        office_extensions = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                           '.odt', '.ods', '.odp', '.rtf'}
        return path.suffix.lower() in office_extensions
    
    async def get_file_info(self, file_path: str) -> dict:
        """파일 정보 반환"""
        try:
            path = Path(file_path)
            if not path.exists():
                return {"error": "File not found"}
            
            stat = path.stat()
            return {
                "name": path.name,
                "size": stat.st_size,
                "extension": path.suffix.lower(),
                "is_office_file": self.is_office_file(file_path),
                "modified_time": stat.st_mtime,
                "can_convert_to_pdf": self.is_office_file(file_path)
            }
        except Exception as e:
            return {"error": str(e)}


# 전역 인스턴스
office_converter = None

def get_office_converter() -> OfficeConverterService:
    """Office 변환 서비스 인스턴스 반환"""
    global office_converter
    if office_converter is None:
        office_converter = OfficeConverterService()
    return office_converter
