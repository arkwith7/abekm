import streamlit as st
import requests
import json
import logging

# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger(__name__)

LLM_URL = "https://wkms-krcentral-apim.azure-api.net/dev-api/Chat"
FEEDBACK_URL = "https://woongjincokr.sharepoint.com/:l:/s/MSCMS/FLgTFpp0jqlIuYROvkI4A54BremMJhfVw18qkNVdXu2CWw?e=ab0yWw"

st.title("WKMS BOT")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == 'user':
            st.markdown(message["content"], unsafe_allow_html=True)
        else:
            # 파일 정보가 리스트로 변경됨
            msg_file_info_list = message.get("file_info", [])
            msg_view_urls = message.get("view_urls", [])
            msg_download_urls = message.get("download_urls", [])

            st.markdown(message["content"], unsafe_allow_html=True)
            
            # 출처 표시
            if msg_file_info_list:
                st.markdown("**출처:**")
                for file_info in msg_file_info_list:
                    # 파일 정보의 세부 사항에 따라 조정 필요
                    filename = file_info.get('file_logic_name', '미확인 파일')
                    path = file_info.get('file_path', '경로 없음')
                    st.markdown(f"- {filename} (경로: {path})")
            
            # 파일 뷰 및 다운로드 옵션
            for view_url, download_url in zip(msg_view_urls, msg_download_urls):
                if view_url:
                    with st.expander("원본 파일 조회"):
                        if download_url:
                            st.link_button("다운로드", url=download_url)
                        st.markdown(f'<iframe src="{view_url}" width="100%" height="400"></iframe>', unsafe_allow_html=True)

# # 사이드바 추가
st.sidebar.header("WKMS Chatbot")
st.sidebar.markdown("""
WKMS Chatbot 
                    
### 사용 방법

#### 질문 입력
- 메인 화면의 **"질문을 입력하세요."** 입력란에 원하는 질문을 입력합니다.
- 질문을 입력한 후 **Enter** 키를 눌러 질문을 제출합니다.
- 예제 질문 : 삼성물산 관련 제안서 찾아줘
                    
#### 응답 확인
- 질문을 제출하면, AI가 응답을 생성하는 동안 스피너가 표시됩니다. 잠시 기다리면 AI의 답변이 화면에 표시됩니다.
- 제공된 파일에 대한 자세한 내용은 **"원본 파일 조회"** 버튼을 클릭하면 볼 수 있습니다 .
- 파일 조회 후 필요하다고 확인된 경우,**"다운로드"** 버튼을 클릭하여 관련 파일을 다운로드할 수 있습니다.

""")
st.sidebar.link_button("피드백", url=FEEDBACK_URL)

if prompt := st.chat_input("질문을 입력하세요."):
    file_info, view_url, download_url = "", "", ""
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.spinner("답변을 생성하는 중..."):
        try:
            # API 호출
            headers = {
                        'Ocp-Apim-Subscription-Key': '4f832ff8b6b94bbda210b942d0a1421f',
                        'Content-Type': 'application/json'
                        }
            payload = json.dumps({
                                    "params": {
                                        "question": prompt,
                                        "loginEmpNo": "77107676",
                                        "sessionId": "77100665_20241217144125",
                                        "filePhysicalName": ""
                                    }
                                    })
            response = requests.request("POST", LLM_URL, headers=headers, data=payload)
            # response = requests.post(LLM_URL, headers={"Ocp-Apim-Subscription-Key": "262faac5031948cdae99666c6ca740c8", "Content-Type": "application/json"}, json={"params": {"question": prompt, "loginEmpNo": "77100665", "sessionId":"testid-20241213"}})
            # response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        except requests.exceptions.ConnectionError:
            st.error("서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요.")
            st.session_state.messages.append({"role": "assistant", 
                                                "content": "서버 연결 실패",
                                                "file_info": file_info, 
                                                "view_url": view_url, 
                                                "download_url": download_url})
        except requests.exceptions.Timeout:
            st.error("서버 응답 시간이 초과되었습니다.")
            st.session_state.messages.append({"role": "assistant", 
                                                "content": "서버 응답 시간 초과",
                                                "file_info": file_info, 
                                                "view_url": view_url, 
                                                "download_url": download_url})
        except requests.exceptions.HTTPError as e:
            st.error(f"HTTP 오류가 발생했습니다: {e}")
            st.session_state.messages.append({"role": "assistant", 
                                                "content": "HTTP 오류 발생",
                                                "file_info": file_info, 
                                                "view_url": view_url, 
                                                "download_url": download_url})
        except requests.exceptions.RequestException as e:
            st.error(f"API 호출 중 오류가 발생했습니다: {e}")
            st.session_state.messages.append({"role": "assistant", 
                                                "content": "API 호출 실패",
                                                "file_info": file_info, 
                                                "view_url": view_url, 
                                                "download_url": download_url})
        else:
            # Process the response if no exceptions occurred
            try:
                # logger.debug(f"Response Text: {response.text}")
                result = response.json()  # Parse the response JSON safely
            except ValueError:
                st.error("서버로부터 유효하지 않은 JSON 응답을 받았습니다.")
                st.session_state.messages.append({"role": "assistant", 
                                                    "content": "잘못된 JSON 응답", 
                                                    "file_info": file_info, 
                                                    "view_url": view_url, 
                                                    "download_url": download_url})
            else:
                with st.chat_message("assistant"):
                    if result.get("status") == "success":
                        pretty_answer = result.get("pretty_answer", "답변이 없습니다.")
                        
                        # 여러 파일 정보를 처리하기 위한 로직
                        file_info_list = result.get("file_info", [])
                        
                        # 첫 번째 파일 정보를 기본으로 사용 (필요에 따라 조정 가능)
                        first_file_info = file_info_list[0] if file_info_list else "파일 출처 없음"

                        st.markdown(pretty_answer, unsafe_allow_html=True)
                        st.markdown(f"**출처:**")
                        
                        # 모든 파일 정보 표시
                        for file_info in file_info_list:
                            # 각 파일 정보의 상세 내용 추출
                            filename = file_info.get('file_logic_name', '미확인 파일')
                            path = file_info.get('file_path', '경로 없음')
                            view_url = file_info.get('file_view_link', '')
                            download_url = file_info.get('download_sas_link', '')
                            
                            st.markdown(f"- {filename} (경로: {path})")
                            
                            # 파일 뷰 및 다운로드 옵션 추가
                            if view_url or download_url:
                                with st.expander(f"{filename} 원본 파일 조회"):
                                    if download_url:
                                        st.link_button("다운로드", url=download_url)
                                    if view_url:
                                        st.markdown(f'<iframe src="{view_url}" width="100%" height="400"></iframe>', unsafe_allow_html=True)

                        # 세션 상태 업데이트
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": pretty_answer, 
                            "file_info": file_info_list, 
                            "view_urls": [info.get('view_url', '') for info in file_info_list], 
                            "download_urls": [info.get('download_url', '') for info in file_info_list]
                        })

                    else:
                        # 상태가 success가 아닌 경우
                        pretty_answer = result.get("pretty_answer", "답변이 없습니다.")
                        st.markdown(pretty_answer, unsafe_allow_html=True)