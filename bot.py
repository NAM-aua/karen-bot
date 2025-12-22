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
import asyncio # ★非同期処理用に追加

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
# ★重要修正：最後に「gemini-1.5-flash」を追加！
# 2.5や3.0が制限(RPD 20)で死んでも、1.5(RPD 1500)が必ず拾ってくれます。
CHAT_MODELS = [
    "gemini-2.5-flash-lite", 
    "gemini-2.5-flash", 
    "gemini-3-flash-preview", 
    "gemini-1.5-flash" # ←★これが救世主です
]
SUMMARY_MODELS = ["gemini-2.5-pro", "gemini-3-pro-preview", "gemini-1.5-flash"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

# ★同期的なrequestsを非同期で実行するラッパー関数
async def fetch_gemini(url, payload):
    loop = asyncio.get_running_loop()
    # run_in_executorでBotを止めずに裏で通信させる
    return await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=60, verify=False))

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
            
            # ★ここを変更！非同期呼び出し
            res = await fetch_gemini(url, data)
            
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
            elif res.status_code == 429:
                print(f"Model {model} limit hit (429). Skipping...") # 制限なら次へ
        except Exception as e:
            print(f"Error with {model}: {e}")
            pass

    # 2. 検索なしでリトライ
    print("Retry without search...")
    for model in model_list:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents": [{"parts": [{"text": f"{system_prompt}\n{prompt}"}]}], "safetySettings": safety}
            
            # ★ここも変更
            res = await fetch_gemini(url, data)
            
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return None

@bot.event
async def on_ready(): print('カレン（スタミナ無限＆安定化版）起動！')

@bot.event
async def on_message(message):
    global last_reply_time
    if message.author.bot: return
    
    cid = message.channel.id
    pid = message.channel.parent.id if hasattr(message.channel, 'parent') and message.channel.parent else 0
    if cid not in ALLOWED_CHANNELS and pid not in ALLOWED_CHANNELS: return

    if message.content.startswith('!'): await bot.process_commands(message); return
    if not message.content and not message.attachments: return
    if is_summarizing: return

    has_role = any(r.name == "カレンのお兄様" for r in message.author.roles)
    is_mentioned = bot.user.mentioned_in(message)
    if not ((has_role and is_mentioned) or random.random() < 0.1): return
    
    if time.time() - last_reply_time.get(cid, 0) < 15: return
    last_reply_time[cid] = time.time()

    async with message.channel.typing():
        JST = timezone(timedelta(hours=+9), 'JST')
        now = datetime.now(JST)
        date_info = f"【現在: {now.strftime('%m/%d')} {['月','火','水','木','金','土','日'][now.weekday()]}曜 {now.strftime('%H:%M')}】"

        history = [f"{m.author.display_name}: {m.content}" + (" (画像)" if m.attachments else "") 
                   async for m in message.channel.history(limit=10)]
        
        prompt = (f"{date_info}\n履歴:\n" + "\n".join(reversed(history)) + 
                  f"\n\n指示: 履歴を踏まえ、妹カレンとして「{message.author.display_name}」に返信して。"
                  f"「〇〇に話しかけて」と言われたらその人に向けて話して。")
        
        target_id = pid if pid in ALLOWED_CHANNELS else cid
        answer = await get_gemini_response(prompt, target_id, CHAT_MODELS)
        
        if answer:
            if is_mentioned: await message.reply(answer)
            else: await message.channel.send(answer)
        else:
            await message.channel.send("……ごめん、頭真っ白になっちゃった（エラー）。もう一回言って？")

@bot.command()
async def 要約(ctx, limit: int = 30):
    global is_summarizing
    if not any(r.name == "カレンのお兄様" for r in ctx.author.roles): return
    
    is_summarizing = True
    await ctx.send("しょうがないなぁ。まとめてあげる！")
    try:
        async with ctx.typing():
            msgs = [f"{m.author.display_name}: {m.content}" async for m in ctx.channel.history(limit=limit)
                    if m.author != bot.user and not m.content.startswith('!')]
            if not msgs: await ctx.send("メッセージがないよ！"); return
            
            prompt = (f"以下の会話を読み、カレンの口調で要約報告して。\n"
                      f"必ず【話題】【発言者】の項目を作って中身を詳しく書くこと。\n"
                      f"対象:\n" + "\n".join(reversed(msgs)))
            
            target_id = ctx.channel.parent.id if hasattr(ctx.channel, 'parent') and ctx.channel.parent else ctx.channel.id
            summary = await get_gemini_response(prompt, target_id, SUMMARY_MODELS)
            
            await ctx.send(f"**【カレンの報告書】**\n{summary}" if summary else "ごめん、失敗しちゃった…。")
    finally: is_summarizing = False

keep_alive()
bot.run(DISCORD_TOKEN)
