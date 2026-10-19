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
            st = self._req("GET", cid, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Media container {cid} failed: {st}")
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
        return link

    # ---------------- public
    def post_image(self, url, caption, alt_text=""):
        return self._publish(self._container(image_url=url, caption=caption, alt_text=alt_text))

    def post_carousel(self, urls, caption, alt_text=""):
        kids = [self._container(image_url=u, is_carousel_item="true", alt_text=alt_text) for u in urls]
        for k in kids:
            self._wait(k)
        return self._publish(self._container(media_type="CAROUSEL", children=",".join(kids), caption=caption))

    def post_reel(self, video_urls, caption, cover_url=None):
        """Instagram public link se video uthata hai. Pehla link fail ho to agla try karte hain."""
        last = None
        for vurl in video_urls:
            params = dict(media_type="REELS", video_url=vurl, caption=caption, share_to_feed="true")
            if cover_url:
                params["cover_url"] = cover_url
            try:
                cid = self._req("POST", f"{self.uid}/media", **params)["id"]
                return self._publish(cid)
            except RuntimeError as e:
                print("Reel upload try failed with", vurl, "→", str(e)[:300])
                last = e
        raise last


def refresh_token():
    """Long-lived tokens last 60 days; this extends them. Run monthly (workflow does it)."""
    tok = os.environ["IG_ACCESS_TOKEN"]
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": tok}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]
