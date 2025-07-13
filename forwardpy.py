from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm
import asyncio
import traceback
import os
import json

# 🧠 Load or ask for config
config_path = "config.json"

if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
    print("✅ Loaded saved configuration.")
else:
    config = {
        "api_id": int(input("🔑 Enter your Telegram API ID: ").strip()),
        "api_hash": input("🔐 Enter your Telegram API Hash: ").strip(),
        "phone": input("📱 Enter your phone number (e.g. +91xxxxxx): ").strip(),
        "source_channel_name": input("📤 Source Channel Name (title): ").strip(),
        "target_channel_name": input("📥 Target Channel Name (title): ").strip()
    }
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    print("💾 Config saved. Next time you won’t be asked again.")

session_name = f"session_{config['phone'].replace('+', '').replace(' ', '')}"
client = TelegramClient(session_name, config['api_id'], config['api_hash'])

async def main():
    print("🔐 Logging into Telegram...")
    await client.start(phone=config['phone'])

    print("🔍 Locating your channels...")
    dialogs = await client.get_dialogs()

    src = tgt = None
    for dialog in dialogs:
        title = dialog.name.strip().lower()
        if title == config['source_channel_name'].strip().lower():
            src = dialog.entity
        if title == config['target_channel_name'].strip().lower():
            tgt = dialog.entity

    if not src or not tgt:
        print("❌ Could not find one or both channels.")
        return

    print("✅ Channels found! Copying 5 messages (test mode)...")

    offset_id = 0
    limit = 5  # for test mode
    messages = []

    while True:
        history = await client(GetHistoryRequest(
            peer=src,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=0,
            hash=0
        ))
        if not history.messages:
            break
        messages.extend(history.messages)
        offset_id = history.messages[-1].id
        break

    print(f"📦 Messages fetched: {len(messages)}")

    for msg in reversed(messages):
        print(f"➡️ Copying msg {msg.id} | media: {bool(msg.media)} | text: {msg.message[:30] if msg.message else 'No text'}")
        try:
            if msg.media:
                await client.send_file(tgt, msg.media, caption=msg.message or '')
            elif msg.message:
                await client.send_message(tgt, msg.message)
        except Exception:
            print(f"⚠️ Error copying message {msg.id}")
            traceback.print_exc()

    print("✅ Done copying!")

with client:
    client.loop.run_until_complete(main())
