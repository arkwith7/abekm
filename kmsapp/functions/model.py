from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult, AnalyzeDocumentRequest
from azure.identity import get_bearer_token_provider

from openai import AzureOpenAI

import requests
import yaml
import time
import os
from tenacity import retry, stop_after_attempt, wait_random_exponential, before_log, after_log

from langchain_openai import AzureChatOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    )
from langchain.chains import LLMChain

from tools import calculate_token

class AzureDI:

    def __init__(self,logger):
        
        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        self.endpoint = config["di"]["endpoint"]
        self.key = config["di"]["key"]
        self.logger = logger
        self.client = DocumentIntelligenceClient(endpoint=self.endpoint, credential=AzureKeyCredential(self.key))
    
    def analyze_document(self, sas_url, file_type, model_type, model ,output_format, features, api_version="2024-02-29-preview"):
        
        print(file_type)
        if file_type == 'pdf' :
            url = f"{self.endpoint}/{model_type}/documentModels/{model}:analyze?api-version={api_version}&features={features}&features=keyValuePairs&outputContentFormat={output_format}"

        else :
            url = f"{self.endpoint}/{model_type}/documentModels/prebuilt-read:analyze?api-version={api_version}&outputContentFormat={output_format}"
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.key,
            'Content-Type': 'application/json'
        }
        data = {
            "urlSource": sas_url,
        }

        response = requests.post(url, headers=headers, json=data)

        if response.status_code == 202:
            self.logger.info("Request was successful. The operation is in progress.")
            operation_location = response.headers.get('Operation-Location')
        else:
            self.logger.info(f"Request failed with status code {response.status_code}: {response.text}")

        
        headers = {
        'Ocp-Apim-Subscription-Key': self.key
        }

        while True:
            response = requests.get(operation_location, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                status = result.get('status')
                
                if status == 'succeeded':
                    self.logger.info("Analysis succeeded.")
                    return result
                elif status == 'failed':
                    self.logger.info("Analysis failed.")
                    return result
                else:
                    self.logger.info("Analysis is still in progress. Checking again...")
                    time.sleep(10)
            else:
                self.logger.info(f"Request failed with status code {response.status_code}: {response.text}")
                
                return None

class AOAI:

    def __init__(self, logger, aoai_model, api_version="2024-02-15-preview"):
        
        if os.environ["ENVIRONMENT"] == 'local':
            with open('./config/config_local.yaml', 'r') as file:
                config = yaml.safe_load(file)
        elif os.environ["ENVIRONMENT"] == 'dev':
            with open('./config/config.yaml', 'r') as file:
                config = yaml.safe_load(file)
        else:
            with open('./config/config_prod.yaml', 'r') as file:
                config = yaml.safe_load(file)

        self.api_base = config["openai"]["api_base"]
        self.api_key = config["openai"]["api_key"]
        self.api_version = config["openai"]["api_version"]
        self.embedding_model = config["openai"]["db_embedding_model"]
        # self.ans_gen_base_model = config["openai"]["ans_gen_base_model"]
        # self.ans_gen_model = '-'.join(['wkms', self.ans_gen_base_model])
        # self.summary_base_model = config["openai"]["summary_base_model"]
        # self.summary_model = '-'.join(['wkms', self.summary_base_model])
        
        self.logger = logger
        self.client = AzureOpenAI(
                                api_key=self.api_key,  
                                api_version=self.api_version,
                                azure_endpoint=self.api_base,
                                )

        self.llm_client = AzureChatOpenAI(
                                            deployment_name=aoai_model,
                                            azure_endpoint=self.api_base,
                                            openai_api_key=self.api_key,
                                            openai_api_version=self.api_version,
                                            temperature=0
                                        )
    
    # image를 gpt를 사용하여 전처리
    @retry(wait=wait_random_exponential(min=2, max=300), stop=stop_after_attempt(5))
    def gpt_preprocessing_image(self, sas_url, model=None) :

        if model is None:
            model = "demo-gpt-4o-mini"
        
        response = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            { "role": "system", "content": "You are a helpful assistant. Be sure to answer in Korean. Organize the PDF contents thoroughly, and avoid adding any explanations or extra information. Use alternative formatting for text marked with **." },
                            { "role": "user", "content": [  
                                { 
                                    "type": "text", 
                                    "text": "Please organize all the contents in the image and create a document" 
                                },
                                { 
                                    "type": "image_url",
                                    "image_url": {
                                        "url": sas_url
                                    }
                                }
                            ] } 
                        ],
                        max_tokens=4096
                    )
        return response
    
    # embedding
    @retry(wait=wait_random_exponential(min=2, max=300), 
           stop=stop_after_attempt(20)
    )
    def generate_embeddings(self, text, model=None):
        self.logger.info("###### Function Name : generate_embeddings")
        if model is None:
            model = '-'.join(['wkms', self.embedding_model])

        self.logger.info(f"###### Embedding Model Name : {model}")

        try:
            # embedding = client.embeddings.create(input=[text], model=model).data[0].embedding
            embedding = self.client.embeddings.create(input=[text], model=model).data[0].embedding
            return embedding
  
        except Exception as error:
            raise HttpResponseError(message="Decryption failed.", error=error)
        # except Exception as e:
        #     # 실패 이유를 로그로 남기기
        #     self.logger.error(f"임베딩 생성 실패: {e}")
        #     raise

    #@retry(wait=wait_random_exponential(min=2, max=300), stop=stop_after_attempt(20))
    def generate_answer(self, query_1, query_2, as_instance, generate_type, chat_history, documents=None, tokenizer=None) :
 
        start_time = time.time()

        if generate_type == 'refinement' :

            system_msg_prompt = as_instance.read_file(file_path="prompt/refinement_system.txt")
            human_msg_prompt = as_instance.read_file(file_path="prompt/refinement_human.txt")

        elif generate_type == 'qa' :
            system_msg_prompt = as_instance.read_file(file_path="prompt/system.txt")
            human_msg_prompt = as_instance.read_file(file_path="prompt/human.txt")

        else :
            system_msg_prompt = as_instance.read_file(file_path="prompt/system.txt")
            human_msg_prompt = as_instance.read_file(file_path="prompt/human.txt")

        system_message_prompt = SystemMessagePromptTemplate.from_template(system_msg_prompt)
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_msg_prompt)

        end_time = time.time()
        prompt_load_time = end_time - start_time

        start_time = time.time()
        content = system_msg_prompt + human_msg_prompt + query_1['question'] + chat_history
        tokenSize = calculate_token(content=content, tokenizer=tokenizer)
        
        if query_2['intent'].lower() == 'summary' or query_2['intent'].lower() == 'drafting':
            max_input_token = 64000 - 1500
        else:
            max_input_token = 16385 - 1500

        limit = max_input_token - tokenSize
        
        # limit = 16385  - len(tokenizer.encode(system_msg_prompt)) - len(tokenizer.encode(human_msg_prompt)) - len(tokenizer.encode(query['question'])) - len(tokenizer.encode(chat_history)) - 1500


        self.logger.info(f"############# MAX_DOCUMENTS_TOKEN : {limit}") 
        

        if documents != None :
            if generate_type == 'qa':
                documents = documents.replace('\n', '').replace('─','')

            document_tokens = tokenizer.encode(documents)
            tokenSize = len(tokenizer.encode(system_msg_prompt + human_msg_prompt + query_1['question'] + documents))
        
            if tokenSize > max_input_token :
                document_tokens = document_tokens[:limit]
                documents = tokenizer.decode(document_tokens)
                tokenSize = len(document_tokens)

            self.logger.info(f"############# TOKEN_SIZE : {tokenSize}") 

        end_time = time.time()
        cal_token_time = end_time - start_time

        chain_kwargs = {
            "llm": self.llm_client,
            "verbose": True,
        }

        chat_prompt = ChatPromptTemplate.from_messages([system_message_prompt, human_message_prompt])
        chain_kwargs["prompt"] = chat_prompt
        llm_chain = LLMChain(**chain_kwargs)

        if generate_type == 'refinement' :
            start_time = time.time()
            answer = llm_chain.predict(question=query_1['question'], chat=chat_history)
            end_time = time.time()
        elif generate_type == 'qa' :
            start_time = time.time()

            keywords = query_1['keywords']
            if isinstance(keywords, str):
                keywords = keywords.split(',')

            answer = llm_chain.predict(question=query_1['question'], chat=chat_history, keywords=keywords, document=documents)
            end_time = time.time()
        elif generate_type == 'search':
            start_time = time.time()

            keywords = query_1['keywords']
            if isinstance(keywords, str):
                keywords = keywords.split(',')

            answer = llm_chain.predict(question=query_1['question'], chat=chat_history, keywords=keywords, document=documents)
            end_time = time.time()
        else:
            pass
        
        predict_time = end_time-start_time
        # answer = answer.replace("```","").replace('json','')

        self.logger.info(f"############# PROMPT_LOAD : {prompt_load_time}") 
        self.logger.info(f"############# CAL_TOKEN_TIME : {cal_token_time}") 
        self.logger.info(f"############# PREDICT_TIME : {predict_time}") 
        
        return answer, predict_time
