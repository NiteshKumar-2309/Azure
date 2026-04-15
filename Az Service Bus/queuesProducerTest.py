# Coonect to Azure Service Bus and send a message to a queue
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

def send_single_message(sender):
  message = ServiceBusMessage("Single Message")
  sender.send_messages(message)
  print("Sent a single message")

def send_multiple_messages(sender):
  messages = [ServiceBusMessage("Message in list") for _ in range(5)]
  sender.send_messages(messages)
  print("Sent a list of 5 messages")

service_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)
with service_client:
    sender = service_client.get_queue_sender(queue_name=QUEUE_NAME)
    with sender:
        send_single_message(sender)
        send_multiple_messages(sender)