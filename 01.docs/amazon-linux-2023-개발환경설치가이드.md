# Amazon Linux 2023 개발환경 설치 가이드

## 시스템 정보

- OS: Amazon Linux 2023.8.20250818
- Platform: Amazon Linux 2023
- Package Manager: dnf (yum 호환)

## 1. 시스템 업데이트 및 기본 패키지 설치

### 1.1 시스템 업데이트

```bash
# Amazon Linux는 dnf 패키지 매니저 사용 (yum도 호환)
sudo dnf update -y
```

### 1.2 필수 패키지 설치

```bash
# 개발 도구 그룹 설치
sudo dnf groupinstall -y "Development Tools"

# 필수 패키지 설치
sudo dnf install -y \
    python3 \
  ### 7.2 LibreOffice 및 폰트 테스트
```

bash
# LibreOffice headless 모드 테스트
libreoffice --headless --version

# 한글 폰트 설치 확인

fc-list | grep -E "(Noto|Nanum)" | wc -l

# 한글 문서 변환 테스트

echo "한글 테스트 문서" > hangul_test.txt
libreoffice --headless --convert-to pdf hangul_test.txt
ls -la hangul_test.pdf
rm hangul_test.txt hangul_test.pdf
```

### 7.3 Docker 테스트### 6.4 Redis 설치 (필요시) 설치 (이미지 처리용)

```bash
# ImageMagick 설치 (이미지 변환 및 처리)
sudo dnf install -y ImageMagick ImageMagick-devel

# 버전 확인
convert --version
```

### 6.3 PostgreSQL 클라이언트 설치 (필요시) python3-pip \

    python3-devel \
    git \
    curl \
    unzip \
    wget \
    postgresql-devel \
    gcc \
    gcc-c++ \
    make \
    openssl-devel \
    libffi-devel \
    sqlite-devel
```

### 1.3 파이썬 버전 확인

```bash
python3 --version
# 예상 출력: Python 3.9.x (Amazon Linux 2023 기본)
```

### 1.4 Python 3.11 업그레이드 (권장)

Amazon Linux 2023의 기본 Python 버전은 3.9.x이지만, 최신 기능과 성능을 위해 Python 3.11로 업그레이드를 권장합니다.

#### 방법 1: Amazon Linux Extras 사용 (권장)

```bash
# 사용 가능한 Python 버전 확인
sudo dnf list available | grep python3.11

# Python 3.11 설치
sudo dnf install -y python3.11 python3.11-pip python3.11-devel

# Python 3.11 버전 확인
python3.11 --version
# 출력: Python 3.11.x

# alternatives를 사용하여 기본 python3를 3.11로 설정
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.9 1
sudo alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 2

# 기본 python3 버전 선택 (2번 선택하여 Python 3.11로 설정)
sudo alternatives --config python3

# pip도 동일하게 설정
sudo alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.9 1
sudo alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 2
sudo alternatives --config pip3
```

#### 방법 2: pyenv 사용 (개발자 권장)

```bash
# pyenv 설치를 위한 의존성 패키지 설치
sudo dnf install -y make gcc gcc-c++ zlib-devel bzip2-devel readline-devel \
    sqlite-devel openssl-devel tk-devel libffi-devel xz-devel

# pyenv 설치
curl https://pyenv.run | bash

# 쉘 설정 추가
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc

# 쉘 재시작
exec "$SHELL"

# 또는 현재 세션에 적용
source ~/.bashrc

# 설치 가능한 Python 버전 확인
pyenv install --list | grep "3.11"

# Python 3.11 최신 버전 설치
pyenv install 3.11.9

# 전역 Python 버전을 3.11로 설정
pyenv global 3.11.9

# 버전 확인
python --version
python3 --version
# 출력: Python 3.11.9
```

#### 설치 후 확인

```bash
# Python 버전 확인
python3 --version

# pip 버전 확인
pip3 --version

# Python 3.11 특정 기능 테스트
python3 -c "import sys; print(f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
```

## 2. Docker 개발 환경 구성

### 2.1 Docker 설치

```bash
# Amazon Linux의 기본 저장소에서 Docker 설치
sudo dnf install -y docker

# Docker 서비스 시작 및 자동 시작 설정
sudo systemctl start docker
sudo systemctl enable docker

# Docker 버전 확인
docker --version
```

### 2.2 Docker Compose Plugin 설치

```bash
# Docker CLI 플러그인 디렉토리 생성
sudo mkdir -p /usr/local/lib/docker/cli-plugins

# Docker Compose Plugin 다운로드 및 설치
sudo curl -SL https://github.com/docker/compose/releases/download/v2.39.2/docker-compose-linux-x86_64 -o /usr/local/lib/docker/cli-plugins/docker-compose

# 실행 권한 부여
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# 버전 확인
docker compose version

# 기존 docker-compose (하이픈 버전)도 설치 (호환성을 위해)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# 버전 확인
docker-compose --version
```

### 2.3 Docker 사용자 그룹 설정

```bash
# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER

# 그룹 변경 적용 방법들:
# 방법 1: 새로운 쉘 세션 시작 (권장)
newgrp docker

# 방법 2: 완전한 새 로그인 세션 (가장 확실함)
# 터미널 종료 후 다시 SSH 접속

# 방법 3: 새 사용자 세션 시작
exec su - $USER

# Docker 그룹 적용 확인
groups
id

# Docker 동작 확인
docker run hello-world

# 권한 문제가 지속될 경우 임시로 sudo 사용
sudo docker run hello-world
```

## 3. Node.js 환경 설정 (프론트엔드 구축 필요시)

### 3.1 Node.js 설치

```bash
# NodeSource 저장소 추가
curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -

# Node.js 설치
sudo dnf install -y nodejs

# 버전 확인
node --version
npm --version
```

### 3.2 NVM (Node Version Manager) 설치

```bash
# NVM 설치
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# 쉘 재시작 또는 source 명령 실행
source ~/.bashrc

# NVM 버전 확인
nvm --version

# 최신 LTS Node.js 설치
nvm install --lts
nvm use --lts
```

## 4. Python 가상환경 설정

### 4.1 프로젝트 환경 구성

```bash
# 프로젝트 디렉토리로 이동
cd ~/wkms-aws

# Python 가상환경 생성 (Python 3.11 사용)
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate

# 가상환경에서 Python 버전 확인
python --version
# 출력: Python 3.11.x

# pip 업그레이드
pip install --upgrade pip

# 필요시 wheel과 setuptools 업데이트
pip install --upgrade wheel setuptools
```

**참고**: pyenv를 사용한 경우, 가상환경 생성 시 자동으로 설정된 Python 3.11이 사용됩니다.

### 4.2 가상환경 사용법

```bash
# 가상환경 활성화
source .venv/bin/activate

# 가상환경 비활성화
deactivate

# 설치된 패키지 확인
pip list

# requirements.txt에서 패키지 설치
pip install -r requirements.txt
```

## 5. 파일 뷰어 & 변환 환경 설치

### 5.1 LibreOffice Headless 설치

파일 변환 및 뷰어 기능을 위한 LibreOffice를 설치합니다. Amazon Linux 2023에서는 EPEL 저장소를 통해 설치할 수 있습니다.

#### 5.1.1 EPEL 저장소 활성화 및 LibreOffice 설치

```bash
# EPEL 저장소 활성화
sudo dnf install -y epel-release

# 시스템 업데이트
sudo dnf update -y

# LibreOffice 코어 패키지 설치
sudo dnf install -y libreoffice-core libreoffice-writer libreoffice-calc libreoffice-impress

# 추가 LibreOffice 구성 요소
sudo dnf install -y libreoffice-headless libreoffice-java-common

# Java Runtime Environment 설치 (LibreOffice에 필요)
sudo dnf install -y java-11-openjdk java-11-openjdk-headless
```

#### 5.1.2 LibreOffice 설치 확인

```bash
# 설치 경로 확인
which libreoffice
# 출력: /usr/bin/libreoffice

which soffice
# 출력: /usr/bin/soffice

# LibreOffice 버전 확인
libreoffice --version
# 예상 출력: LibreOffice 7.x.x.x

# Headless 모드 테스트
libreoffice --headless --version

# Java 버전 확인
java -version
```

#### 5.1.3 LibreOffice 변환 테스트

```bash
# 테스트용 간단한 텍스트 파일 생성
echo "LibreOffice 변환 테스트" > test.txt

# 텍스트를 PDF로 변환 테스트
libreoffice --headless --convert-to pdf test.txt

# 변환된 파일 확인
ls -la test.pdf

# 테스트 파일 정리
rm test.txt test.pdf
```

### 5.2 한글 폰트 설치

한글 문서 처리를 위한 폰트를 설치합니다.

#### 5.2.1 기본 한글 폰트 설치

```bash
# 폰트 디렉토리 생성
sudo mkdir -p /usr/share/fonts/truetype/korean

# Google Noto 한글 폰트 다운로드 및 설치
cd /tmp
wget https://github.com/google/fonts/raw/main/ofl/notosanscjkkr/NotoSansCJKkr%5Bwght%5D.ttf
wget https://github.com/google/fonts/raw/main/ofl/notoserifcjkkr/NotoSerifCJKkr%5Bwght%5D.ttf

# 폰트 파일 이동
sudo mv "NotoSansCJKkr[wght].ttf" /usr/share/fonts/truetype/korean/NotoSansCJKkr.ttf
sudo mv "NotoSerifCJKkr[wght].ttf" /usr/share/fonts/truetype/korean/NotoSerifCJKkr.ttf

# 폰트 권한 설정
sudo chmod 644 /usr/share/fonts/truetype/korean/*.ttf

# 폰트 캐시 업데이트
sudo fc-cache -fv

# 설치된 한글 폰트 확인
fc-list | grep -i noto
fc-list | grep -i korean
```

#### 5.2.2 추가 한글 폰트 설치 (선택사항)

```bash
# 나눔폰트 설치 (epel-release 저장소에서 제공)
sudo dnf search fonts-nanum
sudo dnf install -y fonts-nanum*

# 폰트 캐시 다시 업데이트
sudo fc-cache -fv

# 설치된 나눔폰트 확인
fc-list | grep -i nanum
```

#### 5.2.3 폰트 설치 확인

```bash
# 시스템에 설치된 모든 폰트 목록 확인
fc-list | wc -l

# 한글 폰트만 확인
fc-list | grep -E "(Noto|Nanum|Korean)" | head -10

# 특정 언어 지원 폰트 확인
fc-list :lang=ko
```

### 5.3 LibreOffice 한글 문서 처리 테스트

#### 5.3.1 한글 문서 변환 테스트

```bash
# 한글 텍스트 파일 생성
cat > korean_test.txt << EOF
안녕하세요!
LibreOffice 한글 문서 변환 테스트입니다.
한국어 처리가 정상적으로 작동하는지 확인합니다.
EOF

# 한글 문서를 PDF로 변환
libreoffice --headless --convert-to pdf korean_test.txt

# 변환 결과 확인
ls -la korean_test.pdf
file korean_test.pdf

# 테스트 파일 정리
rm korean_test.txt korean_test.pdf
```

#### 5.3.2 LibreOffice 환경 변수 설정 (선택사항)

```bash
# LibreOffice 환경 설정을 위한 profile 추가
sudo tee /etc/profile.d/libreoffice.sh << 'EOF'
export SAL_USE_VCLPLUGIN=svp
export LIBGL_ALWAYS_SOFTWARE=1
EOF

# 환경 변수 즉시 적용
source /etc/profile.d/libreoffice.sh

# 환경 변수 확인
echo $SAL_USE_VCLPLUGIN
echo $LIBGL_ALWAYS_SOFTWARE
```

## 6. 추가 도구 설치 (선택사항)

### 6.1 AWS CLI 설치

```bash
# AWS CLI v2 설치
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# 버전 확인
aws --version
```

### 5.2 PostgreSQL 클라이언트 설치 (필요시)

```bash
# PostgreSQL 클라이언트 설치
sudo dnf install -y postgresql15

# 버전 확인
psql --version
```

### 5.3 Redis 설치 (필요시)

```bash
# EPEL 저장소 활성화
sudo dnf install -y epel-release

# Redis 설치
sudo dnf install -y redis

# Redis 서비스 시작
sudo systemctl start redis
sudo systemctl enable redis

# Redis 연결 테스트
redis-cli ping
```

## 7. 환경 검증

### 7.1 설치된 도구 버전 확인

```bash
# 시스템 정보
cat /etc/os-release

# Python
python3 --version

# Docker
docker --version
docker-compose --version

# Node.js (설치한 경우)
node --version
npm --version

# Git
git --version

# LibreOffice
libreoffice --version

# Java
java -version

# AWS CLI (설치한 경우)
aws --version
```

### 7.2 LibreOffice 및 폰트 테스트

```bash
# Docker 컨테이너 실행 테스트
docker run --rm hello-world

# Docker Compose 테스트 (docker-compose.yml이 있는 경우)
cd ~/wkms-aws
docker-compose --version
```

## 8. 프로젝트 실행

### 8.1 백엔드 실행

```bash
cd ~/wkms-aws

# 개발 서버 실행 (Docker Compose 기반)
./shell-script/dev-start-backend.sh
```

### 8.2 프론트엔드 실행 (필요시)

```bash
cd ~/wkms-aws/frontend
npm install
npm start
```

### 8.3 전체 서비스 실행

```bash
cd ~/wkms-aws

# 전체 개발 환경 시작
./dev-start-all.sh

# 데이터베이스만 시작
./dev-start-db.sh
```

## 9. 주의사항

### 9.1 Amazon Linux 2023 특징

- 패키지 매니저: `dnf` (yum 호환)
- Python 기본 버전: 3.9.x (3.11로 업그레이드 권장)
- Docker 설치가 간단함 (기본 저장소 제공)
- systemd 사용

### 9.2 LibreOffice 관련 주의사항

```bash
# LibreOffice headless 모드에서 메모리 사용량이 클 수 있음
# 대용량 파일 처리 시 시스템 리소스 모니터링 필요

# 폰트 관련 문제 발생 시
sudo fc-cache -fv  # 폰트 캐시 재생성

# LibreOffice 프로세스가 남아있을 경우 강제 종료
pkill -f libreoffice
pkill -f soffice
```

### 9.3 권한 관련

```bash
# Docker 그룹 추가 후 재로그인이 필요할 수 있음
# 또는 다음 명령으로 즉시 적용
newgrp docker
```

### 9.4 방화벽 설정 (필요시)

```bash
# 방화벽 상태 확인
sudo systemctl status firewalld

# 포트 열기 (예: 8000번 포트)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## 10. 문제 해결

### 10.1 일반적인 문제

- **Docker 권한 오류**: `sudo usermod -aG docker $USER` 후 완전한 재로그인 또는 `exec su - $USER`
- **Docker 권한이 지속적으로 문제가 될 경우**: 임시로 `sudo docker` 명령어 사용
- **Docker Compose 명령어 오류**: `docker compose` (공백)과 `docker-compose` (하이픈) 둘 다 설치 확인
- **Python 패키지 설치 오류**: 개발 도구 그룹이 설치되었는지 확인
- **포트 접근 불가**: 방화벽 설정 확인
- **Python 3.11 설치 후 가상환경 오류**: `python3 -m venv` 대신 `python3.11 -m venv` 사용
- **pyenv 설치 후 명령어 인식 안됨**: 쉘 재시작 또는 `source ~/.bashrc` 실행
- **LibreOffice 변환 오류**: Java가 제대로 설치되었는지 확인
- **한글 폰트 깨짐**: 폰트 캐시 재생성 (`sudo fc-cache -fv`)

### 10.2 Docker 관련 문제해결

```bash
# Docker 서비스 상태 확인
sudo systemctl status docker

# Docker 그룹 확인
groups
id

# Docker 소켓 권한 확인
ls -la /var/run/docker.sock

# Docker 권한 문제 해결 방법들
# 1. 사용자 그룹 재설정
sudo usermod -aG docker $USER

# 2. 완전한 새 세션 시작
exec su - $USER

# 3. 임시 해결책 - sudo 사용
sudo docker ps
sudo docker compose ps

# Docker 로그 확인
sudo journalctl -u docker --since "1 hour ago"

# Docker 데몬 재시작 (필요시)
sudo systemctl restart docker
```

### 10.3 LibreOffice 관련 문제해결

```bash
# LibreOffice 설치 확인
rpm -qa | grep libreoffice

# Java 설치 확인
java -version

# 폰트 목록 확인
fc-list | grep -i korean

# LibreOffice 환경변수 확인
echo $SAL_USE_VCLPLUGIN

# LibreOffice 프로세스 확인
ps aux | grep libreoffice
```

### 10.4 로그 확인

```bash
# Docker 로그
sudo journalctl -u docker

# 서비스 상태 확인
sudo systemctl status docker
```

---

이 가이드는 Amazon Linux 2023.8.20250818 기준으로 작성되었습니다.
