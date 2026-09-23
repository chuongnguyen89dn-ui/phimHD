# TIEP TUC DU AN — phimHD / Ivy❤️

## 1. Mục tiêu hiện tại

Repo `chuongnguyen89dn-ui/phimHD` là addon phim cho Nuvio/Stremio, lấy RoPhim làm nguồn dữ liệu chính.

Mục tiêu production hiện tại:
- Home Nuvio phản chiếu đúng các hàng/section của trang chính RoPhim.
- Phim mới, phim/tập vừa cập nhật và thay đổi section được crawl tự động hằng ngày.
- Metadata lấy từ catalog RoPhim, TMDB chỉ dùng bổ sung khi cần.
- Playback lấy trực tiếp từ nguồn HLS thực trên trang `/xem-phim/`.
- Với phim bộ: chọn tập nào chỉ trả stream đúng của tập đó; RoPhim có bao nhiêu server thật thì Nuvio hiện đúng bấy nhiêu.
- Production chính: `https://phimhd.onrender.com`.
- Manifest: `https://phimhd.onrender.com/manifest.json`.

## 2. Ngày bắt đầu và baseline

- Bắt đầu làm trực tiếp repo: **12/09/2026**.
- Repo lúc tiếp quản: gần như trống.
- Đã tạo crawler RoPhim, catalog JSON, addon Flask, manifest Nuvio/Stremio, Render deploy và GitHub Actions.
- Baseline đầu tiên xác nhận RoPhim có thể cung cấp HLS trực tiếp và playlist/segment trả HTTP 200.

## 3. Tiến trình 12/09/2026 — dựng catalog và addon

- Tạo `rophim_catalog_crawler.py` để quét sitemap + category.
- Tạo `rophim_catalog.json` làm dữ liệu nguồn của addon.
- Tạo `app.py` / `app_full.py` với catalog, meta và stream.
- Đổi branding thành **Ivy❤️**, manifest id `community.ivy.catalog`.
- Tạo crawler taxonomy v5 dùng cache để chỉ refresh phim mới/stale, tránh mở lại toàn bộ hàng nghìn trang ở mỗi lần chạy.
- Seed catalog server-side hoàn tất khoảng 6.168 URL baseline, không cần PC người dùng.
- Production Render `phimHD` được tạo và chạy từ repo này.

## 4. Tiến trình 14/09/2026 — Home bám web nguồn

- Bỏ các hàng Home tự tạo bằng TMDB.
- Chuyển Home Ivy sang cấu trúc editorial của `/phimhay`.
- Các section được lấy theo RoPhim, gồm các nhóm như:
  - Điện ảnh Hàn Quốc
  - Mọt phim Hoa Ngữ
  - Thiên đường Phim Thái
  - Phim US-UK Mới
  - Phim Điện Ảnh Mới Cóng
  - Dấu ấn điện ảnh Việt
  - Đêm Kinh Hoàng
  - Mê Cung Phim Nhật
  - Phim Bộ Đã Hoàn Thành
  - Hành Động Nghẹt Thở
  - Trinh Thám & Bí Ẩn
  - Tinh Hoa Điện Ảnh Hồng Kông
  - Top 10 phim bộ hôm nay
  - Top 10 phim lẻ hôm nay
  - Thế giới Anime
  - Cổ Trang Trung Quốc
  - Mãn Nhãn với Phim Chiếu Rạp
  - Sắp Lên Sóng
- Search được sửa để không nhân kết quả qua nhiều hàng catalog.
- Metadata quốc gia ưu tiên dữ liệu nguồn thay vì suy diễn từ taxonomy.
- Có giai đoạn thử nghiệm trailer/YouTube proxy, yt-dlp, residential backend và muxing. Đây là nhánh nghiên cứu cũ, không phải kiến trúc playback phim production hiện tại.

## 5. Tiến trình 15/09/2026 — crawler, audit và baseline ổn định

- Workflow `Ivy catalog update` được dùng để cập nhật tự động.
- Có lần crawler fail khi web nguồn không phản hồi; từ đó thêm retry, browser User-Agent và quy tắc không được publish snapshot sai khi nguồn không hợp lệ.
- Một lần crawl thành công phát hiện thêm nhiều URL mà crawler cũ bỏ sót; không mặc định coi toàn bộ URL mới phát hiện là “phim mới trong ngày”.
- Playback audit từng đạt **120/120 mẫu phát được**.
- Nguyên tắc cập nhật được chốt:
  - phân biệt phim mới thật với URL cũ crawler vừa phát hiện;
  - phân biệt phim mới với tập mới/cập nhật;
  - theo dõi thay đổi membership và thứ tự section;
  - không dùng vài poster đầu Home làm bằng chứng duy nhất.

## 6. Tiến trình 23/09/2026 — sửa playback sau khi RoPhim đổi domain/cấu trúc

RoPhim chuyển nguồn hiện hành từ `rophim.loan` sang **`rophims.team`** và playback được đưa sang route `/xem-phim/`.

### 6.1. Xác nhận HLS bằng browser AI local

Browser-harness/Codex local đã mở trang thật, bấm Play và bắt được HLS thực.

Ví dụ đã xác nhận:
- master HLS: `https://v7.kkphimplayer7.com/20260707/h9fUpbeJ/index.m3u8`
- 1080p variant: `https://v7.kkphimplayer7.com/20260707/h9fUpbeJ/3500kb/hls/index.m3u8`
- playlist và TS segment trả HTTP 200.
- Không cần cookie đặc biệt trong test; Referer `https://rophims.team/` có thể dùng khi cần.

Kết luận: nguồn playback tồn tại; lỗi trước đó là resolver đang nhìn sai route `/phim/` thay vì `/xem-phim/`.

### 6.2. Resolver production

Đã sửa:
- `BASE` mặc định sang `https://rophims.team`.
- ID/catalog cũ có URL `rophim.loan` vẫn được giữ tương thích, nhưng playback được canonicalize sang host mới.
- `source_watch_url()` đổi `/phim/` → `/xem-phim/`.
- Resolver đọc HLS từ watch page.
- Diagnostic endpoint có thể kiểm tra detail page + watch page.

### 6.3. Render production

Phát hiện một lỗi quan trọng: GitHub đã có code mới nhưng Render `phimhd.onrender.com` còn chạy commit cũ.

Sau khi trigger deploy đúng commit mới:
- `phimhd.onrender.com` lên live.
- Người dùng xác nhận **Nuvio đã có link phát và play được**.

Đây là baseline production quan trọng: khi GitHub đã sửa nhưng Nuvio chưa đổi, phải kiểm tra commit đang live trên Render trước.

## 7. Sửa phim bộ — đúng tập, đúng số server

Đã phát hiện lỗi:
- trang của một season có thể chứa HLS của nhiều tập;
- resolver cũ quét toàn bộ HLS trên trang;
- hậu quả: click Tập 1 có thể thấy HLS của nhiều tập khác.

Phân tích phim mẫu xác nhận:
- 12 HLS là **12 tập**, không phải 12 server của một tập;
- server thật của phim mẫu chỉ là `Vietsub`.

Đã sửa:
- `episode_rows()` ưu tiên `server_data` thật.
- watch-page anchor chỉ là fallback khi tập đó chưa có dữ liệu server.
- direct HLS của `server_data` không bị scan lại cả trang.
- thêm mapping theo số tập: Tập 1 chỉ lấy `tap-1/Tập 1`, Tập 2 chỉ lấy `tap-2/Tập 2`, v.v.
- một tập có bao nhiêu `server_name` thật trên RoPhim thì Nuvio trả đúng bấy nhiêu stream.
- không gộp tất cả về 1 nếu nguồn thật có nhiều server.
- không biến variant 1080p/720p hoặc HLS của tập khác thành server giả.

Các commit chính:
- `e8517039e103192a2d535f377ba40977fb2be5ab` — Match series streams to source servers exactly.
- `7dfcceb4a7074295544f6b4b5908f95aeaf80227` — Bind series streams to the requested episode.

## 8. Sửa cập nhật catalog và Home ngày 23/09/2026

Phát hiện snapshot cũ báo:
- previous: 7.403
- current: 6.167
- added: 0
- removed: 1.236

Đây được xác định là kết quả không đáng tin do crawler/sitemap còn mang host cũ `rophim.loan`, trong khi web thật đã chuyển sang `rophims.team`.

Đã sửa toàn bộ pipeline:
- `rophim_catalog_crawler.py` dùng `rophims.team`.
- `rophim_catalog_crawler_taxonomy_v5.py` dùng `rophims.team`.
- `ivy_sitemap_crawler.py` dùng `rophims.team`.
- URL cũ `rophim.loan` được canonicalize sang `rophims.team` theo cùng path/slug để không coi cùng một phim là phim mới/xóa.
- sửa typo `Phim Điện Ảnh Mới Cóong` → `Phim Điện Ảnh Mới Cóng`.
- Nuvio không còn bắt buộc dùng danh sách row hard-code; `app_fast.py` đọc thứ tự row từ `ivy_sitemap.json` mới được crawl theo thứ tự thật của homepage.
- playback audit trong workflow được giới hạn 100 mục để không chặn publish catalog hàng giờ.
- commit chính:
  - `03d58ddb51016e7f3a3a5eecf54c899a0cac7d6b` — canonicalize catalog source.
  - `2837398dc3166d17d79c26c0049909b92c335cb2` — taxonomy crawler sang host mới.
  - `cc1206683246595543163ea8d009616bb2073c26` — crawl homepage/rows từ host mới.
  - `05f07b6071ae13d7fdaa534e7ba3538404870d01` — Nuvio follow live homepage row ordering.
  - `37e40589a33729629edd5e513da05649cbfbc780` — publish current RoPhim catalog without full playback blocking.

## 9. Cập nhật tự động hằng ngày

Workflow: `.github/workflows/ivy-catalog.yml`

Lịch hiện tại:
- `0 0,8,16 * * *` UTC.
- Tương ứng khoảng **07:00, 15:00, 23:00 giờ Việt Nam**.
- Như vậy catalog được kiểm tra/cập nhật **3 lần mỗi ngày**, vượt yêu cầu tối thiểu cập nhật hằng ngày.

Mỗi run phải:
1. lấy snapshot catalog trước đó từ branch `catalog-data`;
2. crawl catalog/taxonomy từ `https://rophims.team`;
3. tạo báo cáo diff;
4. crawl homepage + pagination thành `ivy_sitemap.json`;
5. verify sitewide và thứ tự section;
6. audit playback mẫu;
7. chỉ sau đó publish catalog/sitemap/report sang branch `catalog-data`.

Không được coi run fail hoặc nguồn không lấy được là “không có phim mới”.

## 10. Kiến trúc production hiện tại

### GitHub
- Repo: `chuongnguyen89dn-ui/phimHD`
- Branch code: `main`
- Branch data runtime: `catalog-data`

### Render
- Service: `phimHD`
- URL: `https://phimhd.onrender.com`
- Branch: `main`
- Runtime: Python
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app`
- Auto-deploy: enabled.

### Runtime
- `app.py` → `app_fast.py` → dùng resolver/meta từ `app_full.py`.
- Catalog runtime tải `rophim_catalog.json` từ branch `catalog-data`.
- Home rows tải `ivy_sitemap.json` từ branch `catalog-data`.
- Playback resolve động từ RoPhim watch page.

## 11. Quy tắc không được phá

- Không quay playback về `rophim.loan`.
- Không chỉ đọc `/phim/` để tìm stream; playback hiện ở `/xem-phim/`.
- Không quét toàn bộ HLS trên season page rồi trả vào một tập.
- Không tạo server giả từ quality variant.
- Không ép 1 stream nếu RoPhim có nhiều server thật.
- Không hard-code thứ tự Home nếu sitemap mới đã có thứ tự từ homepage.
- Không publish catalog mới nếu crawl nguồn thất bại hoặc dữ liệu giảm bất thường mà chưa được xác minh.
- Không coi mọi URL mới phát hiện là phim phát hành mới trong ngày.
- Khi Nuvio không phản ánh code mới, kiểm tra Render đang live commit nào trước khi sửa tiếp.

## 12. Trạng thái tại 23/09/2026

- Playback movie: **đã hoạt động trên Nuvio**.
- Playback series: logic đã sửa để đúng tập và đúng số server nguồn.
- Domain/resolver: đã chuyển sang `rophims.team`.
- Production: `phimhd.onrender.com`.
- Catalog pipeline: đã sửa canonicalization host cũ → mới.
- Home ordering: đã chuyển sang lấy thứ tự từ sitemap/homepage crawl.
- Daily update: chạy tự động 3 lần/ngày.
- Run catalog mới sau thay đổi domain đang được dùng để tạo baseline sạch cho các diff tiếp theo.

## 13. Việc cần theo dõi tiếp

- Xác nhận run catalog sau migration host publish thành công lên `catalog-data`.
- Kiểm tra `catalog_changes_latest.json` sau baseline mới để báo đúng:
  - phim mới thật;
  - phim/tập cập nhật;
  - phim bị gỡ;
  - thay đổi section.
- Định kỳ kiểm tra Render auto-deploy có thực sự bám commit `main`.
- Nếu RoPhim đổi HTML/server schema, ưu tiên kiểm tra bằng browser-harness local và network thực trước khi thay resolver.
