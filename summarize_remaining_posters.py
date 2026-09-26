import json
d=json.load(open("poster_duplicate_audit.json",encoding="utf-8"))
out={
 "multiSeasonSamePoster":d.get("multiSeasonSamePoster",[]),
 "topCrossFamilyPosterReuse":d.get("topCrossFamilyPosterReuse",[]),
 "likelyDuplicateRecords":d.get("likelyDuplicateRecords",[])
}
json.dump(out,open("remaining_poster_groups.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print("MULTI",len(out["multiSeasonSamePoster"]))
for g in out["multiSeasonSamePoster"]:
    print("MS",g.get("family"),g.get("seasons"),g.get("poster"))
print("CROSS",len(out["topCrossFamilyPosterReuse"]))
for g in out["topCrossFamilyPosterReuse"]:
    print("CF",g.get("count"),g.get("families"),g.get("poster"))
print("DUPREC",len(out["likelyDuplicateRecords"]))
for g in out["likelyDuplicateRecords"][:40]:
    print("DR",g.get("key"),g.get("count"))
