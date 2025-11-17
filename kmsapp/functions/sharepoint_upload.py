import logging
import azure.functions as func

SCOPE = ['https://graph.microsoft.com/.default']

sharepoint_upload = func.Blueprint() 

@sharepoint_upload.function_name(name="sharepoint-to-db-upload") 
@sharepoint_upload.route(route="sharepoint-to-db-upload", methods=["POST"]) 
def sharepoint_to_db_upload(req: func.HttpRequest) -> func.HttpResponse:
    from database import SharePoint, CosmosDB
    from log import setup_logger, thread_local

    logging.info('Processing SharePoint data request.')

    # Extract parameters from the request
    req_body = req.get_json()
    list_name = req_body['params']['list_name']
    filter_cols = req_body['params']['filter_cols']
    id_colname = req_body['params']['id_colname']
    item_id =  req_body['params']['item_id']

    if not all([list_name,filter_cols]):
        return func.HttpResponse(
            "Please provide list_name,filter_cols in the query string.",
            status_code=400
        )

    try:
        # Initialize SharePointClient
        log_type = f"Batch processing : {list_name} list of sharepoint id - {item_id} "
        logger = setup_logger(preprocess_type=log_type)

        client = SharePoint(logger,SCOPE)
        # Fetch data from SharePoint
        client.get_access_token()
        site_id = client.get_site_id()
        list_id = client.get_list_id(site_id, list_name)

        filtered_value = {}
        file_value_dict = {}

        field_value = client.get_field_value(site_id, list_id, item_id)
        filtered_value = client.filter_field_value(field_value, filter_cols)
        if list_name == 'file':
            temp_value_dict = rename_key(filtered_value, 'id', 'sharepoint_item_id')
            file_value_dict = rename_key(temp_value_dict, '_xd30c__xc77c__x0020__xc0ad__xc8', 'file_size')
            file_value_dict['id'] = file_value_dict.get(id_colname, '').split('_')[0]
            
            if 'file_kywrd' in file_value_dict and file_value_dict['file_kywrd']:
                file_value_dict['file_kywrd'] = file_value_dict['file_kywrd'].split(',')
        else:
            file_value_dict = filtered_value
            file_value_dict['id'] = str(file_value_dict[id_colname])
            
        # Insert and update data to CosmosDB
        db_instance = CosmosDB(logger=logger, database_name=client.to_db_name, container_name=list_name)
        db_instance.upload_item(data=file_value_dict)

        return func.HttpResponse("Data processed and upserted successfully.", status_code=200)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return func.HttpResponse(f"An error occurred: {e}", status_code=500)
    
def rename_key(original_dictionary, old_key, new_key):
    if old_key not in original_dictionary:
        raise KeyError(f"'{old_key}' key not found in dictionary.")
    
    original_dictionary[new_key] = original_dictionary.pop(old_key)
    return original_dictionary