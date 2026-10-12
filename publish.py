#!/usr/bin/env python3
"""Exam Clue Telegram auto-poster.

Usage:
  python publish.py            -> due posts ko Telegram par bhejta hai
  python publish.py --check    -> sirf jaanch karta hai (kuch bhejta nahi)
  DRY_RUN=1 python publish.py  -> bhejne ki jagah screen par dikhata hai

Secrets (GitHub Settings -> Secrets):
  TELEGRAM_BOT_TOKEN  (BotFather wala token)
  TELEGRAM_CHAT_ID    (test channel ka id, baad me @examcluetelegram)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
API = "https://api.telegram.org/bot{token}/{method}"

# Telegram ki limits
LIM_POLL_Q = 300
LIM_POLL_OPT = 100
LIM_POLL_EXPL = 200
LIM_CAPTION = 1024
LIM_TEXT = 4096
CATCH_UP_HOURS = 12  # itne ghante se purani post "missed" maani jayegi

DRY_RUN = os.environ.get("DRY_RUN") == "1"


def load(name):
    with open(ROOT / name, encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    with open(ROOT / name, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------------------------------------------------------- Telegram

def call(method, fields=None, files=None):
    """Telegram API call. files = {field_name: Path}."""
    if DRY_RUN:
        shown = {k: (v if len(str(v)) < 120 else str(v)[:117] + "...") for k, v in (fields or {}).items()}
        print(f"  [DRY] {method} {shown} files={list((files or {}).keys())}")
        return {"ok": True}
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = API.format(token=token, method=method)
    fields = fields or {}
    if files:
        boundary = uuid.uuid4().hex
        body = b""
        for k, v in fields.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
        for k, path in files.items():
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; '
                     f'filename="{Path(path).name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
            body += Path(path).read_bytes() + b"\r\n"
        body += f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    else:
        data = json.dumps(fields).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            if (e.code == 429 or e.code >= 500) and attempt < 2:  # thodi der ruko, phir dobara
                time.sleep(5 * (attempt + 1))
                continue
            # token kabhi print nahi karte
            raise RuntimeError(f"Telegram error {e.code} on {method}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"Network error on {method}: {type(e).__name__}") from None


def chat():
    return os.environ.get("TELEGRAM_CHAT_ID", "TEST_CHAT")


def send_text(text, markup=None):
    f = {"chat_id": chat(), "text": text, "disable_web_page_preview": True}
    if markup:
        f["reply_markup"] = markup
    return call("sendMessage", f)


def send_photo(path, caption="", markup=None):
    f = {"chat_id": chat()}
    if caption:
        f["caption"] = caption
    if markup:
        f["reply_markup"] = json.dumps(markup)
    return call("sendPhoto", f, files={"photo": ROOT / path})


def send_document(path, caption=""):
    f = {"chat_id": chat()}
    if caption:
        f["caption"] = caption
    return call("sendDocument", f, files={"document": ROOT / path})


def send_album(paths, caption=""):
    media, files = [], {}
    for i, p in enumerate(paths):
        key = f"img{i}"
        item = {"type": "photo", "media": f"attach://{key}"}
        if i == 0 and caption:
            item["caption"] = caption
        media.append(item)
        files[key] = ROOT / p
    return call("sendMediaGroup", {"chat_id": chat(), "media": json.dumps(media)}, files=files)


def send_quiz(q):
    f = {
        "chat_id": chat(),
        "question": q["question"],
        "options": q["options"],  # JSON body me list hi chahiye (string nahi)
        "type": "quiz",
        "correct_option_id": q["correct"],
    }
    if q.get("short_explanation"):
        f["explanation"] = q["short_explanation"]
    return call("sendPoll", f)


def chunk(text, size=LIM_TEXT - 100):
    parts, cur = [], ""
    for block in text.split("\n\n"):
        if len(cur) + len(block) + 2 > size and cur:
            parts.append(cur.strip())
            cur = ""
        cur += block + "\n\n"
    if cur.strip():
        parts.append(cur.strip())
    return parts


# ---------------------------------------------------------------- Promo

def build_promo(entry, cfg, promos):
    p = promos[entry["promo"]]
    lines = [p["title"], ""]
    lines += [f"• {pt}" for pt in p.get("points", [])]
    lines += ["", "👇 पूरी जानकारी और link नीचे button में"]
    if entry["promo"] not in cfg.get("special_promo_ids", []) and cfg.get("special_line"):
        lines += ["", cfg["special_line"]]
    h = cfg["handles"]
    lines += ["", f"📲 Telegram: {h['telegram']}", f"▶️ YouTube: {h['youtube']}", f"📷 Instagram: {h['instagram']}"]
    if h.get("whatsapp"):
        lines.append(f"💬 WhatsApp: {h['whatsapp']}")
    caption = "\n".join(lines)
    markup = {"inline_keyboard": [[{"text": p["button"], "url": p["url"]}]]}
    return p["image"], caption, markup


# ---------------------------------------------------------------- Validation

def validate_entry(e, cfg, promos):
    errs = []
    t = e.get("type")
    if t not in ("text", "photo", "album", "document", "quiz_set", "promo"):
        return [f"unknown type: {t}"]
    try:
        datetime.strptime(e["when"], "%Y-%m-%d %H:%M")
    except Exception:
        errs.append("'when' ka format 'YYYY-MM-DD HH:MM' hona chahiye (IST)")
    if t == "text" and len(e.get("text", "")) > 12000:
        errs.append("text 12000 akshar se zyada (bahut lamba)")
    if t in ("photo", "document") and not (ROOT / e.get("file", "__none__")).exists():
        errs.append(f"file nahi mili: {e.get('file')}")
    if t == "album":
        for p in e.get("files", []):
            if not (ROOT / p).exists():
                errs.append(f"file nahi mili: {p}")
        if not 2 <= len(e.get("files", [])) <= 10:
            errs.append("album me 2 se 10 images chahiye")
    if t in ("photo", "document", "album") and len(e.get("caption", "")) > LIM_CAPTION:
        errs.append("caption 1024 akshar se zyada")
    if t == "quiz_set":
        qs = e.get("questions", [])
        if not qs:
            errs.append("questions khaali hain")
        corrects = []
        for i, q in enumerate(qs, 1):
            if len(q["question"]) > LIM_POLL_Q:
                errs.append(f"Q{i}: sawal {LIM_POLL_Q} akshar se zyada")
            if not 2 <= len(q["options"]) <= 10:
                errs.append(f"Q{i}: options 2-10 hone chahiye")
            for o in q["options"]:
                if len(o) > LIM_POLL_OPT:
                    errs.append(f"Q{i}: option {LIM_POLL_OPT} akshar se zyada: {o[:30]}...")
            if len(q.get("short_explanation", "")) > LIM_POLL_EXPL:
                errs.append(f"Q{i}: short_explanation {LIM_POLL_EXPL} akshar se zyada")
            if not 0 <= q["correct"] < len(q["options"]):
                errs.append(f"Q{i}: correct index galat")
            else:
                corrects.append(q["correct"])
        if len(corrects) >= 5 and len(set(corrects)) == 1:
            errs.append("sabhi sahi answers ek hi option par hain - shuffle karo")
    if t == "promo":
        pid = e.get("promo")
        if pid not in promos:
            errs.append(f"promo id nahi mila: {pid}")
        else:
            p = promos[pid]
            if "TODO" in p["url"]:
                errs.append(f"promo '{pid}' ka link abhi TODO hai")
            if not (ROOT / p["image"]).exists():
                errs.append(f"promo image nahi mili: {p['image']}")
            cap = build_promo(e, cfg, promos)[1]
            if len(cap) > LIM_CAPTION:
                errs.append(f"promo caption {len(cap)} akshar (limit 1024)")
    return errs


# ---------------------------------------------------------------- Send

def send_entry(e, cfg, promos):
    t = e["type"]
    if t == "text":
        for part in chunk(e["text"]):  # 4096 se lamba ho to apne aap tukdon me bhejta hai
            send_text(part)
            time.sleep(0 if DRY_RUN else 1)
    elif t == "photo":
        send_photo(e["file"], e.get("caption", ""))
    elif t == "album":
        send_album(e["files"], e.get("caption", ""))
    elif t == "document":
        send_document(e["file"], e.get("caption", ""))
    elif t == "promo":
        image, caption, markup = build_promo(e, cfg, promos)
        send_photo(image, caption, markup)
    elif t == "quiz_set":
        if e.get("intro"):
            send_text(e["intro"])
        for q in e["questions"]:
            send_quiz(q)
            time.sleep(0 if DRY_RUN else 2)
        if e.get("full_explanations", True):
            blocks = []
            for i, q in enumerate(e["questions"], 1):
                full = q.get("full_explanation", q.get("short_explanation", ""))
                right = q["options"][q["correct"]]
                blocks.append(f"Q{i}. ✅ उत्तर: {right}\n{full}")
            header = f"📘 {e.get('title', 'आज के MCQ')} - पूरे Explanations\n\n"
            for n, part in enumerate(chunk(header + "\n\n".join(blocks))):
                send_text(part)
                time.sleep(0 if DRY_RUN else 1)


def load_status():
    f = ROOT / "status.json"
    if f.exists():
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def main():
    check_only = "--check" in sys.argv
    cfg = load("config.json")
    promos = load("promos.json")
    schedule = load("schedule.json")
    status = load_status()  # sirf bot is file ko badalta hai; schedule.json aap khud badalte ho
    now = datetime.now(IST)
    changed = False
    bad = 0
    failed = 0

    for e in schedule:
        st = status.get(e.get("id"), {}).get("status")
        if st in ("posted", "missed", "error"):
            continue
        errs = validate_entry(e, cfg, promos)
        when = datetime.strptime(e["when"], "%Y-%m-%d %H:%M").replace(tzinfo=IST) if not any("'when'" in x for x in errs) else None
        due = when is not None and when <= now
        if errs:
            bad += 1
            print(f"[{e.get('id')}] GALAT: " + "; ".join(errs))
            continue
        if check_only or not due:
            continue
        if now - when > timedelta(hours=CATCH_UP_HOURS):
            status[e["id"]] = {"status": "missed"}
            changed = True
            print(f"[{e['id']}] bahut purani, missed mark kiya")
            continue
        print(f"[{e['id']}] bhej raha hoon ({e['type']})")
        try:
            send_entry(e, cfg, promos)
            status[e["id"]] = {"status": "posted", "posted_at": now.strftime("%Y-%m-%d %H:%M")}
        except Exception as ex:  # ek post fail ho to baaki rukein nahi; dobara bhejna nahi (duplicate se bachne ke liye)
            status[e["id"]] = {"status": "error", "error": str(ex)[:300]}
            failed += 1
            print(f"[{e['id']}] ERROR: {ex}")
        changed = True

    if changed and not DRY_RUN:
        with open(ROOT / "status.json", "w", encoding="utf-8") as fh:
            json.dump(status, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    if check_only:
        print(f"Jaanch poori. Galat entries: {bad}")
        sys.exit(1 if bad else 0)
    if failed:
        sys.exit(1)  # GitHub failed-run ki email bhejega, tab pata chal jayega


if __name__ == "__main__":
    main()
