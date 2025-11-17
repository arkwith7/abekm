# Azure Functions의 Python 런타임 이미지
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

# LibreOffice 설치
RUN apt-get update && \
    apt-get install -y libreoffice && \
    apt-get clean

# 작업 디렉토리 설정
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

COPY requirements.txt /requirements.txt
# COPY environment.yml /environment.yml
COPY pyrfc-3.3.1-cp311-cp311-linux_x86_64.whl /pyrfc-3.3.1-cp311-cp311-linux_x86_64.whl
COPY functions /home/site/wwwroot

# RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O conda-install.sh && \
#     chmod 755 conda-install.sh && \
#     sh conda-install.sh -b -p $HOME/miniconda && \
#     rm -f conda-install.sh

# ENV PATH="${HOME}/miniconda/bin:${PATH}"

# RUN conda init bash && \
#     conda env update --name base --file /environment.yml && \
#     pip install -r /requirements.txt

RUN pip install -r /requirements.txt
