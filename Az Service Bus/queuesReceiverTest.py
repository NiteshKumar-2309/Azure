# Recieve messgae from Azure Service Bus Queue
import os
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from dotenv import load_dotenv  # load .env for local development
load_dotenv()

# Expected environment variables:
#   SERVICE_BUS_CONNECTION_STR
#   SERVICE_BUS_QUEUE_NAME
CONNECTION_STR = os.getenv('SERVICE_BUS_CONNECTION_STR')
QUEUE_NAME = os.getenv('SERVICE_BUS_QUEUE_NAME')

if not CONNECTION_STR or not QUEUE_NAME:
    raise RuntimeError("Missing SERVICE_BUS_CONNECTION_STR or SERVICE_BUS_QUEUE_NAME environment variables")

def receive_message(receiver):
    received_msgs = receiver.receive_messages(max_message_count=10, max_wait_time=5)
    for msg in received_msgs:
        print("Received: " + str(msg))
        receiver.complete_message(msg)

service_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)
with service_client:
    receiver = service_client.get_queue_receiver(queue_name=QUEUE_NAME)
    with receiver:
        receive_message(receiver)
