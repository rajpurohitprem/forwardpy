from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetHistoryRequest, UpdatePinnedMessageRequest
from tqdm import tqdm
import asyncio
import os
import json

CONFIG_FILE = "config.json"
SESSION_FILE = "anon"
SENT_LOG = "sent_ids.txt"

# Load or create config
if not os.path.exists(CONFIG_FILE):
    api_id = int(input("API ID: "))
    api_hash = input("API Hash: ")
    phone = input("Phone: ")
    source_channel_name = input("Source Channel Name: ")
    target_channel_name = input("Target Channel Name: ")

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
    print(f"✅ Loaded config: {config['source_channel_name']} → {config['target_channel_name']}")

api_id = config["api_id"]
api_hash = config["api_hash"]
phone = config["phone"]
source_channel_name = config["source_channel_name"]
target_channel_name = config["target_channel_name"]

client = TelegramClient(SESSION_FILE, api_id, api_hash)

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
        if dialog.name.strip().lower() == source_channel_name.lower():
            src = dialog.entity
        if dialog.name.strip().lower() == target_channel_name.lower():
            tgt = dialog.entity

    if not src or not tgt:
        print("❌ One of the channels not found.")
        return

    offset_id = 0
    limit = 100
    pbar = tqdm(desc="Copying", unit="msg")

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

            text = msg.message or ''
            if msg.forward:
                try:
                    fwd_from = msg.forward.chat.title if msg.forward.chat else "Unknown"
                except:
                    fwd_from = "Unknown"
                text = f"[Forwarded from {fwd_from}]\n{text}"

            try:
                if msg.media:
                    try:
                        path = await client.download_media(msg)
                        if path and os.path.exists(path):
                            sent = await client.send_file(tgt, path, caption=text)
                            os.remove(path)
                        else:
                            print(f"⚠️ Could not download media for msg {msg.id}")
                            continue
                    except Exception as e:
                        print(f"❌ Media protected or failed at msg {msg.id}: {e}")
                        continue
                elif text:
                    sent = await client.send_message(tgt, text)
                else:
                    continue

                # Success log
                with open(SENT_LOG, "a") as f:
                    f.write(str(msg.id) + "\n")
                sent_ids.add(msg.id)
                pbar.update(1)

                pin_map[msg.id] = sent.id
                if msg.pinned:
                    await client(UpdatePinnedMessageRequest(peer=tgt, id=sent.id, silent=True))

            except Exception as e:
                print(f"⚠️ Error on msg {msg.id}: {e}")
                continue

        offset_id = history.messages[-1].id

    print("\n✅ All messages processed.")

with client:
    client.loop.run_until_complete(main())
