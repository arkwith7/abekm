import logging
import azure.functions as func

SCOPE = ['https://graph.microsoft.com/.default']
sharepoint_batch = func.Blueprint() 

@sharepoint_batch.function_name(name="sharepoint-to-db-batch") 
@sharepoint_batch.route(route="sharepoint-to-db-batch", methods=["POST"]) 
def sharepoint_to_db_batch(req: func.HttpRequest) -> func.HttpResponse:
    from database import SharePoint, CosmosDB
    from log import setup_logger, thread_local

    logging.info('Processing SharePoint data request.')

    # Extract parameters from the request
    req_body = req.get_json()
    list_name = req_body['params']['list_name']
    filter_cols = req_body['params']['filter_cols']
    id_colname = req_body['params']['id_colname']

    if not all([list_name,filter_cols]):
        return func.HttpResponse(
            "Please provide list_name,filter_cols in the query string.",
            status_code=400
        )

    try:
        log_type = f"Batch processing : {list_name}"
        logger = setup_logger(preprocess_type=log_type)
        # Initialize SharePointClient
        client = SharePoint(logger,SCOPE)
        # Fetch data from SharePoint
        client.get_access_token()
        site_id = client.get_site_id()
        list_id = client.get_list_id(site_id, list_name)
        item_id_list = client.get_all_list_items(site_id, list_id)

        if item_id_list:
            for item_id in item_id_list:

                filtered_value = {}
                file_value_dict = {}

                field_value = client.get_field_value(site_id, list_id, item_id)
                filtered_value = client.filter_field_value(field_value, filter_cols)

                file_value_dict = filtered_value
                file_value_dict['id'] = str(file_value_dict[id_colname])
                # Insert and update data to CosmosDB
                db_instance = CosmosDB(logger=logger, database_name=client.to_db_name, container_name=list_name)
                db_instance.upsert_item(data=file_value_dict)

        return func.HttpResponse("Data processed and upserted successfully.", status_code=200)

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return func.HttpResponse(f"An error occurred: {e}", status_code=500)
    
def rename_key(original_dictionary, old_key, new_key):
    if old_key not in original_dictionary:
        raise KeyError(f"'{old_key}' key not found in dictionary.")
    
    original_dictionary[new_key] = original_dictionary.pop(old_key)
    return original_dictionary