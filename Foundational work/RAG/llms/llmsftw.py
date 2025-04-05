from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
import os
from langchain_openai import ChatOpenAI

# Initialize the ChatOpenAI model
llm = ChatOpenAI(model="gpt-3.5-turbo")  # or "gpt-4"

# Prompt user for input
user_input = input("Enter your Question: ")

# Prepare the message for the LLM (this can stay as a list of dicts)
messages = [{"role": "user", "content": user_input}]

# Use the ChatOpenAI call method to get a response (not generate)
response = llm.invoke(messages)

# Print the full response to inspect its structure
print(response)

# If the response contains the expected data, access it like this
# print(response['choices'][0]['message']['content'])
