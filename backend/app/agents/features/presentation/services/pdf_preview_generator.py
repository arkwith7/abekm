"""
PDF Preview Generator for Template PPT
템플릿 PPT를 슬라이드별 PDF/이미지로 변환하여 프리뷰 제공

v1.0 - 초기 구현
- LibreOffice를 사용한 PPTX -> PDF 변환
- pdf2image를 사용한 PDF -> 이미지 변환
- 슬라이드별 개별 이미지 저장
"""
import subprocess
import shutil
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from loguru import logger


@dataclass
class SlidePreview:
    """슬라이드 프리뷰 정보"""
    slide_index: int
    pdf_path: Optional[str]
    image_path: Optional[str]
    thumbnail_path: Optional[str]
    width: int
    height: int


@dataclass
class TemplatePreviewResult:
    """템플릿 프리뷰 생성 결과"""
    template_id: str
    total_slides: int
    pdf_path: Optional[str]
    slides: List[SlidePreview]
    preview_dir: str
    success: bool
    error_message: Optional[str] = None


class PDFPreviewGenerator:
    """템플릿 PPT의 PDF 프리뷰를 생성하는 클래스"""
    
    def __init__(self):
        self.preview_base_dir = self._get_preview_base_dir()
        self._check_dependencies()
    
    def _get_preview_base_dir(self) -> Path:
        """프리뷰 저장 기본 디렉토리"""
        base_dir = Path(__file__).parents[3] / 'uploads' / 'templates' / 'previews'
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    
    def _check_dependencies(self):
        """필요한 외부 도구 확인"""
        self.soffice_path = shutil.which('soffice') or shutil.which('libreoffice')
        if not self.soffice_path:
            logger.warning("LibreOffice가 설치되어 있지 않습니다. PDF 변환 기능이 제한됩니다.")
        
        # pdf2image 체크 (선택적)
        self.has_pdf2image = False
        try:
            import pdf2image
            self.has_pdf2image = True
        except ImportError:
            logger.warning("pdf2image가 설치되어 있지 않습니다. 이미지 변환 기능이 제한됩니다.")
    
    def generate_template_preview(self, template_id: str, template_path: str, 
                                   force_regenerate: bool = False) -> TemplatePreviewResult:
        """
        템플릿의 전체 프리뷰를 생성합니다.
        
        Args:
            template_id: 템플릿 ID
            template_path: 템플릿 PPTX 파일 경로
            force_regenerate: True면 기존 캐시 무시하고 재생성
        
        Returns:
            TemplatePreviewResult: 생성 결과
        """
        template_path = Path(template_path)
        
        if not template_path.exists():
            return TemplatePreviewResult(
                template_id=template_id,
                total_slides=0,
                pdf_path=None,
                slides=[],
                preview_dir="",
                success=False,
                error_message=f"템플릿 파일을 찾을 수 없습니다: {template_path}"
            )
        
        # 프리뷰 디렉토리 설정
        preview_dir = self.preview_base_dir / template_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        
        # 캐시 확인
        pdf_path = preview_dir / f"{template_id}.pdf"
        if not force_regenerate and pdf_path.exists():
            # 캐시 신선도 확인
            if pdf_path.stat().st_mtime >= template_path.stat().st_mtime:
                logger.info(f"캐시된 프리뷰 사용: {template_id}")
                return self._load_cached_preview(template_id, preview_dir, pdf_path)
        
        # PDF 변환
        pdf_result = self._convert_to_pdf(template_path, pdf_path)
        if not pdf_result:
            return TemplatePreviewResult(
                template_id=template_id,
                total_slides=0,
                pdf_path=None,
                slides=[],
                preview_dir=str(preview_dir),
                success=False,
                error_message="PDF 변환 실패"
            )
        
        # 슬라이드별 이미지 생성
        slides = self._generate_slide_images(template_id, pdf_path, preview_dir)
        
        return TemplatePreviewResult(
            template_id=template_id,
            total_slides=len(slides),
            pdf_path=str(pdf_path),
            slides=slides,
            preview_dir=str(preview_dir),
            success=True
        )
    
    def _convert_to_pdf(self, pptx_path: Path, output_path: Path) -> bool:
        """PPTX를 PDF로 변환"""
        if not self.soffice_path:
            logger.error("LibreOffice가 설치되어 있지 않아 PDF 변환 불가")
            return False
        
        try:
            output_dir = output_path.parent
            
            # LibreOffice로 PDF 변환
            cmd = [
                self.soffice_path,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_dir),
                str(pptx_path)
            ]
            
            logger.info(f"PDF 변환 시작: {pptx_path}")
            result = subprocess.run(
                cmd, 
                timeout=120,  # 2분 타임아웃
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"PDF 변환 실패: {result.stderr}")
                return False
            
            # 생성된 PDF 파일을 원하는 이름으로 이동
            generated_pdf = output_dir / f"{pptx_path.stem}.pdf"
            if generated_pdf.exists() and generated_pdf != output_path:
                if output_path.exists():
                    output_path.unlink()
                generated_pdf.rename(output_path)
            
            if output_path.exists():
                logger.info(f"PDF 변환 완료: {output_path}")
                return True
            else:
                logger.error(f"PDF 파일이 생성되지 않음: {output_path}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("PDF 변환 타임아웃 (120초 초과)")
            return False
        except Exception as e:
            logger.error(f"PDF 변환 중 오류: {e}")
            return False
    
    def _generate_slide_images(self, template_id: str, pdf_path: Path, 
                                preview_dir: Path) -> List[SlidePreview]:
        """PDF에서 슬라이드별 이미지 생성"""
        slides = []
        
        if not self.has_pdf2image:
            # pdf2image 없으면 PDF만 반환
            logger.warning("pdf2image 없음 - 이미지 변환 건너뜀")
            # PDF 페이지 수 확인 시도
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(str(pdf_path))
                for i in range(len(doc)):
                    slides.append(SlidePreview(
                        slide_index=i + 1,
                        pdf_path=str(pdf_path),
                        image_path=None,
                        thumbnail_path=None,
                        width=0,
                        height=0
                    ))
                doc.close()
            except ImportError:
                logger.warning("PyMuPDF도 없음 - 슬라이드 수 확인 불가")
                slides.append(SlidePreview(
                    slide_index=1,
                    pdf_path=str(pdf_path),
                    image_path=None,
                    thumbnail_path=None,
                    width=0,
                    height=0
                ))
            return slides
        
        try:
            from pdf2image import convert_from_path
            
            # PDF를 이미지로 변환
            images = convert_from_path(
                str(pdf_path),
                dpi=150,  # 적당한 해상도
                fmt='png'
            )
            
            for idx, image in enumerate(images, start=1):
                # 슬라이드 이미지 저장
                image_path = preview_dir / f"slide_{idx}.png"
                image.save(str(image_path), 'PNG')
                
                # 썸네일 생성 (200px 너비)
                thumbnail_path = preview_dir / f"slide_{idx}_thumb.png"
                thumbnail = image.copy()
                thumbnail.thumbnail((200, 150))
                thumbnail.save(str(thumbnail_path), 'PNG')
                
                slides.append(SlidePreview(
                    slide_index=idx,
                    pdf_path=str(pdf_path),
                    image_path=str(image_path),
                    thumbnail_path=str(thumbnail_path),
                    width=image.width,
                    height=image.height
                ))
            
            logger.info(f"슬라이드 이미지 생성 완료: {len(slides)}개")
            return slides
            
        except Exception as e:
            logger.error(f"슬라이드 이미지 생성 실패: {e}")
            return []
    
    def _load_cached_preview(self, template_id: str, preview_dir: Path, 
                              pdf_path: Path) -> TemplatePreviewResult:
        """캐시된 프리뷰 정보 로드"""
        slides = []
        
        # 기존 이미지 파일들 찾기
        image_files = sorted(preview_dir.glob("slide_*.png"))
        image_files = [f for f in image_files if "_thumb" not in f.name]
        
        if image_files:
            for idx, image_file in enumerate(image_files, start=1):
                thumbnail_path = preview_dir / f"slide_{idx}_thumb.png"
                
                # 이미지 크기 확인
                width, height = 0, 0
                try:
                    from PIL import Image
                    with Image.open(image_file) as img:
                        width, height = img.size
                except Exception:
                    pass
                
                slides.append(SlidePreview(
                    slide_index=idx,
                    pdf_path=str(pdf_path),
                    image_path=str(image_file),
                    thumbnail_path=str(thumbnail_path) if thumbnail_path.exists() else None,
                    width=width,
                    height=height
                ))
        else:
            # 이미지 없으면 PDF만
            slides.append(SlidePreview(
                slide_index=1,
                pdf_path=str(pdf_path),
                image_path=None,
                thumbnail_path=None,
                width=0,
                height=0
            ))
        
        return TemplatePreviewResult(
            template_id=template_id,
            total_slides=len(slides),
            pdf_path=str(pdf_path),
            slides=slides,
            preview_dir=str(preview_dir),
            success=True
        )
    
    def get_slide_preview_url(self, template_id: str, slide_index: int) -> Optional[str]:
        """특정 슬라이드의 프리뷰 URL 반환"""
        return f"/api/v1/agent/presentation/templates/{template_id}/preview/{slide_index}"
    
    def get_slide_thumbnail_url(self, template_id: str, slide_index: int) -> Optional[str]:
        """특정 슬라이드의 썸네일 URL 반환"""
        return f"/api/v1/agent/presentation/templates/{template_id}/thumbnail/{slide_index}"
    
    def get_slide_preview_path(self, template_id: str, slide_index: int) -> Optional[str]:
        """특정 슬라이드의 프리뷰 이미지 경로 반환"""
        preview_dir = self.preview_base_dir / template_id
        image_path = preview_dir / f"slide_{slide_index}.png"
        
        if image_path.exists():
            return str(image_path)
        
        return None
    
    def get_slide_thumbnail_path(self, template_id: str, slide_index: int) -> Optional[str]:
        """특정 슬라이드의 썸네일 이미지 경로 반환"""
        preview_dir = self.preview_base_dir / template_id
        thumb_path = preview_dir / f"slide_{slide_index}_thumb.png"
        
        if thumb_path.exists():
            return str(thumb_path)
        
        return None
    
    def delete_template_preview(self, template_id: str) -> bool:
        """템플릿 프리뷰 삭제"""
        try:
            preview_dir = self.preview_base_dir / template_id
            if preview_dir.exists():
                shutil.rmtree(preview_dir)
                logger.info(f"템플릿 프리뷰 삭제됨: {template_id}")
            return True
        except Exception as e:
            logger.error(f"템플릿 프리뷰 삭제 실패: {e}")
            return False
    
    def list_template_previews(self, template_id: str) -> Dict[str, Any]:
        """템플릿의 모든 프리뷰 정보 반환"""
        preview_dir = self.preview_base_dir / template_id
        
        if not preview_dir.exists():
            return {
                "template_id": template_id,
                "has_preview": False,
                "slides": []
            }
        
        # 이미지 파일들 찾기
        image_files = sorted(preview_dir.glob("slide_*.png"))
        image_files = [f for f in image_files if "_thumb" not in f.name]
        
        slides_info = []
        for idx, image_file in enumerate(image_files, start=1):
            thumb_path = preview_dir / f"slide_{idx}_thumb.png"
            slides_info.append({
                "slide_index": idx,
                "preview_url": self.get_slide_preview_url(template_id, idx),
                "thumbnail_url": self.get_slide_thumbnail_url(template_id, idx),
                "has_thumbnail": thumb_path.exists()
            })
        
        pdf_path = preview_dir / f"{template_id}.pdf"
        
        return {
            "template_id": template_id,
            "has_preview": bool(slides_info) or pdf_path.exists(),
            "pdf_url": f"/api/v1/agent/presentation/templates/{template_id}/pdf" if pdf_path.exists() else None,
            "total_slides": len(slides_info),
            "slides": slides_info
        }


# 전역 인스턴스
pdf_preview_generator = PDFPreviewGenerator()
