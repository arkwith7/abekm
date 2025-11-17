# import pptx2md
from tools import process_file
import json
from tenacity import retry, stop_after_attempt, wait_random_exponential
import base64
import pandas as pd

class Preprocessing:

    def __init__(self, logger):
        self.logger = logger
    
    #@retry(wait=wait_random_exponential(min=2, max=300), stop=stop_after_attempt(3))
    def document_intelligence(self, file_path, file_name, file_type, as_instance_raw, as_instance_pre, di_instnace) :
        
        #====================================================== 
        # AZURE DOCUMENT INTELLIGENCE
        #====================================================== 
        self.logger.info(f"============================== GET_SAS_URL\n")
        
        if file_type == 'conv_pdf' :
            sas_url = as_instance_pre.get_sas_url(blob_path=f"pdf/{file_name}", expiry_time=False)
        else :
            sas_url = as_instance_raw.get_sas_url(blob_path=file_path, expiry_time=False)
        
        self.logger.info(f"============================== START AZURE DOCUMENT INTELLIGENCE\n")
        
        ori_result = di_instnace.analyze_document(sas_url=sas_url, file_type=file_type, model_type= "documentintelligence", model="prebuilt-layout", output_format="markdown", features="ocrHighResolution", api_version="2024-11-30")
        self.logger.info(f"============================== get DI results (type: {type(ori_result)})\n")

        save_path = f"DI_result/{file_name}.json"
        json_data = json.dumps(ori_result, ensure_ascii=False, indent=4).encode('utf-8') 
        as_instance_pre.upload_file(json_data, file_path=save_path, overwrite=True)
        #====================================================== 
        # PREPROCESSING DOCUMENTS
        #====================================================== 
        #content = result['analyzeResult']['content']
        self.logger.info(f"============================== read json (type: {type(json_data)})\n")
        json_data = as_instance_pre.read_file(save_path)

        try :
            # data = pd.read_json(json_data)
            self.logger.info(f"============================== convert json (type: {type(json_data)})\n")
            # all_data = pd.DataFrame(json_data)
            
            self.logger.info(f"============================== export data\n")
            
            content = json_data['analyzeResult']['content']
            paragraphs = json_data['analyzeResult']['paragraphs']
            pages = json_data['analyzeResult']['pages']
            page_data =pd.DataFrame(pages)
            data = pd.DataFrame(paragraphs)
            self.logger.info(f"{data}\n")

            data_headers = data.columns.values.tolist()

            # self.logger.info(f"============================== {data['boundingRegions']}\n")

            result = []
            combined_text = ""
            combined_spans = []
            page_num = 1

            self.logger.info(f"============================== loop\n")
            if 'boundingRegions' in data_headers:
                for i, row in data.iterrows():
                    
                    if 'role' in data_headers:
                        role = row['role']
                    else:
                        role = ''
                        
                    paragraphs_content = row['content']
                    row_page_num = row['boundingRegions'][0]['pageNumber']
                    spans = row['spans'] if pd.notna(row['spans']) else []

                    if page_num != row_page_num:
                        if combined_text:  # 합쳐진 텍스트가 있다면 결과에 추가
                            result.append([None, combined_text.strip(), combined_spans])
                            combined_text = ""
                            combined_spans = []
                        result.append([role, paragraphs_content, spans])

                        page_num = row_page_num
                    else:
                        if pd.notna(paragraphs_content):
                            combined_text += "--" + str(paragraphs_content)
                            combined_spans.extend(spans)

                            # page_num = row_page_num

                if combined_text:  # 마지막 남은 텍스트를 저장
                    result.append([None, combined_text.strip(), combined_spans])

                # 결과를 DataFrame으로 변환
                result_df = pd.DataFrame(result, columns=["role", "content", "spans"])
                df = result_df.replace("title","sectionHeading")

                rows_to_drop = []
                for i in range(1, len(df)):
                    if df.loc[i, 'role'] == 'sectionHeading' and df.loc[i-1, 'role'] == 'sectionHeading':
                        # Combine the current and previous content
                        df.loc[i-1, 'content'] = f"{df.loc[i-1, 'content']} -- {df.loc[i, 'content']}"
                        rows_to_drop.append(i)

                # Drop the rows that have been merged
                df = df.drop(rows_to_drop).reset_index(drop=True)
                df = df.dropna()
                spans_list = df.dropna()['spans'].tolist()
                offset_list = [item[0]['offset'] for item in spans_list]

                result = []
                for i in range(len(offset_list) - 1):
                    start = offset_list[i]
                    end = offset_list[i + 1]
                    result.append(content[start:end])

                # 마지막 부분은 마지막 offset부터 끝까지
                result.append(content[offset_list[-1]:])
                
                df['main_text'] = result

            else:
                result = []

                for i, row in page_data.iterrows():
                    role = ''
                    spans = row['spans']
                    page_start_idx = row['spans'][0]['offset']
                    page_text_len = row['spans'][0]['length']
                    page = content[page_start_idx:page_start_idx+page_text_len]

                    result.append([role, page, spans])

                # for i, page in enumerate(content.split('<!-- PageBreak -->')):
                #     role = ''
                #     spans = []

                #     result.append([role, page, spans])

                df = pd.DataFrame(result, columns=["role", "main_text", "spans"])


            for i in range(len(df)):
                tmp = df.iloc[i]
                # title = tmp['content']
                # title = title.replace('/',' ').replace('\\','')
                segment = tmp['main_text']
                # self.logger.info(f"============================== content : {segment}\n")
                segment = process_file(segment)
                save_path = f"extracted_text/{file_name}/page{i+1}.txt"
                as_instance_pre.upload_file(data=segment, file_path=save_path, overwrite=True)

        except Exception as e:
            self.logger.error(f"============================== ERROR : {e}\n")
            content = ori_result['analyzeResult']['content']
            title = f"{file_name}"
            save_path = f"extracted_text/{file_name}/{title}.txt"
            print(save_path)
            as_instance_pre.upload_file(data=content, file_path=save_path, overwrite=True)

        return None
