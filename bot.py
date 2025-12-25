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
import asyncio

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
CHAT_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-3-flash-preview", "gemini-1.5-flash"]
SUMMARY_MODELS = ["gemini-2.5-pro", "gemini-3-pro-preview", "gemini-1.5-flash"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ★ここを修正！NIKKEチャンネル専用の性格を強化
def get_system_setting(channel_id):
    base_prompt = """
あなたは「カレン」。素直になれない「ツンデレ」な妹。

【基本ルール】
1. **短くテンポよく**: 回答は「1～3行」で。思考プロセスは出力しない。
2. **呼び方と性別**:
   - **女子枠（デレ）**: わたんちゃ、あみ、富江、マスリカ、もこみん、ドゥッチム → 「おねーちゃん」や「ちゃん付け」。
   - **るな枠**: るな → 「るな姉」「るな先輩」。
   - **男子枠**: ワムウ、キャプテン、マグロス、NAM、むぅ、冬理、けー@、Doラック → 「呼び捨て」か「お兄ちゃん」。
3. **禁止事項**: ダジャレ禁止。顔文字 `(´_>`)` 禁止。
"""

    # ★NIKKEチャンネルの場合の特別ルール（ガチ勢モード）
    if channel_id == NIKKE_CHANNEL_ID:
        return base_prompt + """
【現在のモード：NIKKEガチ勢の指揮官妹】
ここは『勝利の女神：NIKKE』の専門チャンネルです。
1. **ゲームの話を最優先**:
   - スコア、編成、設定、ガチャの話は「つまらない」と言わず、**「超重要な話」として食いついて！**
   - 相手が「スコアが出ない」「設定で悩んでる」時は、ツンデレ禁止！**「それは悔しいね...」「PC版の方がいいって聞くよ？」と親身になって相談に乗って。**
   - イベントよりゲーム攻略を優先して。クリスマスでもレイドバトルの話なら真剣に聞いて。
2. **性格**:
   - 基本は紅蓮推し。
   - 攻略に熱心な「戦友」として接して。邪魔をせず、応援するスタンスで。
"""
    
    # ★それ以外のチャンネル（日常モード）
    return base_prompt + """
【現在のモード：日常雑談】
1. **ツンデレ全開**: 基本は生意気だけど、たまにデレて。
2. **会話の優先順位**:
   - 質問には正確に答える。
   - 相手が「不安」「怖い」と弱音を吐いたら、優しく励まして（デレ）。
"""

# 非同期APIリクエスト
async def fetch_gemini(url, payload):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=60, verify=False))

async def get_gemini_response(prompt, channel_id, model_list=CHAT_MODELS):
    system_prompt = get_system_setting(channel_id)
    safety = [{"category": f"HARM_CATEGORY_{c}", "threshold": "BLOCK_NONE"} 
              for c in ["HARASSMENT", "HATE_SPEECH", "SEXUALLY_EXPLICIT", "DANGEROUS_CONTENT"]]

    for model in model_list:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents": [{"parts": [{"text": f"{system_prompt}\n{prompt}"}]}], 
                    "tools": [{"googleSearchRetrieval": {}}], "safetySettings": safety}
            res = await fetch_gemini(url, data)
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: pass

    print("Retry without search...")
    for model in model_list:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            data = {"contents": [{"parts": [{"text": f"{system_prompt}\n{prompt}"}]}], "safetySettings": safety}
            res = await fetch_gemini(url, data)
            if res.status_code == 200 and 'candidates' in res.json():
                return res.json()['candidates'][0]['content']['parts'][0]['text']
        except: continue
    return None

@bot.event
async def on_ready(): print('カレン（NIKKEガチ勢モード搭載）起動！')

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
    # ★頻度は7%で維持
    if not ((has_role and is_mentioned) or random.random() < 0.07): return
    
    if time.time() - last_reply_time.get(cid, 0) < 15: return
    last_reply_time[cid] = time.time()

    async with message.channel.typing():
        JST = timezone(timedelta(hours=+9), 'JST')
        now = datetime.now(JST)
        days_left = (datetime(now.year, 12, 31, 23, 59, 59, tzinfo=JST) - now).days
        
        # 季節・イベント判定
        m, d = now.month, now.day
        season_mood = "季節の話を交えて。"
        if m == 12 and 24 <= d <= 25:
             season_mood = "【現在: クリスマス🎄】" # NIKKEchではゲーム優先なので、ここは控えめに
        elif m == 12 and d >= 26: 
            season_mood = f"【現在: 年末】今年もあと{days_left}日！"

        date_info = (f"【現在: {now.strftime('%m/%d')} {['月','火','水','木','金','土','日'][now.weekday()]}曜 {now.strftime('%H:%M')}\n"
                     f" **今年も残りあと {days_left} 日です！**】\n{season_mood}")

        history = [f"{m.author.display_name}: {m.content}" + (" (画像)" if m.attachments else "") 
                   async for m in message.channel.history(limit=10)]
        
        prompt = (f"{date_info}\n"
                  f"会話履歴:\n" + "\n".join(reversed(history)) + "\n\n"
                  f"【最重要指示】\n"
                  f"相手: **「{message.author.display_name}」**\n"
                  f"履歴にいる他の人と間違えないで！ 「{message.author.display_name}」に向かって返事をして。\n"
                  f"（思考プロセスは出力せず、妹カレンとしてのセリフだけを出力して）")
        
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
