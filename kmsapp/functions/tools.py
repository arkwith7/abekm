import json
import re
import ast
import base64
import subprocess
import os

from bs4 import BeautifulSoup
from datetime import datetime
from openai import AzureOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    )


def calculate_token(content, tokenizer):
    # tokenizer = tiktoken.get_encoding("cl100k_base")
    # tokenizer = tiktoken.encoding_for_model(model)
    encoding_result = tokenizer.encode(content)
    return len(encoding_result)

def chunked_texts(logger, content, tokenizer, max_tokens=6000, min_tokens=1000, overlap_percentage=0.1):
    logger.info("###### Function Name : chunked_texts")
    tokens = tokenizer.encode(content)
    overlap_tokens = int(max_tokens * overlap_percentage)
    min_tokens = min_tokens  # 설정한 최소 토큰 수
    chunk_list = []
    start_index = 0

    while start_index < len(tokens):
        if start_index + max_tokens >= len(tokens):  # 다음 청크가 마지막 청크인 경우
            if len(tokens) - start_index < min_tokens:  # 마지막 청크의 크기가 최소 토큰 수보다 작은 경우
                if chunk_list:  # 이전 청크가 있다면 마지막 청크를 이전 청크와 합침
                    chunk_list[-1] += tokenizer.decode(tokens[start_index:])
                    break
                else:  # 청크가 하나도 없다면 현재 토큰들을 그대로 사용
                    chunk_list.append(tokenizer.decode(tokens[start_index:]))
                    break
            else:  # 마지막 청크의 크기가 최소 토큰 수 이상인 경우
                chunk_list.append(tokenizer.decode(tokens[start_index:]))
                break
        else:
            end_index = min(start_index + max_tokens, len(tokens))
            chunk_tokens = tokens[start_index:end_index]
            chunk = tokenizer.decode(chunk_tokens)
            chunk_list.append(chunk)
            start_index += max_tokens - overlap_tokens
    
    return chunk_list

def preprocessing_documents(logger, content, file_psl_nm, file_lgc_nm, ori_file_id, tokenizer, num_token, content_file, aoai_instance, aisearch_instance, config):
    now = datetime.now()
    preprocessing_time = now.strftime("%Y-%m-%dT00:00:00Z")
    
    model_name = '-'.join(['wkms', config["openai"]["db_embedding_model"]])
    file_name = file_psl_nm
    title = content.strip().split('\n')[0]
    page_num = int(content_file.split('/')[-1].split('.txt')[0][4:])

    if num_token > 8000 :
        chunked_list = chunked_texts(logger=logger, content=content, tokenizer=tokenizer, max_tokens=7000, overlap_percentage=0.3)
        for i, chunk in enumerate(chunked_list) :
            chunk = chunk.strip()
            main_text = \
f"""
(file_name) {file_lgc_nm}

(title) {title}

(content)
{chunk}
""".strip()
            document = {"file_index_id": ori_file_id,
                        "file_lgc_nm" : file_lgc_nm,
                        "file_psl_nm" : file_name,
                        "title" : title,
                        "page_num" : page_num,
                        "chunk_num" : i,
                        "chunk_text": chunk,
                        "main_text" : main_text,
                        "preprocessing_time" : preprocessing_time,
                        "del_yn" : False}
            
            # save_path = f"documents/{'.'.join(file_name.split('.')[:-1])}/{title}_{i}.json"
            # json_data = json.dumps(document, ensure_ascii=False, indent=4).encode('utf-8')  
            # as_instance.upload_file(json_data, file_path=save_path, overwrite=True)
            # logger.info(f"Upload Complete ( {save_path} )")
            original_key = document['file_psl_nm'] + '_' + str(document['page_num']) + '_' + str(document['chunk_num'])
            encoded_key = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
            document['id'] = encoded_key

            # result = aisearch_instance.get_item(file_physical_name = chunk, target_nm='chunk_text', select_list=['chunk_text_vector', 'main_text_vector'], is_result = True)
            # if result:
            #     if result['chunk_text_vector']:
            #         chunk_text_vector = result['chunk_text_vector']
            #     else:
            #         chunk_text_vector = aoai_instance.generate_embeddings(document['chunk_text'].strip(), model=model_name)
                
            #     if result['main_text_vector']:
            #         main_text_vector = result['main_text_vector']
            #     else:
            #         main_text_vector = aoai_instance.generate_embeddings(document['main_text'].strip(), model=model_name)
            
            chunk_text_vector = aoai_instance.generate_embeddings(document['chunk_text'].strip(), model=model_name)
            main_text_vector = aoai_instance.generate_embeddings(document['main_text'].strip(), model=model_name)
            document['chunk_text_vector'] = chunk_text_vector
            document['main_text_vector'] = main_text_vector
            

            aisearch_instance.upload_to_index(document=document)
            
    else :
        content = content.strip()
        main_text = \
f"""
(file_name) {file_lgc_nm}

(title) {title}

(content)
{content}
""".strip()
        document = {"file_index_id": ori_file_id,
                    "file_lgc_nm" : file_lgc_nm,
                    "file_psl_nm" : file_name,
                    "title" : title,
                    "page_num" : page_num,
                    "chunk_num" : 0,
                    "chunk_text": content,
                    "main_text" : main_text,
                    "preprocessing_time" : preprocessing_time,
                    "del_yn" : False
                    }

        # save_path = f"documents/{'.'.join(file_name.split('.')[:-1])}/{title}.json"
        # json_data = json.dumps(document, ensure_ascii=False, indent=4).encode('utf-8')  
        # as_instance.upload_file(json_data, file_path=save_path, overwrite=True)
        # logger.info(f"Upload Complete ( {save_path} )")

        chunk_text = document['chunk_text'].strip()
        main_text = document['main_text'].strip()

        if len(chunk_text) == 0:
            return None

        original_key = document['file_psl_nm'] + '_' + str(document['page_num'])
        encoded_key = base64.urlsafe_b64encode(original_key.encode('utf-8')).decode('utf-8')
        document['id'] = encoded_key

        # result = aisearch_instance.get_item(file_physical_name = content, target_nm='chunk_text', select_list=['chunk_text_vector', 'main_text_vector'], is_result = True)
        # if result:
        #     if result['chunk_text_vector']:
        #         chunk_text_vector = result['chunk_text_vector']
        #     else:
        #         chunk_text_vector = aoai_instance.generate_embeddings(document['chunk_text'].strip(), model=model_name)
               
        #     if result['main_text_vector']:
        #         main_text_vector = result['main_text_vector']
        #     else:
        #         main_text_vector = aoai_instance.generate_embeddings(document['main_text'].strip(), model=model_name)

        chunk_text_vector = aoai_instance.generate_embeddings(document['chunk_text'].strip(), model=model_name)
        main_text_vector = aoai_instance.generate_embeddings(document['main_text'].strip(), model=model_name)
        document['chunk_text_vector'] = chunk_text_vector
        document['main_text_vector'] = main_text_vector
        

        aisearch_instance.upload_to_index(document=document)
        logger.info(f"Upload Complete")
    
    return None

def get_prompt(logger, prompt_path):
    
    logger.info("###### Function Name : get_prompt")
    logger.info(prompt_path)
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()
    
    return prompt

def extract_data(logger, text, start, end=None):
    logger.info("###### Function Name : extract_data")
    data_list = []
    start_index = text.find(start)

    if start_index != -1:
    
        while start_index != -1:
            start_index += len(start)
            
            if end is None:
                data = text[start_index:].strip()
                data_list.append(data)
                break
            else:
                end_index = text.find(end, start_index)
                if end_index != -1:
                    data = text[start_index:end_index].strip()
                    data_list.append(data)
                    start_index = text.find(start, end_index)
                else:
                    data = text[start_index:].strip()
                    data_list.append(data)
                    break

    elif start_index == -1:
        data_list.append("None")
 
    return data_list

def preprocessing_answer(logger, answer, answer_type):
    logger.info("###### Function Name : preprocessing_answer")
    
    if answer_type == 'qa' :
        try :
            cleaned_json = "\n".join(line for line in answer.splitlines() if not line.startswith("```"))
            answer = json.loads(cleaned_json)

        except:
            cleaned_json = fix_json_returns(logger, answer)
            answer = json.loads(cleaned_json)

            
    elif answer_type == 'refinement' :
        try :
            cleaned_json = "\n".join(line for line in answer.splitlines() if not line.startswith("```"))
            answer = json.loads(cleaned_json)

        except:
            cleaned_json = fix_json_returns(logger, answer)
            answer = json.loads(cleaned_json)
 
    return answer

def fix_json_returns(logger, answer):
    cleaned_json = "\n".join(line for line in answer.splitlines() if not line.startswith("```"))
    cleaned_json_list = cleaned_json.splitlines()
    logger.info(f'############ cleaned_json_list: {cleaned_json_list}')

    for i, line in enumerate(cleaned_json_list):
        # print(line)
        # 첫번째 항목('{')은 건너뜀
        if i == 0:
            if line == '{':
                continue
            else:
                line = '{'
        # 마지막 항목 ('}')도 건너뜀
        elif i == (len(cleaned_json_list)-1):
            if line == '}':
                break
            else:
                line = '}'
        
        # 문자열이 [로 끝나거나 ','로 끝나거나 4번째 전이거나 2번째 전인 경우??
        if line.endswith('[') or line.endswith(',') or i == (len(cleaned_json_list)-4) or i == (len(cleaned_json_list)-2):
            pass
        else:
            line += ','
        
        if not line.strip().startswith(']') and not line.strip().startswith('"'):
            first_non_space_index = len(line) - len(line.lstrip())
            line = line[:first_non_space_index] + '"' + line[first_non_space_index:]

        if line[-2] == ']' or line.endswith('[') or i == (len(cleaned_json_list)-2):
            pass
        elif i == (len(cleaned_json_list)-4):
            if line[-1] != '"' and line[-1] != ',':
                line += '"'
        else:
            if 'None' not in line and line[-2] != '"':
                line_to_list = list(line)
                line_to_list[-2] = line_to_list[-2] + '"'
                line = ''.join(line_to_list)
            elif 'None' in line:
                line = line.replace('None', '""')

        line = re.sub(r'(?<!\\)\\(?!\\)', r'\\\\', line)
        line = line.replace('"[', '[').replace(']"', ']')
        # line = line.replace("'", '"')
        line = line.rstrip()

        cleaned_json_list[i] = line

    cleaned_json = '\n'.join(cleaned_json_list)

    logger.info(f'############ cleaned_json: {cleaned_json}')

    return cleaned_json

def preprocessing_req_body(logger, body, body_type):
    logger.info("###### Function Name : preprocessing_req_body")

    if body_type == 'chat' :
        query = {'question' : body['params']['question'],
                 'loginEmpNo' : body['params']['loginEmpNo'],
                 'sessionId' : body['params']['sessionId'],
                 'filePhysicalName' : body['params']['filePhysicalName']}
    
    elif body_type == 'preprocessing' :
        query = {'file_name' : body['params']['FileName']}

    elif body_type == 'search':
        query = {
                 'question' : body['params']['question'],
                 'loginEmpNo' : body['params']['loginEmpNo'],
                 'sessionId' : body['params']['sessionId'],
                 'searchMode' : body['params']['searchMode']
                }

    else :
        pass

    return query

def preprocessing_output(logger, query, search_result=None, code=None, error=None):
    logger.info("###### Function Name : preprocessing_output")

    # 답변 내보내기 전 마지막 형식 체크
    if isinstance(query['qa_answer']['response_body'], str):
        query['qa_answer']['response_body'] = []
    
    if isinstance(query['qa_answer']['keyword_list'], str):
        query['qa_answer']['keyword_list'] = []

    if code == None :
        logger.info(f"============================== GENERATE ANSWER\n")
        output = {'status' : 'success',
                'question' : query['question'], 
                # 'refinement' : query['refinement_answer'],
                'qa_answer' : query['qa_answer'],
                'pretty_answer' : query['pretty_answer'],
                # 'search_result' : search_result,
                "file_info" : query['file_info']}
    
    elif code == "Error" :
        logger.info(f"============================== GENERATE ERROR OUTPUT\n")
        output = {'status' : f'Error',
                'question' : query['question'], 
                # 'refinement' : "",
                'qa_answer' : {'check':error},
                'pretty_answer' : "불편을 끼쳐드려서 죄송합니다. <br><br>다시 시도해 주세요.",
                # 'search_result' : "",
                "file_info" : []}
        
        query['pretty_answer'] = output['pretty_answer']
    
    elif code == "FIX_1" :
        logger.info(f"============================== GENERATE FIX OUTPUT\n")
        output = {'status' : 'FIX_1',
        'question' : query['question'], 
        # 'refinement' :query['refinement_answer'],
        'qa_answer' : {},
        'pretty_answer' : "죄송합니다. 저는 웅진의 업무를 도와드리는 <strong>사내 챗봇</strong>입니다. <br><br>질문의 의도를 잘 파악하지 못했습니다. <br><br>다시 시도하시거나 <strong>업무와 관련된 질문</strong>을 해주시겠어요? <br><br>감사합니다.",
        # 'search_result' : "",
        "file_info" : []}

        query['pretty_answer'] = output['pretty_answer']
    
    elif code == "FIX_2" :
        logger.info(f"============================== GENERATE FIX OUTPUT\n")
        output = {'status' : 'FIX_2',
        'question' : query['question'], 
        # 'refinement' :query['refinement_answer'],
        'qa_answer' : query['qa_answer'],
        'pretty_answer' : "죄송합니다. <strong>현재로서는</strong> 관련된 문서를 찾을 수 없습니다. <br><br>지속적인 업데이트를 통해 문서들을 계속 추가중에 있습니다. <br><br>관련 문서가 업데이트 되면 다시 시도해 주세요. <br><br>감사합니다.",
        # 'search_result' : search_result,
        "file_info" : query['file_info']}       

        query['pretty_answer'] = output['pretty_answer']

    elif code == "FIX_3" :
        logger.info(f"============================== GENERATE FIX OUTPUT\n")
        output = {'status' : 'FIX_3',
        'question' : query['question'], 
        # 'refinement' :query['refinement_answer'],
        'qa_answer' : query['qa_answer'],
        'pretty_answer' : "죄송합니다. <strong>선택하신 파일</strong>에서는 관련된 답변을 드릴 수 없습니다. <br><br>선택하신 파일을 확인해주세요. <br><br>감사합니다.",
        # 'search_result' : search_result,
        "file_info" : query['file_info']}       

        query['pretty_answer'] = output['pretty_answer']

    else:
        pass

    return output

def pretty_answer(logger, answer) :
    logger.info("###### Function Name : pretty_answer")

    if isinstance(answer.get('response_body'), list):
        answer = '\n'.join(answer['response_body'])
        ## 변환 결과인 Answer_temp 지정
        answer_pretty = ""

        ## answer를 "\n" 단위로 분리
        lines = answer.split('\n')

        ## 머릿말 안내문구 Bold체 변환 방지
        for i in range(len(lines)):
            ## ":"이 라인이 검출되면, 다음 라인에도 "**"이 있는지 확인하여, 그 여부에 따라 처리
            if lines[i].endswith("**"):
                ## list indexing 에러 방지
                try: 
                    ## "**" 이 있을 경우, 다음 라인에도 "**"이 있는지 확인
                    if lines[i+1].endswith("**"):
                        ## 머릿말 안내문구에 대하여 줄바꿈 개행문자 대신 "<br>" 추가 : 0번 Index가 맞는지 여부에 따라 <br> 추가
                        if i == 0:
                            lines[i] =lines[i][:-1]
                        else:
                            lines[i] = '<br>' + lines[i][:-1]
                        ## 머릿말 안내문구가 확인되었으므로 반복문 정지
                        break
                except: ## Indexerror
                    continue
            ## ":"이 라인이 검출되지 않는 경우 다음 line 확인
            else:
                continue
                
        ## 꼬릿말 안내문구 줄바꿈
        for i in range(len(lines) - 1, 0, -1):
            ## 가장 마지막 줄에서부터 시작하여 "-" 또는 "(숫자)."으로 시작하는 라인이 검출되면, 다음 라인이 꼬릿말 안내문구라고 가정하여 처리
            if '-' in lines[i] or lines[i].strip().split('.')[0].isdigit():
                ## 다음 라인이 없거나 다음 라인이 공백인 경우에만 pass
                if i + 1 >= len(lines) or not lines[i + 1].strip():
                    continue
                ## 다음 라인이 '-'나 숫자로 시작하지 않는 경우에만 <br> 추가
                if not lines[i + 1].strip().startswith('-') and not lines[i + 1].strip().split('.')[0].isdigit():
                    lines[i + 1] = '<br>' + lines[i + 1]
                ## 꼬릿말 안내문구가 확인되었으므로 반복문 정지
                break


        ## 분리된 각 Line들에 대하여 처리
        for line in lines:
            line = line.strip()

            ## Line의 마지막이 "**"으로 종료되면, Bold체로 변환 및 줄바꿈 변경
            if line.endswith("**"):
                line = line.replace("**", "")
                answer_pretty += "\n" + "<strong>" + line + "</strong>" + "\n"
            ## 그렇지 않으면 "\n" 2개
            else:
                answer_pretty += line + "\n"

        answer = answer_pretty[:].strip()
        answer = answer.replace("\n", "<br>")
    else :
        answer = answer['response_body'].replace("\n","<br>")
        answer = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', answer)

    return answer

def filter_logs(logs, log_type):
    filter_chat = str(log_type)
    return [log for log in logs if filter_chat in log]

def count_keywords(file_name, keywords):
    count = 0
    for keyword in keywords:
        if keyword in file_name:
            count += 1
    return count

def process_table_to_text(table_data):
    soup = BeautifulSoup(table_data, 'html.parser')

    # Extract all rows from the table
    rows = soup.find_all('tr')

    # Initialize a list to store the content of each row
    formatted_rows = []

    for row in rows:
        cells = row.find_all(['th', 'td'])
        row_text = [cell.get_text(strip=True) for cell in cells]
        formatted_rows.append(row_text)

    # Determine the maximum number of columns in any row
    max_columns = max(len(row) for row in formatted_rows)

    # Calculate the width of each column considering display width differences
    col_widths = [max(sum(2 if c >= '\u3000' else 1 for c in row[i]) if i < len(row) else 0 for row in formatted_rows) for i in range(max_columns)]

    # Build the formatted text table
    output_text = ""

    for i, row in enumerate(formatted_rows):
        # Create the top border only for the first row or between data rows
        output_text += "+" + "+".join("─" * (width + 2) for width in col_widths) + "+\n"
        
        # Adjust the content considering the visual width
        for j in range(max_columns):
            content = row[j] if j < len(row) else ""
            actual_width = sum(2 if c >= '\u3000' else 1 for c in content)
            padding = col_widths[j] - actual_width
            output_text += f"| {content}{' ' * padding} "
        output_text += "|\n"

    # Add the bottom border for the last row
    output_text += "+" + "+".join("─" * (width + 2) for width in col_widths) + "+\n"

    return output_text

def process_file(content):

    # Find and process all <table> sections
    soup = BeautifulSoup(content, 'html.parser')
    tables = soup.find_all('table')

    pattern = r"<table.*?>(.*?)</table>"
    matches = re.findall(pattern, content, re.DOTALL)

    for i, table in enumerate(tables):
        table_html = str(table)
        table_html_2 = table_html.replace('\n','').replace('<table>','<table>\n').replace('</tr>','</tr>\n')
        processed_text = process_table_to_text(table_html_2)
        content = content.replace(matches[i], processed_text)
    
    pattern = r'!\[\]\(figures/\d+\)'
    content = re.sub(pattern, '', content)

    pattern = r'<!--\s*FigureContent="([^"]+)"\s*-->'
    content = re.sub(pattern, r'\1', content)
    
    pattern = r'<!--.*?-->'
    content = re.sub(pattern, '', content, flags=re.DOTALL)

    pattern = r'<[^>]+>\s*(.*?)\s*</[^>]+>'
    content = re.sub(pattern, r'\1', content)
    content = content.replace('<figure>','').replace('</figure>','')
    content = content.replace('<table>', '').replace('</table>', '')

    pattern = r'\n{3,}'
    content = re.sub(pattern, '\n\n', content)
    return content

def convert_pdf(logger, file_name, as_instance_raw, as_instance_pre) :
    download_file_path = as_instance_raw.download_file(file_path=file_name)
    logger.info(f"download_file_path : {download_file_path}")
    convert_file_dir = os.path.dirname(download_file_path)
    convert_file_name = os.path.splitext(os.path.basename(download_file_path))[0]+'.pdf'
    convert_file_path = os.path.join(convert_file_dir, convert_file_name)

    if not os.path.exists(convert_file_dir):
        os.makedirs(convert_file_dir)

    # LibreOffice CLI 명령어 구성
    command = [
        "/usr/bin/soffice",  # 또는 Windows의 경우 'soffice.exe' 경로 지정
        "--headless",  # GUI 없이 실행
        "--convert-to", 'pdf:impress_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"1"}}',  # 변환 형식 지정
        "--outdir", convert_file_dir,  # 출력 디렉터리 지정
        download_file_path  # 입력 파일
    ]

    try:
        # 명령어 실행
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logger.info("pdf convert complete")
        
        # 변환된 PDF 파일 경로 생성
        output_file = os.path.join(convert_file_dir, convert_file_path)

        logger.info("upload pdf")
        as_instance_pre.upload_file(data= output_file, file_path=f"pdf/{convert_file_name}", overwrite=True)
        return "SUCCESS"
    
    except subprocess.CalledProcessError as e:
        print(f"FAIL CONVERT PDF : {file_name}")
        print(e)
        logger.error(f"FAIL CONVERT PDF : {download_file_path}")
        logger.error(f"FAIL CONVERT PDF : {file_name}")
        logger.error(f"FAIL CONVERT PDF : {e}")
        return "FAIL"

def convert_pdf_sp(logger, file_name, file_type, as_instance_raw, sp_instance, as_instance_pre) :
    try : 
        content = as_instance_raw.read_file(file_path=file_name)

        # sharepoint access info
        sp_instance.get_access_token()
        site_url = 'woongjincokr.sharepoint.com:/sites/wkms'
        site_id = sp_instance.get_site_id(site_url=site_url)
        drive_id = sp_instance.get_drive_id(site_id=site_id)

        # upload file to sharepoint drive
        response = sp_instance.upload_file_to_drive(drive_id, content, file_name)
        file_id = response.get('id')

        # convert pdf to blob storage
        pdf_response = sp_instance.request_item_content('convert',file_id,drive_id)
        as_instance_pre.upload_file(data= pdf_response.content, file_path=f"pdf/{file_name.split(f'.{file_type}')[0]}.pdf", overwrite=True)

        # delete file to sharepoint
        del_result = sp_instance.delete_file_to_drive(drive_id=drive_id, file_id=file_id)

        logger.info(f"SUCCESS CONVERT PDF : {file_name}")

        return "SUCCESS"

    except Exception as e :
        print(f"FAIL CONVERT PDF : {file_name}")
        print(e)
        logger.error(f"FAIL CONVERT PDF : {file_name}")
        logger.error(f"FAIL CONVERT PDF : {e}")
        return "FAIL"
    
    
def extract_keywords(logger, as_instance, search_instance, chat_client, question) :

    refinement_prompt = as_instance.read_file(file_path="prompt/refinement_query.txt")

    human_message_prompt = HumanMessagePromptTemplate.from_template(refinement_prompt)

    chat_prompt = ChatPromptTemplate.from_messages([human_message_prompt])
    synonym_map = search_instance.get_synonym_map('file-index-synonyms')
    logger.info(f"synonym Map: {synonym_map}")

    messages = chat_prompt.format_prompt(question=question, synonym_map=synonym_map)

    openai_response = chat_client.invoke(messages).content.strip()

    try :
        keywords = json.loads(openai_response)

    except:
        # cleaned_json = fix_json_returns(logger, openai_response)
        cleaned_json = "\n".join(line for line in openai_response.splitlines() if not line.startswith("```"))
        keywords = json.loads(cleaned_json)
    
    if isinstance(keywords['nouns'], str) and keywords['nouns'].startswith('['):
        keywords['nouns'] = ast.literal_eval(keywords['nouns'])
    
    if isinstance(keywords['proper_nouns'], str) and keywords['proper_nouns'].startswith('['):
        keywords['proper_nouns'] = ast.literal_eval(keywords['proper_nouns'])

    if isinstance(keywords['corp_names'], str) and keywords['corp_names'].startswith('['):
        keywords['corp_names'] = ast.literal_eval(keywords['corp_names'])

    logger.info(f"KEYWORDS : {keywords}")

    return keywords

def remove_special_characters_and_spaces(text):
    # 정규 표현식을 사용하여 알파벳과 숫자를 제외한 모든 문자 제거
    cleaned_text = re.sub(r'[^a-zA-Z0-9]', '', text)
    return cleaned_text

def make_query_filter(search_filter, target_field, value_list, using_facet_result=False):

    if not using_facet_result:
        main_search_filter = search_filter

        for i, value in enumerate(value_list):
            if i == 0:
                if len(main_search_filter) > 0:
                    value_filter = f" and search.ismatch('{value}', '{target_field}')"
                else:
                    value_filter = f"search.ismatch('{value}', '{target_field}')"
            else:
                value_filter = f" and search.ismatch('{value}', '{target_field}')"
            main_search_filter += value_filter
    
    else:
        main_search_filter = search_filter

        for i, value in enumerate(value_list):
            if i == 0:
                value_filter = f"{target_field} eq '{value}'"
            else:
                value_filter = f" or {target_field} eq '{value}'"
            main_search_filter += value_filter

    return main_search_filter

