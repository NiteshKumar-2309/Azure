import azure.functions as func
import logging
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from azure.ai.contentunderstanding import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisInput
from azure.core.credentials import AzureKeyCredential
from azure.cosmos import CosmosClient
import os
import uuid
import redis
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.ERROR)
logging.getLogger("azure.storage.blob").setLevel(logging.WARNING)
logging.getLogger("azure.ai.documentintelligence").setLevel(logging.WARNING)
logging.getLogger("azure.ai.contentunderstanding").setLevel(logging.WARNING)    
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)

app = func.FunctionApp()

redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST"),
    port=int(os.environ.get("REDIS_PORT", 6380)),
    password=os.environ.get("REDIS_PASSWORD"),
    ssl=os.environ.get("REDIS_SSL", "True").lower() == "true",
    socket_timeout=int(os.environ.get("REDIS_SOCKET_TIMEOUT", 5)),
    decode_responses=True
)

@app.event_grid_trigger(arg_name="event")
def func_event_grid_blob_trigger(event: func.EventGridEvent):
    data = event.get_json()
    blob_url = data.get('url', '')

    logging.info(f"Blob URL: {blob_url}")

    # ── DEDUP USING BLOB URL (Redis) ─────────────────────
    try:
        logging.info("Checking Redis for deduplication")
        redis_key = f"processed:{blob_url}"
        is_new = redis_client.set(redis_key, "1", ex=300, nx=True)  # set if not exists, expire in 5 mins
        if not is_new:
            logging.info("Duplicate event detected, skipping processing.")
            return
        logging.info("New event, proceeding with processing.")
    except Exception as e:
        logging.error(f"Redis error: {str(e)} - proceeding without deduplication")
        
    try:
        # ── 1. Parse URL ───────────────────────────────────────────
        parsed = urlparse(blob_url)
        path = parsed.path.lstrip("/")
        container_name, blob_name = path.split("/", 1)

        # ── 2. Read blob from storage ──────────────────────────────
        conn_str = os.environ["stellar07042026_STORAGE"]
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        blob_content = blob_client.download_blob().readall()
        logging.info(f" Read blob: {blob_name}, {len(blob_content)} bytes")

        # ── 3. Send to Document Intelligence ──────────────────────
        endpoint = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
        key = os.environ["DOCUMENT_INTELLIGENCE_KEY"]
        di_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

        poller = di_client.begin_analyze_document(
            model_id="prebuilt-invoice",
            body=AnalyzeDocumentRequest(bytes_source=blob_content)
        )
        result = poller.result()
        logging.info(f"Analyzed document with Document Intelligence")

        # ── 4. Extract Fields ──────────────────────────────────────
        invoice_doc = result.documents[0] if result.documents else None
        if not invoice_doc:
            logging.warning("No invoice found in document")
            return

        fields = invoice_doc.fields

        def get_field(key):
            return fields.get(key, {}).get("content", None)

        # extract line items
        line_items = []
        for item in fields.get("Items", {}).get("valueArray", []):
            obj = item.get("valueObject", {})
            line_items.append({
                "description": (
                    obj.get("Description", {}).get("content")
                    or obj.get("Item", {}).get("content")
                    or "N/A"
                ),
                "quantity":  obj.get("Quantity",  {}).get("content", "N/A"),
                "unitPrice": obj.get("UnitPrice", {}).get("content", "N/A"),
                "amount":    obj.get("Amount",    {}).get("content", "N/A")
            })

        # ── 5. Content Understanding — Summary ─────────────────────
        # Pass blob_service + already parsed names — no re-parsing needed
        summary = get_invoice_summary(
            blob_service=blob_service,
            blob_url=blob_url,
            container_name=container_name,
            blob_name=blob_name
        )
        logging.info(f"✅ CU Summary: {summary}")

        # ── 6. Build Cosmos Document ───────────────────────────────
        cosmos_doc = {
            "id":           str(uuid.uuid4()),   # required by Cosmos
            "fileName":     blob_name,
            "blobUrl":      blob_url,
            "processedAt":  datetime.now(timezone.utc).isoformat(),

            # DI extracted fields
            "vendorName":   get_field("VendorName")   or "Unknown",
            "invoiceId":    get_field("InvoiceId")    or "N/A",
            "invoiceDate":  get_field("InvoiceDate")  or "N/A",
            "dueDate":      get_field("DueDate")       or "N/A",
            "invoiceTotal": get_field("InvoiceTotal") or "N/A",
            "subTotal":     get_field("SubTotal")     or "N/A",
            "totalTax":     get_field("TotalTax")     or "N/A",
            "lineItems":    line_items,
            "summary":      summary,

            # confidence of overall extraction
            "confidence":   invoice_doc.confidence
        }

        logging.info(f" Invoice: {cosmos_doc['invoiceId']} from {cosmos_doc['vendorName']}")

        # ── 7. Save to Cosmos DB ───────────────────────────────────
        cosmos_client = CosmosClient.from_connection_string(
            os.environ["COSMOS_CONNECTION_STRING"]
        )
        container = cosmos_client \
            .get_database_client(os.environ["COSMOS_DATABASE_NAME"]) \
            .get_container_client(os.environ["COSMOS_CONTAINER_NAME"])

        container.upsert_item(cosmos_doc)
        logging.info(f"Saved to Cosmos DB: {cosmos_doc['id']}")


    except Exception as e:
        logging.error(f"Error processing blob: {str(e)}")


def get_invoice_summary(
    blob_service: BlobServiceClient,
    blob_url: str,
    container_name: str,
    blob_name: str
) -> str:
    """Generate SAS URL and send to CU SDK for summarization."""
    try:
        # ── 1. Generate SAS URL (CU needs public URL to fetch blob) ──
        sas_token = generate_blob_sas(
            account_name=blob_service.account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=blob_service.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(minutes=10)
        )
        sas_url = f"{blob_url}?{sas_token}"
        logging.info("Generated SAS URL for CU")

        # ── 2. Call CU via SDK ────────────────────────────────────
        client = ContentUnderstandingClient(
            endpoint=os.environ["CU_ENDPOINT"],
            credential=AzureKeyCredential(os.environ["CU_KEY"]),
            api_version="2025-11-01"
        )
        poller = client.begin_analyze(
            analyzer_id=os.environ["CU_ANALYZER_ID"],
            inputs=[AnalysisInput(url=sas_url)]
        )
        result = poller.result()

        # ── 3. Extract summary field ──────────────────────────────
        contents = result.get("contents", [])
        if contents:
            summary = contents[0].get("fields", {}).get("Summary", {}).get("valueString", "")
            if summary:
                return summary

        logging.warning("CU returned no summary field")
        return "Summary not available"

    except Exception as e:
        # CU failure won't break the pipeline — DI + Cosmos still save
        logging.error(f"CU Error: {str(e)}")
        return "Summary unavailable"