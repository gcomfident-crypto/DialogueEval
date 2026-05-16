# Please install OpenAI SDK first: `pip3 install openai`
import os

from openai import OpenAI
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing DEEPSEEK_API_KEY. Create a `.env` file in the project root with:\n"
            'DEEPSEEK_API_KEY="your_api_key_here"'
        )

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"},
        ],
        stream=False,
    )

    content = response.choices[0].message.content
    print(content or "The API returned an empty content field.")


if __name__ == "__main__":
    main()
