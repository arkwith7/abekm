#!/bin/bash

# 오픈소스 파이프라인 설치 스크립트
# 사용법: ./install_opensource_pipeline.sh

echo "🚀 WKMS 오픈소스 파이프라인 라이브러리 설치 시작..."

# 현재 디렉토리 확인
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt 파일을 찾을 수 없습니다."
    echo "   /home/admin/wkms-aws/backend 디렉토리에서 실행해주세요."
    exit 1
fi

echo "📦 pip 업그레이드..."
pip install --upgrade pip

echo "📋 requirements.txt에서 패키지 설치..."
pip install -r requirements.txt

echo ""
echo "🎯 핵심 오픈소스 라이브러리 설치 확인:"

# 핵심 라이브러리 설치 확인
libraries=(
    "easyocr"
    "paddleocr" 
    "PyMuPDF"
    "camelot"
    "opencv-python"
    "Pillow"
)

for lib in "${libraries[@]}"; do
    if python -c "import ${lib}" 2>/dev/null; then
        echo "✅ ${lib} - 설치 완료"
    else
        echo "❌ ${lib} - 설치 실패 또는 import 오류"
    fi
done

echo ""
echo "🔍 시스템 요구사항 확인:"

# Tesseract 설치 확인
if command -v tesseract &> /dev/null; then
    tesseract_version=$(tesseract --version | head -n1)
    echo "✅ ${tesseract_version}"
    
    # 한국어 언어팩 확인
    if tesseract --list-langs | grep -q "kor"; then
        echo "✅ 한국어 언어팩 설치됨"
    else
        echo "⚠️  한국어 언어팩 미설치. 다음 명령어로 설치:"
        echo "   Ubuntu/Debian: sudo apt-get install tesseract-ocr-kor"
        echo "   CentOS/RHEL: sudo yum install tesseract-langpack-kor"
    fi
else
    echo "⚠️  Tesseract 미설치. 다음 명령어로 설치:"
    echo "   Ubuntu/Debian: sudo apt-get install tesseract-ocr"
    echo "   CentOS/RHEL: sudo yum install tesseract"
fi

# LibreOffice 확인
if command -v libreoffice &> /dev/null; then
    echo "✅ LibreOffice 설치됨 (unoconv 지원)"
else
    echo "⚠️  LibreOffice 미설치. unoconv 사용 불가"
    echo "   Ubuntu/Debian: sudo apt-get install libreoffice"
fi

echo ""
echo "🎉 오픈소스 파이프라인 설치 완료!"
echo ""
echo "📚 다음 단계:"
echo "   1. DocumentProcessorService에 EasyOCR 통합"
echo "   2. 멀티 OCR 폴백 시스템 구현"
echo "   3. 고급 표 구조 인식 추가"
echo ""
echo "🔗 참고 문서: /home/admin/wkms-aws/01.docs/02.document_ingestion_vectorstore.md"
