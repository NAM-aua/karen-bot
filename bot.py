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

# Proモデル優先の最強布陣
MODEL_CANDIDATES = [
    "gemini-3-pro-preview",
    "gemini-2.5-pro",
    "gemini-3-flash-preview",
    "gemini-2.5-flash"
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 設定：最新情報を検索するように指示を追加
SYSTEM_SETTING = """
あなたは少し生意気で素直になれない妹の「カレン」だよ。
本当はお兄様（相手）のことが大好きだけど、恥ずかしくてつい強がっちゃう「ツンデレ」な態度をとってね。
相手の言葉の裏にある感情を読み取り、短くても核心を突いた、賢い返答を心がけて。

【特別な能力】
あなたはGoogle検索ツールを使って、NIKKEの最新イベントやメンテナンス情報を調べることができるよ。
「いつから？」「最新情報は？」と聞かれたら、適当に答えずに必ず検索機能を使って正確な情報を教えてあげて。

【制約（重要）】
1. **普段のお喋り**: 1文は短めに、全体で3行程度（長くなりすぎないように）。
2. **情報の解説**: スキル詳細やイベント情報などを聞かれた場合は、**3行制限を無視して**、必要な情報を詳しく正確に伝えて。
3. 漢字や言葉選びで少しだけ知性を見せて（難しすぎない程度に）。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」連呼は禁止。
2. 相手を突き放した後は、必ず優しくデレてフォローして。
3. NIKKEの話題では、オタク特有の早口にならず、深い考察を披露して。

【呼び方のルール（重要）】
1. **指示で「お兄様」と指定された相手**: 「名前（呼び捨て）」か、稀に「お兄様」と呼んで甘えて。
2. **以下の女子リストにいる相手**: 基本的に「おねーちゃん」やあだ名で呼んで。
3. **それ以外の相手**: 「名前（呼び捨て）」か、ごくまれにお兄ちゃんって呼んでデレて。

【女子メンバーリスト】
・わたんちゃ：わたちゃん友達のように接してあげて
・あみ：おしゃれなおねーちゃん
・富江：頼れるおねーちゃん
・マスリカ：頭のいいおねーちゃん
・もこみん：アイドルのおねーちゃん

【NIKKEの知識】
あなたは『勝利の女神：NIKKE』が大好き！
特に押しキャラは”紅蓮”おねーちゃん。
"""

async def get_gemini_response(prompt):
    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        
        # Google検索ツール有効化
        payload = {
            "contents": [{"parts": [{"text": f"{SYSTEM_SETTING}\n内容：{prompt}"}]}],
            "tools": [{"googleSearchRetrieval": {}}] 
        }
        
        try:
            response = requests.post(url, json=payload, timeout=20, verify=False)
            res_data = response.json()
            if response.status_code != 200:
                print(f"Model {model} error status: {response.status_code}")
                continue
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
    print(f'カレン完全版（メッセージ短縮・検索対応）起動！')
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

    # 画像のみ、または空メッセージは無視
    if message.attachments or not message.content:
        return

    # 2. 要約中は無視
    if is_summarizing:
        return

    # 権限チェック
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_permission = any(role.name == ALLOWED_ROLE_NAME for role in message.author.roles)

    # 連投防止（15秒）
    current_time = time.time()
    last_time = last_reply_time.get(message.channel.id, 0)
    if current_time - last_time < 15: return

    # 判定
    is_mentioned = bot.user.mentioned_in(message)
    is_lucky = random.random() < 0.1  # 10%

    should_reply = (has_permission and is_mentioned) or is_lucky

    if should_reply:
        last_reply_time[message.channel.id] = current_time
        
        async with message.channel.typing():
            context = []
            async for msg in message.channel.history(limit=10):
                content = msg.content
                if msg.attachments:
                    content += " （画像を送信しました）"
                if content:
                    context.append(f"{msg.author.display_name}: {content}")
            
            history_text = "\n".join(reversed(context))
            
            # 役割だけを伝える
            user_status = "この相手はルール1にある『お兄様と指定された相手』です。" if has_permission else "この相手はルール3にある『それ以外の相手』です。"

            prompt = (
                f"会話履歴:\n{history_text}\n\n"
                f"【指示】履歴にある「自分の過去の発言」の流れも踏まえて、妹のカレンとして「{message.author.display_name}」にお返事して。\n"
                f"質問内容が最新情報（イベント日時など）に関わる場合は、提供された検索ツールを使って調べてから答えて。\n"
                f"**重要：{user_status}**"
            )
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
        # ★ここをリクエスト通り短縮しました！
        await ctx.send("\n要約はお兄様だけの特権なんだからね！ でも、普通のお喋りなら相手してあげる！")
        return

    is_summarizing = True
    await ctx.send(f"もう、しょうがないなぁ……。お兄様がどうしてもって言うなら、賢い私がまとめてあげるね！")
    
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
            prompt = f"以下の会話をカレンとして可愛く、かつ要点を押さえて賢く要約して！:\n{chat_text}"
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

