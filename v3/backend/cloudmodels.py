import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# List all models
for m in client.models.list().data:
    print(m.id)