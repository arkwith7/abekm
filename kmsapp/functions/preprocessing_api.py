# function_app.py
import azure.functions as func
import logging

import logging
import os
import yaml
import tiktoken
import json

from aisearch import AISearch
from database import AzureMySQL
from log import setup_logger, thread_local

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


tokenizer = tiktoken.encoding_for_model(db_embedding_model)

preprocessing_api_bp = func.Blueprint() 
# app = func.FunctionApp()


@preprocessing_api_bp.function_name(name='preprocessing_api')
@preprocessing_api_bp.route(route="preprocessing_api", methods=["POST"])
@preprocessing_api_bp.queue_output(arg_name="msg", queue_name=queue_storage, connection="AzureWebUploadStorage")
def preprocessing_api(req: func.HttpRequest, msg: func.Out[str]) -> func.HttpResponse:
    logging.info('HTTP 트리거 함수가 요청을 받았습니다.')
    response = {}

    try:
        req_body = req.get_json()

        # 요청에서 작업 데이터를 추출 (필요에 따라 조정)
        job_data = req_body.get("params")['file_bss_info_sno']
        job_code = req_body.get("params")['status_code']

        if not isinstance(job_data, int):
            job_data = int(job_data)

    except ValueError:
        response['result_code'] = 'F_001'
        response['message'] = '잘못된 JSON 페이로드입니다.'
        return func.HttpResponse(body=json.dumps(response,indent=4,ensure_ascii=False),
                                mimetype="application/json",
                                status_code=400)

    if not job_data:
        response['result_code'] = 'F_002'
        response['message'] = 'file_bss_info_sno 값이 누락되었습니다.'
        return func.HttpResponse(body=json.dumps(response,indent=4,ensure_ascii=False),
                                mimetype="application/json",
                                status_code=400)
    
    if not job_code:
        response['result_code'] = 'F_003'
        response['message'] = 'status가 누락되었습니다.'
        return func.HttpResponse(body=json.dumps(response,indent=4,ensure_ascii=False),
                                mimetype="application/json",
                                status_code=400)

    log_type = f"preprocessing-{job_code}"
    logger = setup_logger(preprocess_type=log_type)

    logging.info(f'=====================file_name : {job_data}')
    logging.info(f'=====================status_code : {job_code}')


    if job_code == 'c':
        # 작업 메시지를 큐에 추가 (output binding이 메시지 전송을 처리)
        msg.set(str(job_data))
        # pass
    elif job_code == 'd':
        mysql_instance = AzureMySQL(logger=logger)
        mysql_conn, mysql_cursor = mysql_instance.get_connection()

        file_info = mysql_instance.select_file_info_bss_sno(mysql_conn, mysql_cursor, file_bss_info_sno = job_data)
        file_info = {key.lower(): value for key, value in file_info.items()}

        # del_yn 업데이트
        aisearch_instance_file = AISearch(logger=logger, index_name=file_index_name)
        aisearch_instance_search = AISearch(logger=logger, index_name=search_index_name)

        # file_name = os.path.basename(job_data)
        # file_origin_psl_nm = file_name.split('.')[0]
        file_origin_psl_nm = file_info['file_psl_nm']
        logger.info(f'======================== file_name::::: {file_origin_psl_nm}')

        file_info_select_list = ['*']
        file_contents_select_list = ['*']

        file_info = aisearch_instance_file.get_item(file_physical_name=file_origin_psl_nm, select_list=file_info_select_list, is_result=True)
        logger.info(f'========================{file_info}')
        file_contents_list = aisearch_instance_search.get_item(file_physical_name=file_origin_psl_nm, select_list=file_contents_select_list, is_result=True)

        # 파일정보 업데이트
        if len(file_info) > 0:
            aisearch_instance_file.update_del_yn(file_info[0]['document'])

        # 상세정보 업데이트
        if len(file_contents_list) > 0:
            for file_contents in file_contents_list:
                aisearch_instance_search.update_del_yn(file_contents['document'])
        else:
            pass
    else:
        response['result_code'] = 'F_004'
        response['message'] = '옳지 않은 status(only c/d used)'
        return func.HttpResponse(body=json.dumps(response,indent=4,ensure_ascii=False),
                                mimetype="application/json",
                                status_code=404)


    response['result_code'] = 'S'
    response['message'] = '작업이 제출되었습니다.'
    # 즉시 HTTP 응답 반환
    return func.HttpResponse(body=json.dumps(response,indent=4,ensure_ascii=False),
                            mimetype="application/json",
                            status_code=202)
