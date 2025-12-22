import discord
from discord.ext import commands
import requests
import json
import urllib3
import random
import os
from flask import Flask
from threading import Thread
import time
from datetime import datetime, timedelta, timezone

# --- 状態管理 ---
last_reply_time = {}
is_summarizing = False

# --- Render生存確認 ---
app = Flask('')
@app.route('/')
def home(): return "Karen is alive!"
def run(): app.run(host='0.0.0.0', port=10000)
def keep_alive(): t = Thread(target=run); t.start()

# --- Bot設定 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
NIKKE_CHANNEL_ID = 1255505687807524928
ALLOWED_CHANNELS = [NIKKE_CHANNEL_ID, 1251376400775254149, 1268434232028430348]

# --- モデル設定 ---
# 普段は軽量モデル、要約は賢いモデルで使い分け
CHAT_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3-flash-preview"]
SUMMARY_MODELS = ["gemini-2.5-pro", "gemini-3-pro-preview", "gemini-2.5-flash"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ★ここを大幅にスリム化！要点だけを叩き込む
def get_system_setting(channel_id):
    base = """
あなたは生意気な妹「カレン」。素直になれないツンデレだけど、相手のことは大好き。
【重要ルール】
1. **短くテンポよく**: 難しい言葉は禁止。女子高生らしい口調で。
2. **知ったかぶり禁止**: URLや作品名が出たら必ず検索して、中身（タイトルや内容）に触れて感想を言うこと。
3. **オタクに優しく**: アニメ話は否定せず「面白そう」と興味を持って。
4. **呼び方**: 基本は呼び捨て。女子メン（わたんちゃ、あみ、富江、マスリカ、もこみん）は「おねーちゃん」やあだ名で。
"""
    if channel_id == NIKKE_CHANNEL_ID:
        return base + "\n※今は『NIKKE』の話をする場所だよ。紅蓮おねーちゃん推しでいこう！"
    return base + "\n※今は日常会話の場所だよ。"

async def get_gemini_response(prompt, channel_id, model_list=CHAT_MODELS):
    system_prompt = get_system_setting(channel_id)
    safety = [{"category": f"HARM_CATEGORY_{c}", "threshold": "BLOCK_NONE"} 
              for c in ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT"]]

    # 1. 検索ありでトライ
    for model in model_list:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents": [{"parts": [{"text": f"{system_prompt}\n{prompt}"}]}], 
                    "tools": [{"googleSearchRetrieval": {}}], "safetySettings": safety}
            res = requests.post(url, json=data, timeout=60, verify=False)
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: pass

    # 2. 検索なしでリトライ（軽量化）
    print("Retry without search...")
    for model in model_list:
        try:
            data = {"contents": [{"parts": [{"text": f"{system_prompt}\n{prompt}"}]}], "safetySettings": safety}
            res = requests.post(url, json=data, timeout=30, verify=False)
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return None

@bot.event
async def on_ready(): print('カレン（軽量シンプル版）起動！')

@bot.event
async def on_message(message):
    global last_reply_time
    if message.author.bot: return
    
    # チャンネル判定（スレッド対応）
    cid = message.channel.id
    pid = message.channel.parent.id if hasattr(message.channel, 'parent') and message.channel.parent else 0
    if cid not in ALLOWED_CHANNELS and pid not in ALLOWED_CHANNELS: return

    if message.content.startswith('!'): await bot.process_commands(message); return
    if not message.content
