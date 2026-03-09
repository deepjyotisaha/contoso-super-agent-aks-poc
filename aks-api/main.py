import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
from models import PromptRequest, PromptResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AKS Prompt API",
    description="Receives a user prompt, forwards it to an Azure OpenAI endpoint, and returns the response.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Azure OpenAI configuration — read from environment variables.
# Set these in aks-api/.env (local) or Kubernetes ConfigMap/Secret (AKS).
AZURE_AI_ENDPOINT_URL: str | None = os.getenv("AZURE_AI_ENDPOINT_URL")
AZURE_AI_API_KEY: str | None = os.getenv("AZURE_AI_API_KEY")
AZURE_AI_MODEL: str = os.getenv("AZURE_AI_MODEL", "gpt-4o")
AZURE_AI_API_VERSION: str = os.getenv("AZURE_AI_API_VERSION", "2024-05-01-preview")
AZURE_AI_SYSTEM_PROMPT: str = os.getenv(
    "AZURE_AI_SYSTEM_PROMPT",
    "You are a helpful assistant. Answer the user's question clearly and concisely.",
)


def _get_client() -> AzureOpenAI:
    """Create and return an AzureOpenAI client."""
    if not AZURE_AI_ENDPOINT_URL or not AZURE_AI_API_KEY:
        raise ValueError(
            "AZURE_AI_ENDPOINT_URL and AZURE_AI_API_KEY must be set in environment variables."
        )
    return AzureOpenAI(
        azure_endpoint=AZURE_AI_ENDPOINT_URL,
        api_key=AZURE_AI_API_KEY,
        api_version=AZURE_AI_API_VERSION,
    )


@app.get("/health", tags=["Operations"])
async def health() -> dict:
    """Kubernetes readiness/liveness probe endpoint."""
    ai_configured = bool(AZURE_AI_ENDPOINT_URL and AZURE_AI_API_KEY)
    return {
        "status": "healthy",
        "service": "contoso-agent-api",
        "version": "0.3.0",
        "ai_backend": "azure-openai" if ai_configured else "not-configured",
    }


@app.post("/api/prompt", response_model=PromptResponse, tags=["Prompt"])
async def handle_prompt(request: PromptRequest) -> PromptResponse:
    """
    Accept a user prompt, forward it to Azure OpenAI, and return the response.

    - **prompt**: The text sent by the user.
    - **context**: Optional metadata (reserved for future use).

    Requires environment variables:
    - `AZURE_AI_ENDPOINT_URL`: Azure OpenAI resource base URL
    - `AZURE_AI_API_KEY`: Azure OpenAI API key
    - `AZURE_AI_MODEL`: Deployment name (default: `gpt-4o`)
    - `AZURE_AI_API_VERSION`: API version (default: `2024-05-01-preview`)
    """
    if not AZURE_AI_ENDPOINT_URL or not AZURE_AI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail=(
                "Azure OpenAI is not configured. "
                "Set AZURE_AI_ENDPOINT_URL and AZURE_AI_API_KEY environment variables."
            ),
        )

    try:
        logger.info("Forwarding prompt to Azure OpenAI: model=%s", AZURE_AI_MODEL)

        client = _get_client()
        response = client.chat.completions.create(
            model=AZURE_AI_MODEL,
            messages=[
                {"role": "system", "content": AZURE_AI_SYSTEM_PROMPT},
                {"role": "user", "content": request.prompt},
            ],
        )

        response_text = response.choices[0].message.content
        logger.info("Received response from Azure OpenAI")

        return PromptResponse(
            response=response_text,
            source=f"azure-openai/{AZURE_AI_MODEL}",
            prompt_received=request.prompt,
        )

    except Exception as e:
        logger.error("Azure OpenAI call failed: %s", str(e))
        raise HTTPException(
            status_code=502,
            detail=f"Azure AI Foundry request failed: {str(e)}",
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
