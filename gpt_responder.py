"""
GptWitness object lets Sheriff ask questions to the WITNESS via GPT-3.5 Turbo.
"""

import openai
import re
import os
from dotenv import load_dotenv

# Get OpenAI API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

class GptWitness:
    '''
    Uses GPT-3.5 Turbo to allow Sheriff to ask open-ended questions to the Witness.
    '''
    
    game = None
    keyword = None              # String keyword
    n_words = None              # Target number of words for GPT output
    banned_words = None         # List of string banned words
    system_instructions = None  # String system-level prompt to GPT
    verbose = None              # Boolean whether to print prompts and responses to terminal for debugging

    witness_questions = None
    witness_responses = None

    def __init__(self, game, keyword, n_words, banned_words, verbose=True):
        '''
        Initializes this Witness
        INPUT
            game; the associated Game() instance
            keyword; string keyword
            n_words; target number of words for GPT output
            banned_words; list of string banned words
            verbose; boolean whether to print results to terminal
        '''
        self.game = game
        self.keyword = keyword
        self.n_words = n_words
        self.verbose = verbose
        self.banned_words = banned_words
        self.witness_questions = []
        self.witness_responses = []
        
        # Load in system instructions
        with open("GPT System Instructions.txt") as f:
            lines = f.readlines()
        self.system_instructions = "".join(lines)

    def ask(self, question):
        '''
        Asks GPT the input question, then returns a cleaned-up response.
        INPUT
            question; string of the Sheriff's question
        RETURNS
            list of words of self.n_words length, where the words form the GPT response.
                "-" is inserted if the GPT response was fewer than self.n_words length.
                words are truncated off if the GPT response is greater than self.n_words length.
        '''
        if "Hacker" in self.game.powers.keys():
            question = self.witness_questions[-1]

        self.witness_questions.append(question)
        prompt = self.make_prompt(question)

        # Get GPT response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            max_tokens=120,
            messages=[
                    {"role": "system", "content": self.system_instructions},
                    {"role": "user", "content": prompt}
                ]
        )
        answer = response["choices"][0]["message"]["content"]
        self.witness_responses.append(answer)

        # Print if verbose
        if self.verbose:
            print(answer)
            print(response["usage"])
        return self.clean_response(answer)

    def make_prompt(self, question):
        '''
        Constructs the user prompt for GPT.
        INPUT
            question; string of the Sheriff's question
        RETURNS
            string of the user-level prompt for this question
        '''
        prompt = 'Prompt: '
        prompt += f'Length: {self.n_words} words. '
        prompt += f'Keyword: "{self.keyword}". '
        prompt += (f'Banned words: '
                   + ', '.join([f'"{word}"'
                                for word in self.banned_words]
                                + self.keyword.split())
                   + '. ')
        prompt += f'Question: "{question}"'
        if self.verbose:
            print(prompt)
        return prompt
    
    def clean_response(self, answer):
        '''
        Cleans the GPT-issued response.
        Removes off "[#]" notation.
        Adds "-" to fill word count to self.n_words.
        Truncates off words to reduce word count to self.n_words.
        INPUT
            answer; string response from GPT
        '''
        # Clear off "[#]"" notation
        pattern = r"\[\d+\]"
        cleaned = re.sub(pattern, "", answer).split()
        
        # Pad word count
        while len(cleaned) < self.n_words:
            cleaned.append("-")
        
        # Reduce word count
        cleaned = cleaned[: self.n_words]
        return cleaned
    
    def get_banned_words(self):
        with open("GPT Related Words.txt") as f:
            lines = f.readlines()
        instruct = "".join(lines)
        prompt = f'Keyword: "{self.keyword}". Word count: {self.n_words}.'
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            max_tokens=25,
            messages=[
                    {"role": "system", "content": instruct},
                    {"role": "user", "content": prompt}
                ]
        )
        answer = response["choices"][0]["message"]["content"]
        self.banned_words = answer.lower().split()
        if self.verbose:
            print(self.banned_words)


