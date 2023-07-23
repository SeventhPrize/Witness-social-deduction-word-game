import openai
import os
from dotenv import load_dotenv

# load_dotenv()  # take environment variables from .env.

# openai.api_key = os.getenv("OPENAI_API_KEY")

# response = openai.ChatCompletion.create(
#   model="gpt-3.5-turbo",
#   max_tokens=100,
#   messages=[
#         {"role": "user", "content": "Who won the world series in 2020?"},
#     ]
# )

# print(response)
# print(response["choices"][0]["message"]["content"])

class GptWitness:
    
    keyword = None
    n_words = None
    banned_words = None

    def __init__(self, keyword, n_words, banned_words):
        self.keyword = keyword
        self.n_words = n_words
        self.banned_words = keyword.split() + banned_words

    def ask(self, prompt):
        msg = ""
        for ind in range(self.n_words):
            msg += "word" + str(ind) + " "
        return msg