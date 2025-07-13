from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest
from tqdm import tqdm
import asyncio
import os
import json

# ===============================
# ✅ SETTINGS + SESSION SETUP
# ===============================

print("\n🔧 Telegram Channel Copier with Resume Support")

# Save credentials in a config.json so it's used once
CONFIG_FILE = "config.json"
SESSION_FILE = "anon"  # Named session file

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

api_id = config["api_id"]
api_hash = config["api_hash"]
phone = config["phone"]
source_channel_name = config["source_channel_name"]
target_channel_name = config["target_channel_name"]

client = TelegramClient(SESSION_FILE, api_id, api_hash)

# ===============================
# ✅ MAIN LOGIC
# ===============================

# Track sent messages
SENT_LOG = "sent_ids.txt"
sent_ids = set()
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().splitlines()))


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
                continue  # skip already copied

            try:
                if msg.media:
                    await client.send_file(tgt, msg.media, caption=msg.message or '')
                elif msg.message:
                    await client.send_message(tgt, msg.message)
                else:
                    continue  # skip unknown types

                # Log sent message ID
                with open(SENT_LOG, "a") as f:
                    f.write(str(msg.id) + "\n")
                sent_ids.add(msg.id)
                pbar.update(1)

            except Exception as e:
                print(f"⚠️ Error copying message {msg.id}: {e}")
                continue

        offset_id = history.messages[-1].id

    print("\n✅ Done copying!")


# ===============================
# ✅ RUN SCRIPT
# ===============================

with client:
    client.loop.run_until_complete(main())
