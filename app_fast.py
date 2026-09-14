import app_full as core

SECTION_RULES={
 'Điện ảnh Hàn Quốc':['han quoc','korea'],
 'Mọt phim Hoa Ngữ':['trung quoc','hoa ngu','china'],
 'Thiên đường Phim Thái':['thai lan','thailand'],
 'Phim US-UK Mới':['au my','us uk','anh','my'],
 'Phim Điện Ảnh Mới Cóng':['dien anh','chieu rap'],
 'Dấu ấn điện ảnh Việt':['viet nam','vietnam'],
 'Đêm Kinh Hoàng':['kinh di','horror'],
 'Mê Cung Phim Nhật':['nhat ban','japan'],
 'Phim Bộ Đã Hoàn Thành':['phim bo','hoan thanh'],
 'Hành Động Nghẹt Thở':['hanh dong','action'],
 'Trinh Thám & Bí Ẩn':['trinh tham','bi an','mystery'],
 'Tinh Hoa Điện Ảnh Hồng Kông':['hong kong','hongkong'],
 'Thế giới Anime':['anime'],
 'Cổ Trang Trung Quốc':['co trang'],
 'Mãn Nhãn với Phim Chiếu Rạp':['chieu rap'],
}
LIMITED={'Top 10 phim bộ hôm nay','Top 10 phim lẻ hôm nay','Sắp Lên Sóng'}

def _all_text(x):
    vals=[]
    for k in ('sections','genres','countries'):
        vals += core.tax(x,k)
    vals += [x.get('title',''),x.get('description','')]
    return core.norm(' '.join(str(v) for v in vals if v))

def source_section_items_fast(label):
    info=core.source_home_sections().get(label) or {}
    urls=list(info.get('home') or [])
    if label not in LIMITED:
        rules=SECTION_RULES.get(label,[])
        if rules:
            for x in core.load().get('movies',[]):
                text=_all_text(x)
                if any(core.norm(r) in text for r in rules):
                    u=x.get('url')
                    if u and u not in urls: urls.append(u)
    return core.ordered(urls)

def source_menu_fast(kind):
    data=core.load();rows=data.get('movies',[]);stored=(data.get('sourceOrders') or {}).get('series' if kind=='series' else 'movies') or []
    items=core.ordered(stored,lambda x:core.typ(x)==kind)
    seen={x.get('url') for x in items}
    for x in rows:
        if core.typ(x)==kind and x.get('url') not in seen:
            items.append(x);seen.add(x.get('url'))
    return core.dedupe_series(items) if kind=='series' else items

def manifest_fast():
    common=[{'name':'skip','isRequired':False},{'name':'search','isRequired':False}]
    cats=[{'type':'movie','id':'ivy_movies','name':'❤️ Ivy • Phim Lẻ','extra':common},{'type':'series','id':'ivy_series','name':'❤️ Ivy • Phim Bộ','extra':common}]
    active=core.source_home_sections()
    for i,label in enumerate(core.SOURCE_SECTIONS):
        if active.get(label):
            cats.append({'type':'series' if label in core.SERIES_SECTIONS else 'movie','id':f'ivy_src_{i}','name':f'❤️ Ivy • {label}','extra':common})
    return {'id':'community.ivy.catalog','version':'1.9.2','name':'Ivy❤️','description':'Ivy❤️ • source catalogs, cached full listings, web playback resolver','resources':['catalog','meta','stream'],'types':['movie','series'],'idPrefixes':['ivy_'],'behaviorHints':{'configurable':False},'catalogs':cats}

core.source_section_items=source_section_items_fast
core.source_menu=source_menu_fast
core.manifest_data=manifest_fast
app=core.app
