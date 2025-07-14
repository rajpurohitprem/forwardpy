from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, UpdatePinnedMessageRequest
from tqdm import tqdm
import asyncio
import os
import json

# ===============================
# ✅ SETTINGS + SESSION SETUP
# ===============================

print("\n🔧 Telegram Channel Copier with Resume + Pin Support")

CONFIG_FILE = "config.json"
SESSION_FILE = "anon"

if not os.path.exists(CONFIG_FILE):
    api_id = int(input("🔑 Enter your Telegram API ID: ").strip())
    api_hash = input("🔐 Enter your Telegram API Hash: ").strip()
    phone = input("📱 Enter your phone number (with country code, e.g. +91xxxxxx): ").strip()
    source_channel_name = input("📤 Source Channel Name: ").strip()
    target_channel_name = input("📥 Target Channel Name: ").strip()
    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
        "source_channel_name": source_channel_name,
        "target_channel_name": target_channel_name
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
else:
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    print("\n📦 Loaded previous config:")
    print(f"Source: {config['source_channel_name']} | Target: {config['target_channel_name']}")

    if input("✏️ Do you want to edit source/target channels? (y/n): ").lower() == 'y':
        config['source_channel_name'] = input("📤 New Source Channel Name: ").strip()
        config['target_channel_name'] = input("📥 New Target Channel Name: ").strip()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

api_id = config.get("api_id")
api_hash = config.get("api_hash")
phone = config.get("phone")
source_channel_name = config.get("source_channel_name")
target_channel_name = config.get("target_channel_name")

client = TelegramClient(SESSION_FILE, api_id, api_hash)

# ===============================
# ✅ MAIN LOGIC
# ===============================

SENT_LOG = "sent_ids.txt"
sent_ids = set()
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().splitlines()))

# Mapping source msg ID → target msg ID (for pinning)
pin_map = {}

async def main():
    print("\n🔐 Logging into Telegram...")
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
        print("❌ Could not find one or both channels. Make sure you're a member.")
        return

    print("✅ Channels found! Starting copy...")

    offset_id = 0
    limit = 100
    pbar = tqdm(desc="Copying messages", unit="msg")

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

        for msg in reversed(history.messages):
            if msg.id in sent_ids:
                continue

            try:
                if msg.media:
                    sent = await client.send_file(tgt, msg.media, caption=msg.message or '')

                    # Delete temp downloaded file (if exists)
                    if hasattr(msg.media, 'document') and msg.media.document:
                        for attr in msg.media.document.attributes:
                            if hasattr(attr, 'file_name'):
                                fname = attr.file_name
                                if os.path.exists(fname):
                                    os.remove(fname)

                elif msg.message:
                    sent = await client.send_message(tgt, msg.message)
                else:
                    continue

                # Log copied message
                with open(SENT_LOG, "a") as f:
                    f.write(str(msg.id) + "\n")
                sent_ids.add(msg.id)
                pbar.update(1)

                # Save source → target ID for possible pin
                pin_map[msg.id] = sent.id

                # Check and pin if needed
                if msg.pinned:
                    await client(UpdatePinnedMessageRequest(
                        peer=tgt,
                        id=sent.id,
                        silent=True
                    ))

            except Exception as e:
                print(f"⚠️ Error copying message {msg.id}: {e}")
                continue

        offset_id = history.messages[-1].id

    print("\n✅ Done copying including pinned messages!")

# ===============================
# ✅ RUN SCRIPT
# ===============================

with client:
    client.loop.run_until_complete(main())
