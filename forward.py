from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm
import asyncio
import traceback
import os

print("🔧 Telegram Channel Copier Setup")

api_id = int(input("🔑 Enter your Telegram API ID: ").strip())
api_hash = input("🔐 Enter your Telegram API Hash: ").strip()
phone = input("📱 Enter your phone number (with country code, e.g. +91xxxxxx): ").strip()
source_channel_name = input("📤 Source Channel Name (visible title): ").strip()
target_channel_name = input("📥 Target Channel Name (visible title): ").strip()

# Session file name = session_{phone}.session so multiple accounts can work
session_name = f"session_{phone.replace('+', '').replace(' ', '')}"
client = TelegramClient(session_name, api_id, api_hash)

async def main():
    print("\n🔐 Logging into Telegram (session will be saved)...")
    await client.start(phone=phone)

    print("🔍 Locating your channels...")
    dialogs = await client.get_dialogs()

    src = tgt = None
    for dialog in dialogs:
        title = dialog.name.strip().lower()
        if title == source_channel_name.strip().lower():
            src = dialog.entity
        if title == target_channel_name.strip().lower():
            tgt = dialog.entity

    if not src or not tgt:
        print("❌ Could not find one or both channels. Make sure you're a member of both.")
        return

    print("✅ Channels found! Starting copy (test mode: 5 messages)...")

    offset_id = 0
    limit = 5  # <-- Test mode limit, remove or increase later
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
        break  # Remove this 'break' if you want to fetch more messages later

    print(f"📦 Messages fetched: {len(messages)}")

    for msg in reversed(messages):
        print(f"➡️ Copying msg {msg.id} | media: {bool(msg.media)} | text: {msg.text[:30] if msg.text else 'No text'}")
        try:
            if msg.media:
                await client.send_file(tgt, msg.media, caption=msg.text or '')
            elif msg.text:
                await client.send_message(tgt, msg.text)
        except Exception:
            print(f"⚠️ Error copying message {msg.id}")
            traceback.print_exc()

    print("✅ Done copying!")

with client:
    client.loop.run_until_complete(main())
