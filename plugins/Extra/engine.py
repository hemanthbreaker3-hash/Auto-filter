# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

import os
import openai

async def ai(query):
    openai.api_key = os.environ.get("OPENAI_API_KEY")  # set this in your environment/config, never hardcode it
    response = openai.Completion.create(engine="text-davinci-002", prompt=query, max_tokens=100, n=1, stop=None, temperature=0.9, timeout=5)
    return response.choices[0].text.strip()
     
async def ask_ai(client, m, message):
    try:
        question = message.text.split(" ", 1)[1]
        # Generate response using OpenAI API
        response = await ai(question)
        # Send response back to user
        await m.edit(f"{response}")
    except Exception as e:
        # Handle other errors
        error_message = f"An error occurred: {e}"
        await m.edit(error_message)
