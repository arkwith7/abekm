import azure.functions as func 
from chat_api import chat_bp
from preprocessing_blob import preprocessing_bp
from preprocessing_api import preprocessing_api_bp
from preprocessing_queue import preprocessing_queue_bp
from preprocessing_timer import preprocessing_timer_bp
from sap_rfc_pers_info import sap_pers_bp
from sap_rfc_org_info import sap_org_bp
from sharepoint_batch import sharepoint_batch
from sharepoint_upload import sharepoint_upload

# auth_level=func.AuthLevel.ANONYMOUS
app = func.FunctionApp()

app.register_functions(chat_bp) 
# app.register_functions(preprocessing_bp)
app.register_functions(preprocessing_api_bp)
app.register_functions(preprocessing_queue_bp)
app.register_functions(preprocessing_timer_bp)
app.register_functions(sap_pers_bp)
app.register_functions(sap_org_bp)
app.register_functions(sharepoint_batch)
app.register_functions(sharepoint_upload)
