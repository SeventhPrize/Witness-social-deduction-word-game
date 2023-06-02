import openai
import os
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

openai.api_key = os.getenv("OPENAI_API_KEY")

response = openai.ChatCompletion.create(
  model="gpt-3.5-turbo",
  max_tokens=100,
  messages=[
        {"role": "user", "content": "Who won the world series in 2020?"},
    ]
)

print(response)
print(response["choices"][0]["message"]["content"])