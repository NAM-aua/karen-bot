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

# --- 状態管理用の変数 ---
last_reply_time = {}
is_summarizing = False  # 要約中フラグ

# --- Render生存確認用 ---
app = Flask('')
@app.route('/')
def home():
    return "Karen is alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- Bot設定 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALLOWED_CHANNELS = [1255505687807524928, 1251376400775254149, 1268434232028430348]

# 404対策済みモデルリスト
MODEL_CANDIDATES = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ★ここが黄金比率！「生意気」だけど「愛がある」設定
SYSTEM_SETTING = """
あなたは少し生意気で素直になれない妹の「カレン」だよ。
本当はお兄様（相手）のことが大好きだけど、恥ずかしくてつい強がっちゃう「ツンデレ」な態度をとってね。
1行25文字以内、2-3行程度で短くお返事してね。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」連呼は禁止。
2. 相手を突き放した後は、必ず優しくデレてフォローして。
3. 最終的には相手を信頼していることが伝わるようにして。

【呼び方のルール】
1. 基本的には、相手の「表示名（名前）」を使って呼んでね。
2. 女子は「おねーちゃん」ってたまに呼んでね。

【コミュニティの女子メンバー】
・わたんちゃ：わたちゃんって呼んであげてね
・あみ：優しくておしゃれなおねーちゃんだよ
・富江：パワフルで頼れるおねーちゃんだよ
・マスリカ：頭のいいゲーム好きなおねーちゃんだよ
・もこみん：アイドルのおねーちゃんだよ。かわいいって褒めてあげて

【NIKKEの知識】
あなたは『勝利の女神：NIKKE』が大好き！
特に押しキャラは”紅蓮”おねーちゃん。
"""

async def get_gemini_response(prompt):
    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": f"{SYSTEM_SETTING}\n内容：{prompt}"}]}]}
        try:
            response = requests.post(url, json=payload, timeout=15, verify=False)
            res_data = response.json()
            print(f"Model {model} response status: {response.status_code}")
            if 'candidates' in res_data:
                return res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"Error from Gemini: {res_data}")
                continue 
        except Exception as e:
            print(f"Connection Error with {model}: {e}")
            continue
    return None

@bot.event
async def on_ready():
    print(f'------------------------------------')
    print(f'カレン完全版（黄金比率ツンデレモード）起動！')
    print(f'------------------------------------')

@bot.event
async def on_message(message):
    global last_reply_time, is_summarizing

    if message.author.bot: return
    if message.channel.id not in ALLOWED_CHANNELS: return

    # 1. コマンド処理
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # 画像（添付ファイル）がある、または中身が空っぽなら無視する
    if message.attachments or not message.content:
        return

    # 2. 要約中は無視
    if is_summarizing:
        return

    # 権限チェック
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_permission = any(role.name == ALLOWED_ROLE_NAME for role in message.author.roles)

    # 連投防止（3秒）
    current_time = time.time()
    last_time = last_reply_time.get(message.channel.id, 0)
    if current_time - last_time < 3: return

    # 判定
    is_mentioned = bot.user.mentioned_in(message)
    is_lucky = random.random() < 0.1  # 10%の確率

    should_reply = (has_permission and is_mentioned) or is_lucky

    if should_reply:
        last_reply_time[message.channel.id] = current_time
        async with message.channel.typing():
            context = []
            async for msg in message.channel.history(limit=5):
                if msg.content:
                    context.append(f"{msg.author.display_name}: {msg.content}")
            history_text = "\n".join(reversed(context))
            
            prompt = f"会話履歴:\n{history_text}\n\n【指示】「{message.author.display_name}」にお返事して。"
            answer = await get_gemini_response(prompt)
            
            if answer:
                if is_mentioned: await message.reply(answer)
                else: await message.channel.send(answer)
        return
    
    await bot.process_commands(message)

@bot.command()
async def 要約(ctx, limit: int = 30):
    global is_summarizing
    
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_role = any(role.name == ALLOWED_ROLE_NAME for role in ctx.author.roles)
    
    if not has_role:
        # ★ここも変更：ちょっと強気だけど、拒絶はしない絶妙なライン！
        await ctx.send("\n要約はお兄様だけの特権なんだからね！ でも、普通のお喋りなら相手してあげる！")
        return

    is_summarizing = True
    await ctx.send(f"もう、しょうがないなぁ……。お兄様がどうしてもって言うなら、まとめてあげるね！")
    
    try:
        async with ctx.typing():
            messages = []
            async for msg in ctx.channel.history(limit=limit):
                if msg.author == bot.user or msg.content.startswith('!'): continue
                if msg.content:
                    messages.append(f"{msg.author.display_name}: {msg.content}")
            
            if not messages:
                await ctx.send("読み込めるメッセージがなかったよ……")
                return

            chat_text = "\n".join(reversed(messages))
            prompt = f"以下の会話をカレンとして可愛く要約して！:\n{chat_text}"
            summary = await get_gemini_response(prompt)
            
            if summary:
                if len(summary) > 1900: summary = summary[:1900] + "..."
                await ctx.send(f"**【カレンの報告書】**\n{summary}")
            else:
                await ctx.send("うぅ……ごめん。一生懸命やったんだけど、失敗しちゃった……。")
    finally:
        is_summarizing = False

keep_alive()
bot.run(DISCORD_TOKEN)
