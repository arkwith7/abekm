from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from azure.core.exceptions import *

from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceExistsError

from datetime import datetime, timedelta, timezone

import mysql.connector
from mysql.connector import errorcode

import pandas as pd

import requests
import msal
import yaml
import io
import json
import os
import ast

from tools import count_keywords, make_query_filter

class AzureMySQL:
    def __init__(self, logger):
        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        # Construct connection string

        self.db_name = config['mysql']['database']
        self.connection_config = {
            'host' : config['mysql']['host'],
            'user' : config['mysql']['user'],
            'password' : config['mysql']['password'],
            'database' : config['mysql']['database'],
            }
        
        self.logger = logger

    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.connection_config)
            self.logger.info("Connection established")

        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                self.logger.error("Something is wrong with the user name or password")
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                self.logger.error("Database does not exist")
            else:
                self.logger.error(err)

        else:
            cursor = conn.cursor(dictionary=True)
        
        return conn, cursor
    
    def close_connection(self, conn, cursor):
        cursor.close()
        conn.close()

    def select_file_total_info(self, conn, cursor, file_psl_nm):
        self.logger.info('================ Get file detail info ================')
        # columns = ['FILE_BSS_INFO_SNO', 'DRCY_SNO', 'FILE_DTL_INFO_SNO', 'FILE_LGC_NM', 'FILE_PSL_NM', 'PATH', 'DEL_YN', 'SJ', 'CN', 'KW', 'CTG_LVL1_NM', 'CTG_LVL2_NM', 'FORMATTED_CREATED_DATE', 'FORMATTED_LAST_MODIFIED_DATE']
        file_bss_dtl_query = f'''
                            WITH RECURSIVE category_hierarchy AS (
                                SELECT 
                                    ITEM_ID,
                                    ITEM_NM,
                                    REF_ITEM_ID,
                                    1 as LEVEL
                                FROM {self.db_name}.tb_cmns_cd_grp_item
                                WHERE REF_ITEM_ID IS NULL

                                UNION ALL

                                SELECT 
                                    i.ITEM_ID,
                                    i.ITEM_NM,
                                    i.REF_ITEM_ID,
                                    h.LEVEL + 1
                                FROM {self.db_name}.tb_cmns_cd_grp_item i
                                INNER JOIN category_hierarchy h ON i.REF_ITEM_ID = h.ITEM_ID
                            )
                            SELECT 
                                bss.FILE_BSS_INFO_SNO,
                                bss.DRCY_SNO,
                                bss.FILE_DTL_INFO_SNO,
                                bss.FILE_LGC_NM,
                                bss.FILE_PSL_NM,
                                bss.FILE_EXTSN,
                                bss.PATH,
                                bss.DEL_YN,
                                dtl.SJ,
                                dtl.CN,
                                dtl.KW,
                                cat1.ITEM_NM AS CTG_LVL1_NM,
                                cat2.ITEM_NM AS CTG_LVL2_NM,
                                hri_crt.USER_FNM AS CREATED_BY,
                                hri_mod.USER_FNM AS LAST_MODIFIED_BY,
                                DATE_FORMAT(COALESCE(bss.CREATED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_CREATED_DATE,
                                DATE_FORMAT(COALESCE(bss.LAST_MODIFIED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_LAST_MODIFIED_DATE
                            FROM 
                                {self.db_name}.tb_file_bss_info bss
                                INNER JOIN {self.db_name}.tb_file_dtl_info dtl
                                    ON bss.FILE_DTL_INFO_SNO = dtl.FILE_DTL_INFO_SNO
                                LEFT JOIN category_hierarchy cat2
                                    ON dtl.CTG_LVL2 = cat2.ITEM_ID
                                LEFT JOIN category_hierarchy cat1
                                    ON dtl.CTG_LVL1 = cat1.ITEM_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_crt
                                    ON bss.CREATED_BY = hri_crt.USER_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_mod
                                    ON bss.LAST_MODIFIED_BY = hri_mod.USER_ID
                            WHERE 
                                bss.FILE_PSL_NM = "{file_psl_nm}";
                        '''
        # Read data
        cursor.execute(file_bss_dtl_query)
        file_info = cursor.fetchone()

        self.logger.info(f"================== DB FILE INFO: {file_info}")

        file_info['KW'] = ast.literal_eval(file_info['KW'])
        file_info['KW'] = [value["keyword"] for value in list(file_info['KW'])]
        file_info['DEL_YN'] = True if file_info['DEL_YN'] =='Y' else False


        # Cleanup
        conn.commit()

        return file_info
    
    def select_file_info_bss_sno(self, conn, cursor, file_bss_info_sno):
        self.logger.info('================ Get file detail info ================')
        # columns = ['FILE_BSS_INFO_SNO', 'DRCY_SNO', 'FILE_DTL_INFO_SNO', 'FILE_LGC_NM', 'FILE_PSL_NM', 'PATH', 'DEL_YN', 'SJ', 'CN', 'KW', 'CTG_LVL1_NM', 'CTG_LVL2_NM', 'FORMATTED_CREATED_DATE', 'FORMATTED_LAST_MODIFIED_DATE']
        file_bss_dtl_query = f'''
                            WITH RECURSIVE category_hierarchy AS (
                                SELECT 
                                    ITEM_ID,
                                    ITEM_NM,
                                    REF_ITEM_ID,
                                    1 as LEVEL
                                FROM {self.db_name}.tb_cmns_cd_grp_item
                                WHERE REF_ITEM_ID IS NULL

                                UNION ALL

                                SELECT 
                                    i.ITEM_ID,
                                    i.ITEM_NM,
                                    i.REF_ITEM_ID,
                                    h.LEVEL + 1
                                FROM {self.db_name}.tb_cmns_cd_grp_item i
                                INNER JOIN category_hierarchy h ON i.REF_ITEM_ID = h.ITEM_ID
                            )
                            SELECT 
                                bss.FILE_BSS_INFO_SNO,
                                bss.DRCY_SNO,
                                bss.FILE_DTL_INFO_SNO,
                                bss.FILE_LGC_NM,
                                bss.FILE_PSL_NM,
                                bss.FILE_EXTSN,
                                bss.PATH,
                                bss.DEL_YN,
                                dtl.SJ,
                                dtl.CN,
                                dtl.KW,
                                cat1.ITEM_NM AS CTG_LVL1_NM,
                                cat2.ITEM_NM AS CTG_LVL2_NM,
                                hri_crt.USER_FNM AS CREATED_BY,
                                hri_mod.USER_FNM AS LAST_MODIFIED_BY,
                                DATE_FORMAT(COALESCE(bss.CREATED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_CREATED_DATE,
                                DATE_FORMAT(COALESCE(bss.LAST_MODIFIED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_LAST_MODIFIED_DATE
                            FROM 
                                {self.db_name}.tb_file_bss_info bss
                                INNER JOIN {self.db_name}.tb_file_dtl_info dtl
                                    ON bss.FILE_DTL_INFO_SNO = dtl.FILE_DTL_INFO_SNO
                                LEFT JOIN category_hierarchy cat2
                                    ON dtl.CTG_LVL2 = cat2.ITEM_ID
                                LEFT JOIN category_hierarchy cat1
                                    ON dtl.CTG_LVL1 = cat1.ITEM_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_crt
                                    ON bss.CREATED_BY = hri_crt.USER_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_mod
                                    ON bss.LAST_MODIFIED_BY = hri_mod.USER_ID
                            WHERE 
                                bss.FILE_BSS_INFO_SNO = "{file_bss_info_sno}";
                        '''
        # Read data
        cursor.execute(file_bss_dtl_query)
        file_info = cursor.fetchone()

        self.logger.info(f"================== DB FILE INFO: {file_info}")

        file_info['KW'] = ast.literal_eval(file_info['KW'])
        file_info['KW'] = [value["keyword"] for value in list(file_info['KW'])]
        file_info['DEL_YN'] = True if file_info['DEL_YN'] =='Y' else False


        # Cleanup
        conn.commit()

        return file_info
    
    def select_one_bss_info(self, conn, cursor, file_lgc_nm):
        self.logger.info('================ Get file detail info ================')
        # columns = ['FILE_BSS_INFO_SNO', 'DRCY_SNO', 'FILE_DTL_INFO_SNO', 'FILE_LGC_NM', 'FILE_PSL_NM', 'PATH', 'DEL_YN', 'SJ', 'CN', 'KW', 'CTG_LVL1_NM', 'CTG_LVL2_NM', 'FORMATTED_CREATED_DATE', 'FORMATTED_LAST_MODIFIED_DATE']
        file_bss_dtl_query = f'''
                            SELECT 
                                bss.FILE_BSS_INFO_SNO,
                                bss.DRCY_SNO,
                                bss.FILE_DTL_INFO_SNO,
                                bss.FILE_LGC_NM,
                                bss.FILE_PSL_NM,
                                bss.FILE_EXTSN,
                                bss.PATH,
                                bss.DEL_YN
                            FROM 
                                {self.db_name}.tb_file_bss_info bss
                            WHERE 
                                bss.FILE_LGC_NM = "{file_lgc_nm}"
                            AND
                                bss.DEL_YN = "N";
                        '''
        # Read data
        cursor.execute(file_bss_dtl_query)
        file_info = cursor.fetchone()

        self.logger.info(f"================== DB FILE INFO: {file_info}")

        file_info['KW'] = ast.literal_eval(file_info['KW'])
        file_info['KW'] = [value["keyword"] for value in list(file_info['KW'])]
        file_info['DEL_YN'] = True if file_info['DEL_YN'] =='Y' else False


        # Cleanup
        conn.commit()

        return file_info

    
    def select_all_file_info(self, conn, cursor, time_span):
        '''
        description: timer용 전체 가져오는 함수, 5분 간격 실행하는 코드라 여유까지 포함 10분전까지의 데이터를 가져오도록 쿼리
        '''
        self.logger.info('================ Get file detail info ================')
        # columns = ['FILE_BSS_INFO_SNO', 'DRCY_SNO', 'FILE_DTL_INFO_SNO', 'FILE_LGC_NM', 'FILE_PSL_NM', 'PATH', 'DEL_YN', 'SJ', 'CN', 'KW', 'CTG_LVL1_NM', 'CTG_LVL2_NM', 'FORMATTED_CREATED_DATE', 'FORMATTED_LAST_MODIFIED_DATE']
        file_bss_dtl_query = f'''
                            WITH RECURSIVE category_hierarchy AS (
                                SELECT 
                                    ITEM_ID,
                                    ITEM_NM,
                                    REF_ITEM_ID,
                                    1 as LEVEL
                                FROM {self.db_name}.tb_cmns_cd_grp_item
                                WHERE REF_ITEM_ID IS NULL

                                UNION ALL

                                SELECT 
                                    i.ITEM_ID,
                                    i.ITEM_NM,
                                    i.REF_ITEM_ID,
                                    h.LEVEL + 1
                                FROM {self.db_name}.tb_cmns_cd_grp_item i
                                INNER JOIN category_hierarchy h ON i.REF_ITEM_ID = h.ITEM_ID
                            )
                            SELECT 
                                bss.FILE_BSS_INFO_SNO,
                                bss.DRCY_SNO,
                                bss.FILE_DTL_INFO_SNO,
                                bss.FILE_LGC_NM,
                                bss.FILE_PSL_NM,
                                bss.FILE_EXTSN,
                                bss.PATH,
                                bss.DEL_YN,
                                dtl.SJ,
                                dtl.CN,
                                dtl.KW,
                                cat1.ITEM_NM AS CTG_LVL1_NM,
                                cat2.ITEM_NM AS CTG_LVL2_NM,
                                hri_crt.USER_FNM AS CREATED_BY,
                                hri_mod.USER_FNM AS LAST_MODIFIED_BY,
                                DATE_FORMAT(COALESCE(bss.CREATED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_CREATED_DATE,
                                DATE_FORMAT(COALESCE(bss.LAST_MODIFIED_DATE, CURRENT_TIMESTAMP), 
                                        '%Y-%m-%dT%H:%i:%s.000Z') AS FORMATTED_LAST_MODIFIED_DATE
                            FROM 
                                {self.db_name}.tb_file_bss_info bss
                                INNER JOIN {self.db_name}.tb_file_dtl_info dtl
                                    ON bss.FILE_DTL_INFO_SNO = dtl.FILE_DTL_INFO_SNO
                                LEFT JOIN category_hierarchy cat2
                                    ON dtl.CTG_LVL2 = cat2.ITEM_ID
                                LEFT JOIN category_hierarchy cat1
                                    ON dtl.CTG_LVL1 = cat1.ITEM_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_crt
                                    ON bss.CREATED_BY = hri_crt.USER_ID
                                LEFT JOIN {self.db_name}.tb_sap_hr_info hri_mod
                                    ON bss.LAST_MODIFIED_BY = hri_mod.USER_ID
                            WHERE bss.LAST_MODIFIED_DATE >= NOW() - INTERVAL {time_span} MINUTE;
                        '''
        # Read data
        cursor.execute(file_bss_dtl_query)
        file_info_rows = cursor.fetchall()

        renewed_rows = []

        for i, file_info in enumerate(file_info_rows):
            file_info['KW'] = ast.literal_eval(file_info['KW'])
            file_info['KW'] = [value["keyword"] for value in list(file_info['KW'])]
            file_info['DEL_YN'] = True if file_info['DEL_YN'] =='Y' else False

            renewed_rows.append(file_info)


        # Cleanup
        conn.commit()

        return renewed_rows


        

class AzureStorage:

    def __init__(self, logger, type, container_name, storage_type = None):
        
        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        self.ai_account_key = config["storage"]["ai"]["account_key"]
        self.ai_account_name = config["storage"]["ai"]["account_name"]
        self.ai_account_str = config["storage"]["ai"]["account_str"]

        self.web_account_key = config["storage"]["web"]["account_key"]
        self.web_account_name = config["storage"]["web"]["account_name"]
        self.web_account_str = config["storage"]["web"]["account_str"]
        self.web_account_raw_folder = config["storage"]["web"]["raw_folder"]
        
        self.logger = logger
        self.type = type

        # client 초기화
        self.ai_blob_service_client = BlobServiceClient.from_connection_string(self.ai_account_str)
        self.web_blob_service_client = BlobServiceClient.from_connection_string(self.web_account_str)
        self.container_name = container_name
        try : 
            if type == 'ai':
                self.ai_container_client = self.ai_blob_service_client.get_container_client(self.container_name)
            else:
                self.web_container_client = self.web_blob_service_client.get_container_client(self.container_name)
            self.logger.info(f"Container connection completed \nContainer name : {container_name}")
        
        except Exception as e :
            self.logger.error(f"Container connection error \nContainer name : {container_name} \nError message : {str(e)}")

    # web 업로드 폴더 내 전체 blob 목록
    def list_all_blobs(self):
        """
        Azure Blob Storage 컨테이너 내의 모든 파일 목록을 가져옵니다.

        Returns:
            list: 파일 정보를 담은 딕셔너리 리스트
        """
        try:
            ext = ['docx', 'pptx', 'xlsx', 'pdf']
            ext_count = 0
            # 모든 blob 리스트 가져오기
            blob_list = []
            for blob in self.web_container_client.list_blobs():
                if blob.name.split('/')[0] == self.web_account_raw_folder:
                    if blob.content_settings.content_type:
                        blob_info = {
                            'name': os.path.splitext(os.path.basename(blob.name))[0],
                            'file_extension': os.path.splitext(os.path.basename(blob.name))[1][1:],
                            'size': blob.size,
                            'last_modified': blob.last_modified,
                            'creation_time': blob.creation_time,
                            'content_type': blob.content_settings.content_type
                        }

                        if blob_info['file_extension'] in ext:
                            ext_count += 1
                    
                        blob_list.append(blob_info)
                
            return blob_list, ext_count
        
        except ResourceNotFoundError:
            print(f"컨테이너를 찾을 수 없습니다: {self.container_name}")
            return []
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            return []
    
    # 파일 다운로드
    def download_file(self, file_path):
        try:
            file_client = self.web_container_client.get_blob_client(file_path)
            file_name = os.path.basename(file_path)

            download_file_path = os.path.join('/tmp', file_name)
            self.logger.info(download_file_path)

            with open(file=download_file_path, mode="wb") as temp_blob:
                download_stream = file_client.download_blob()
                temp_blob.write(download_stream.readall())

            return download_file_path
        
        except Exception as e:
            self.logger.error(f"File load error \nPath : {file_path} \nError message : {str(e)}")
            return print("Error")


    # 파일 읽기
    def read_file(self, file_path, sheet_name=None):
        self.logger.info("###### Function Name : read_file")
        try:
            if self.type == 'ai':
                file_client = self.ai_container_client.get_blob_client(file_path)
            else:
                file_client = self.web_container_client.get_blob_client(file_path)

            if file_path.split('.')[-1] == 'xlsx' or file_path.split('.')[-1] == 'csv':
                download = file_client.download_blob()
                downloaded_bytes = download.readall()
                return downloaded_bytes
                # with io.BytesIO() as blob_io:
                #     file_client.download_blob().readinto(blob_io)
                #     blob_io.seek(0)
                #     if file_path.split('.')[-1] == 'xlsx' : 
                #         file = pd.read_excel(blob_io, sheet_name=sheet_name if sheet_name is not None else 0)
                #     else :
                #         file = pd.read_csv(blob_io)
                # self.logger.info(f"File load completed \nPath : {file_path}")
                # return file
            
            elif (file_path.split('.')[-1] == 'pdf') :
                download = file_client.download_blob()
                file = io.BytesIO(download.readall())
                print(type(file))
                self.logger.info(f"File load completed \nPath : {file_path}")
                return file
            
            elif (file_path.split('.')[-1] == 'pptx') or (file_path.split('.')[-1] == 'doc'):
                download = file_client.download_blob()
                downloaded_bytes = download.readall()
                return downloaded_bytes
            
            elif file_path.split('.')[-1] == 'json' : 
                download = file_client.download_blob()
                file = download.readall().decode("utf-8")
                json_data = json.loads(file)
                self.logger.info(f"File load completed \nPath : {file_path}")
                return json_data
            
            else:
                download = file_client.download_blob()
                downloaded_bytes = download.readall()
                self.logger.info(f"File load completed \nPath : {file_path}")
                return downloaded_bytes.decode("utf-8")

        except Exception as e:
            self.logger.error(f"File load error \nPath : {file_path} \nError message : {str(e)}")
            return print("Error")

    # 파일 sas url 발급
    def get_sas_url(self, blob_path, expiry_time=True):
        self.logger.info("###### Function Name : get_sas_url")
        blob_path = '/'.join(blob_path.split('/')[1:])
        blob_client = self.web_container_client.get_blob_client(blob_path)
        
        kst = timezone(timedelta(hours=9))
        start_time_kst = datetime.now(kst) - timedelta(minutes=5)
        start_time_utc = start_time_kst.astimezone(timezone.utc)
        
        if expiry_time:
            expiry_time_kst = start_time_kst + timedelta(days=1)
        else:
            expiry_time_kst = datetime(9999, 12, 31, tzinfo=kst)
        
        expiry_time_utc = expiry_time_kst.astimezone(timezone.utc)
        
        try:
            sas_token = generate_blob_sas(
                account_name=self.web_account_name,
                account_key=self.web_account_key,
                container_name=self.web_container_client.container_name,
                blob_name=blob_path,
                permission=BlobSasPermissions(read=True),
                start=start_time_utc,
                expiry=expiry_time_utc                  
            )
            sas_url = blob_client.url + '?' + sas_token
            self.logger.info(f"SAS URL issued completed \nUrl: {sas_url}")
            return sas_url

        except Exception as e:
            self.logger.error(f"SAS URL issued error \nUrl: {blob_client.url} \nError message: {str(e)}")
            return print(str(e))


    # 파일 sas url 발급
    def get_sas_url_inline(self, blob_path, expiry_time=True):
        self.logger.info("###### Function Name : get_sas_url")
        blob_client = self.ai_container_client.get_blob_client(blob_path)
        
        kst = timezone(timedelta(hours=9))
        start_time_kst = datetime.now(kst) - timedelta(minutes=5)
        start_time_utc = start_time_kst.astimezone(timezone.utc)
        
        if expiry_time:
            expiry_time_kst = start_time_kst + timedelta(days=1)
        else:
            expiry_time_kst = datetime(9999, 12, 31, tzinfo=kst)
        
        expiry_time_utc = expiry_time_kst.astimezone(timezone.utc)
        
        try:
            sas_token = generate_blob_sas(
                account_name=self.ai_account_name,
                account_key=self.ai_account_key,
                container_name=self.ai_container_client.container_name,
                blob_name=blob_path,
                permission=BlobSasPermissions(read=True),
                start=start_time_utc,
                expiry=expiry_time_utc,
                content_type = 'application/pdf',
                content_disposition="inline"  # 브라우저 미리보기 설정                  
            )
            sas_url = blob_client.url + '?' + sas_token
            self.logger.info(f"SAS URL issued completed \nUrl: {sas_url}")
            return sas_url

        except Exception as e:
            self.logger.error(f"SAS URL issued error \nUrl: {blob_client.url} \nError message: {str(e)}")
            return print(str(e))
    
    # blob 파일 리스트 읽기
    def extract_blob_list(self, blob_path, file_type=None) :
        self.logger.info("###### Function Name : extract_blob_list")
        if self.type == 'ai': 
            container_name = self.ai_container_client.container_name
            file_list = self.ai_container_client.list_blobs(name_starts_with=blob_path)
        else:
            container_name = self.web_container_client.container_name
            file_list = self.web_container_client.list_blobs(name_starts_with=blob_path)

        if file_type :
            filter_list = [item['name'] for item in file_list if f'.{file_type}' in item['name']]
            self.logger.info(f"File list extraction completed, File extension : {file_type} \nPath: {container_name}/{blob_path}")
            return filter_list
        else :
            file_list = [item['name'] for item in file_list]
            self.logger.info(f"File list extraction completed, File extension : ALL \nPath: {container_name}/{blob_path}")
            return file_list

    # 파일 업로드
    def upload_file(self, data, file_path, content_type=None, overwrite=False):
        self.logger.info("###### Function Name : upload_file")
        try:
            content_settings = None
            if content_type is not None:
                content_settings = ContentSettings(content_type=content_type)

            blob_client = self.ai_container_client.upload_blob(
                name=file_path,
                data=data,
                content_settings=content_settings,
                overwrite=overwrite
            )
            return self.logger.info(f"File upload completed, Path: {blob_client.url}")

        except ResourceExistsError as e:
            blob_client = self.ai_container_client.upload_blob(
                name=file_path,
                data=data,
                content_settings=content_settings,
                overwrite=overwrite
            )
            return self.logger.error(f"File already exists, Path: {blob_client.url}\n Please set the overwrite variable to True.")

        except Exception as e: 
            return self.logger.error(f"File upload error, Path: {file_path}\n Error message : {str(e)}")
        
    def upload_log(self, data, file_path, content_type=None):
        self.logger.info("###### Function Name : upload_log")
        try:
            content_settings = None
            if content_type is not None:
                content_settings = ContentSettings(content_type=content_type)

            blob_client = self.ai_container_client.get_blob_client(blob=file_path)

            if not blob_client.exists():
                blob_client.create_append_blob(content_settings=content_settings)
                self.logger.info("Created new append blob.")

            blob_client.append_block(data)
            return self.logger.info(f"File upload completed, Path: {blob_client.url}")
        except Exception as e:
            self.logger.error(f"Failed to upload file: {str(e)}")
            return None
        
    def copy_file(self, file_path, target_path):
        # Azure
        # Get this from Settings/Access keys in your Storage account on Azure portal
        account_name = "YOUR_AZURE_ACCOUNT_NAME"
        connection_string = "YOUR_AZURE_CONNECTION_STRING"

        # Source
        source_container_name = "sourcecontainer"
        source_file_path = "soure.jpg"
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        source_blob = (f"https://{account_name}.blob.core.windows.net/{source_container_name}/{source_file_path}")

        # Target
        target_container_name = "targetcontainer"
        target_file_path = "target.jpg"
        copied_blob = blob_service_client.get_blob_client(target_container_name, target_file_path)
        copied_blob.start_copy_from_url(source_blob)

        # If you would like to delete the source file
        remove_blob = blob_service_client.get_blob_client(source_container_name, source_file_path)
        remove_blob.delete_blob()
        return
        

class CosmosDB:

    def __init__(self, logger, database_name=None, container_name=None):
        self.logger = logger
        
        # 설정 파일 읽기
        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)
        
        self.account_url = config["cosmosdb"]["account_url"]
        self.account_key = config["cosmosdb"]["account_key"]

        self.cosmos_client = CosmosClient(url=self.account_url, credential=self.account_key)

        if database_name != None :
            self.database_client = self.cosmos_client.get_database_client(database_name)
            self.container_client = self.database_client.get_container_client(container_name)
        
        else :
            pass
    
    def upload_item(self, data):
        
        try:
            try:
                # Try to create the item
                self.container_client.create_item(body=data)
                self.logger.info(f"Item with id '{data['id']}' created successfully")
            except CosmosResourceExistsError:
                # If the item already exists, replace it (update it)
                self.container_client.replace_item(item=data['id'], body=data)
                self.logger.info(f"Item with id '{data['id']}' already exists, so it was updated successfully")

        except Exception as e:
            self.logger.info(f"An error occurred while processing item with id '{data['id']}': {str(e)}")
        
        return None
    
    def upsert_item(self, data):
        
        try:
            self.container_client.upsert_item(body=data)
            self.logger.info(f"Item with id '{data['id']}' upsert successfully")
        
        except Exception as e:
            self.logger.info(f"An error occurred while upserting item with id '{data['id']}': {e.message}")
        
        return None    
    
    def search(self, query_1, query_2, aoai_instance, num_results = 3, similarity_score = 0.02) :
        
        self.logger.info(query_2['filePhysicalName'])
        
        if len(query_2['filePhysicalName']) == 0 :

            keyword_list = [item.strip() for item in query_1['refinement']['keywords'].split(',')]

            results = self.container_client.query_items(query=f'''
                                                                SELECT DISTINCT(c.file_name)
                                                                FROM c
                                                                ''',
                                                                enable_cross_partition_query=True,
                                                                populate_query_metrics=True
                                                            )
            file_list = [item for item in results]
            max_count = 0
            best_match = None

            for item in file_list:
                file_name = item['file_name']
                keyword_count = count_keywords(file_name, keyword_list)
                
                if keyword_count > max_count:
                    max_count = keyword_count
                    best_match = file_name

            self.logger.info(f"============================== KEYWORD : {keyword_list}\n")
            self.logger.info(f"============================== KEYWORD COUNT : {best_match} ( {max_count} )\n")
            # keyword_conditions = ' OR '.join([f"LOWER(c.file_name) LIKE LOWER(@keyword{i})" for i in range(len(keyword_list))])
            question = query_1['refinement']['question']
            vector_question = aoai_instance.generate_embeddings(text=question)

            parameters = [{"name": f"@keyword{i}", "value": f"%{keyword}%" } for i, keyword in enumerate(keyword_list)]
            parameters.extend([
                {"name": "@embedding", "value": vector_question},
                {"name": "@num_results", "value": num_results},
                {"name": "@similarity_score", "value": similarity_score}
            ])

            if keyword_count >= 1 :

                results = self.container_client.query_items(
                    query=f'''
                    SELECT TOP @num_results c.id, c.file_name, c.chunk_name, c.main_text, VectorDistance(c.main_text_vector, @embedding) as SimilarityScore
                    FROM c
                    WHERE c.file_name = '{best_match}'
                    AND VectorDistance(c.main_text_vector,@embedding) > @similarity_score
                    ORDER BY VectorDistance(c.main_text_vector,@embedding)
                    ''',
                    parameters = parameters,
                    enable_cross_partition_query=True,
                    populate_query_metrics=True
                )
            
            else :
                results = self.container_client.query_items(
                    query=f'''
                    SELECT TOP @num_results c.id, c.file_name, c.chunk_name, c.main_text, VectorDistance(c.main_text_vector, @embedding) as SimilarityScore
                    FROM c
                    WHERE VectorDistance(c.main_text_vector,@embedding) > @similarity_score
                    ORDER BY VectorDistance(c.main_text_vector,@embedding)
                    ''',
                    parameters = parameters,
                    enable_cross_partition_query=True,
                    populate_query_metrics=True
                )
            results = list(results)
            formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results]

            # formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results if result.get('SimilarityScore', 0) > 0.8]
        
        else :

            question = query_1['refinement']['question']
            vector_question = aoai_instance.generate_embeddings(text=question)
            parameters=[{"name": "@embedding", "value": vector_question},
                        {"name": "@num_results", "value": num_results},
                        {"name": "@similarity_score", "value": similarity_score}]

            results = self.container_client.query_items(
            query=f'''
            SELECT TOP @num_results c.id, c.file_name, c.chunk_name, c.main_text, VectorDistance(c.main_text_vector, @embedding) as SimilarityScore
            FROM c
            WHERE c.file_name = '{query_2['filePhysicalName']}'
            AND VectorDistance(c.main_text_vector,@embedding) > @similarity_score
            ORDER BY VectorDistance(c.main_text_vector,@embedding)
            ''',
            
            parameters = parameters,
            enable_cross_partition_query=True,
            populate_query_metrics=True
            )
            
            results = list(results)
            formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results]

            # formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results if result.get('SimilarityScore', 0) > 0.8]

        if len(formatted_results) == 0:
            results = self.container_client.query_items(
                query=f'''
                SELECT TOP @num_results c.id, c.file_name, c.chunk_name, c.main_text, VectorDistance(c.main_text_vector, @embedding) as SimilarityScore
                FROM c
                WHERE VectorDistance(c.main_text_vector,@embedding) > @similarity_score
                ORDER BY VectorDistance(c.main_text_vector,@embedding)
                ''',
                parameters = parameters,
                enable_cross_partition_query=True,
                populate_query_metrics=True
            )
            results = list(results)
            formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results]

            # formatted_results = [{'SimilarityScore': result.pop('SimilarityScore'), 'document': result} for result in results if result.get('SimilarityScore', 0) > 0.8]
        else :
            pass
        # formatted_results = [formatted_results[-1]]
    
        documents = ""
        for i in range(len(formatted_results)) :
            documents += f"\n[{i+1}]\n{formatted_results[i]['document']['main_text']}".replace('\n\n\n','\n')

        self.logger.info(documents)
        return documents, formatted_results

    def get_item(self, file_name):
        
        item = self.container_client.query_items(
            query=f'''
            SELECT c.file_logic_name, c.file_physical_name, c.file_path, c.sharepoint_item_id, c.file_view_link, c.graph_api_id
            FROM c
            WHERE c.file_physical_name = '{file_name}'
            ''',
            enable_cross_partition_query=True,
            populate_query_metrics=True
        )
        self.logger.info(f"file load success : { (file_name) }")
        
        return item
    

class SharePoint:
    def __init__(self, logger, scope):
        self.logger = logger

        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        self.site_url = config["sharepoint"]["site_url"]
        self.to_db_name = config["sharepoint"]["to_db_name"]
        self.client_id = config["sharepoint"]["client_id"]
        self.tenant_id = config["sharepoint"]["tenant_id"]
        self.client_secret = config["sharepoint"]["client_secret"]
        self.scope = scope
        self.access_token = None

    def get_access_token(self):
        try:
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                client_credential=self.client_secret,
            )
            result = app.acquire_token_for_client(scopes=self.scope)
            self.access_token = result.get('access_token')
            if not self.access_token:
                raise ValueError("Failed to obtain access token.")
            return self.access_token
        except Exception as e:
            raise RuntimeError(f"Error obtaining access token: {e}")

    def _get_headers(self):
        if not self.access_token:
            raise ValueError("Access token is not available. Call get_access_token() first.")
        return {'Authorization': f'Bearer {self.access_token}'}
    
    def _make_get_request(self, url):
        headers = self._get_headers()
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    
    def _make_put_request(self, url, file):
        headers = self._get_headers()
        response = requests.put(url, headers=headers, data=file)
        # response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    
    def _make_delete_request(self, url):
        headers = self._get_headers()
        response = requests.delete(url, headers=headers)
        # response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    
    def get_site_id(self, site_url):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_url}"
            response = self._make_get_request(url)
            return response.json().get('id')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching site ID: {e}")
        except KeyError:
            raise ValueError("Site ID not found in the response.")

    def get_file_item_id(self, site_id, file_name):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root/search(q='{file_name}')"
            response = self._make_get_request(url)
            items = response.json().get('value', [])
            print(response.json())
            if items:
                return items[0].get('id')
            else:
                return None
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching file item ID: {e}")
        except KeyError:
            raise ValueError("File item ID not found in the response.")

    def get_list_id(self, site_id, list_name):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_name}"
            response = self._make_get_request(url)
            list_info = response.json()
            return list_info.get('id')
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching list ID: {e}")
        except KeyError:
            raise ValueError("List ID not found in the response.")

    def get_all_list_items(self, site_id, list_id):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
            all_items = []
            
            while url : 
                response = self._make_get_request(url)
                data = response.json()
                items = data.get('value', [])
                all_items.extend(items)
                # 다음 페이지가 있는지 확인하고 url을 업데이트
                url = data.get('@odata.nextLink')
            return [item.get('id') for item in all_items]
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching list items: {e}")
        except KeyError:
            raise ValueError("List items not found in the response.")

    def get_all_documnet_lib_items(self, site_id, list_id):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
            response = self._make_get_request(url)
            data = response.json()
            all_items = data.get('value', [])
            item_id_list = []
            for item in all_items:
                 if (item['contentType']['name'] == '문서') and (not item['webUrl'].lower().endswith('.pdf') ):
                     item_id_list.append(item['id'])
            return item_id_list
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching documnet library list items: {e}")
        except KeyError:
            raise ValueError("Documnet Library lis items not found in the response.")
    
    def get_field_value(self, site_id, list_id, item_id):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{item_id}/fields"
            response = self._make_get_request(url)
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching field value: {e}")
        except KeyError:
            raise ValueError("Field value not found in the response.")

    def filter_field_value(self, original_dict, filter_col_list):
        if not isinstance(original_dict, dict):
            raise TypeError("original_dict must be a dictionary.")
        
        if not isinstance(filter_col_list, list):
            raise TypeError("filter_col_list must be a list.")
        
        filtered_dict = {}
        
        for key in filter_col_list:
            if key in original_dict:
                filtered_dict[key] = original_dict[key]
            else:
                filtered_dict[key] =''
        
        return filtered_dict
    
    def request_item_content(self, action, file_id, drive_id):
        # to convert doumnet to pdf for better DI 
        try:
            if action == 'convert':
                # url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{file_id}/driveItem/content?format=pdf"
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/content?format=pdf"
            else: 
                # url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items/{file_id}/driveItem/content"
                url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}/content"
            response = self._make_get_request(url)
            return response
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error request {action} content of item : {e}")
        
    def get_drive_id(self, site_id):
        try:
            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives"
            response = self._make_get_request(url)
            list_info = response.json().get('value', [])

            drive_value = [item for item in list_info if item['name'] == '문서']
            print(drive_value)

            return drive_value[0]['id']
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error fetching drive ID: {e}")
        except KeyError:
            raise ValueError("Drive ID not found in the response.")
        
    def upload_file_to_drive(self, drive_id, file, file_name, folder_id=None):
        if folder_id:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}:/{file_name}:/content"
        else:
            url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{file_name}:/content"

        response = self._make_put_request(url, file)
        response.raise_for_status()
        print(f"File uploaded: {response.json()}")
        
        return response.json()
    
    def delete_file_to_drive(self, drive_id, file_id):
        url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{file_id}"

        response = self._make_delete_request(url)
        response.raise_for_status()
        # print(f"File deleted: {response.json()}")
        
        return response