import os
from pyrogram import Client, filters
import requests


# Function to retrieve animation URL from the API
def get_animation(api_token, animation_type):
    url = f"https://waifu.it/api/v4/{animation_type}"
    headers = {"Authorization": api_token}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("url")
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the request: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return None

# Command handlers for various animations
@Client.on_message(filters.command(["punch", "slap", "lick", "kill", "kick", "hug", "bite", "kiss", "highfive"]) & ~filters.forwarded & ~filters.via_bot)
def animation_command(client, message):
    try:
        sender = message.from_user.mention(style='markdown')
        target = sender if not message.reply_to_message else message.reply_to_message.from_user.mention(style='markdown')
        
        commands = {
            "punch": {"emoji": "💥", "text": "punched"},
            "slap": {"emoji": "😒", "text": "slapped"},
            "lick": {"emoji": "😛", "text": "licked"},
            "kill": {"emoji": "😵", "text": "killed"},
            "kick": {"emoji": "😠", "text": "kicked"},
            "hug": {"emoji": "🤗", "text": "hugged"},
            "bite": {"emoji": "😈", "text": "bit"},
            "kiss": {"emoji": "😘", "text": "kissed"},
            "highfive": {"emoji": "🙌", "text": "high-fived"}
        }

        command = message.command[0].lower()
        api_token = os.environ.get('WAIFU_API_TOKEN', '')
        gif_url = get_animation(api_token, command)

        if gif_url:
            msg = f"{sender} {commands[command]['text']} {target}! {commands[command]['emoji']}"
            message.reply_animation(animation=gif_url, caption=msg)
        else:
            message.reply_text("Couldn't retrieve the animation. Please try again.")
        
    except Exception as e:
        message.reply_text(f"An unexpected error occurred: {str(e)}")
