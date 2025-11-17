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
queue_storage = config["storage"]["web"]["queue_storage"]

file_index_name = config["aisearch"]["file_index_name"]
search_index_name = config["aisearch"]["search_index_name"]
preprocessing_result_index_name = config["aisearch"]["preprocessing_result_index_name"]

aoai_ans_gen_model = '-'.join(['wkms', config["openai"]["ans_gen_base_model"]])


tokenizer = tiktoken.encoding_for_model(db_embedding_model)


preprocessing_queue_bp = func.Blueprint() 
# app = func.FunctionApp()

@preprocessing_queue_bp.function_name(name='preprocessing_queuetrigger')
@preprocessing_queue_bp.queue_trigger(arg_name="msg", queue_name=queue_storage, connection="AzureWebUploadStorage")  # Queue trigger
def preprocessing_queuetrigger(msg: func.QueueMessage):
    logging.info('Python queue trigger function processed a queue item: %s',
                 msg.get_body().decode('utf-8'))
    
    # file_path = msg.get_body().decode('utf-8')
    file_bss_info_sno = int(msg.get_body().decode('utf-8'))

    log_type = f"preprocessing-{file_bss_info_sno}"
    logger = setup_logger(preprocess_type=log_type)


    try:
        #====================================================== 
        # 파일 정보 획득
        #======================================================

        mysql_instance = AzureMySQL(logger=logger)
        mysql_conn, mysql_cursor = mysql_instance.get_connection()

        file_info = mysql_instance.select_file_info_bss_sno(mysql_conn, mysql_cursor, file_bss_info_sno)
        file_info = {key.lower(): value for key, value in file_info.items()}

        file_type = file_info['file_extsn']
        file_info['file_lgc_nm'] = file_info['file_lgc_nm']+'.'+file_type
        file_lgc_nm = file_info['file_lgc_nm']
        file_psl_nm = file_info['file_psl_nm']

        file_path = file_info['path'][1:]+'/'+file_psl_nm+'.'+file_type
        file_info.pop('file_extsn', None)
        
        logger.info(f"============================== START PREPROCESSING\n")
        #====================================================== 
        # 객체 정의
        #======================================================
        as_instance_raw = AzureStorage(logger=logger, type='web', container_name=raw_storage)
        as_instance_pre = AzureStorage(logger=logger, type='ai', container_name=preprosessed_storage)
        as_instance_log = AzureStorage(logger=logger, type='ai', container_name=log_storage)

        di_instnace = AzureDI(logger=logger)
        # db_instance_file = CosmosDB(logger=logger, database_name=db_name, container_name=file_container)
        aisearch_instance_file = AISearch(logger=logger, index_name=file_index_name)
        aisearch_instance_search = AISearch(logger=logger, index_name=search_index_name)
        aisearch_instance_preprocessing_result = AISearch(logger=logger, index_name=preprocessing_result_index_name)
        aoai_instance = AOAI(logger=logger, aoai_model=aoai_ans_gen_model)
        pre_instance = Preprocessing(logger=logger)

        korea_timezone = pytz.timezone('Asia/Seoul')
        now = datetime.now(korea_timezone)
        formatted_date = now.strftime('%Y-%m-%d')


        logger.info(f"============================== FILE_TYPE : {file_type.upper()}\n")
        logger.info(f"============================== FILE_PSL_NM : {file_psl_nm}\n")    

        logging.info('Python queue trigger function processed %s', file_info['path'])

    except Exception as e :
        logger.error(traceback.format_exc())
        error_contents = f"{type(e).__name__} : '{e}'"
        logger.error(error_contents)
        
        status = "fail(file_bss_info_sno error)"
        error_code = "E002"

        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/error_log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)

        logging_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        result_dict = {
            "id": None,
            "path": None,
            "file_lgc_nm": None,
            "file_psl_nm": None,
            "file_bss_info_sno": file_bss_info_sno,
            "file_dtl_info_sno": None,
            "drcy_sno": None,
            "preprocessing_time": logging_time,
            "preprocessing_result": status
        }

        aisearch_instance_preprocessing_result.upload_to_index(document=result_dict)


    try :
        #====================================================== 
        # 전처리
        #======================================================

        original_key = str(file_info['file_bss_info_sno']) + '_' + str(file_info['drcy_sno']) + '_' + str(file_info['file_dtl_info_sno']) + '_' + file_info['file_psl_nm']
        encoded_key = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
        file_info['id'] = encoded_key

        aisearch_instance_file.upload_to_index(document=file_info)

        select_list = ['file_bss_info_sno', 'drcy_sno', 'file_dtl_info_sno', 'file_lgc_nm', 'file_psl_nm', 'path', 'preprocessing_result']
        item_result = aisearch_instance_preprocessing_result.get_item(file_physical_name=file_psl_nm, select_list=select_list, is_result=True)

        if len(item_result) == 0:
            pass

        status = "file_info_uploaded"

        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)

        logging_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        result_dict = {
            "id": file_info['id'],
            "path": file_info['path'],
            "file_lgc_nm": file_info['file_lgc_nm'],
            "file_psl_nm": file_info['file_psl_nm'],
            "file_bss_info_sno": file_info['file_bss_info_sno'],
            "file_dtl_info_sno": file_info['file_dtl_info_sno'],
            "drcy_sno": file_info['drcy_sno'],
            "preprocessing_time": logging_time,
            "preprocessing_result": status
        }

        aisearch_instance_preprocessing_result.upload_to_index(document=result_dict)
        # else:
        #     if item_result[0]['document']['preprocessing_result'] == 'success':
        #         return
            # if item_result[0]['document']['preprocessing_result'] == 'fail':
            #     return

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
        pre_instance.document_intelligence(file_path=file_path, file_name=file_psl_nm, file_type=file_type, as_instance_raw=as_instance_raw, as_instance_pre=as_instance_pre, di_instnace=di_instnace)

        #====================================================== 
        # UPLOAD DOCUMENTS TO STORAGE ( JSON )
        #======================================================

        content_list = as_instance_pre.extract_blob_list(blob_path=f"extracted_text/{file_psl_nm}/", file_type='txt')
        for content_file in content_list :
            content = as_instance_pre.read_file(file_path=content_file)
            num_token = calculate_token(content, tokenizer)
            preprocessing_documents(logger=logger, content=content, file_psl_nm=file_psl_nm, file_lgc_nm=file_lgc_nm, ori_file_id=encoded_key, tokenizer=tokenizer, num_token=num_token, content_file=content_file, aoai_instance=aoai_instance, aisearch_instance=aisearch_instance_search, config=config)
        
        status = "success"

        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)

        logging_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        result_dict = {
            "id": file_info['id'],
            "path": file_info['path'],
            "file_lgc_nm": file_info['file_lgc_nm'],
            "file_psl_nm": file_info['file_psl_nm'],
            "file_bss_info_sno": file_info['file_bss_info_sno'],
            "file_dtl_info_sno": file_info['file_dtl_info_sno'],
            "drcy_sno": file_info['drcy_sno'],
            "preprocessing_time": logging_time,
            "preprocessing_result": status
        }

        aisearch_instance_preprocessing_result.upload_to_index(document=result_dict)
    
    except Exception as e :
        logger.error(traceback.format_exc())
        error_contents = f"{type(e).__name__} : '{e}'"
        logger.error(error_contents)
        
        status = "fail"

        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=log_type)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"preapi/{formatted_date}/error_log/{file_psl_nm}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)

        logging_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        result_dict = {
            "id": file_info['id'],
            "path": file_info['path'],
            "file_lgc_nm": file_info['file_lgc_nm'],
            "file_psl_nm": file_info['file_psl_nm'],
            "file_bss_info_sno": file_info['file_bss_info_sno'],
            "file_dtl_info_sno": file_info['file_dtl_info_sno'],
            "drcy_sno": file_info['drcy_sno'],
            "preprocessing_time": logging_time,
            "preprocessing_result": status
        }

        aisearch_instance_preprocessing_result.upload_to_index(document=result_dict)
