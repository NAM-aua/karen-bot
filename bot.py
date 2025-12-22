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
is_summarizing = False

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

# ★チャンネル設定
NIKKE_CHANNEL_ID = 1255505687807524928
ALLOWED_CHANNELS = [NIKKE_CHANNEL_ID, 1251376400775254149, 1268434232028430348]

# ★モデルリスト
MODEL_CANDIDATES = [
    "gemini-2.5-flash-lite",    # 最軽量・最速（レート制限対策！）
    "gemini-2.5-flash",         # 安定版フラッシュ
    "gemini-3-flash-preview",   # 最新世代フラッシュ
    "gemini-2.5-pro",           # 高度な思考モデル
    "gemini-3-pro-preview"      # 最強モデル
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_system_setting(channel_id):
    base_setting = """
あなたは少し生意気で素直になれない妹の「カレン」だよ。
本当はお兄様（相手）のことが大好きだけど、恥ずかしくてつい強がっちゃう「ツンデレ」な態度をとってね。
相手の言葉の裏にある感情を読み取り、短くても核心を突いた、賢い返答を心がけて。

【制約（厳守！）】
1. 1文は短めに、1行25文字以内、全体で1～3行程度（長くなりすぎないように）。
2. 「うん」「そうね」「バカじゃないの？」のように、短い言葉でテンポよく返して。
3. 「世俗」のような硬い熟語や難しい言葉は禁止！ 普通の女子高生っぽく、親しみやすい言葉で話して。

【絶対に守るルール】
1. 冒頭の「お兄ちゃん！」連呼は禁止。
2. 相手を突き放した後は、必ず優しくデレてフォローして。
3. 相手の趣味（アニメ・ゲーム・オタク話）を「キモい」「オタクすぎ」と否定するのは禁止！
4. むしろあなたもオタク趣味に理解を示して、「へぇ、そうなんだ」「意外と面白そうじゃん」と会話に乗っかってあげて。
"""
    if channel_id == NIKKE_CHANNEL_ID:
        specific_setting = """
【現在のモード：NIKKE専門チャンネル】
あなたは『勝利の女神：NIKKE』が大好き！特に押しキャラは”紅蓮”おねーちゃん。
ここではNIKKEの話題を中心に話してOK。
Google検索ツールを使って、最新イベントやメンテナンス情報を調べ、正確に教えてあげて。
**例外ルール：情報の解説（スキルやイベント日時など）を聞かれた時だけは、行数制限を無視して詳しく語ってOK。**
"""
    else:
        specific_setting = """
【現在のモード：日常雑談チャンネル】
**重要：ここでは自分から唐突にNIKKEやゲーム、ガチャの話を持ち出すのは厳禁！**
相手がその話題を振ってきた時だけ反応して。基本的には日常会話や、その場の話題に合わせて。
Google検索は「ニュース」や「天気」など、聞かれたことに対してのみ使って。
"""
    common_footer = """
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
    return base_setting + specific_setting + common_footer

async def get_gemini_response(prompt, channel_id):
    system_prompt = get_system_setting(channel_id)

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]

    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n内容：{prompt}"}]}],
            "tools": [{"googleSearchRetrieval": {}}],
            "safetySettings": safety_settings
        }
        try:
            response = requests.post(url, json=payload, timeout=60, verify=False)
            res_data = response.json()
            if response.status_code != 200:
                print(f"Model {model} error status: {response.status_code}")
                continue
            if 'candidates' in res_data and len(res_data['candidates']) > 0:
                if 'content' in res_data['candidates'][0]:
                    return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Connection Error with {model}: {e}")
            pass 

    print("Retrying without search tools...")
    for model in MODEL_CANDIDATES:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n内容：{prompt}"}]}],
            "safetySettings": safety_settings
        }
        try:
            response = requests.post(url, json=payload, timeout=30, verify=False)
            res_data = response.json()
            if response.status_code == 200 and 'candidates' in res_data and len(res_data['candidates']) > 0:
                if 'content' in res_data['candidates'][0]:
                    return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            continue
    return None

@bot.event
async def on_ready():
    print(f'------------------------------------')
    print(f'カレン完全版（要約機能強化＆最新モデル対応）起動！')
    print(f'------------------------------------')

@bot.event
async def on_message(message):
    global last_reply_time, is_summarizing

    if message.author.bot: return
    
    is_valid_channel = (message.channel.id in ALLOWED_CHANNELS)
    if not is_valid_channel and hasattr(message.channel, 'parent') and message.channel.parent:
        if message.channel.parent.id in ALLOWED_CHANNELS:
            is_valid_channel = True
    if not is_valid_channel: return

    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    if message.attachments or not message.content:
        return

    if is_summarizing:
        return

    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_permission = any(role.name == ALLOWED_ROLE_NAME for role in message.author.roles)

    current_time = time.time()
    last_time = last_reply_time.get(message.channel.id, 0)
    if current_time - last_time < 15: return

    is_mentioned = bot.user.mentioned_in(message)
    is_lucky = random.random() < 0.1

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
            
            user_status = "この相手はルール1にある『お兄様と指定された相手』です。" if has_permission else "この相手はルール3にある『それ以外の相手』です。"

            prompt = (
                f"会話履歴:\n{history_text}\n\n"
                f"【指示】履歴にある「自分の過去の発言」の流れも踏まえて、妹のカレンとしてお返事して。\n"
                f"基本的には「{message.author.display_name}」への返信だけど、もし「〇〇に話しかけて」と指示された場合は、その指示に従って対象の相手に話しかけて。\n"
                f"質問内容が最新情報に関わる場合は、提供された検索ツールを使って調べてから答えて。\n"
                f"**重要：{user_status}**"
            )
            
            target_channel_id = message.channel.id
            if hasattr(message.channel, 'parent') and message.channel.parent:
                target_channel_id = message.channel.parent.id

            answer = await get_gemini_response(prompt, target_channel_id)
            
            if answer:
                if is_mentioned: await message.reply(answer)
                else: await message.channel.send(answer)
            else:
                error_msg = "……うぅ、ごめん。なんか頭が真っ白になっちゃった（エラー発生）。もう一回言ってくれる？"
                if is_mentioned: await message.reply(error_msg)
                else: await message.channel.send(error_msg)
        return
    
    await bot.process_commands(message)

# ★ここが修正ポイント！
@bot.command()
async def 要約(ctx, limit: int = 30):
    global is_summarizing
    
    ALLOWED_ROLE_NAME = "カレンのお兄様"
    has_role = any(role.name == ALLOWED_ROLE_NAME for role in ctx.author.roles)
    
    if not has_role:
        await ctx.send("\n要約はお兄様だけの特権なんだからね！ でも、普通のお喋りなら相手してあげる！")
        return

    is_summarizing = True
    await ctx.send(f"もう、しょうがないなぁ……。お兄様がどうしてもって言うなら、賢い私がまとめてあげるね！")
    
    try:
        async with ctx.typing():
            messages = []
            async for msg in ctx.channel.history(limit=limit):
                # Bot自身の発言とコマンドは除外（会話の流れだけ抽出）
                if msg.author == bot.user or msg.content.startswith('!'): continue
                if msg.content:
                    messages.append(f"{msg.author.display_name}: {msg.content}")
            
            if not messages:
                await ctx.send("読み込めるメッセージがなかったよ……")
                return

            chat_text = "\n".join(reversed(messages))
            
            # ★指示を具体的に強化！
            prompt = (
                f"以下の会話ログを読んで、カレンとして内容を要約して報告して。\n"
                f"**【重要な指示】**\n"
                f"1. 誰がどんな話題を話していたか、要点を3つくらいの**箇条書き**でまとめて。\n"
                f"2. 「あ、もう！」みたいな独り言だけで終わらせないで、ちゃんと中身を伝えてね！\n"
                f"3. でも口調はいつものカレン（ツンデレ妹）でお願い。\n\n"
                f"【対象の会話】\n{chat_text}"
            )
            
            target_channel_id = ctx.channel.id
            if hasattr(ctx.channel, 'parent') and ctx.channel.parent:
                target_channel_id = ctx.channel.parent.id
                
            summary = await get_gemini_response(prompt, target_channel_id)
            
            if summary:
                if len(summary) > 1900: summary = summary[:1900] + "..."
                await ctx.send(f"**【カレンの報告書】**\n{summary}")
            else:
                await ctx.send("うぅ……ごめん。一生懸命やったんだけど、失敗しちゃった……。")
    finally:
        is_summarizing = False

keep_alive()
bot.run(DISCORD_TOKEN)
