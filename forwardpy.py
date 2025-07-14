from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, UpdatePinnedMessageRequest
from tqdm import tqdm
import asyncio
import os
import json

CONFIG_FILE = "config.json"
SESSION_FILE = "anon"
SENT_LOG = "sent_ids.txt"

# Load or ask config
if not os.path.exists(CONFIG_FILE):
    api_id = int(input("API ID: "))
    api_hash = input("API Hash: ")
    phone = input("Phone number (+91xxxx): ")
    source_channel_name = input("Source Channel Name: ")
    target_channel_name = input("Target Channel Name: ")

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
        if input("✏️ Do you want to edit source/target channels? (y/n): ").lower() == 'y':
        "source_channel_name": source_channel_name,
        "target_channel_name": target_channel_name
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
else:
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    print(f"Loaded config — Source: {config['source_channel_name']} | Target: {config['target_channel_name']}")

    if input("✏️ Do you want to edit source/target channels? (y/n): ").lower() == 'y':
        config['source_channel_name'] = input("📤 New Source Channel Name: ").strip()
        config['target_channel_name'] = input("📥 New Target Channel Name: ").strip()
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
            
api_id = config["api_id"]
api_hash = config["api_hash"]
phone = config["phone"]
source_channel_name = config["source_channel_name"]
target_channel_name = config["target_channel_name"]

client = TelegramClient(SESSION_FILE, api_id, api_hash)

# Load sent log
sent_ids = set()
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().splitlines()))

pin_map = {}

async def main():
    await client.start(phone=phone)

    dialogs = await client.get_dialogs()
    src = tgt = None
    for dialog in dialogs:
        title = dialog.name.strip().lower()
        if title == source_channel_name.lower():
            src = dialog.entity
        if title == target_channel_name.lower():
            tgt = dialog.entity

    if not src or not tgt:
        print("❌ Channels not found!")
        return

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
                # Build full message text
                caption_text = msg.text or ''
                if msg.forward:
                    fwd_from = ""
                    if msg.forward.sender:
                        fwd_from = msg.forward.sender.username or "Unknown User"
                    elif msg.forward.chat:
                        fwd_from = msg.forward.chat.title or "Unknown Channel"
                    caption_text = f"[Forwarded from {fwd_from}]\n{caption_text}"

                # Try to download media
                file_path = None
                if msg.media:
                    try:
                        file_path = await msg.download_media()
                    except Exception:
                        print(f"⚠️ Media in message {msg.id} is protected and could not be downloaded.")
                        file_path = None

                # Send to target
                if file_path and os.path.exists(file_path):
                    sent = await client.send_file(tgt, file_path, caption=caption_text)
                    os.remove(file_path)
                elif caption_text:
                    sent = await client.send_message(tgt, caption_text)
                else:
                    continue  # Skip if nothing to send

                with open(SENT_LOG, "a") as f:
                    f.write(str(msg.id) + "\n")
                sent_ids.add(msg.id)
                pbar.update(1)

                pin_map[msg.id] = sent.id
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

    print("\n✅ Done copying all messages.")

with client:
    client.loop.run_until_complete(main())
