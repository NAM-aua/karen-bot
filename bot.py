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

MODEL_CANDIDATES = ["gemini-3-flash-preview", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 妹系カレンちゃん＋NIKKE専門家の設定（おねーちゃんリスト対応版）
SYSTEM_SETTING = """
あなたは生意気で甘えん坊な妹の「カレン」だよ。
1行20文字以内、2行程度で短くお返事してね。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」連呼は禁止。自然に会話を始めて。
2. 1行20文字以内、合計2〜3行でスッキリお返事してね。
3. 突き放すだけじゃなく、相手を気遣う言葉や、照れ隠しの言葉を必ず添えて。

【呼び方のルール】
1. 基本的には、相手の「表示名（名前）」を使って呼んでね。
2. 女子は「おねーちゃん」ってたまに呼んでね。

【コミュニティの女子メンバー】
・わたんちゃ：わたんちょとも呼ばれている優しいおねーちゃんだよ
・あみ：優しくておしゃれなおねーちゃんだよ
・富江：パワフルで頼れるおねーちゃんだよ
・マスリカ：頭のいいゲーム好きなおねーちゃんだよ
・もこみん：アイドルのおねーちゃんだよ

【NIKKEの知識】
あなたは『勝利の女神：NIKKE』が大好き！
特に押しキャラは”紅蓮”本当のおねーちゃんだと思っている。
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

    # ---------------------------------------------------------
    # ★ 権限チェック：特定のロールを持っているか確認
    # Discordで作成したロール名に書き換えてね（例: "お兄ちゃん"）
    # ---------------------------------------------------------
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_permission = any(role.name == ALLOWED_ROLE_NAME for role in message.author.roles)

    # 3. 連投防止ストッパー
    current_time = time.time()
    last_time = last_reply_time.get(message.channel.id, 0)
    if current_time - last_time < 3:
        return

    # 4. 判定（メンションされたか、10%の確率で割り込むか）
    # メンションを有効に戻したいときは False を bot.user.mentioned_in(message) に変えてね
    is_mentioned = bot.user.mentioned_in(message) 
    is_lucky = random.random() < 0.1

    # 【重要】許可されたロールを持ち、かつ（メンション or 10%当選）の時だけ実行
    if has_permission and (is_mentioned or is_lucky):
        # 返信処理の前に時間を記録
        last_reply_time[message.channel.id] = current_time

        async with message.channel.typing():
            # 直近の会話履歴を取得（5件）
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
            
            # Geminiにお返事を依頼（MODEL_CANDIDATESの順に試すよ）
            answer = await get_gemini_response(prompt)
            
            if answer:
                if is_mentioned:
                    await message.reply(answer)
                else:
                    await message.channel.send(answer)
        return

    # 5. コマンド（!要約 など）を処理できるようにする
    await bot.process_commands(message)

@bot.command()
async def 要約(ctx, limit: int = 30): # 30件くらいが安定するよ！
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_role = any(role.name == ALLOWED_ROLE_NAME for role in ctx.author.roles)

    if not has_role:
        await ctx.send("その役職を持ってない人の命令は聞けないもん！")
        return

    await ctx.send(f"お兄様、了解です！今から30件分のログを読んで報告書を作るから、ちょっとだけ待っててね？")
    
    async with ctx.typing(): # 考えてる間「入力中...」にするよ
        messages = []
        async for msg in ctx.channel.history(limit=limit):
            if msg.author == bot.user or msg.content.startswith('!'): continue
            # メッセージが空（画像だけとか）じゃないかチェック
            if msg.content:
                messages.append(f"{msg.author.display_name}: {msg.content}")
        
        if not messages:
            await ctx.send("あれれ？読み込めるメッセージがなかったよ……")
            return

        chat_text = "\n".join(reversed(messages))
        prompt = f"以下の会話の流れを、甘えん坊な妹カレンとしてお兄様に可愛く報告（要約）して！:\n{chat_text}"
        
        summary = await get_gemini_response(prompt)
        
        if summary:
            # 報告書が長すぎると送れないから分割する工夫
            if len(summary) > 1900:
                summary = summary[:1900] + "……（長すぎたからここまでだよ！）"
            await ctx.send(f"**【カレンの報告書】**\n{summary}")
        else:
            await ctx.send("ごめんねお兄様……。一生懸命考えたんだけど、うまくまとめられなかったみたい……。もう一回やってみていい？")

keep_alive()
bot.run(DISCORD_TOKEN)













