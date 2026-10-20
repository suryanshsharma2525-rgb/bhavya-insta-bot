"""Auto-reply: comments + DMs ka jawab, customer ko cafe bulane ke liye — personal rishta bana ke.

Kaise:
- Har customer ki chhoti si yaad (naam, pasandida item, kya baat hui) → agli baar usi hisaab se baat
  ("Rahul, pichhli baar momos bole the — aaj cheese corn wale try karo, shaam 6 ke baad garma-garam milte hain")
- Jawab specific hota hai: unka item, sahi time, ek wajah aane ki. Generic "visit us" nahi.
- Shikayat → maafi + DM me baat + owner ko flag. Wahan bechne ki koshish NAHI.
- Spam / gaali → koi jawab nahi.
- Koi pooche "bot ho?" → sach bolta hai.
- Sirf menu ke asli prices aur config.yaml ka approved offer. Koi naya discount/promise kabhi nahi.

Privacy: repo public hai, isliye customer memory ENCRYPTED file me (data/customers.enc) — key sirf
GitHub Secret CUSTOMER_MEMORY_KEY me. Logs me koi naam/DM text print nahi hota (Actions logs bhi public hote hain).
"""
import base64
import csv
import datetime as dt
import hashlib
import json
import os

from . import ai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEM = os.path.join(ROOT, "data", "customers.enc")
DONE = os.path.join(ROOT, "data", "replied.json")
INBOX = os.path.join(ROOT, "data", "owner_inbox.csv")


# ---------------------------------------------------------------- encrypted memory
def _fernet():
    pw = os.environ.get("CUSTOMER_MEMORY_KEY", "").strip()
    if not pw:
        return None
    from cryptography.fernet import Fernet
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(pw.encode()).digest()))


def load_memory():
    f = _fernet()
    if not f or not os.path.exists(MEM):
        return {}
    try:
        return json.loads(f.decrypt(open(MEM, "rb").read()))
    except Exception:
        print("Customer memory nahi khuli (CUSTOMER_MEMORY_KEY badla?) — nayi shuru kar rahe hain.")
        return {}


def save_memory(mem):
    f = _fernet()
    if not f:
        return  # key nahi → kuch save nahi (public repo me kabhi plain text nahi)
    os.makedirs(os.path.dirname(MEM), exist_ok=True)
    with open(MEM, "wb") as fh:
        fh.write(f.encrypt(json.dumps(mem, ensure_ascii=False).encode()))


def _uid(x):
    return hashlib.sha256(str(x).encode()).hexdigest()[:16]


def _done():
    try:
        return json.load(open(DONE, encoding="utf-8"))
    except Exception:
        return {"comments": [], "messages": []}


def _save_done(d):
    d = {k: v[-3000:] for k, v in d.items()}
    os.makedirs(os.path.dirname(DONE), exist_ok=True)
    json.dump(d, open(DONE, "w", encoding="utf-8"))


# ---------------------------------------------------------------- the brain
def _brief(cfg):
    menu = ", ".join(f"{m['name']} ₹{m['price']}" for m in cfg["menu"] if m.get("price"))
    rc = cfg.get("replies") or {}
    o = cfg.get("weekly_offer", {})
    offer = ""
    if o.get("enabled", True):
        items = ", ".join(i["name"] for i in o.get("free_items", []))
        offer = f"Approved weekly offer (only on {o.get('weekday')}): free {items}. Terms: {o.get('terms')}."
    b = cfg.get("brand", {})
    return (
        "You are the friendly host of BHAVYA CAFE, a premium-but-warm cafe near IIT Roorkee (students + Roorkee locals). "
        "You reply to Instagram comments/DMs like a real cafe host who remembers regulars — warm, witty, respectful, never "
        "pushy. GOAL: make the person feel personally welcome and give ONE specific reason + time to visit soon.\n"
        "STYLE: match their language (Hinglish/English/Hindi); 1-2 short lines for public comments, max 3 for DMs; use their "
        "first name if known; refer to what they said or what they liked before; suggest a specific item from the menu "
        "that fits; light humour ok; max 1 emoji; no hashtags.\n"
        "HARD RULES: use ONLY these menu items/prices; never invent discounts, freebies, timings or promises. Only mention "
        f"the offer below if relevant. Never confirm table bookings, delivery, stock or special requests yourself — say the "
        "team will confirm and keep the conversation open (set escalate=true for bookings/bulk orders). "
        f"{('Opening hours: ' + b['hours']) if b.get('hours') else 'Do not state opening hours.'} "
        f"{('Perk you may mention: ' + rc['invite_perk']) if rc.get('invite_perk') else ''}\n"
        "If it's a complaint/bad experience: apologise sincerely, no selling, ask them to DM details, set escalate=true. "
        "If spam, abuse, or unrelated promo: reply_type='skip'. If they ask if you're a bot: be honest (Bhavya Cafe's "
        "assistant; the team reads messages too). Don't ask for phone numbers or personal data.\n"
        f"MENU: {menu}\n{offer}\nLocation: {b.get('location_line', 'near IIT Roorkee')}"
    )


def _think(kind, text, who, memory, history, cfg):
    prompt = (_brief(cfg) + f"\n\nCHANNEL: {kind}\nCUSTOMER: {who}\nWHAT WE REMEMBER ABOUT THEM: "
              f"{json.dumps(memory or {}, ensure_ascii=False)}\nRECENT CONVERSATION: "
              f"{json.dumps(history or [], ensure_ascii=False)}\nTHEIR MESSAGE: {text}\n\n"
              'Return JSON: {"reply_type": "reply" | "skip", "reply": "...", '
              '"private_dm": "optional one DM for a comment that asked price/location/order (else empty)", '
              '"escalate": true/false, "category": "praise|question|complaint|tag|order|other", '
              '"remember": {"name": "first name if they said it", "likes": ["menu items they like/asked"], '
              '"note": "one short harmless fact for next time (e.g. exam week, comes with friends) or empty"}}')
    d = ai._gemini(prompt, cfg)
    return d if isinstance(d, dict) else None


def _remember(mem, key, who, upd):
    m = mem.setdefault(key, {"first_seen": dt.date.today().isoformat(), "likes": [], "notes": [], "chats": 0})
    m["last_seen"] = dt.date.today().isoformat()
    m["chats"] = m.get("chats", 0) + 1
    m["handle"] = who
    upd = upd or {}
    if upd.get("name"):
        m["name"] = str(upd["name"])[:30]
    for it in upd.get("likes") or []:
        if isinstance(it, str) and it not in m["likes"]:
            m["likes"] = (m["likes"] + [it])[-6:]
    if upd.get("note"):
        m["notes"] = (m["notes"] + [str(upd["note"])[:80]])[-4:]
    return m


def _inbox(row):
    new = not os.path.exists(INBOX)
    with open(INBOX, "a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["time", "where", "link", "category", "what"])
        w.writerow(row)


# ---------------------------------------------------------------- run
def run(cfg):
    rc = cfg.get("replies") or {}
    if not rc.get("enabled", True):
        print("Auto-reply band hai (config.yaml → replies.enabled)")
        return
    if not os.environ.get("GEMINI_API_KEY"):
        print("GEMINI_API_KEY nahi hai — auto-reply skip (bina AI ke generic jawab nahi bhejte).")
        return
    from .instagram import IG
    ig = IG(cfg)
    me = ig._req("GET", "me", fields="user_id,username")
    my_name = (me.get("username") or "").lower()
    my_ids = {str(me.get("user_id")), str(me.get("id")), str(ig.uid)}
    mem, done = load_memory(), _done()
    budget = int(rc.get("max_per_run", 25))
    stats = {"comments": 0, "dms": 0, "private": 0, "skipped": 0, "escalated": 0}
    can_dm = rc.get("dm_replies", True)
    now = dt.datetime.now(dt.timezone.utc)

    # ---- comments
    for media in ig.recent_media(rc.get("media_to_check", 10)):
        if budget <= 0:
            break
        try:
            comments = ig.comments(media["id"])
        except Exception as e:
            print("Comments padh nahi paaye:", str(e)[:200])
            break
        for c in comments:
            if budget <= 0:
                break
            cid = c["id"]
            who = (c.get("from") or {}).get("username") or c.get("username") or ""
            if cid in done["comments"] or who.lower() == my_name:
                continue
            if any(((r.get("from") or {}).get("username") or r.get("username") or "").lower() == my_name
                   for r in (c.get("replies") or {}).get("data", [])):
                done["comments"].append(cid)  # pehle hi (haath se) reply ho chuka
                continue
            ts = dt.datetime.fromisoformat(c["timestamp"].replace("+0000", "+00:00"))
            if (now - ts).days > 6:
                done["comments"].append(cid)
                continue
            key = _uid((c.get("from") or {}).get("id") or who)
            d = _think("public comment on our post: " + (media.get("caption") or "")[:120], c.get("text", ""),
                       "@" + who, mem.get(key), [], cfg)
            if not d:
                continue
            done["comments"].append(cid)
            budget -= 1
            if d.get("reply_type") == "skip" or not d.get("reply"):
                stats["skipped"] += 1
                continue
            try:
                ig.reply_comment(cid, ai.strip_emoji(d["reply"]) if rc.get("no_emoji") else d["reply"][:300])
                stats["comments"] += 1
            except Exception as e:
                print("Comment reply failed:", str(e)[:200])
                continue
            _remember(mem, key, who, d.get("remember"))
            if d.get("escalate"):
                stats["escalated"] += 1
                _inbox([now.strftime("%Y-%m-%d %H:%M"), "comment", media.get("permalink"), d.get("category"),
                        (c.get("text") or "")[:200]])
            if can_dm and d.get("private_dm") and rc.get("private_replies", True):
                try:
                    ig.private_reply(cid, d["private_dm"][:600])
                    stats["private"] += 1
                except Exception as e:
                    can_dm = _dm_off(e)

    # ---- DMs (24 ghante ki window ke andar hi)
    if can_dm:
        try:
            convs = ig.conversations()
        except Exception as e:
            convs = []
            _dm_off(e)
        for cv in convs:
            if budget <= 0:
                break
            msgs = (cv.get("messages") or {}).get("data", [])
            if not msgs:
                continue
            last = msgs[0]  # newest first
            frm = last.get("from") or {}
            if str(frm.get("id")) in my_ids or (frm.get("username") or "").lower() == my_name:
                continue  # aakhri message hamara hai
            if last["id"] in done["messages"]:
                continue
            ts = dt.datetime.fromisoformat(last["created_time"].replace("+0000", "+00:00"))
            if (now - ts).total_seconds() > 23 * 3600:
                done["messages"].append(last["id"])
                continue
            key = _uid(frm.get("id"))
            hist = [{"from": "us" if str((m.get("from") or {}).get("id")) in my_ids else "them", "text": m.get("message", "")}
                    for m in reversed(msgs[1:6])]
            d = _think("Instagram DM", last.get("message", ""), "@" + (frm.get("username") or "customer"),
                       mem.get(key), hist, cfg)
            if not d:
                continue
            done["messages"].append(last["id"])
            budget -= 1
            if d.get("escalate"):
                stats["escalated"] += 1  # shikayat → owner khud dekhe (DM unread rehta hai), bot jawab nahi deta
                _remember(mem, key, frm.get("username"), d.get("remember"))
                continue
            if d.get("reply_type") == "skip" or not d.get("reply"):
                stats["skipped"] += 1
                continue
            try:
                ig.send_dm(frm.get("id"), d["reply"][:900])
                stats["dms"] += 1
                _remember(mem, key, frm.get("username"), d.get("remember"))
            except Exception as e:
                if not _dm_off(e):
                    break
    save_memory(mem)
    _save_done(done)
    print("Auto-reply:", stats)  # sirf ginti — naam/text log me nahi (logs public hote hain)


_DM_WARNED = []


def _dm_off(e):
    msg = str(e)
    if any(k in msg for k in ("permission", "(#10)", "(#200)", "(#3)", "not allowed", "OAuthException", "190")):
        if not _DM_WARNED:
            _DM_WARNED.append(1)
            print("DM reply abhi band: Meta app ko 'instagram_business_manage_messages' ka Advanced Access chahiye "
                  "(Business Verification + App Review). Tab tak sirf comment replies chalenge.")
        return False
    print("DM error:", msg[:160])
    return True


if __name__ == "__main__":  # halka entry (bina video/photo libraries ke): python -m bot.replies
    import yaml
    with open(os.path.join(ROOT, "config.yaml"), encoding="utf-8") as fh:
        run(yaml.safe_load(fh))
