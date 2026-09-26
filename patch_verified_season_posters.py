import json,sys
p=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"
d=json.load(open(p,encoding="utf-8"))
fix={
 "https://rophims.team/phim/tho-san-yeu-tinh-phan-1":"https://image.tmdb.org/t/p/original/b2aHl6I3AaDru4hgnhvqlu4aFtr.jpg",
 "https://rophims.team/phim/tho-san-yeu-tinh-phan-2":"https://image.tmdb.org/t/p/original/zG0shLBaHHpiwAtuRKJO4dPsBOM.jpg",
}
changed=0
for x in d.get("movies",[]):
    u=x.get("url")
    if u in fix and x.get("poster")!=fix[u]:
        x["poster"]=fix[u]; changed+=1
json.dump(d,open(p,"w",encoding="utf-8"),ensure_ascii=False,indent=2)
print({"changed":changed})
