# 베이스 이미지를 postgres 16 버전으로 지정
FROM postgres:16

# pgvector 설치 (root 권한으로 실행)
# Debian 패키지 리스트를 업데이트하고 postgresql-16-pgvector 패키지를 설치
RUN apt-get update && apt-get install -y postgresql-16-pgvector

