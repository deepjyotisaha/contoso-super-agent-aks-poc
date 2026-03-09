from pydantic import BaseModel


class PromptRequest(BaseModel):
    prompt: str
    context: dict | None = None  # optional metadata, reserved for future use


class PromptResponse(BaseModel):
    response: str
    source: str
    prompt_received: str
