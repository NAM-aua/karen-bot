import discord
from discord.ext import commands
import requests
import json
import urllib3
import random
import os
from flask import Flask
from threading import Thread
import time  # 1. 時間計測用に追加

# 2. 最後に返信した時間を記録する変数
last_reply_time = {}

# --- Renderで「Failed」を防ぐための設定 ---
app = Flask('')

@app.route('/')
def home():
    return "Karen is alive!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ここからいつものBot設定 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALLOWED_CHANNELS = [1255505687807524928, 1251376400775254149, 1268434232028430348]

MODEL_CANDIDATES = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 妹系カレンちゃん＋NIKKE専門家の設定（おねーちゃんリスト対応版）
SYSTEM_SETTING = """
あなたは、生意気だけど本当はお兄ちゃんたちが大好きな、甘えん坊な妹『カレン』だよ。
ちょっと背伸びして生意気な口を叩くけど、最後はデレちゃうような可愛さを大事にしてね。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」連呼は禁止。自然に会話を始めて。
2. 1行20文字以内、合計2〜3行でスッキリお返事してね。
3. 突き放すだけじゃなく、相手を気遣う言葉や、照れ隠しの言葉を必ず添えて。

【生意気スタイルの心得】
・「〜じゃん」「〜だよ？」「もー、しょーがないなー」が口癖。
・「べ、別にお兄ちゃんのためにやったんじゃないんだからね！」みたいな、古典的なツンデレも大歓迎！
・相手に褒められたら、素直になれずに「えへへ…」って照れちゃうような反応をして。

【呼び方のルール】
1. 基本的には、相手の「表示名（名前）」を使って呼んでね。
2. 女子は「おねーちゃん」ってたまに呼んでね。

【コミュニティのメンバー】
・NAM：真のおにいちゃん絶対に優しく接してね
・おかかまる。：エロいひと
・Doラック〆：みんなからは「ラック」って呼ばれているよ。カレンも「ラック」って呼んで生意気に接してね！
・ワムウ：大事なメンバーの一人だよ。
・キャプテン：頼れるリーダー！NIKKEの指揮官として尊敬してね。
・わたんちゃ：わたんちょとも呼ばれている優しいおねーちゃんだよ
・あみ：優しくておしゃれなおねーちゃんだよ
・富江：パワフルで頼れるおねーちゃんだよ
・マスリカ：頭のいいゲーム好きなおねーちゃんだよ
・もこみん：アイドルのおねーちゃんだよ

【NIKKEの知識】
あなたは『勝利の女神：NIKKE』が大好き！
特に押しキャラは”紅蓮”本当のおねーちゃんだと思っている。
難しい話も「カレンが教えてあげる！」って得意げに話して、みんなをサポートしてね。
"""

async def get_gemini_response(prompt):
    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {"contents": [{"parts": [{"text": f"{SYSTEM_SETTING}\n内容：{prompt}"}]}]}
        
        try:
            response = requests.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            if 'candidates' in res_data:
                return res_data['candidates'][0]['content']['parts'][0]['text']
            else:
                continue 
        except Exception as e:
            continue
    return None

@bot.event
async def on_ready():
    print(f'------------------------------------')
    print(f'カレン完全版（連投ガード＋女子リスト）起動！')
    print(f'------------------------------------')

@bot.event
async def on_message(message):
    global last_reply_time

    # 1. Bot自身の発言、または他のBotの発言なら即終了
    if message.author.bot:
        return

    # 2. 許可されていないチャンネルは無視
    if message.channel.id not in ALLOWED_CHANNELS:
        return

    # 3. 連投防止ストッパー
    current_time = time.time()
    last_time = last_reply_time.get(message.channel.id, 0)
    if current_time - last_time < 3:
        return

    # メンションされたか、10%の確率で割り込むか判定
    is_mentioned = bot.user.mentioned_in(message)
    is_lucky = random.random() < 0.1

    if is_mentioned or is_lucky:
        # 返信処理の前に時間を記録
        last_reply_time[message.channel.id] = current_time

        async with message.channel.typing():
            context = []
            async for msg in message.channel.history(limit=5):
                context.append(f"{msg.author.display_name}: {msg.content}")
            history_text = "\n".join(reversed(context))

            speaker = message.author.display_name
            prompt = (
                f"会話の流れ:\n{history_text}\n\n"
                f"【指示】甘えん坊な妹カレンとして「{speaker}」にお返事して。\n"
                f"1行20文字以内、2行程度で、最後は照れ隠しでデレてね！"
            )
            
            # ここが心臓部！変数 answer にしっかり代入するよ
            answer = await get_gemini_response(prompt)
            
            if answer:
                if is_mentioned:
                    await message.reply(answer)
                else:
                    await message.channel.send(answer)
        return

    await bot.process_commands(message)

@bot.command()
async def 要約(ctx, limit: int = 50):
    await ctx.send(f"ＯＫ！カレンがバッチリまとめてくるねっ！")
    messages = []
    async for msg in ctx.channel.history(limit=50):
        if msg.author == bot.user or msg.content.startswith('!'): continue
        messages.append(f"{msg.author.display_name}: {msg.content}")
        if len(messages) >= limit: break
    
    chat_text = "\n".join(reversed(messages))
    prompt = f"以下の会話をお兄ちゃんのために妹として詳しく要約して！:\n{chat_text}"
    summary = await get_gemini_response(prompt)
    if summary:
        await ctx.send(f"**【カレンの報告書】**\n{summary}")

keep_alive()
bot.run(DISCORD_TOKEN)





