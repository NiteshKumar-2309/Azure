# EventPipeline - Configuration Guide

## Overview
This Azure Function processes invoice documents uploaded to Azure Blob Storage using Azure Event Grid triggers. It extracts information using Document Intelligence, generates summaries with Content Understanding, and stores the results in Cosmos DB.

## Environment Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy the `.env.example` file to `.env` and fill in your actual credentials:

```bash
cp .env.example .env
```

Then edit the `.env` file with your Azure service credentials.

### Required Environment Variables

#### Azure Storage
- `stellar07042026_STORAGE`: Connection string for your Azure Storage Account
  - Format: `DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net`

#### Azure Document Intelligence
- `DOCUMENT_INTELLIGENCE_ENDPOINT`: Your Document Intelligence service endpoint
  - Example: `https://your-resource-name.cognitiveservices.azure.com/`
- `DOCUMENT_INTELLIGENCE_KEY`: Your Document Intelligence API key

#### Azure Content Understanding
- `CU_ENDPOINT`: Your Content Understanding service endpoint
- `CU_KEY`: Your Content Understanding API key
- `CU_ANALYZER_ID`: Your analyzer ID for document summarization

#### Azure Cosmos DB
- `COSMOS_CONNECTION_STRING`: Cosmos DB connection string
  - Format: `AccountEndpoint=https://...;AccountKey=...;`
- `COSMOS_DATABASE_NAME`: Database name in Cosmos DB
- `COSMOS_CONTAINER_NAME`: Container name in Cosmos DB

#### Redis Cache
- `REDIS_HOST`: Azure Redis Cache host (e.g., `your-redis.redis.azure.net`)
- `REDIS_PORT`: Redis port (default: `6380`)
- `REDIS_PASSWORD`: Redis access key
- `REDIS_SSL`: Enable SSL connection (default: `True`)
- `REDIS_SOCKET_TIMEOUT`: Socket timeout in seconds (default: `5`)

## Security Notes

⚠️ **IMPORTANT**: 
- Never commit the `.env` file to version control
- The `.env` file is already included in `.gitignore`
- Use `.env.example` as a template (without real credentials)
- For production, use Azure Key Vault or Azure Function App Settings instead of .env files

## Local Development

1. Create and configure your `.env` file
2. Run the function locally:
   ```bash
   func start
   ```

## Deployment

For production deployment:
1. Do NOT deploy the `.env` file
2. Instead, configure these values in Azure Portal:
   - Go to your Function App
   - Navigate to Configuration → Application Settings
   - Add each environment variable there


