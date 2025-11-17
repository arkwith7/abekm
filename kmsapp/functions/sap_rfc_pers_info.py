import logging
import azure.functions as func
import json
from datetime import datetime
import os
import pyrfc
import socket

sap_pers_bp = func.Blueprint() 

@sap_pers_bp.function_name(name="sap-rfc-pers-info")
@sap_pers_bp.route(route="sap-rfc-pers-info", methods=["POST"]) 
def sap_rfc_pers_info(req: func.HttpRequest) -> func.HttpResponse:
    
    RFC_FUNC_NAME , RFC_TABLE = "ZWKMS_GET_PERSON_INFO","WKMS_PERS_INFO"
    try:
        # Environment variable fetch remains the same
        logging.info('Python HTTP trigger function processed a request.')
        
        try:
            import ctypes
            # Set the LD_LIBRARY_PATH environment variable
            os.environ['LD_LIBRARY_PATH'] = '/home/site/wwwroot/.python_packages/lib/site-packages/pyrfc'

            # Add the library path to the DLL search directories
            if hasattr(os, 'add_dll_directory'):
                os.add_dll_directory('/home/site/wwwroot/.python_packages/lib/site-packages/pyrfc')

            # Manually load the shared libraries
            ctypes.CDLL('/home/site/wwwroot/.python_packages/lib/site-packages/pyrfc/libicudata.so.50')
            ctypes.CDLL('/home/site/wwwroot/.python_packages/lib/site-packages/pyrfc/libicui18n.so.50')
            ctypes.CDLL('/home/site/wwwroot/.python_packages/lib/site-packages/pyrfc/libicuuc.so.50')
        except Exception as e:
            logging.error(f'cdll error : {e}')
        
        logging.info(f'pyrfc version : {pyrfc.__version__}') 
        conn_test = sap_conn_info()
        logging.info(f'sap_conn_info : {conn_test}')
    
        # Connection creation wrapped in a future to avoid blocking
        try:
            conn_dict = sap_conn_info()
            if conn_dict:
                ashost = conn_dict['ashost']
                sysnr = conn_dict['sysnr']
                port = int(f'33{sysnr}')
                address = f'{ashost}:{port}'
                if is_reachable(ashost, port):
                    logging.info(f"Address {address} is reachable")
                else:
                    logging.error(f"Address {address} is not reachable")
            else:
                logging.error("SAP connection information is not available")
            conn = pyrfc.Connection(**conn_dict)
            logging.info("Successfully established pyrfc connection")
        except Exception as conn_error:
            logging.error(f"Error establishing pyrfc connection: {str(conn_error)}")
            return func.HttpResponse(f"Error establishing pyrfc connection: {str(conn_error)}", status_code=500)
        # test : 77000063 , 윤영근, 실장
        try:

            # input params : I_PERNR, I_RETIREYN, I_CH           
            try:
                req_body = req.get_json()
            except ValueError:
                req_body = None

            # Call the RFC function with the parameters if any are present, otherwise call without parameters
            if req_body:
                result = conn.call(RFC_FUNC_NAME, **req_body)
            else:
                result = conn.call(RFC_FUNC_NAME)

            pers_info_table = json.dumps(result[RFC_TABLE])

            logging.info(f"Successfully called SAP RFC function({RFC_FUNC_NAME})")
            return func.HttpResponse(body=pers_info_table, status_code=200,mimetype="application/json")
        except Exception as call_error:
            logging.error(f"Error calling SAP RFC function({RFC_FUNC_NAME}): {str(call_error)}")
            return func.HttpResponse(f"Error calling SAP RFC function({RFC_FUNC_NAME}): {str(call_error)}", status_code=500)
        
    except Exception as e:
        logging.error(f"Error connection: {str(e)}")
        return func.HttpResponse(f"Error sap connection: {str(e)}", status_code=500)
    
def sap_conn_info():
    try:
        conn_dict = {
            "ashost": os.environ["sap_ashost"],
            "sysnr" : os.environ["sap_sysnr"],
            "client":os.environ["sap_client"],
            "user":os.environ["sap_user"],
            "passwd":os.environ["sap_passwd"],
        }
        return conn_dict
    except Exception as e:
        logging.error(f"Error import environment variables: {str(e)}")
        return None
    
def is_reachable(address, port, timeout=5):
    try:
        # Create a socket object
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        # Try to connect to the address
        sock.connect((address, port))
        sock.close()
        return True
    except socket.error as e:
        logging.error(f"Error connecting to {address}:{port} - {str(e)}")
        return False