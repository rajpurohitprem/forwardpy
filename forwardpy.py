from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm
import asyncio
import traceback
import os
import json

# 🔧 Load or prompt config
config_path = "config.json"
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = json.load(f)
else:
    config = {
        "api_id": int(input("🔑 Enter API ID: ").strip()),
        "api_hash": input("🔐 Enter API Hash: ").strip(),
        "phone": input("📱 Phone (e.g. +91...): ").strip(),
        "source_channel_name": input("📤 Source Channel Title: ").strip(),
        "target_channel_name": input("📥 Target Channel Title: ").strip()
    }
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)
    print("💾 Config saved.")

session_name = f"session_{config['phone'].replace('+','')}"
client = TelegramClient(session_name, config['api_id'], config['api_hash'])

# ✅ Load copied message IDs
copied_ids_file = 'copied_ids.txt'
if os.path.exists(copied_ids_file):
    with open(copied_ids_file, 'r') as f:
        copied_ids = set(int(line.strip()) for line in f if line.strip().isdigit())
else:
    copied_ids = set()

async def main():
    print("🔐 Logging in...")
    await client.start(phone=config['phone'])

    print("🔍 Finding channels...")
    dialogs = await client.get_dialogs()
    src = tgt = None
    for dialog in dialogs:
        title = dialog.name.strip().lower()
        if title == config['source_channel_name'].strip().lower():
            src = dialog.entity
        if title == config['target_channel_name'].strip().lower():
            tgt = dialog.entity

    if not src or not tgt:
        print("❌ Channel not found. Check names and membership.")
        return

    print("✅ Channels found! Fetching messages (oldest first)...")

    offset_id = 0
    total_copied = 0
    fetch_limit = 5  # You can increase this later
    stop_after = 5   # To stop after 5 total messages for testing

    while total_copied < stop_after:
        history = await client(GetHistoryRequest(
            peer=src,
            offset_id=offset_id,
            offset_date=None,
            add_offset=0,
            limit=100,
            max_id=0,
            min_id=0,
            hash=0
        ))

        if not history.messages:
            break

        messages = history.messages
        messages = list(reversed(messages))  # oldest to newest

        for msg in messages:
            if msg.id in copied_ids:
                continue  # Skip already copied
            try:
                print(f"➡️ Copying message {msg.id}")
                if msg.media:
                    await client.send_file(tgt, msg.media, caption=msg.message or '')
                elif msg.message:
                    await client.send_message(tgt, msg.message)
                copied_ids.add(msg.id)
                total_copied += 1

                # Save after each message
                with open(copied_ids_file, 'a') as f:
                    f.write(str(msg.id) + "\n")

                if total_copied >= stop_after:
                    break
            except Exception as e:
                print(f"⚠️ Error copying message {msg.id}")
                traceback.print_exc()

        offset_id = messages[-1].id

    print(f"✅ Copied {total_copied} new messages.")

with client:
    client.loop.run_until_complete(main())
