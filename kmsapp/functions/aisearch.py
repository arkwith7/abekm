from azure.core.exceptions import *
from azure.core.credentials import AzureKeyCredential

from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery, VectorFilterMode
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SynonymMap

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from typing import List, Dict, cast

from statistics import mean

import yaml
import uuid
import os

from tools import make_query_filter


class AISearch:
    def __init__(self, logger, index_name):
        

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
        
        self.index_name = index_name
        self.search_endpoint = config["aisearch"]["search_endpoint"]
        self.search_api_key = config["aisearch"]["search_api_key"]
        self.embedding_deployment = '-'.join(['wkms-', config["openai"]["db_embedding_model"]])
        self.search_type = config["aisearch"]["search_type"]
        self.api_version = config["aisearch"]["api_version"]

        self.search_client = SearchClient(endpoint=self.search_endpoint, index_name=self.index_name, credential=AzureKeyCredential(self.search_api_key))
        self.search_index_client = SearchIndexClient(self.search_endpoint, AzureKeyCredential(self.search_api_key))

    
    def get_item(self, file_physical_name, target_nm='file_psl_nm', select_list = ['file_bss_info_sno', 'drcy_sno', 'file_dtl_info_sno', 'file_lgc_nm', 'file_psl_nm', 'path'], is_result=False):

        if is_result:
            filter = f"{target_nm} eq '{file_physical_name}'"
        else:
            filter = f"{target_nm} eq '{file_physical_name}' and del_yn eq false"

        results = self.search_client.search(  
                        search_text = '*', 
                        filter = filter,
                        select = select_list
                    )

        # filtered_results = [
        #     res for res in results if res.get("@search.score", 0) >= 0
        # ]

        # self.logger.info(results)
        # vector_question = aoai_instance.generate_embeddings(text=question)
        formatted_results = [{'SimilarityScore': result.get("@search.score", 0), 'document': result} for result in results]
        # self.logger.info(formatted_results)

        return formatted_results
    

    def file_search(self, query, query_2=None, filter=None, num_results = 3, similarity_score = 0.02, summary=False, drafting=False):
        
        
        # question = query['refinement']['question']
        keyword_list = query['refinement']['keywords']

        proper_nouns = query['refinement']['proper_nouns']  # 필요에 따라 동적으로 변경 가능
        corp_names = query['refinement']['corp_names']
        doc_type = query['refinement']['doc_type']
        
        if isinstance(doc_type, str):
            doc_type = [doc_type]

        if '기타' in doc_type:
            doc_type.remove('기타')

        self.logger.info(f'================================ DOC TYPE : {doc_type}')
        
        search_filter = ""

        file_name_keyword_list = []

        question = ' '.join(keyword_list+proper_nouns+corp_names)
        # ismatch 필터는 한단어씩 들어가야함
        # 예시 = "filter": "search.ismatch('제안요청서', 'file_logic_name') and search.ismatch('야놀자', 'file_logic_name') and search.ismatch('인터파크', 'file_logic_name')",

        if len(doc_type) > 0 and not summary and not drafting:
            target_field = 'ctg_lvl2_nm'
            added_filter = make_query_filter(search_filter, target_field, doc_type, using_facet_result=True)
            search_filter = added_filter
        elif len(doc_type) > 0 and summary and not drafting:
            target_field = 'ctg_lvl2_nm'
            added_filter = make_query_filter(search_filter, target_field, doc_type, using_facet_result=True)
            search_filter = added_filter
        elif len(doc_type) > 0 and not summary and drafting:
            pass

        if filter:
            if search_filter:
                search_filter = search_filter + ' and ' + filter + ' and del_yn eq false'
            else:
                search_filter += filter
                search_filter += ' and del_yn eq false'

            results = self.search_client.search(  
                        search_text = '*', 
                        search_fields = ['file_lgc_nm'],
                        filter = search_filter,
                        select = ['file_lgc_nm', 'file_psl_nm'],
                        top = num_results
                    )
        else:
            # if len(proper_nouns) > 0:
            #     file_name_keyword_list += proper_nouns
            
            if len(corp_names) > 0 and not query_2:
                file_name_keyword_list += corp_names
            elif len(corp_names) == 0 and not query_2:
                pass
            else:
                # query_2가 들어오는 경우: 파일을 지정한 경우
                file_name_keyword_list = query_2['filePhysicalName']

            # if len(file_name_keyword_list) > 0 and not query_2:
            #     pass
            #     # target_field = 'file_lgc_nm'
            #     # added_filter = make_query_filter(search_filter, target_field, file_name_keyword_list)
            #     # search_filter = added_filter

            #     # target_field = 'kw'
            #     # added_filter = 
            #     # search_filter += ' and del_yn eq false'
   
            # elif len(file_name_keyword_list) > 0 and query_2:
            #     target_field = 'file_lgc_nm'
            #     added_filter = make_query_filter(search_filter, target_field, file_name_keyword_list, using_facet_result=True)
            #     search_filter = added_filter
            #     search_filter += ' and del_yn eq false'

            if len(file_name_keyword_list) > 0 and query_2:
                target_field = 'file_lgc_nm'
                added_filter = make_query_filter(search_filter, target_field, file_name_keyword_list, using_facet_result=True)
                search_filter = added_filter
                search_filter += ' and del_yn eq false'


            if not 'del_yn' in search_filter:
                if search_filter:
                    search_filter += ' and del_yn eq false'

                else:
                    search_filter = 'del_yn eq false'

            results = self.search_client.search(  
                        search_text = question, 
                        filter = search_filter,
                        select = ['file_lgc_nm', 'file_psl_nm'],
                        top = num_results
                    )

        self.logger.info(f"============================== FILTER : {search_filter}\n")
        # 필터링 적용
        # sim_score_list = [res.get("@search.score", 0) for res in results]
        # self.logger.info(f"results @search.score list (type: {type(sim_score_list[0])})")

        # similarity_score = mean(sim_score_list)
        # self.logger.info(f"Calculated similarity_score: {similarity_score} (type: {type(similarity_score)})")

        filtered_results = [
            res for res in results if res.get("@search.score", 0) >= similarity_score
        ]

        filtered_doc = str(filtered_results)

        # vector_question = aoai_instance.generate_embeddings(text=question)
        formatted_results = [{'SimilarityScore': result['@search.score'], 'document': result} for result in filtered_results]

        # sim_score_list = [formed_res['SimilarityScore'] for formed_res in formatted_results]
        # # self.logger.info(f"results @search.score list (type: {type(sim_score_list[0])})")
        # similarity_score = mean(sim_score_list)

        # filtered_results = [res for res in results if res['SimilarityScore'] >= similarity_score]

        # for filtered_result in filtered_results:
        #     filtered_result['document']['file_name'] = filtered_result['document']['file_physical_name']

        # documents = str(filtered_results)

        documents = str(formatted_results)

        # self.logger.info(f"============================== SEARCH_RESULTS : {search_results}\n")
        self.logger.info(f"============================== FILTERED_RESULTS : {filtered_doc}\n")
        self.logger.info(f"============================== FORMATTED_RESULTS : {documents}\n")

        # return documents, formatted_results, vector_question
        return documents, formatted_results


    def search(self, query_1, query_2, question_vector, num_results = 3, similarity_score = 0.02, using_facet = False, summary_or_drafting = False):
        # self.logger.info(query_2['filePhysicalName'])
        
        FACETS_YN = True
        
        file_physical_name = query_2['filePhysicalName']
        input_physical_name_flag = True

        keyword_list = query_1['refinement']['keywords']

        proper_nouns = query_1['refinement']['proper_nouns']
        corp_names = query_1['refinement']['corp_names']
        doc_type = query_1['refinement']['doc_type']


        if summary_or_drafting and keyword_list and proper_nouns and corp_names:
            question = '*'
        # elif summary_or_drafting and (len(keyword_list) > 0 or len(proper_nouns) > 0 or len(corp_names) > 0):
        #     question = query_1['refinement']['question']
        #     FACETS_YN = False
        else:
            # question = query_1['refinement']['question']
            question = ' '.join(keyword_list+proper_nouns+corp_names)


        # if isinstance(doc_type, str):
        #     doc_type = [doc_type]

        search_filter = ""
        
        if len(file_physical_name) == 0 and not using_facet:
            input_physical_name_flag = False

            # if proper_nouns:
            #     target_field = 'file_name'
            #     file_name_filter_query = make_query_filter(search_filter, target_field, proper_nouns)

            #     search_filter = file_name_filter_query

            # if doc_type:
            #     # TODO: 추후 target field 변경할 것(upload 기능 마무리되면 카테고리 바라보도록)
            #     target_field = 'file_lgc_nm'
            #     doc_type_filter_query = make_query_filter(search_filter, target_field, doc_type)

            #     search_filter = doc_type_filter_query
        
        # facet 결과만 필요한 경우
        elif len(file_physical_name) == 0 and using_facet:
            input_physical_name_flag = False
            try:
                keyword_list.remove('적용')
            except:
                pass
            facets_words_list = keyword_list + proper_nouns
            question = ' '.join(facets_words_list)

            self.logger.info(f"============================== FACET QUESTION : {question}\n")

            results = self.search_client.search(
                                                search_text=question, 
                                                search_fields=["chunk_text"],
                                                filter="del_yn eq false",
                                                facets=["file_lgc_nm,count:200"])

                        
            facets: Dict[str, List[str]] = cast(Dict[str, List[str]], results.get_facets())

            self.logger.info(f"============================== FACETS : {facets}\n")

            file_name_list = [facet["value"] for facet in facets["file_lgc_nm"]]


            return results, file_name_list
        
        elif len(file_physical_name) > 0 and using_facet:
            input_physical_name_flag = True

            question = ' '.join(facets_words_list)

            self.logger.info(f"============================== FACET QUESTION : {question}\n")

            target_field = 'file_lgc_nm'
            if isinstance(file_physical_name, str):
                file_physical_name_list = [file_physical_name]
            else:
                file_physical_name_list = file_physical_name
            file_physical_name_query = make_query_filter(search_filter, target_field, file_physical_name_list, True)

            search_filter = file_physical_name_query + ' and del_yn eq false'

            results = self.search_client.search(
                                                search_text=question, 
                                                search_fields=["main_text"],
                                                filter=search_filter,
                                                facets=["file_lgc_nm,count:200"])

                        
            facets: Dict[str, List[str]] = cast(Dict[str, List[str]], results.get_facets())

            self.logger.info(f"============================== FACETS : {facets}\n")

            file_name_list = [facet["value"] for facet in facets["file_lgc_nm"]]


            return results, file_name_list

        if input_physical_name_flag:
            target_field = 'file_lgc_nm'
            if isinstance(file_physical_name, str):
                file_physical_name_list = [file_physical_name]
            else:
                file_physical_name_list = file_physical_name
            file_physical_name_query = make_query_filter(search_filter, target_field, file_physical_name_list, True)

            search_filter = file_physical_name_query
        
            # search_filter = f"file_name eq '{file_physical_name}'"
 
        
        # 삭제여부 확인 필터 추가
        if search_filter:
            search_filter += ' and del_yn eq false'
        else:
            search_filter = 'del_yn eq false'

        self.logger.info(f"============================== KEYWORD : {keyword_list}\n")
        self.logger.info(f"============================== FILENAME KEYWORD : {file_physical_name}\n")
        self.logger.info(f"============================== SEARCH FILTER : {search_filter}\n")

        if summary_or_drafting:
            # results = self.keyword_search(question, num_results, similarity_score, search_filter)
            self.logger.info(f"============================== SEARCHING FOR SUMMARY OR DRAFTING ==============================\n")
            results = self.hybrid_search(question, question_vector, num_results, similarity_score, search_filter)
        else:
            if self.search_type == 'vector':
                results = self.vector_search(question_vector, num_results, similarity_score, search_filter)

            elif self.search_type == 'keyword':
                # question = ' '.join(keyword_list)
                question = ' '.join(keyword_list)
                # question = ' '.join([question, ' '.join(keyword_list)])
                results = self.keyword_search(question, num_results, similarity_score, search_filter)

            else:
                # question = ' '.join(keyword_list)
                if not summary_or_drafting:
                    question = ' '.join(keyword_list+proper_nouns+corp_names)
                # question = ' '.join([question, ' '.join(keyword_list)])
                results = self.hybrid_search(question, question_vector, num_results, similarity_score, search_filter)
        

        formatted_results = [{'SimilarityScore': result['@search.score'], 'document': result} for result in results]


        
        if summary_or_drafting:
            doc_dict = {}
            for i in range(len(formatted_results)) :
                if formatted_results[i]['document']['file_lgc_nm'] in list(doc_dict.keys()):
                    doc_dict[formatted_results[i]['document']['file_lgc_nm']] += f"\n[{i+1}]\n{formatted_results[i]['document']['chunk_text']}".replace('\n\n\n','\n')
                else:
                    doc_dict[formatted_results[i]['document']['file_lgc_nm']] = f"[{i+1}]\n{formatted_results[i]['document']['chunk_text']}".replace('\n\n\n','\n')

            documents = str(doc_dict)
            # self.logger.info("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
            # self.logger.info(documents[:10])

        else:
            documents = ""
            for i in range(len(formatted_results)) :
                documents += f"\n[{i+1}]\n{formatted_results[i]['document']['chunk_text']}".replace('\n\n\n','\n')
                # documents += f"\n[{i+1}]\n{formatted_results[i]['document']['main_text']}".replace('\n\n\n','\n')

        return documents, formatted_results
        # return documents, formatted_results, question_vector
    

    def vector_search(self, question_vector, num_results, similarity_score, search_filter=None):
        vector_query = VectorizedQuery(vector=question_vector, k_nearest_neighbors=num_results, fields="main_text_vector")

        results = self.search_client.search(  
                    search_text = None, 
                    filter = search_filter,
                    vector_queries = [vector_query],
                    vector_filter_mode=VectorFilterMode.PRE_FILTER,
                    select = ["id", "file_lgc_nm", "title", "main_text", "chunk_text"],
                    top = num_results
                )
        
        # 필터링 적용
        filtered_results = [
            res for res in results if res.get("@search.score", 0) >= similarity_score
        ]
        return filtered_results
    
    
    def keyword_search(self, question, num_results, similarity_score, search_filter=None):
        results = self.search_client.search(  
                    search_text = question, 
                    filter = search_filter,
                    select = ["id", "file_lgc_nm", "file_psl_nm", "title", "main_text", "chunk_text"],
                    top = num_results
                ) 

        # # 필터링 적용
        # filtered_results = [
        #     res for res in results if res.get("@search.score", 0) >= similarity_score
        # ]

        # return filtered_results

        return results


    def hybrid_search(self, question, question_vector, num_results, similarity_score, search_filter=None):
        vector_query = VectorizedQuery(vector=question_vector, k_nearest_neighbors=num_results, fields="main_text_vector")

        self.logger.info(f"=================filter in search log: {search_filter}")

        results = self.search_client.search(  
                    search_text = question,
                    search_fields=["main_text"],
                    filter = search_filter,
                    vector_queries = [vector_query],
                    vector_filter_mode=VectorFilterMode.PRE_FILTER,
                    select = ["id", "file_lgc_nm", "file_psl_nm", "title", "main_text", "chunk_text"],
                    # scoring_profile = 'hybrid-profile',
                    top = num_results
                )
    
        # 필터링 적용
        filtered_results = [
            res for res in results if res.get("@search.score", 0) >= similarity_score
        ]
        return filtered_results

        # return results

    def default_search(self, query, similarity_score, search_filter=None):
        self.logger.info(f"=================default file search")
        self.logger.info(f"=================filter in search log: {search_filter}")

        question = query['question']

        search_filter = 'del_yn eq false'

        results = self.search_client.search(  
                    search_text = question,
                    highlight_fields= "chunk_text",
                    filter = search_filter,
                    select = ["id", "file_index_id", "file_lgc_nm", "file_psl_nm"],
                    include_total_count=True
                ) 

        # 필터링 적용
        filtered_results = [
            res for res in results if res.get("@search.score", 0) >= similarity_score
        ]

        file_psl_nm_set = set()
        file_filtered_list = []

        for i, doc in enumerate(filtered_results):
            file_psl_nm = doc['document']['file_psl_nm']
            
            if file_psl_nm not in file_psl_nm_set:
                file_psl_nm_set.add(file_psl_nm)
                file_filtered_list.append(doc)


        return file_filtered_list

    def check_chat_history(self, query, scoring_profile, question_vector, num_results):
        self.logger.info(f"============================== CHECK CHAT HISTORY\n")
        vector_query = VectorizedQuery(vector=question_vector, k_nearest_neighbors=num_results, fields="question_vector")
        question = query['refinement']['question']

        proper_nouns = query['refinement']['proper_nouns']
        doc_type = query['refinement']['doc_type']
        intent = query['evaluation']['intent']

        chat_history_find_nouns = []

        self.logger.info(f"============================== {type(doc_type)}\n")

        chat_history_find_nouns += proper_nouns
        # if isinstance(doc_type, str):
        #     chat_history_find_nouns.append(doc_type)

        search_filter = ""

        if len(chat_history_find_nouns) > 0:
            target_field = 'question'
            question_filter = make_query_filter(search_filter, target_field, chat_history_find_nouns)

            search_filter = question_filter

        # 질문 유형이 같은 경우로 필터링 범위 축소
        if intent:
            target_field = 'intent'
            intent_filter = make_query_filter(search_filter, target_field, [intent])

            search_filter = intent_filter

        # chat_history로부터 온 답변인지 검토 (n인 경우 file이나 vector index 직접 검색하여 반환된 답변)
        if search_filter:
            search_filter += " and search.ismatch('n', 'is_chat_history')"
        else:
            search_filter = "search.ismatch('n', 'is_chat_history')"

        self.logger.info(f"============================== CHAT SEARCH FILTER : {search_filter}\n")

        results = self.search_client.search(  
                    search_text = question,
                    search_fields=["question"],
                    filter = search_filter,
                    vector_queries = [vector_query],
                    vector_filter_mode=VectorFilterMode.PRE_FILTER,
                    order_by=['chat_time desc'],
                    scoring_profile = scoring_profile,
                    select = ["id", "question", "loginEmpNo", "answer", "file_info", "check", "is_chat_history", "intent"],
                    top = num_results
                )
    
        # # 필터링 적용
        # filtered_results = [
        #     res for res in results if res.get("@search.score", 0) >= similarity_score
        # ]
        # for result in results:
        #     self.logger.info(f'#### results: {result}')
        # self.logger.info(f'#### results: {results_str}')

        if results is not None:
            formatted_results = [{'SimilarityScore': result['@search.score'], 'document': result} for result in results]
        else:
            formatted_results = []

        return formatted_results


    def upload_chat_history(self, chat_id, query, question_vector) :
        # korea_timezone = pytz.timezone('Asia/Seoul')
        korea_timezone = ZoneInfo('Asia/Seoul')
        now = datetime.now(korea_timezone)

        chat_time = now.isoformat()

        if 'file_info' not in list(query.keys()) or len(query['file_info']) == 0:
            query['file_info'] = [{
                "file_bss_info_sno": -99,
                "drcy_sno": -99,
                "file_dtl_info_sno": -99,
                "file_lgc_nm": "",
                "file_psl_nm": "",
                "path": ""
            }]

        if 'qa_answer' not in list(query.keys()):
            query['qa_answer'] = {}
            query['qa_answer']['check'] = 'No'

        file_info_list = []

        for i, file_info in enumerate(query['file_info']):
            filter_dict = {}
            for k, v in file_info.items():
                if k == 'download_sas_link':
                    continue
                else:
                    filter_dict[k] = v

            file_info_list.append(filter_dict)

        history = {"id" : chat_id,
                "loginEmpNo" : query['loginEmpNo'],
                "sessionId" : query['sessionId'],
                "question" : query['question'],
                "answer" : query['pretty_answer'],
                "intent" : query['intent'],
                "file_info" : file_info_list,
                "check" : query['qa_answer']['check'],
                "question_vector" : question_vector,
                "is_chat_history" : query['is_chat_history'],
                "chat_time": chat_time}
        
        self.search_client.upload_documents(documents=[history])

        return None

    def get_chat_history(self, query) :         
        today = datetime.now()
        start_time = today.strftime("%Y-%m-%dT00:00:00Z")
        next_day = today + timedelta(days=1)
        end_time = next_day.strftime("%Y-%m-%dT00:00:00Z")

        login_emp_no = query['loginEmpNo']
        session_id = query['sessionId']
        check = 'Yes'

        time_filter = f"chat_time ge {start_time} and chat_time lt {end_time}"
        login_emp_no_filter = f"loginEmpNo eq '{login_emp_no}'"
        session_id_filter = f"sessionId eq '{session_id}'"
        check_filter = f"check eq '{check}'"

        filter_list = [time_filter, login_emp_no_filter, session_id_filter, check_filter]

        chat_history_filter = ' and '.join(filter_list)

        results = self.search_client.search(  
                    search_text = '*', 
                    filter = chat_history_filter,
                    order_by = ['chat_time desc'],
                    select = ['question', 'answer', 'file_info'],
                    top = 10
                ) 


        sorted_data = [{'SimilarityScore': result['@search.score'], 'chat_history': result} for result in results]

        chat_data =[]
        for i, item in enumerate(sorted_data) :
            chat_data.append(f"------------------------------- {i+1} ----------------------------\nUSER : {item['chat_history']['question']}\n\nASSISTANT : {item['chat_history']['answer']}\nFILE INFO : {[file['file_physical_name'] for file in item['chat_history']['file_info']]}")

        chat_data = '\n\n'.join(chat_data)

        self.logger.info(f'#### CHAT DATA: {chat_data}')

        return chat_data
    

    def upload_to_index(self, document) :
        # # korea_timezone = pytz.timezone('Asia/Seoul')
        # korea_timezone = ZoneInfo('Asia/Seoul')
        # now = datetime.now(korea_timezone)

        # processing_time = now.strftime("%Y-%m-%dT00:00:00Z")

        # # document['processing_time'] = processing_time
        try:
            self.logger.info(f'================= Insert/Upsert document to index: {self.index_name}')
            self.search_client.upload_documents(documents=[document])
        except Exception as e:
            self.logger.error(f'================= Insert/Upsert failed as: {e}')


    def get_synonym_map(self, synonyms_map_name):
        # [START get_synonym_map]
        result = self.search_index_client.get_synonym_map(synonyms_map_name)

        synonyms_map_list = []
        if result:
            for syn in result.synonyms:
                if '=>' in syn:
                    key_val = syn.split('=>')
                    dict = {key_val[1].strip(): [item.strip() for item in key_val[0].split(',')]}
                else:
                    continue

                synonyms_map_list.append(dict)

        return synonyms_map_list
    

    def update_del_yn(self, document, del_yn=True):
        document['del_yn'] = del_yn
        
        try:
            self.logger.info(f'================= Upsert document to index: {self.index_name}')
            self.search_client.upload_documents(documents=[document])
        except Exception as e:
            self.logger.error(f'================= Upsert failed as: {e}')
