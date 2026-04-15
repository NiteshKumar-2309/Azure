#reciever for messages in topic for multiple subscribers
import os
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from dotenv import load_dotenv  # load .env for local development

load_dotenv()

# Expected environment variables:
#   SERVICE_BUS_CONNECTION_STR
#   SERVICE_BUS_TOPIC_NAME
#   SERVICE_BUS_SUBSCRIPTIONS  (comma-separated list, e.g. "subscription_2,subscription_1")
CONNECTION_STR = os.getenv('SERVICE_BUS_CONNECTION_STR')
TOPIC_NAME = os.getenv('SERVICE_BUS_TOPIC_NAME')
subscriptions_raw = os.getenv('SERVICE_BUS_SUBSCRIPTIONS')

if not CONNECTION_STR or not TOPIC_NAME:
    raise RuntimeError("Missing SERVICE_BUS_CONNECTION_STR or not SERVICE_BUS_TOPIC_NAME environment variables")

if not subscriptions_raw:
    # Fallback to a sensible default list if env is not set
    SUBSCRIPTION_NAMES = ['subscription_2', 'susbscription_1']
else:
    SUBSCRIPTION_NAMES = [s.strip() for s in subscriptions_raw.split(',') if s.strip()]

def receive_message(receiver):
    received_msgs = receiver.receive_messages(max_message_count=10, max_wait_time=5)
    for msg in received_msgs:
        print("Received: " + str(msg))
        receiver.complete_message(msg)

service_client = ServiceBusClient.from_connection_string(conn_str=CONNECTION_STR, logging_enable=True)
with service_client:
    for subscription_name in SUBSCRIPTION_NAMES:
        receiver = service_client.get_subscription_receiver(
            topic_name=TOPIC_NAME, 
            subscription_name=subscription_name,
            prefetch_count=0,
            max_lock_renewal_duration=300  # Set lock renewal duration to 5 minutes
        )
        print(f"Listening to subscription: {subscription_name}")
        with receiver:
            receive_message(receiver)
