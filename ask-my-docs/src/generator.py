import openai
import httpx
import re
from typing import AsyncGenerator

class LLMGenerator:
    def __init__(
        self,
        api_key: str = '',
        model: str = 'gpt-4o-mini',
        use_env_proxy: bool = False,
        base_url: str | None = None,
    ):
        self.api_key = api_key
        self.model = model
        if self.api_key:
            self._http_client = httpx.Client(timeout=15.0, trust_env=use_env_proxy)
            self._async_http_client = httpx.AsyncClient(timeout=15.0, trust_env=use_env_proxy)
            client_options = {"api_key": self.api_key, "max_retries": 0, "http_client": self._http_client}
            async_client_options = {"api_key": self.api_key, "max_retries": 0, "http_client": self._async_http_client}
            if base_url:
                client_options["base_url"] = base_url
                async_client_options["base_url"] = base_url
            self.client = openai.OpenAI(
                **client_options,
            )
            self.aclient = openai.AsyncOpenAI(
                **async_client_options,
            )
        else:
            self.client = None
            self.aclient = None

    def generate(self, query: str, context: str, system_prompt: str) -> str:
        if not self.client:
            return self._fallback_response(context)
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return self._fallback_response(context)

    async def agenerate(self, query: str, context: str, system_prompt: str) -> str:
        if not self.aclient:
            return self._fallback_response(context)
            
        try:
            response = await self.aclient.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return self._fallback_response(context)

    async def agenerate_stream(self, query: str, context: str, system_prompt: str) -> AsyncGenerator[str, None]:
        if not self.aclient:
            yield self._fallback_response(context)
            return
            
        try:
            response = await self.aclient.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                ],
                stream=True
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield self._fallback_response(context)

    def _fallback_response(self, context: str) -> str:
        """Return a cited extract when generation is unavailable.

        This preserves source provenance and lets users read relevant material
        instead of receiving an opaque abstention for a retrievable answer.
        """
        match = re.search(r"^\[1\] Source:.*?\n(.*?)(?=^\[\d+\] Source:|\Z)", context, re.MULTILINE | re.DOTALL)
        if not match:
            return "I don't have enough verified context to answer this question."
        excerpt = " ".join(match.group(1).split())
        if len(excerpt) > 1_500:
            excerpt = excerpt[:1_500].rsplit(" ", 1)[0]
        if not excerpt:
            return "I don't have enough verified context to answer this question."
        return f"Based on the retrieved documentation: {excerpt} [1]"

