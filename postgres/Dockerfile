# PostgreSQL with pgvector, textsearch_ko (Mecab), and kor_search extensions
# Using PostgreSQL 15 for extension compatibility
FROM postgres:15

ENV DEBIAN_FRONTEND=noninteractive

# Install locales first and configure Korean locale properly
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends locales; \
    # Add Korean locale to locale.gen and generate it
    echo "ko_KR.UTF-8 UTF-8" >> /etc/locale.gen; \
    echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen; \
    locale-gen; \
    update-locale LANG=ko_KR.UTF-8; \
    # Verify locale is available
    locale -a | grep ko_KR

# Set Korean locale environment variables
ENV LANG=ko_KR.UTF-8
ENV LC_ALL=ko_KR.UTF-8
ENV LC_CTYPE=ko_KR.UTF-8

# Install build dependencies and compile extensions
RUN set -eux; \
    apt-get install -y --no-install-recommends \
    build-essential \
    git \
    wget \
    curl \
    ca-certificates \
    postgresql-server-dev-15 \
    automake \
    libtool \
    pkg-config \
    libmecab-dev \
    unzip; \
    update-ca-certificates; \
    \
    # pgvector
    git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git /tmp/pgvector; \
    cd /tmp/pgvector; \
    make; \
    make install; \
    cd /; \
    rm -rf /tmp/pgvector; \
    \
    # Mecab (core)
    wget --no-check-certificate https://bitbucket.org/eunjeon/mecab-ko/downloads/mecab-0.996-ko-0.9.2.tar.gz -O /tmp/mecab.tar.gz; \
    cd /tmp; \
    tar -xzf mecab.tar.gz; \
    cd mecab-0.996-ko-0.9.2; \
    ./configure CC=gcc CXX=g++ CFLAGS="-O2" CXXFLAGS="-O2"; \
    make; \
    make install; \
    ldconfig; \
    \
    # Mecab Korean dictionary
    cd /tmp; \
    wget --no-check-certificate https://bitbucket.org/eunjeon/mecab-ko-dic/downloads/mecab-ko-dic-2.1.1-20180720.tar.gz -O mecab-ko-dic.tar.gz; \
    tar -xzf mecab-ko-dic.tar.gz; \
    cd mecab-ko-dic-2.1.1-20180720; \
    ./autogen.sh; \
    ./configure; \
    make; \
    make install; \
    ldconfig; \
    \
    # textsearch_ko (PostgreSQL extension wrapping Mecab)
    git clone https://github.com/i0seph/textsearch_ko.git /tmp/textsearch_ko; \
    cd /tmp/textsearch_ko; \
    make USE_PGXS=1; \
    make USE_PGXS=1 install; \
    \
    # kor_search extension (with error handling)
    git clone https://github.com/junhkang/kor_search.git /tmp/kor_search; \
    cd /tmp/kor_search; \
    make; \
    make install; \
    \
    # Cleanup
    cd /; \
    rm -rf /tmp/*; \
    apt-get purge -y --auto-remove \
    build-essential \
    git \
    wget \
    curl \
    automake \
    libtool \
    pkg-config \
    postgresql-server-dev-15 \
    unzip; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

# Initialization scripts
COPY init.sql /docker-entrypoint-initdb.d/20_init.sql