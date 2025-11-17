import logging 

import os
import azure.functions as func
import json
from datetime import datetime
import pytz
import traceback
import time
import yaml
import tiktoken
import sys
    
from tools import preprocessing_answer, preprocessing_req_body, preprocessing_output, pretty_answer, filter_logs, extract_keywords, remove_special_characters_and_spaces
from log import setup_logger, thread_local
from model import AOAI
from database import AzureStorage
from aisearch import AISearch
from chatbot import WJChatbot

if os.environ["ENVIRONMENT"] == 'local':
    with open('./config/config_local.yaml', 'r') as file:
        config = yaml.safe_load(file)
elif os.environ["ENVIRONMENT"] == 'dev':
    with open('./config/config.yaml', 'r') as file:
        config = yaml.safe_load(file)
else:
    with open('./config/config_prod.yaml', 'r') as file:
        config = yaml.safe_load(file)

korea_timezone = pytz.timezone('Asia/Seoul')
now = datetime.now(korea_timezone)
current_time = now.strftime('%Y%m%d')

aoai_api_version = config["openai"]["api_version"]
aoai_ans_gen_model = '-'.join(['wkms', config["openai"]["ans_gen_base_model"]])
aoai_summary_model = '-'.join(['wkms', config["openai"]["summary_base_model"]])
embedding_model = config["openai"]["db_embedding_model"]

log_storage = config["storage"]["ai"]["log_storage"]
preprosessed_storage = config["storage"]["ai"]["preprosessed_storage"]
raw_storage = config["storage"]["web"]["raw_storage"]

file_index_name = config["aisearch"]["file_index_name"]
search_index_name = config["aisearch"]["search_index_name"]
chat_history_index_name = config["aisearch"]["chat_history_index_name"]
scoring_profile = config["aisearch"]["chat_history_scoring_profile"]

tokenizer = tiktoken.encoding_for_model(embedding_model)


chat_bp = func.Blueprint() 

@chat_bp.function_name(name="Chat")
@chat_bp.route(route="Chat", methods=["POST"]) 
def chat(req: func.HttpRequest) -> func.HttpResponse: 

    BASED_ON_CHAT_HISTORY = True
    MAKE_FIX_1_ANSWER = True
    GENERATE_ANSWER_TRIGGER = False
    GET_FILE_NAME = False

    req_body = req.get_json()
    
    chat_id = f'{req_body["params"]["loginEmpNo"]}-{req_body["params"]["sessionId"]}-{current_time}'
    logger = setup_logger(preprocess_type=chat_id)

    start_time = time.time()
    query = preprocessing_req_body(logger=logger, body=req_body, body_type='chat')
    
    if len(query['filePhysicalName']) > 0:
        GET_FILE_NAME = True

    origin_file_psl_nm = query['filePhysicalName']

    end_time = time.time()

    preprocessing_req_time = end_time - start_time

    aoai_instance = AOAI(logger=logger, aoai_model=aoai_ans_gen_model, api_version=aoai_api_version)
    summary_aoai_instance = AOAI(logger=logger, aoai_model=aoai_summary_model, api_version=aoai_api_version)

    aisearch_instance_file = AISearch(logger=logger, index_name=file_index_name)
    aisearch_instance_search = AISearch(logger=logger, index_name=search_index_name)
    aisearch_instance_chat_history = AISearch(logger=logger, index_name=chat_history_index_name)
    as_instance_log = AzureStorage(logger=logger, type='ai', container_name=log_storage)
    as_instance_pre = AzureStorage(logger=logger, type='ai', container_name=preprosessed_storage)
    
    chatbot_instance = WJChatbot(logger=logger, aoai_instance=aoai_instance, as_instance=as_instance_pre, aisearch_instance_file=aisearch_instance_file, aisearch_instance_search=aisearch_instance_search)


    korea_timezone = pytz.timezone('Asia/Seoul')
    now = datetime.now(korea_timezone)
    formatted_date = now.strftime('%Y-%m-%d')
    #====================================================== 
    # REQUEST BODY
    #======================================================
    
    logger.info(f"============================== START CHAT API\n")
    logger.info(f"============================== REQ_BODY : {json.dumps(req_body,indent=4,ensure_ascii=False)}\n")


    try :
        #====================================================== 
        # REFINEMENT
        #====================================================== 
        query, question_vector, generate_type, refinement_time = chatbot_instance.step1_refinement(query)

        # 멀티턴이 필요하지 않은 경우, 기존의 채팅기록을 확인
        if query['use_chat_history'].lower() == 'n':
            #====================================================== 
            # CHECK CHAT HISTORY
            #======================================================
            chat_history_answer = aisearch_instance_chat_history.check_chat_history(query=query['refinement_answer'], scoring_profile=scoring_profile, question_vector=question_vector, num_results=1)
            BASED_ON_CHAT_HISTORY = False
        else:
            chat_history_answer = []

        
        #====================================================== 
        # CHECK INTENTION
        #======================================================
        intent = query['intent'].lower()
        if intent != "others":
            MAKE_FIX_1_ANSWER = False

        #====================================================== 
        # MAKE ANSWER
        #======================================================
        # 유사 질의가 있는 경우(chat history  기반의 응답 x, 기존 질의에서 바로 응답 생성)
        if len(chat_history_answer) > 0 and not BASED_ON_CHAT_HISTORY and not MAKE_FIX_1_ANSWER:
            logger.info(f"============================== CASE 1\n")
            #====================================================== 
            # MAKE CHAT HISTORY ANSWER
            #======================================================
            # query['is_chat_history'] = 'n'
            # rag_time = 0
            # qa_time = 0
            # qa_predict_time = 0
            #====================================================== 
            # RAG
            #======================================================     
            query, documents, search_result, rag_time = chatbot_instance.step2_rag(query, question_vector)
            chat_history = ''
            GENERATE_ANSWER_TRIGGER = True
            # query, output = chatbot_instance.make_chat_history_output(query, chat_history_answer, preprocessing_req_time, refinement_time)
            # time_info = query['time_info']
            # query['is_chat_history'] = 'y'

        # chat-history-index에 유사 질의가 없으면서, 챗봇 히스토리만으로 응답을 내야하는게 아닌 경우(최초 응답인 경우)
        elif len(chat_history_answer) == 0 and not BASED_ON_CHAT_HISTORY and not MAKE_FIX_1_ANSWER:
            logger.info(f"============================== CASE 2\n")
            #====================================================== 
            # RAG
            #======================================================     
            query, documents, search_result, rag_time = chatbot_instance.step2_rag(query, question_vector)
            chat_history = ''
            GENERATE_ANSWER_TRIGGER = True
        
        # chat-history-index에 유사 질의가 없으면서, 챗봇 히스토리만으로 응답을 내야하는 경우? 가 있을까
        # TODO: 질의 보강이 아닌 히스토리만으로 응답을 해야하는 경우가 있을 수 있음(확인 필요), 그런 경우는 step2_rag_backup의 if 조건 검토해서 코드 살릴것
        elif len(chat_history_answer) == 0 and BASED_ON_CHAT_HISTORY and not MAKE_FIX_1_ANSWER:
            logger.info(f"============================== CASE 3\n")
            #====================================================== 
            # LOAD CHAT HISTORY
            #====================================================== 
            chat_history = aisearch_instance_chat_history.get_chat_history(query=query)
            query, generate_type, refinement_time = chatbot_instance.step1_1_refinement(query, chat_history)

            #====================================================== 
            # RAG
            #======================================================     
            query, documents, search_result, rag_time = chatbot_instance.step2_rag(query, question_vector)
            
            GENERATE_ANSWER_TRIGGER = True

        # 아무 관련 없는 질문을 한 경우
        elif MAKE_FIX_1_ANSWER:
            logger.info(f"============================== CASE 4\n")
            start_time = time.time()
            output = preprocessing_output(logger=logger, query=query, code="FIX_1")
            end_time = time.time()
            rag_time = 0
            qa_time = end_time - start_time
            qa_predict_time = 0
            query['is_chat_history'] = 'n'

        # 위 케이스에 해당되지 않는 질의가 들어온 경우
        else:
            logger.info(f"============================== CASE 1\n")
            start_time = time.time()
            output = preprocessing_output(logger=logger, query=query, code="Error")
            end_time = time.time()
            rag_time = 0
            qa_time = end_time - start_time
            qa_predict_time = 0
            query['is_chat_history'] = 'n'

        # 직접 답변을 생성해야 하는 경우
        if GENERATE_ANSWER_TRIGGER:
            #====================================================== 
            # GENERATE ANSWER ( QA )
            #====================================================== 
            start_time = time.time()
            logger.info(f"============================== GENERATE ANSWER\n")
            # logger.info(query)
            
            if intent == 'summary' or intent == 'drafting':
                qa_answer, qa_predict_time = summary_aoai_instance.generate_answer(query_1=query['refinement_answer']['refinement'], query_2=query, as_instance=as_instance_pre, generate_type=generate_type, chat_history=chat_history, documents=documents, tokenizer = tokenizer)
            else:
                qa_answer, qa_predict_time = aoai_instance.generate_answer(query_1=query['refinement_answer']['refinement'], query_2=query, as_instance=as_instance_pre, generate_type=generate_type, chat_history=chat_history, documents=documents, tokenizer = tokenizer)
            logger.info(f"============================== QA ANSWER : {qa_answer}\n")
            qa_answer = preprocessing_answer(logger=logger, answer=qa_answer, answer_type='qa')
            query['qa_answer'] = qa_answer
            check = remove_special_characters_and_spaces(qa_answer['check'])
            query['qa_answer']['check'] = check
            query['is_chat_history'] = 'n'

            #======================================================     
            # CHECK DOCUMENTS AND ANSWER
            #====================================================== 
            logger.info(f"============================== CHECK : {check}\n")

            fixed_answer_code = ["no", "incorrectquestion", "unabletoanswer"]

            if check.lower() in fixed_answer_code or documents == '':
                if GET_FILE_NAME:
                    code = 'FIX_3'
                else:
                    code = 'FIX_2'
                    query['file_info'] = []
            elif check.lower() == "intention" :
                code = 'FIX_1'
            else:
                if GET_FILE_NAME and not query['file_info']:
                    code = 'FIX_3'
                elif not GET_FILE_NAME and not query['file_info']:
                    code = 'FIX_2'
                else:
                    code = None
                query['pretty_answer'] = pretty_answer(logger=logger, answer = query['qa_answer'])

            if code == 'FIX_3':
                logger.info(f"================================{query['refinement_answer']}")
                logger.info(f"================================{query}")

                keys_to_extract = ['file_bss_info_sno', 'drcy_sno', 'file_lgc_nm']

                file_info_list = []
                for name in origin_file_psl_nm :
                    file_info = aisearch_instance_file.get_item(file_physical_name = name, target_nm = 'file_lgc_nm')[0]['document']
                    extracted_data = {key: file_info.get(key, None) for key in keys_to_extract}
                    # self.logger.info(f"============================== {file_info}\n")
                    file_info_list.append(extracted_data)

                # self.logger.info(f"============================== file info list: {file_info_list}\n")
                unique_list = [dict(t) for t in {tuple(d.items()) for d in file_info_list}]

                query['file_info'] = unique_list
                
            output = preprocessing_output(logger=logger, query=query, search_result=search_result, code=code)

            end_time = time.time()
            qa_time = end_time - start_time

        #====================================================== 
        # LOG
        #======================================================
        start_time = time.time()
        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=chat_id)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"chatapi/{formatted_date}/log/{chat_id}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)

        end_time = time.time()
        logging_time = end_time - start_time

        if query['is_chat_history'] == 'n':
            time_info = {"preprocessing_req" : preprocessing_req_time,
                        "refinement" : refinement_time,
                        "rag" : rag_time,
                        "qa" : qa_time,
                        "qa_predict_time" : qa_predict_time,
                        "logging_time" : logging_time}

        aisearch_instance_chat_history.upload_chat_history(chat_id=chat_id, query=query, question_vector=question_vector)

        if isinstance(output["qa_answer"]["keyword_list"], str):
            output["qa_answer"]["keyword_list"] = [output["qa_answer"]["keyword_list"]]

        output = json.dumps(output,indent=4,ensure_ascii=False)

        logger.info(f"============================== CHECK OUTPUT : {output}\n")

        logger.info(f"============================== TIME INFO\n{json.dumps(time_info,indent=4,ensure_ascii=False)}\n")
            
        
    except Exception as e :
        code = "Error"
        error = traceback.format_exc()
        logger.error(error)
        filter_logs_string = filter_logs(logs=thread_local.log_list, log_type=chat_id)
        logs_str = "\n".join(filter_logs_string)
        log_file_path = f"chatapi/{formatted_date}/error_log/{chat_id}.log"
        as_instance_log.upload_log(logs_str, file_path=log_file_path)
        output = preprocessing_output(logger=logger, query=query, code=code, error=error)
        output = json.dumps(output,indent=4,ensure_ascii=False)

    return func.HttpResponse(body=output,
                        mimetype="application/json",
                        status_code=200)

