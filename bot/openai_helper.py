from typing import Optional
import openai
import config


class OpenAIHelper:
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)

    async def send_message(
        self,
        message: str,
        dialog_messages: list,
        system_prompt: str,
    ) -> tuple[str, int]:
        messages = [{"role": "system", "content": system_prompt}]
        messages += dialog_messages
        messages.append({"role": "user", "content": message})

        response = await self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )
        answer = response.choices[0].message.content.strip()
        n_tokens = response.usage.total_tokens
        return answer, n_tokens

    async def generate_image(self, prompt: str) -> str:
        response = await self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        return response.data[0].url

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        with open(audio_path, "rb") as audio_file:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return transcript.text.strip() if transcript.text else None
