from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, UpdatePinnedMessageRequest
from tqdm import tqdm
import asyncio
import os
import json
import time

CONFIG_FILE = "config.json"
SESSION_FILE = "anon"
SENT_LOG = "sent_ids.txt"
ERROR_LOG = "errors.txt"

# Load or ask config
if not os.path.exists(CONFIG_FILE):
    api_id = int(input("API ID: "))
    api_hash = input("API Hash: ")
    phone = input("Phone number (+91xxxx): ")
    source_channel_name = input("Source Channel Name: ")
    target_channel_name = input("Target Channel Name: ")
    dry_run = input("Dry run mode? (y/n): ").strip().lower() == 'y'

    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
        "source_channel_name": source_channel_name,
        "target_channel_name": target_channel_name,
        "dry_run": dry_run
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
        config['dry_run'] = input("Dry run mode? (y/n): ").strip().lower() == 'y'
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

api_id = config["api_id"]
api_hash = config["api_hash"]
phone = config["phone"]
source_channel_name = config["source_channel_name"]
target_channel_name = config["target_channel_name"]
dry_run = config.get("dry_run", False)

client = TelegramClient(SESSION_FILE, api_id, api_hash)

# Load sent log
sent_ids = set()
if os.path.exists(SENT_LOG):
    with open(SENT_LOG, "r") as f:
        sent_ids = set(map(int, f.read().splitlines()))

pin_map = {}
status_msg = None

async def update_status(text):
    global status_msg
    if status_msg:
        try:
            await client.edit_message(status_msg.chat_id, status_msg.id, text)
        except:
            pass
    else:
        status_msg = await client.send_message(target_channel_name, text)

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

    await update_status("🔄 Syncing messages from source to target...")

    last_msg_id = max(sent_ids) if sent_ids else 0
    limit = 100

    try:
        history = await client(GetHistoryRequest(
            peer=src,
            offset_id=0,
            offset_date=None,
            add_offset=0,
            limit=limit,
            max_id=0,
            min_id=last_msg_id,
            hash=0
        ))

        if not history.messages:
            print("✅ No new messages to sync.")
            return

        print(f"📥 Found {len(history.messages)} new messages")

        text_count = media_count = skipped_count = 0

        for msg in reversed(history.messages):
            if msg.id in sent_ids:
                continue

            try:
                caption_text = msg.text or ''
                if msg.forward:
                    fwd_from = ""
                    if msg.forward.sender:
                        fwd_from = msg.forward.sender.username or "Unknown User"
                    elif msg.forward.chat:
                        fwd_from = msg.forward.chat.title or "Unknown Channel"
                    caption_text = f"[Forwarded from {fwd_from}]\n{caption_text}"

                file_path = None
                await update_status(f"⬇️ Downloading message {msg.id}...")

                if msg.media:
                    try:
                        file_path = await msg.download_media()
                    except Exception:
                        await update_status(f"⚠️ Media in message {msg.id} could not be downloaded.")
                        file_path = None

                await update_status(f"📤 Sending message {msg.id}...")

                if dry_run:
                    print(f"[DRY RUN] Would send message {msg.id}")
                elif file_path and os.path.exists(file_path):
                    sent = await client.send_file(tgt, file_path, caption=caption_text)
                    os.remove(file_path)
                    media_count += 1
                elif caption_text:
                    sent = await client.send_message(tgt, caption_text)
                    text_count += 1
                else:
                    skipped_count += 1
                    continue

                if not dry_run:
                    with open(SENT_LOG, "a") as f:
                        f.write(str(msg.id) + "\n")
                    sent_ids.add(msg.id)

                    if msg.pinned:
                        await client(UpdatePinnedMessageRequest(
                            peer=tgt,
                            id=sent.id,
                            silent=True
                        ))

                await update_status(f"✅ Message {msg.id} copied!")
                last_msg_id = max(last_msg_id, msg.id)

            except Exception as e:
                with open(ERROR_LOG, "a") as ef:
                    ef.write(f"Message {msg.id}: {e}\n")
                await update_status(f"⚠️ Error copying message {msg.id}: {e}")
                continue

        await update_status(f"✅ Batch done: {media_count} media, {text_count} text, {skipped_count} skipped")

    except Exception as e:
        await update_status(f"⚠️ Loop error: {e}")

with client:
    client.loop.run_until_complete(main())
