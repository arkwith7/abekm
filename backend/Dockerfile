FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치 (한국어 처리 및 문서 처리용)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libjpeg-dev \
    libpng-dev \
    fonts-nanum \
    poppler-utils \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    libreoffice-impress \
    libreoffice-draw \
    libreoffice-math \
    libreoffice-base-core \
    default-jre-headless \
    xvfb \
    tesseract-ocr \
    tesseract-ocr-kor \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# LibreOffice 환경 변수 설정 (헤드리스 모드)
ENV SAL_USE_VCLPLUGIN=svp
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV HOME=/tmp
ENV TMPDIR=/tmp

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 업로드 및 사전 디렉토리 생성
RUN mkdir -p uploads dictionaries

# 사용자 사전 복사
COPY dictionaries/ dictionaries/

# 초기화 및 시작 스크립트 복사
COPY start_with_init.sh .
RUN chmod +x start_with_init.sh

# 포트 노출
EXPOSE 8000

# 조건부 초기화 및 서버 시작 스크립트 실행
CMD ["./start_with_init.sh"]
