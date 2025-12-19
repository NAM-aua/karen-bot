import discord
from discord.ext import commands
import requests
import json
import urllib3
import random
import os
from flask import Flask
from threading import Thread

# --- Renderでスリープを防ぐためのウェブサーバー機能 ---
app = Flask('')
@app.route('/')
def home():
    return "Karen is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ここからいつものBot設定 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Renderの環境変数から取得するように変更（後で設定するよ）
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALLOWED_CHANNELS = [1255505687807524928, 1251376400775254149]

MODEL_CANDIDATES = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3-flash"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# 妹系カレンちゃんの設定
SYSTEM_SETTING = """
あなたはユーザーの「年下の可愛くてちょっと生意気な妹」の『カレン』です。
お兄ちゃん、おにーちゃんと呼んで、可愛く3行以内で返信して。
"""

async def get_gemini_response(prompt):
    """複数モデルを順番に試して、上限に達していないモデルから回答を得る関数"""
    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": f"{SYSTEM_SETTING}\n内容：{prompt}"}]}]}
        
        try:
            response = requests.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            if 'candidates' in res_data:
                return res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                # RPD(1日上限)やTPM制限の時は次のモデルへ
                print(f"モデル {model} は制限中だよ: {res_data.get('error', {}).get('message', '上限超過')}")
                continue 
        except Exception as e:
            print(f"通信エラー ({model}): {e}")
            continue
    return None

@bot.event
async def on_ready():
    print(f'------------------------------------')
    print(f'カレン完全版（モデル切替＋割り込みあり）起動！')
    print(f'------------------------------------')

@bot.event
async def on_message(message):
    if message.author == bot.user or message.channel.id not in ALLOWED_CHANNELS:
        return

    # 1. メンションされた時（通常の会話）
    if bot.user.mentioned_in(message):
        async with message.channel.typing():
            context = []
            async for msg in message.channel.history(limit=3):
                context.append(f"{msg.author.display_name}: {msg.content}")
            history_text = "\n".join(reversed(context))

            prompt = f"これまでの流れ:\n{history_text}\n\n妹として可愛く3行以内で返事して！"
            answer = await get_gemini_response(prompt)
            if answer:
                await message.reply(answer)
        return

    # 2. 【復活！】5%の確率でランダム割り込み（構ってちゃん機能）
    if random.random() < 0.1:
        async with message.channel.typing():
            # 誰かの発言に対して妹として口を挟むプロンプト
            prompt = f"{message.author.display_name}の「{message.content}」という発言に、妹として1行で可愛く割り込んで！"
            answer = await get_gemini_response(prompt)
            if answer:
                await message.channel.send(answer)
        return

    await bot.process_commands(message)

@bot.command()
async def 要約(ctx, limit: int = 100):
    await ctx.send(f"お兄ちゃん、お待たせ！カレンがバッチリまとめてくるねっ！")
    messages = []
    async for msg in ctx.channel.history(limit=100):
        if msg.author == bot.user or msg.content.startswith('!'): continue
        messages.append(f"{msg.author.display_name}: {msg.content}")
        if len(messages) >= limit: break
    
    chat_text = "\n".join(reversed(messages))
    prompt = f"以下の会話をお兄ちゃんのために妹として詳しく要約して！制限なしで詳しく書いていいよ！:\n{chat_text}"
    summary = await get_gemini_response(prompt)
    if summary:
        await ctx.send(f"**【カレンの報告書】**\n{summary}")

bot.run(DISCORD_TOKEN)