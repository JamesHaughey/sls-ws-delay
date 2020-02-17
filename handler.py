import json
import boto3
import logging
import time

DYN_TABLE_NAME = "delay_webhook_connections"

logger = logging.getLogger("handler_logger")
logger.setLevel(logging.DEBUG)

dynamodb = boto3.resource("dynamodb")
lmbda = boto3.client("lambda")

def _get_response(status_code, body):
    if not isinstance(body, str):
        body = json.dumps(body)
    return {"statusCode": status_code, "body": body}

def _get_body(event):
    try:
        return json.loads(event.get("body", ""))
    except:
        logger.debug("event body count not be JSON decoded.")
        return {}
    
def _send_to_connection(connection_id, data, event):
    domainName = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    gatewayapi = boto3.client(
        "apigatewaymanagementapi",
        endpoint_url = f"https://{domainName}/{stage}"
    )
    return gatewayapi.post_to_connection(
        ConnectionId=connection_id,
        Data=json.dumps(data).encode('utf-8')
    )
    
def _get_all_connections():
    table = dynamodb.Table(DYN_TABLE_NAME)
    response = table.scan(ProjectionExpression="ConnectionID")
    items = response.get("Items", [])
    return [x["ConnectionID"] for x in items if "ConnectionID" in x]

def request_optimisation(event, context):
    logger.info("Optimisation requested.")
    logger.info(event)
    
    body = _get_body(event)
    for attribute in ["stuff", "things"]:
        if attribute not in body:
            logger.debug(f"Failed: '{attribute}' not in message dict.")
            return _get_response(400, f"'{attribute}' not in message dict.")
    
    stuff = body["stuff"]
    things = body["things"]
    domainName = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    connectionID = event["requestContext"].get("connectionId")
    
    payload_dict = {
        "body" : {
            "connectionID": connectionID,
            "stuff": stuff,
            "things": things,
            "domainName": domainName,
            "stage": stage,
        }
    }
    payload = json.dumps(payload_dict)
    
    lmbda.invoke(
        FunctionName="sls-ws-delay-dev-returnOptimisation",
        InvocationType="Event",
        LogType="Tail",
        Payload=payload
    )
    
    return _get_response(200, "Optimisation requested.")

""" Dummy request
{"action": "requestOptimisation", "stuff": "something", "things": "else"}
"""

def return_optimisation(event, context):
    logger.info("Optimisation calculating.")    
    # Delay to simulate some really dope calculations
    
    logger.info(event)  
    body = event.get("body", "")
    for attribute in ["connectionID", "stuff", "things", "domainName", "stage"]:
        if attribute not in body:
            logger.debug(f"Failed: '{attribute}' not in message dict.")
            return _get_response(400, f"'{attribute}' not in message dict.")
    
    connectionID = body["connectionID"]
    stuff = body["stuff"]
    things = body["things"]
    domainName = body["domainName"]
    stage = body["stage"]
    
    connections = _get_all_connections()
    time.sleep(60)

    message = {
        "message": "Optimisation succesfull",
        "stuff": stuff,
        "things": things
    }
    logger.debug(f"Broadcasting message: {message}")
    data = {"messages": [message]}
    pass_event = {"requestContext": {"domainName": domainName, "stage": stage}}
    for recipient in connections:
        _send_to_connection(recipient, data, pass_event)
        
    return _get_response(200, "Message sent to all connections.")

def connection_manager(event, context):
    """
    Handles connecting and disconecting for the Websocket.
    """
    connectionID = event["requestContext"].get("connectionId")
    
    if event["requestContext"]["eventType"] == "CONNECT":
        logger.info(f"Connect requested: {connectionID}")
        
        # Add connectionID to the database
        table = dynamodb.Table(DYN_TABLE_NAME)
        table.put_item(Item={"ConnectionID": connectionID})
        return _get_response(200, "Connect succesful.")

    elif event["requestContext"]["eventType"] == "DISCONNECT":
        logger.info(f"Disconnect requested : {connectionID}")
        
        # Remove connectionID from the database
        table = dynamodb.Table(DYN_TABLE_NAME)
        table.delete_item(Key={"ConnectionID": connectionID})
        return _get_response(200, "Disconnect succesful.")
    
    else:
        logger.error("Connection manager eceived unrecognized eventType.")
        return _get_response(500, "Unrecognized eventType.")
