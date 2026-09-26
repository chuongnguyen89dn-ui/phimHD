import json,re,collections,urllib.parse,sys,hashlib
CAT=sys.argv[1] if len(sys.argv)>1 else "rophim_catalog.json"

def clean_title(t):
    t=str(t or "")
    t=re.sub(r"\s*\|\s*RoPhim\s*$","",t,flags=re.I)
    t=re.sub(r"\s*-\s*(?:Vietsub|Thuyết Minh|Lồng Tiếng).*?$","",t,flags=re.I)
    return re.sub(r"\s+"," ",t).strip()

def season_no(t):
    m=re.search(r"(?i)(?:phần|season)\s*[-:]?\s*(\d+)",str(t or ""))
    return int(m.group(1)) if m else None

def year(t,x):
    y=x.get("year")
    if isinstance(y,int): return y
    m=re.findall(r"\((19\d{2}|20\d{2}|21\d{2})\)",str(t or ""))
    return int(m[-1]) if m else None

def family_key(t):
    s=clean_title(t).lower()
    s=re.sub(r"\([^)]*(?:phần|season)\s*[-:]?\s*\d+[^)]*\)"," ",s,flags=re.I)
    s=re.sub(r"[-–—:]?\s*(?:phần|season)\s*[-:]?\s*\d+\b"," ",s,flags=re.I)
    s=re.sub(r"\((19\d{2}|20\d{2}|21\d{2})\)"," ",s)
    s=re.sub(r"\s+"," ",s).strip(" -–—:()")
    return s

def title_year_key(t,x):
    s=clean_title(t).lower()
    s=re.sub(r"\((19\d{2}|20\d{2}|21\d{2})\)"," ",s)
    s=re.sub(r"\s+"," ",s).strip()
    return s,year(t,x)

d=json.load(open(CAT,encoding="utf-8"))
rows=[x for x in d.get("movies",[]) if isinstance(x,dict)]
for i,x in enumerate(rows):
    x["_idx"]=i
    x["_poster"]=str(x.get("poster") or "").strip()
    x["_family"]=family_key(x.get("title"))
    x["_season"]=season_no(x.get("title"))
    x["_year"]=year(x.get("title"),x)
    x["_titleclean"]=clean_title(x.get("title"))

by_poster=collections.defaultdict(list)
for x in rows:
    if x["_poster"]: by_poster[x["_poster"]].append(x)

dup_groups={p:g for p,g in by_poster.items() if len(g)>1}
affected={x["_idx"] for g in dup_groups.values() for x in g}

same_family=[]
cross_family=[]
for p,g in dup_groups.items():
    fams={x["_family"] for x in g if x["_family"]}
    rec={"poster":p,"count":len(g),"families":sorted(fams),"items":[{"title":x["_titleclean"],"url":x.get("url"),"year":x["_year"],"season":x["_season"]} for x in g]}
    if len(fams)<=1:same_family.append(rec)
    else:cross_family.append(rec)

# Same normalized title/family with multiple years sharing same poster
same_name_diff_year=[]
fam_groups=collections.defaultdict(list)
for x in rows:
    if x["_family"]: fam_groups[x["_family"]].append(x)
for fam,g in fam_groups.items():
    years={x["_year"] for x in g if x["_year"] is not None}
    if len(years)<2: continue
    pmap=collections.defaultdict(list)
    for x in g:
        if x["_poster"]:pmap[x["_poster"]].append(x)
    for p,gg in pmap.items():
        ys={x["_year"] for x in gg if x["_year"] is not None}
        if len(ys)>=2:
            same_name_diff_year.append({"family":fam,"poster":p,"years":sorted(ys),"count":len(gg),"items":[{"title":x["_titleclean"],"url":x.get("url"),"year":x["_year"],"season":x["_season"]} for x in gg]})

# Same family with multiple seasons sharing same poster
season_dup=[]
for fam,g in fam_groups.items():
    ss={x["_season"] for x in g if x["_season"] is not None}
    if len(ss)<2: continue
    pmap=collections.defaultdict(list)
    for x in g:
        if x["_poster"]:pmap[x["_poster"]].append(x)
    for p,gg in pmap.items():
        s2={x["_season"] for x in gg if x["_season"] is not None}
        if len(s2)>=2:
            season_dup.append({"family":fam,"poster":p,"seasons":sorted(s2),"count":len(gg),"items":[{"title":x["_titleclean"],"url":x.get("url"),"year":x["_year"],"season":x["_season"]} for x in gg]})

# likely exact duplicate records = same family + same season + same year
exact_record_sets=[]
keymap=collections.defaultdict(list)
for x in rows:
    key=(x["_family"],x["_season"],x["_year"])
    if x["_family"]:keymap[key].append(x)
for k,g in keymap.items():
    urls={x.get("url") for x in g}
    if len(g)>1 and len(urls)>1:
        exact_record_sets.append({"key":{"family":k[0],"season":k[1],"year":k[2]},"count":len(g),"items":[{"title":x["_titleclean"],"url":x.get("url"),"poster":x["_poster"]} for x in g]})

# worst poster reuse across unrelated titles
cross_family.sort(key=lambda r:(-r["count"],r["poster"]))
same_family.sort(key=lambda r:(-r["count"],r["poster"]))
season_dup.sort(key=lambda r:(-r["count"],r["family"]))
same_name_diff_year.sort(key=lambda r:(-r["count"],r["family"]))

out={
 "catalogTotal":len(rows),
 "withPoster":sum(1 for x in rows if x["_poster"]),
 "uniquePosterUrls":len(by_poster),
 "duplicatePosterUrlGroups":len(dup_groups),
 "recordsUsingDuplicatedPosterUrl":len(affected),
 "duplicatePosterSameFamilyGroups":len(same_family),
 "duplicatePosterCrossFamilyGroups":len(cross_family),
 "multiSeasonSamePosterGroups":len(season_dup),
 "sameFamilyDifferentYearSamePosterGroups":len(same_name_diff_year),
 "likelyDuplicateRecordSets":len(exact_record_sets),
 "topCrossFamilyPosterReuse":cross_family[:100],
 "topSameFamilyPosterReuse":same_family[:200],
 "multiSeasonSamePoster":season_dup[:300],
 "sameFamilyDifferentYearSamePoster":same_name_diff_year[:300],
 "likelyDuplicateRecords":exact_record_sets[:300]
}
json.dump(out,open("poster_duplicate_audit.json","w",encoding="utf-8"),ensure_ascii=False,indent=2)
print(json.dumps({k:out[k] for k in [
 "catalogTotal","withPoster","uniquePosterUrls","duplicatePosterUrlGroups",
 "recordsUsingDuplicatedPosterUrl","duplicatePosterSameFamilyGroups",
 "duplicatePosterCrossFamilyGroups","multiSeasonSamePosterGroups",
 "sameFamilyDifferentYearSamePosterGroups","likelyDuplicateRecordSets"]},ensure_ascii=False))
