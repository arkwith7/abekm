# function_app.py
import azure.functions as func
import logging

import logging
import json
import traceback
import pytz
import os
import base64
import yaml
import tiktoken
from datetime import datetime

from database import AzureStorage, AzureMySQL
from aisearch import AISearch
from preprocessing import Preprocessing
from log import setup_logger, thread_local
from model import AzureDI, AOAI
from tools import calculate_token, preprocessing_documents, filter_logs, convert_pdf

if os.environ["ENVIRONMENT"] == 'local':
    with open('./config/config_local.yaml', 'r') as file:
        config = yaml.safe_load(file)
elif os.environ["ENVIRONMENT"] == 'dev':
    with open('./config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
else:
    with open('./config/config_prod.yaml', 'r') as file:
        config = yaml.safe_load(file)

db_embedding_model = config["openai"]["db_embedding_model"]

log_storage = config["storage"]["ai"]["log_storage"]
preprosessed_storage = config["storage"]["ai"]["preprosessed_storage"]
raw_storage = config["storage"]["web"]["raw_storage"]
account_str = config["storage"]["web"]["account_str"]

file_index_name = config["aisearch"]["file_index_name"]
search_index_name = config["aisearch"]["search_index_name"]


tokenizer = tiktoken.encoding_for_model(db_embedding_model)


preprocessing_bp = func.Blueprint() 
# app = func.FunctionApp()

@preprocessing_bp.function_name(name='preprocessing_blob')
# @preprocessing_bp.route(route="preprocessingBlob", methods=["POST"])
@preprocessing_bp.blob_trigger(arg_name="blobFile", source="EventGrid", path="upload", 
               connection="AzureWebUploadStorage")
def preprocessing_blob(blobFile: func.InputStream):
    logging.info('Python Blob trigger function processed %s', blobFile.name)
    # logging.info('Python Blob trigger function processed %s', blobFile.name)

    
    #====================================================== 
    # REQUEST BODY
    #====================================================== 
    file_path = blobFile.name

    if len(file_path.split('.')) < 2:
        return
    
    file_name = blobFile.name.split('/')[-1]
    file_type = file_path.split('.')[-1]
    log_type = f"preprocessing-{file_name}"
    logger = setup_logger(preprocess_type=log_type)
    
    logger.info(f"============================== START PREPROCESSING API\n")    
    as_instance_raw = AzureStorage(logger=logger, type='web', container_name=raw_storage)
    as_instance_pre = AzureStorage(logger=logger, type='ai', container_name=preprosessed_storage)
    as_instance_log = AzureStorage(logger=logger, type='ai', container_name=log_storage)

    mysql_instance = AzureMySQL(logger=logger)
    mysql_conn, mysql_cursor = mysql_instance.get_connection()

    di_instnace = AzureDI(logger=logger)
    # db_instance_file = CosmosDB(logger=logger, database_name=db_name, container_name=file_container)
    aisearch_instance_file = AISearch(logger=logger, index_name=file_index_name)
    aisearch_instance_search = AISearch(logger=logger, index_name=search_index_name)
    aoai_instance = AOAI(logger=logger)
    pre_instance = Preprocessing(logger=logger)

    korea_timezone = pytz.timezone('Asia/Seoul')
    now = datetime.now(korea_timezone)
    formatted_date = now.strftime('%Y-%m-%d')

    try :
        logger.info(f"============================== FILE_TYPE : {file_type.upper()}\n")

        file_info = mysql_instance.select_file_total_info(conn=mysql_conn, cursor=mysql_cursor, file_psl_nm=os.path.splitext(file_name)[0])

        file_info = {key.lower(): value for key, value in file_info.items()}

        file_info['file_lgc_nm'] = file_info['file_lgc_nm']+'.'+file_type
        file_lgc_nm = file_info['file_lgc_nm']
        file_psl_nm = file_info['file_psl_nm']

        original_key = str(file_info['file_bss_info_sno']) + '_' + str(file_info['drcy_sno']) + '_' + str(file_info['file_dtl_info_sno']) + '_' + file_info['file_psl_nm']
        encoded_key = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
        file_info['id'] = encoded_key

        aisearch_instance_file.upload_to_index(document=file_info)

        # file_info_columns = [column.lower() for column in list(file_info.keys())]
        
        # #====================================================== 
        # # GET FILE INFO
        # #======================================================   
        # item = db_instance_file.get_item(file_name=file_name)
        # file_info = list(item)

        # #====================================================== 
        # # GRAPH API ( CONVERT TO PDF )
        # #======================================================
        # if file_type != 'pdf':
        #     conv_result = convert_pdf(logger=logger, file_name=file_name, as_instance_raw=as_instance_raw, as_instance_pre=as_instance_pre)

        #     if conv_result == "SUCCESS" :
        #         file_name = f"{file_name.split(f'.{file_type}')[0]}.pdf"
        #         file_type = 'conv_pdf'
        #     else :
        #         file_name = ori_file_name
        #         file_type = file_name.split('.')[-1]
        #         error_code = "E001"
        #         status = "fail"

        # else:
        #     ## 업로드
        #     pass
        
        # # allow_file_list = ['docx','xlsx','pdf']
        # if file_type not in allow_file_list :
            
        #     conv_result = convert_pdf(logger=logger, file_name=file_name, file_type=file_type, item=file_info, sp_instance=sp_instance, as_instance_pre=as_instance_pre)

        #     if conv_result == "SUCCESS" :
        #         file_name = f"{file_name.split(f'.{file_type}')[0]}.pdf"
        #         file_type = 'conv_pdf'
        #     else :
        #         file_name = ori_file_name
        #         file_type = file_name.split('.')[-1]
        #         error_code = "E001"
        #         status = "fail"
        
        #====================================================== 
        # DOCUMENT INTELLIGENCE
        #======================================================
        # 경로 만드는 부분은 blobtrigger 사용시에는 없어질 예정
        # file_path = '/'.join(file_info['path'].split('/')[1:]) + file_name
        pre_instance.document_intelligence(file_path=file_path, file_name=file_name, file_type=file_type, as_instance_raw=as_instance_raw, as_instance_pre=as_instance_pre, di_instnace=di_instnace)

        #====================================================== 
        # UPLOAD DOCUMENTS TO STORAGE ( JSON )
        #======================================================

        content_list = as_instance_pre.extract_blob_list(blob_path=f"extracted_text/{file_psl_nm}/", file_type='txt')
        for content_file in content_list :
            content = as_instance_pre.read_file(file_path=content_file)
            num_token = calculate_token(content, tokenizer)
            preprocessing_documents(logger=logger, content=content, file_psl_nm=file_psl_nm, file_lgc_nm=file_lgc_nm, ori_file_id=encoded_key, tokenizer=tokenizer, num_token=num_token, content_file=content_file, aoai_instance=aoai_instance, aisearch_instance=aisearch_instance_search, config=config)
        
        status = "success"
        error_code = ""
        
        output = {"status" : status,
                  "error_code" : error_code,
                  "file_name" : file_psl_nm}

        output = json.dumps(output,indent=4,ensure_ascii=False)
        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)
    
    except Exception as e :
        logger.error(traceback.format_exc())
        error_contents = f"{type(e).__name__} : '{e}'"
        logger.error(error_contents)
        
        status = "fail"
        error_code = "E002"

        output = {"status" : status,
                  "error_code" : error_code,
                  "file_name" : file_psl_nm}
        
        output = json.dumps(output,indent=4,ensure_ascii=False)

        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/error_log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)
