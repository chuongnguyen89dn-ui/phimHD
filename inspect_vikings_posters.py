import json
d=json.load(open("rophim_catalog.json",encoding="utf-8"))
for x in d.get("movies",[]):
    u=x.get("url") or ""
    if "huyen-thoai-vikings-phan-" in u:
        print((x.get("title") or "")+"\t"+u+"\t"+str(x.get("poster") or ""))
