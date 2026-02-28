from src.ai.providers.base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is missing")

        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(f"openai package not available: {exc}") from exc

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str, system_prompt: str = "", temperature: float = 0.2) -> str:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.responses.create(
            model=self.model,
            input=messages,
            temperature=temperature,
        )

        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        output = getattr(response, "output", None)
        if output:
            text_parts: list[str] = []
            for item in output:
                for block in getattr(item, "content", []):
                    block_text = getattr(block, "text", "")
                    if block_text:
                        text_parts.append(block_text)
            if text_parts:
                return "\n".join(text_parts).strip()

        return str(response)

