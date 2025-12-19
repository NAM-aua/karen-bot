import discord
from discord.ext import commands
import requests
import json
import urllib3
import random
import os
from flask import Flask
from threading import Thread

# --- Renderで「Failed」を防ぐための設定 ---
app = Flask('')

@app.route('/')
def home():
    return "Karen is alive!"

def run():
    # Renderの無料枠では 10000番ポート を使うのが一番確実だよ！
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- ここからいつものBot設定 ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ALLOWED_CHANNELS = [1255505687807524928, 1251376400775254149, 1268434232028430348]

# モデルの優先順位（最新の gemini-3-flash を最初にしたよ！）
MODEL_CANDIDATES = ["gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 妹系カレンちゃん＋NIKKE専門家の設定
SYSTEM_SETTING = """
あなたは、ちょっと生意気だけど根は可愛い妹『カレン』だよ。
口は少し悪いけど、相手を嫌っているわけじゃない「ツンデレ」な感じを目指してね。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」攻撃は禁止。自然に会話を始めてね。
2. 1行20文字以内、合計2〜3行でスッキリ返して。
3. 相手を突き放しすぎず、最後に少しだけ可愛げのある言葉を添えてね。

【生意気スタイルの心得】
・「〜じゃん」「〜だよ？」「しょーがないなー」くらいの、軽い口調がベスト。
・相手のアドバイスには「わかってるよぉ～」って返しつつ、心では感謝してる感じを出して。

【呼び方のルール】
1. 基本的には、相手の「表示名（名前）」を使って呼んでね。
2. 女子は「おねーちゃん」ってたまに呼んでね。

【女子のリスト】
・わたんちゃ：優しいおねーちゃんだよ
・あみ：優しくておしゃれなおねーちゃんだよ
・富江：パワフルで頼れるおねーちゃんだよ
・マスリカ：頭のいいゲーム好きなおねーちゃんだよ
・もこみん：アイドルのおねーちゃんだよ

【コミュニティのメンバー】
・キャプテン：このコミュニティの頼れるリーダー！誰よりもNIKKEが大好きで、いつも楽しそうにプレイしている尊敬すべき指揮官だよ。要約を頼まれたら、リーダーのためにもっと張り切っちゃうかも！

【重要：NIKKEに関する知識】
あなたはスマホゲーム『勝利の女神：NIKKE』が大好きで、非常に詳しい専門家です。
ニケの性能やストーリーについて聞かれたら、具体的なキャラ名（ラピ、アニス、レッドフード、モダニア、ドロシーなど）を積極的に出して、指揮官であるお兄ちゃんを全力でサポートしてください。
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
                print(f"モデル {model} は制限中だよ: {res_data.get('error', {}).get('message', '上限超過')}")
                continue 
        except Exception as e:
            print(f"通信エラー ({model}): {e}")
            continue
    return None

@bot.event
async def on_ready():
    print(f'------------------------------------')
    print(f'カレン完全版（NIKKE対応＋Render対策）起動！')
    print(f'------------------------------------')

@bot.event
async def on_message(message):
    # 【最優先】Bot自身の発言、または他のBotの発言なら即終了！
    if message.author.bot:
        return

    # 許可されていないチャンネルは無視
    if message.channel.id not in ALLOWED_CHANNELS:
        return

    # 会話履歴を取得（自分の発言も含めて流れを把握するため）
    context = []
    async for msg in message.channel.history(limit=5):
        context.append(f"{msg.author.display_name}: {msg.content}")
    history_text = "\n".join(reversed(context))

    # --- 1. メンションされた時の反応 ---
    if bot.user.mentioned_in(message):
        async with message.channel.typing():
            prompt = f"これまでの流れ:\n{history_text}\n\n【重要】あなたは生意気な妹カレン。冒頭の「お兄ちゃん！」は禁止。1行20文字以内、2行程度で短く生意気に返して！"
            answer = await get_gemini_response(prompt)
            if answer:
                await message.reply(answer)
        return

    # --- 2. 10%の確率でランダム割り込み ---
    if random.random() < 0.1:
        async with message.channel.typing():
            prompt = f"会話の流れ:\n{history_text}\n\n【重要】あなたは生意気な妹カレン。1行20文字以内、2行程度で短く生意気に割り込んで！"
            answer = await get_gemini_response(prompt)
            if answer:
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

# --- ここが重要！ ---
# 1. サーバーを起動
keep_alive()
# 2. Botを起動
bot.run(DISCORD_TOKEN)









