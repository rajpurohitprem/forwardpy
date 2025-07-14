try:
    if msg.forward:
        print(f"⚠️ Skipping message {msg.id} — forwarded from a protected chat")
        continue

    sent = await client.send_file(tgt, msg.media, caption=msg.message or '')

except Exception as e:
    print(f"⚠️ Error copying message {msg.id}: {e}")
    continue
