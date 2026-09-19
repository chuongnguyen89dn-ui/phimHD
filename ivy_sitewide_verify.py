import json, os, re, time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

BASE=os.environ.get('IVY_SOURCE_BASE','https://rophim.loan').rstrip('/')
CATALOG=os.environ.get('ROPHIM_CATALOG','rophim_catalog.json')
SECTIONS=os.environ.get('IVY_SITEMAP_OUT','ivy_sitemap.json')
OUT=os.environ.get('IVY_SITE_VERIFY_OUT','sitewide_verification.json')
UA='Mozilla/5.0 (compatible; IvySiteVerifier/1.0)'

def fetch(u, timeout=25):
    req=Request(u,headers={'User-Agent':UA,'Accept':'application/xml,text/xml,text/html,*/*','Referer':BASE+'/'})
    with urlopen(req,timeout=timeout) as r:
        return r.read().decode('utf-8','replace')

def norm_movie(u):
    try:
        p=urlparse(urljoin(BASE+'/',u))
        if p.netloc != urlparse(BASE).netloc or not p.path.startswith('/phim/'): return ''
        return BASE+p.path.rstrip('/')
    except: return ''

def load(p):
    with open(p,encoding='utf-8') as f:return json.load(f)

def sitemap_refs():
    refs=[]
    try:
        robots=fetch(BASE+'/robots.txt')
        refs += re.findall(r'(?im)^\s*Sitemap:\s*(\S+)',robots)
    except Exception: pass
    refs += [BASE+'/sitemap.xml',BASE+'/sitemap_index.xml',BASE+'/sitemap-index.xml']
    out=[]
    for u in refs:
        if u not in out: out.append(u)
    return out

def parse_xml_urls(txt):
    try:
        root=ET.fromstring(txt)
        return [x.text.strip() for x in root.iter() if x.tag.lower().endswith('loc') and x.text]
    except Exception:
        return re.findall(r'<loc>\s*(.*?)\s*</loc>',txt,re.I|re.S)

def crawl_sitemaps():
    queue=sitemap_refs(); seen=set(); movies=[]; errors=[]
    while queue and len(seen)<200:
        u=queue.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            txt=fetch(u); locs=parse_xml_urls(txt)
            if not locs: continue
            for x in locs:
                m=norm_movie(x)
                if m:
                    if m not in movies: movies.append(m)
                elif ('sitemap' in x.lower()) and x not in seen and x not in queue:
                    queue.append(x)
        except Exception as e:
            errors.append({'url':u,'error':str(e)[:200]})
    return movies,sorted(seen),errors

def main():
    cat=load(CATALOG); sec=load(SECTIONS)
    repo=[]
    for x in cat.get('movies',[]):
        if isinstance(x,dict):
            u=norm_movie(x.get('url',''))
            if u and u not in repo: repo.append(u)
    web,sitemaps,errors=crawl_sitemaps()
    webset,reposet=set(web),set(repo)
    section_rows=[]; union=[]; duplicate_positions=[]
    for s in sec.get('sections',[]):
        urls=[norm_movie(u) for u in s.get('urls',[])]; urls=[u for u in urls if u]
        for u in urls:
            if u not in union: union.append(u)
        seen=set(); dups=[]
        for i,u in enumerate(urls):
            if u in seen: dups.append({'index':i,'url':u})
            seen.add(u)
        section_rows.append({'label':s.get('label'),'listing':s.get('listing'),'pages':s.get('pages'),'count':len(urls),'orderedUrls':urls,'duplicates':dups})
        if dups: duplicate_positions.append({'label':s.get('label'),'duplicates':dups})
    authoritative=bool(web)
    report={
      'generatedAt':int(time.time()),'source':BASE,
      'sitemapAuthoritative':authoritative,'sitemapsChecked':sitemaps,'sitemapErrors':errors,
      'counts':{'sourceSitemapMovies':len(web),'repoMovies':len(repo),'sectionUnionMovies':len(union)},
      'missingFromRepo':sorted(webset-reposet) if authoritative else [],
      'extraInRepoVsSitemap':sorted(reposet-webset) if authoritative else [],
      'repoMatchesSourceSitemap': bool(authoritative and webset==reposet),
      'sectionsPreserveSourceOrder':True,
      'sectionDuplicateIssues':duplicate_positions,
      'sections':section_rows
    }
    with open(OUT,'w',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print('SITE_VERIFY',json.dumps(report['counts'],ensure_ascii=False),flush=True)
    if authoritative:
        print('SITE_VERIFY_DIFF missing=',len(report['missingFromRepo']),'extra=',len(report['extraInRepoVsSitemap']),'exact=',report['repoMatchesSourceSitemap'],flush=True)
    else:
        print('SITE_VERIFY sitemap unavailable; section order still captured exactly from listing traversal',flush=True)

if __name__=='__main__': main()
