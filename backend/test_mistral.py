import os
from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI

load_dotenv()

llm = ChatMistralAI(model="mistral-large-latest")
response = llm.invoke("Hello, are you working?")
print(response.content)