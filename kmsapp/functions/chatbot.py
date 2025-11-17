import time
import yaml
import os

from langchain_openai import AzureChatOpenAI

from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    )


from tools import preprocessing_answer, preprocessing_output, extract_keywords, get_prompt, make_query_filter
from log import setup_logger, thread_local

class WJChatbot:
    def __init__(self, logger, aoai_instance, as_instance, aisearch_instance_file, aisearch_instance_search):
        self.logger = logger
        self.aoai_instance = aoai_instance
        self.as_instance = as_instance
        self.aisearch_instance_file = aisearch_instance_file
        self.aisearch_instance_search = aisearch_instance_search

        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        api_base = config["openai"]["api_base"]
        api_key = config["openai"]["api_key"]
        api_version = config["openai"]["api_version"]
        ans_gen_base_model = config["openai"]["ans_gen_base_model"]
        ans_gen_model = '-'.join(['wkms', ans_gen_base_model])
        
        self.chat_client = AzureChatOpenAI(deployment_name=ans_gen_model,
                                azure_endpoint=api_base,
                                openai_api_key=api_key,
                                openai_api_version=api_version,
                                temperature=0)
        


    def step1_refinement(self, query):
        #====================================================== 
        # REFINEMENT
        #====================================================== 
        start_time = time.time()
        self.logger.info(f"============================== REFINEMENT\n")

        keywords_dict = extract_keywords(logger=self.logger, as_instance=self.as_instance, search_instance=self.aisearch_instance_search, chat_client=self.chat_client, question=query['question'])
        # keywords_dict = { "nouns": [...], "proper_nouns": [...], "intent": "...", "intention score": "..." }
        intent = keywords_dict['intent'] ## 'Search', 'Service Request', 'Q&A', 'Others'
        use_chat_history = keywords_dict['use_chat_history']
        refinement_answer = {
                            "evaluation": {
                                "intent": keywords_dict['intent'], ## 'Search', 'Service Request', 'Q&A', 'Others'
                                "doc_search_type": keywords_dict['document_search_type'] ## "COMPANY", "TECH", "GENERAL", "APPLIED"
                            },
                            "refinement": {
                                "question": query['question'],
                                "keywords": keywords_dict['nouns'],
                                "proper_nouns": keywords_dict['proper_nouns'],
                                "corp_names": keywords_dict['corp_names'],
                                "doc_type": keywords_dict['doc_type']
                                }
                            }
        question_vector = self.aoai_instance.generate_embeddings(text=query['question'])
        
        query['intent'] = intent

        if intent.lower() == "search":
            generate_type = 'search'
        else:
            generate_type = 'qa'

        query['refinement_answer'] = refinement_answer
        query['use_chat_history'] = use_chat_history
        self.logger.info(f"============================== REFINEMENT ANSWER : {refinement_answer}\n")
            
        end_time = time.time()
        after_refinement_query = query
        refinement_time = end_time - start_time

        return after_refinement_query, question_vector, generate_type, refinement_time


    def step1_1_refinement(self, query, chat_history):
        #====================================================== 
        # REFINEMENT USING CHAT HISTORY
        #====================================================== 
        start_time = time.time()
        self.logger.info(f"============================== REFINEMENT USING CHAT HISTORY \n")

        # 프롬프트를 읽어옴(검색한 특정문서에 대해서 특정 action을 원하는 경우)
        # TODO: 추후 질의 내용에 따라서 보강이 필요할 수 있음
        # system_msg_prompt = get_prompt(logger=self.logger, prompt_path="prompt/refinement_system.txt")
        # human_msg_prompt = get_prompt(logger=self.logger, prompt_path="prompt/refinement_chathistory.txt")

        system_msg_prompt = self.as_instance.read_file(file_path="prompt/refinement_system.txt")
        human_msg_prompt = self.as_instance.read_file(file_path="prompt/refinement_chathistory.txt")

        system_message_prompt = SystemMessagePromptTemplate.from_template(system_msg_prompt)
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_msg_prompt)

        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])

        messages = chat_prompt.format_prompt(chat_history=chat_history, question = query['question'])

        result = self.chat_client.invoke(messages).content

        result_dict = preprocessing_answer(logger=self.logger, answer=result, answer_type='refinement')
        query['filePhysicalName'] = result_dict['file_physical_name']
        query['intent'] = result_dict['intent']

        query['refinement_answer']['evaluation']['intent'] = result_dict['intent']
        
        query['intent'] = result_dict['intent']

        if result_dict['intent'].lower() == "search":
            generate_type = 'search'
        else:
            generate_type = 'qa'

        self.logger.info(f"============================== REFINEMENT QUERY : {query}\n")
            
        end_time = time.time()
        after_refinement_query = query
        refinement_time = end_time - start_time

        return after_refinement_query, generate_type, refinement_time
    

    def step2_rag(self, query, question_vector):
        start_time = time.time()

        # only_proper_nouns = [item for item in query['refinement_answer']['refinement']['proper_nouns'] if item not in query['refinement_answer']['refinement']['corp_names']]

        SEARCH_REQUEST = True if query['intent'].lower() == 'search' else False
        SUMMARY_REQUEST = True if query['intent'].lower() == 'summary' else False
        DRAFTING_REQUEST = True if query['intent'].lower() == 'drafting' else False 
        USING_PROPER_NOUNS = True if len(query['refinement_answer']['refinement']['proper_nouns']) > 0 else False
        USING_CORP_NAMES = True if len(query['refinement_answer']['refinement']['corp_names']) > 0 else False
        INCLUDE_FILE_NAMES = True if len(query['filePhysicalName']) > 0 else False

        doc_search_type = query['refinement_answer']['evaluation']['doc_search_type'].lower()

        self.logger.info(f"============================== {query['refinement_answer']['refinement']['proper_nouns']}\n")
        self.logger.info(f"============================== {query['refinement_answer']['refinement']['corp_names']}\n")

        self.logger.info(f"============================== RAG\n")

        file_name_field = 'file_lgc_nm'
        search_result = []
        documents = ''
        # 특정 기업에 대한 문서를 찾는 경우
        if SEARCH_REQUEST and doc_search_type == 'company':
            self.logger.info(f"============================== 특정 기업에 대한 문서를 찾는 경우\n")
            if INCLUDE_FILE_NAMES:
                documents, search_result = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=1000)
            else:
                documents, search_result = self.aisearch_instance_file.file_search(query=query['refinement_answer'], num_results=10)
                
            # file_name_field = 'file_lgc_nm'

        # 특정 기술에 대해서만 찾는 경우
        elif SEARCH_REQUEST and doc_search_type == 'tech':
            self.logger.info(f"============================== 특정 기술에 대해서만 찾는 경우\n")
            if INCLUDE_FILE_NAMES:
                documents, search_result = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=1000)
            else:
                _, file_name_list = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=10, using_facet = True)
                self.logger.info(f"============================== {file_name_list}\n")
                
                for file_name in file_name_list:
                    file_name = [file_name]
                    query_filter = make_query_filter(search_filter='', target_field=file_name_field, value_list=file_name, using_facet_result=True)

                    document, search_result_block = self.aisearch_instance_file.file_search(query=query['refinement_answer'], filter=query_filter, num_results=10)

                    documents += document
                    search_result += search_result_block

            # file_name_field = 'file_lgc_nm'

        # 데이터 엔지니어링 등 일반적인 기술에 대해 찾는 경우
        elif SEARCH_REQUEST and doc_search_type == 'general':
            self.logger.info(f"============================== 데이터 엔지니어링 등 일반적인 기술에 대해 찾는 경우\n")
            if INCLUDE_FILE_NAMES:
                documents, search_result = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=1000)
            else:
                _, file_name_list = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=10, using_facet = True)
                self.logger.info(f"============================== {file_name_list}\n")

                for file_name in file_name_list:
                    if isinstance(file_name, str):
                        file_name = [file_name]
                    else:
                        file_name = file_name['document']['file_lgc_nm']
                    query_filter = make_query_filter(search_filter='', target_field=file_name_field, value_list=file_name, using_facet_result=True)

                    document, search_result_block = self.aisearch_instance_file.file_search(query=query['refinement_answer'], filter=query_filter, num_results=10)

                    documents += document
                    search_result += search_result_block

            # file_name_field = 'file_psl_nm'

        # 특정 기술이 특정 기업에 적용된 사례를 찾는 경우
        elif SEARCH_REQUEST and doc_search_type == 'applied':
            self.logger.info(f"============================== 특정 기술이 특정 기업에 적용된 사례를 찾는 경우\n")
            _, file_name_list = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=10, using_facet = True)
            documents, search_result = self.aisearch_instance_file.file_search(query=query['refinement_answer'], num_results=10)

            # 두가지 겹치는거.. 파일목록만 남겨야함;;
            joined_search_results = []
            for search_result_item in search_result:
                if search_result_item['document']['file_lgc_nm'] in file_name_list:
                    joined_search_results.append(search_result_item)

            # self.logger.info(f'=-=-=-=-=-=-=-=-=-=-=-=-=- search result_1: {file_name_list}')
            # self.logger.info(f'=-=-=-=-=-=-=-=-=-=-=-=-=- search result_2: {search_result}')

            self.logger.info(f"============================== 특정 기술이 특정 기업에 적용된 사례 겹친 문서: {joined_search_results}\n")
            if joined_search_results:
                if INCLUDE_FILE_NAMES:
                    intersection_list = list(set(query['filePhysicalName']).intersection(file_lgc_nm_list))

                    if intersection_list:
                        documents = str(joined_search_results)
                    else:
                        documents = ''
                
            elif not joined_search_results:
                documents = ''

            self.logger.info(f"============================== search 결과: {documents}\n")

        elif SUMMARY_REQUEST or DRAFTING_REQUEST:

            file_lgc_nm_list = []
            CHECK_INTERSECTION = False
            
            if USING_CORP_NAMES and len(query['filePhysicalName']) == 0:
                self.logger.info(f"============================== 특정 기업을 질의 내에서 지정하는 경우, 그런데 파일 선택은 안 되어있는 경우\n")
                documents, search_result = self.aisearch_instance_file.file_search(query=query['refinement_answer'], num_results=10, summary=SUMMARY_REQUEST, drafting=DRAFTING_REQUEST)

                
                if len(search_result) > 0 and len(query['filePhysicalName']) == 0:
                    for doc in search_result:
                        query['filePhysicalName'].append(doc['document']['file_lgc_nm'])
                
                # 파일 선택을 하면 선택을 한 파일이 우선되어야 한다..

            elif USING_CORP_NAMES and len(query['filePhysicalName']) > 0:

                CHECK_INTERSECTION = True
                self.logger.info(f"============================== 파일을 지정한 요청, 근데 질의에 기업명이 언급되는 경우\n")
                self.logger.info(query)

            documents, search_result = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=1000, summary_or_drafting=True)
            

            if CHECK_INTERSECTION:
                for doc in search_result:
                        file_lgc_nm_list.append(doc['document']['file_lgc_nm'])


                self.logger.info(f'summary search result +++++++++++++++++++++++++++++++++++{file_lgc_nm_list}')
                intersection = list(set(query['filePhysicalName']).intersection(file_lgc_nm_list))

                if not intersection:
                    documents = ''
                
            # file_name_field = 'file_psl_nm'

        else:
            documents, search_result = self.aisearch_instance_search.search(query_1=query['refinement_answer'], query_2=query, question_vector=question_vector, num_results=1000)
                
            # file_name_field = 'file_psl_nm'
        
        self.logger.info(f"============================== RAG COMPLETE\n")
        self.logger.info([f"{item['document']['file_psl_nm']} ( {item['SimilarityScore']} )" for item in search_result])
        
        
        keys_to_extract = ['file_bss_info_sno', 'drcy_sno', 'file_lgc_nm']
        
        file_info_list = []
        for doc in search_result :
            self.logger.info(f"============================== DOC INFO: {doc}\n")
            file_info = self.aisearch_instance_file.get_item(file_physical_name = doc['document']['file_psl_nm'])[0]['document']
            self.logger.info(f"============================== FILE INFO: {file_info}\n")
            extracted_data = {key: file_info.get(key, None) for key in keys_to_extract}
            # self.logger.info(f"============================== {file_info}\n")
            file_info_list.append(extracted_data)

        # self.logger.info(f"============================== file info list: {file_info_list}\n")
        unique_list = [dict(t) for t in {tuple(d.items()) for d in file_info_list}]

        self.logger.info(f"============================== FILE INFO\n")
        self.logger.info(f"{unique_list}")

        query['file_info'] = unique_list
        end_time = time.time()
        rag_time = end_time - start_time
        
        after_rag_query = query

        return after_rag_query, documents, search_result, rag_time


    def make_chat_history_output(self, query, chat_history_answer, preprocessing_req_time, refinement_time):
        self.logger.info(f"============================== MAKE CHAT HISTORY ANSWER\n")
        time_info = {
                    "preprocessing_req" : preprocessing_req_time,
                    "refinement" : refinement_time,
                    "rag" : 0,
                    "qa" : 0,
                    "qa_predict_time" : 0,
                    "logging_time" : 0
                    }
        query['qa_answer'] = {}
        query['qa_answer']['keyword_list'] = ','.join(query['refinement_answer']['refinement']['keywords'])
        query['qa_answer']['response_body'] = [chat_history_answer[0]['document']['answer']]
        query['qa_answer']['check'] = chat_history_answer[0]['document']['check']
        query['pretty_answer'] = chat_history_answer[0]['document']['answer']
        query['file_info'] = chat_history_answer[0]['document']['file_info']

        output = preprocessing_output(logger=self.logger, query=query, search_result=chat_history_answer)
        # output['time_info'] = time_info
        query['is_chat_history'] = 'y'

        return query, output