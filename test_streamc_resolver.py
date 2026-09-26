import app_full as core

URL="https://embed13.streamc.xyz/embed.php?hash=7d16a34b60bd28dee122fa48cf872573"
pairs=core.resolve_media_url(URL,"https://rophims.team/")
assert pairs, "StreamC resolver returned no playlist"
playlist,ref=pairs[0]
assert "streamc.xyz" in playlist, playlist
assert playlist.startswith("https://"), playlist

from curl_cffi import requests
r=requests.get(playlist,headers={"User-Agent":core.UA,"Referer":ref},timeout=20,impersonate="chrome",allow_redirects=True)
assert r.status_code < 400, (r.status_code,playlist)
assert "#EXTM3U" in r.text[:1000], r.text[:200]
assert "#ENC-AESGCM" not in r.text[:1000], "resolver requested encrypted playlist instead of plain HLS"
print("STREAMC_RESOLVER_PASS",playlist,r.status_code,r.text[:80].replace("\n"," | "))
