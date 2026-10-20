"""Publishes to Instagram using the official Instagram API (Business/Creator account, free)."""
import os
import time

import requests


class IG:
    def __init__(self, cfg):
        self.base = cfg.get("instagram", {}).get("api_base", "https://graph.instagram.com/v23.0").rstrip("/")
        self.token = os.environ["IG_ACCESS_TOKEN"]
        self.location_id = str(cfg.get("brand", {}).get("location_id") or "").strip()
        self.uid = os.environ.get("IG_USER_ID") or self._me()

    # ---------------- helpers
    def _req(self, method, path, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{self.base}/{path}", data=params if method == "POST" else None,
                             params=params if method == "GET" else None, timeout=120)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram API error {r.status_code} on {path}: {r.text}")
        return r.json()

    def _me(self):
        me = self._req("GET", "me", fields="user_id,username")
        print("Posting as @%s" % me.get("username"))
        return me.get("user_id") or me["id"]

    def _wait(self, cid, timeout=600):
        start = time.time()
        while time.time() - start < timeout:
            d = self._req("GET", cid, fields="status_code,status")
            st = d.get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Media container {cid} failed: {st} — {d.get('status')}")
            time.sleep(8)
        raise RuntimeError("Instagram took too long to process the media")

    def _container(self, **params):
        extra = {}
        if self.location_id and not params.get("is_carousel_item"):
            extra["location_id"] = self.location_id
        try:
            return self._req("POST", f"{self.uid}/media", **params, **extra)["id"]
        except RuntimeError as e:
            # alt_text / location may not be supported on every API version → retry without them
            if "alt_text" in params or extra:
                print("Retrying without alt_text/location:", e)
                params.pop("alt_text", None)
                return self._req("POST", f"{self.uid}/media", **params)["id"]
            raise

    def _publish(self, cid):
        self._wait(cid)
        mid = self._req("POST", f"{self.uid}/media_publish", creation_id=cid)["id"]
        link = self._req("GET", mid, fields="permalink").get("permalink")
        print("Published:", link)
        self.last_media_id = mid
        return link

    # ---------------- public
    def post_image(self, url, caption, alt_text=""):
        return self._publish(self._container(image_url=url, caption=caption, alt_text=alt_text))

    def post_carousel(self, urls, caption, alt_text=""):
        kids = [self._container(image_url=u, is_carousel_item="true", alt_text=alt_text) for u in urls]
        for k in kids:
            self._wait(k)
        return self._publish(self._container(media_type="CAROUSEL", children=",".join(kids), caption=caption))

    def post_story(self, image_url=None, video_url=None):
        """Story (24 ghante). API se stickers (poll/link) nahi lagte."""
        params = dict(media_type="STORIES")
        if video_url:
            params["video_url"] = video_url
        else:
            params["image_url"] = image_url
        cid = self._req("POST", f"{self.uid}/media", **params)["id"]
        self._wait(cid)
        mid = self._req("POST", f"{self.uid}/media_publish", creation_id=cid)["id"]
        print("Story published:", mid)
        self.last_media_id = mid
        return mid

    # ---------------- comments + DMs (auto-reply)
    def _json(self, path, body):
        r = requests.post(f"{self.base}/{path}", params={"access_token": self.token}, json=body, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram API error {r.status_code} on {path}: {r.text}")
        return r.json()

    def recent_media(self, limit=12):
        return self._req("GET", f"{self.uid}/media", fields="id,caption,timestamp,permalink,media_product_type",
                         limit=limit).get("data", [])

    def comments(self, media_id, limit=50):
        """Top-level comments + hamare replies (taaki dobara reply na karein)."""
        return self._req("GET", f"{media_id}/comments", limit=limit,
                         fields="id,text,timestamp,from{id,username},username,replies{id,text,from{id,username},username}"
                         ).get("data", [])

    def reply_comment(self, comment_id, text):
        return self._req("POST", f"{comment_id}/replies", message=text)

    def private_reply(self, comment_id, text):
        """Comment karne wale ko ek DM (comment ke 7 din ke andar, sirf ek baar)."""
        return self._json(f"{self.uid}/messages", {"recipient": {"comment_id": comment_id}, "message": {"text": text}})

    def conversations(self, limit=20):
        return self._req("GET", f"{self.uid}/conversations", platform="instagram", limit=limit,
                         fields="id,updated_time,participants,messages.limit(6){id,message,from,created_time}").get("data", [])

    def send_dm(self, user_id, text):
        """Sirf tab jab customer ne pichhle 24 ghante me message kiya ho (Instagram rule)."""
        return self._json(f"{self.uid}/messages", {"recipient": {"id": user_id}, "message": {"text": text}})

    def post_reel(self, video_urls, caption, cover_url=None):
        """Instagram public link se video uthata hai. Pehla link fail ho to agla try karte hain."""
        last = None
        tries = [(v, cover_url) for v in video_urls] + ([(video_urls[0], None)] if cover_url else [])
        for vurl, cov in tries:  # aakhri koshish bina cover ke (cover ki galti se reel na ruke)
            params = dict(media_type="REELS", video_url=vurl, caption=caption, share_to_feed="true")
            if cov:
                params["cover_url"] = cov
            try:
                cid = self._req("POST", f"{self.uid}/media", **params)["id"]
                return self._publish(cid)
            except RuntimeError as e:
                print("Reel upload try failed with", vurl, "→", str(e)[:300])
                last = e
        raise last


    def insights(self, media_id):
        """Post ki performance. Permission chahiye: instagram_business_manage_insights."""
        out = {}
        try:
            basic = self._req("GET", media_id, fields="like_count,comments_count,media_product_type")
            out["likes"] = basic.get("like_count", 0)
            out["comments"] = basic.get("comments_count", 0)
        except RuntimeError as e:
            print("Basic stats failed:", str(e)[:150])
        for metrics in ("reach,saved,shares,views,total_interactions", "reach,saved,shares,total_interactions", "reach,saved"):
            try:
                d = self._req("GET", f"{media_id}/insights", metric=metrics)
                for m in d.get("data", []):
                    out[m["name"]] = (m.get("values") or [{}])[0].get("value", m.get("total_value", {}).get("value", 0))
                break
            except RuntimeError as e:
                last = str(e)
        else:
            print("Insights nahi mile (permission check karo):", last[:160])
        return out


def refresh_token():
    """Long-lived tokens last 60 days; this extends them. Run monthly (workflow does it)."""
    tok = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]
