import os

import boto3
from langchain_aws import ChatBedrockConverse
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import Settings


class ModelStrategyFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build_chat_model(self, temperature: float | None = None):
        resolved_temperature = (
            self._settings.model_temperature if temperature is None else temperature
        )
        if self._settings.model_provider == "groq":
            if not self._settings.groq_api_key:
                raise ValueError("GROQ_API_KEY is required when MODEL_PROVIDER=groq.")
            os.environ["GROQ_API_KEY"] = self._settings.groq_api_key
            return ChatGroq(
                model=self._settings.groq_model,
                temperature=resolved_temperature,
            )

        if self._settings.model_provider == "gemini":
            if not self._settings.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required when MODEL_PROVIDER=gemini.")
            return ChatGoogleGenerativeAI(
                model=self._settings.gemini_model,
                temperature=resolved_temperature,
                google_api_key=self._settings.google_api_key,
            )

        session_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": self._settings.aws_region,
        }
        if self._settings.aws_access_key_id and self._settings.aws_secret_access_key:
            session_kwargs["aws_access_key_id"] = self._settings.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = self._settings.aws_secret_access_key
        if self._settings.aws_session_token:
            session_kwargs["aws_session_token"] = self._settings.aws_session_token

        client = boto3.client(**session_kwargs)
        return ChatBedrockConverse(
            model=self._settings.bedrock_model_id,
            region_name=self._settings.aws_region,
            temperature=resolved_temperature,
            client=client,
        )
