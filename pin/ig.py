"""Instagram (official API, Instagram Login) — image post + token refresh."""
import os
import time

import requests


class IG:
    def __init__(self, cfg):
        self.base = cfg.get("instagram", {}).get("api_base", "https://graph.instagram.com/v23.0").rstrip("/")
        self.token = os.environ["IG_ACCESS_TOKEN"].strip()
        self.uid = os.environ.get("IG_USER_ID", "").strip() or self._me()

    def _req(self, method, path, **params):
        params["access_token"] = self.token
        r = requests.request(method, f"{self.base}/{path}", data=params if method == "POST" else None,
                             params=params if method == "GET" else None, timeout=120)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram API error {r.status_code} on {path}: {r.text[:400]}")
        return r.json()

    def _me(self):
        me = self._req("GET", "me", fields="user_id,username")
        print("Posting as @%s" % me.get("username"))
        return me.get("user_id") or me["id"]

    def _wait(self, cid, timeout=300):
        t0 = time.time()
        while time.time() - t0 < timeout:
            d = self._req("GET", cid, fields="status_code,status")
            if d.get("status_code") == "FINISHED":
                return
            if d.get("status_code") in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram ne media reject kiya: {d.get('status')}")
            time.sleep(5)
        raise RuntimeError("Instagram processing timeout")

    def post_image(self, url, caption, alt_text=""):
        cid = self._req("POST", f"{self.uid}/media", image_url=url, caption=caption, alt_text=alt_text)["id"]
        self._wait(cid)
        mid = self._req("POST", f"{self.uid}/media_publish", creation_id=cid)["id"]
        link = self._req("GET", mid, fields="permalink").get("permalink")
        print("Published:", link)
        return mid, link


def refresh_token():
    r = requests.get("https://graph.instagram.com/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_ACCESS_TOKEN"].strip()},
                     timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]
