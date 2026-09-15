# tiep tuc du an

## Bắt đầu tiếp quản

- Ngày bắt đầu làm việc trực tiếp với repo này: 12/09/2026.
- Repo lúc tiếp quản: trống.

## Tiến trình từ ngày tiếp quản

- Kết nối GitHub và xác nhận có quyền `push`/`admin` trên `chuongnguyen89dn-ui/phimHD`.
- Tạo crawler `rophim_catalog_crawler.py` để ưu tiên đọc sitemap/index sitemap rồi mở rộng qua các danh mục chính.
- Crawler hiện thu thập một file `rophim_catalog.json` gồm URL, slug, title, poster/backdrop, mô tả, năm, thời lượng, thể loại, chất lượng và loại movie/series khi nguồn công khai các trường đó.
- Tạo `app.py` làm addon catalog/meta cho Nuvio/Stremio với hai catalog Movies và Series, hỗ trợ poster, description, year, runtime, genres và website.
- Tạo `requirements.txt`, `README.md` và một `rophim_catalog.json` placeholder để repo có thể chạy ngay trước khi dữ liệu crawler thật được upload.
- Scanner local trước đó đã xác nhận một trang phim RoPhim phát HLS trực tiếp và playlist/segments trả HTTP 200; playback chưa được nối vào addon ở giai đoạn hiện tại.
- Crawler taxonomy v4 chạy thực tế trên Windows đã phát hiện 6.167 URL phim và tạo baseline catalog lớn; xác nhận taxonomy có phân trang sâu cho Phim Bộ, Phim Lẻ, Hoạt Hình và Lịch Chiếu.
- Thêm `rophim_catalog_crawler_taxonomy_v5.py`: dùng catalog hiện có làm cache, chỉ crawl chi tiết phim mới; mỗi lần cập nhật vẫn quét taxonomy/menu để cập nhật `genres`, `countries`, `sections`, `schedules`, tránh quét lại toàn bộ hàng nghìn trang phim.
- v5 ghi file theo cơ chế temporary + atomic replace để catalog cũ không bị mất nếu lần crawl mới thất bại trước khi hoàn tất.

## Việc tiếp theo

- Đưa baseline `rophim_catalog.json` thực tế lên nơi service có thể dùng bền vững.
- Cấu hình job/server chạy `rophim_catalog_crawler_taxonomy_v5.py` tự động, không phụ thuộc PC người dùng.
- Kiểm tra taxonomy mapping thực tế sau lần chạy v5 đầu tiên và nối catalog cập nhật vào addon.

## Cập nhật 12/09/2026 - Ivy❤️

- Đổi phần hiển thị addon sang `Ivy❤️`, manifest id `community.ivy.catalog`.
- Thêm catalog Phim Lẻ, Phim Bộ, Thể loại và Quốc gia.
- Nối resolver HLS HTTP vào endpoint stream; chỉ trả link thực tìm thấy từ trang phim, không đoán link.
- Thêm workflow tự cập nhật catalog và tối ưu crawler taxonomy chạy song song.
- Tạo workflow seed khẩn cấp 48 workers để đưa dữ liệu lên server mà không cần PC.
- Seed hoàn tất thành công: 6.168/6.168 phim, lỗi 0; catalog thực 5.374.169 bytes đã được commit lên `main` tại commit `c79af738072e314e1d436f6673f4f6d526d16483`.
- Render service `phimHD` đã auto-deploy commit catalog mới và trạng thái `live` tại deploy `dep-daij6j0jo6nc73blbpv0`.
- Từ thời điểm này dữ liệu phim đã nằm trên server; bước kế tiếp là kiểm tra catalog/stream thực tế trong Nuvio và tiếp tục làm taxonomy giàu dữ liệu hơn bằng job v5.x.

## Cập nhật 14/09/2026 - Home bám web nguồn

- Bỏ cách dùng TMDB để tự tạo các hàng Trending/Popular/Top Rated trên Home; TMDB chỉ còn dùng bổ sung poster/backdrop/rating cho phim đã có trong Ivy.
- Home Ivy chuyển sang đọc trực tiếp cấu trúc editorial của trang `/phimhay` và chỉ hiện section khi section đó thực sự tồn tại trên web nguồn.
- Bổ sung các section theo cấu trúc web nguồn: Điện ảnh Hàn Quốc, Mọt phim Hoa Ngữ, Thiên đường Phim Thái, Phim US-UK Mới, Phim Điện Ảnh Mới Cóng, Dấu ấn điện ảnh Việt, Đêm Kinh Hoàng, Mê Cung Phim Nhật, Phim Bộ Đã Hoàn Thành, Hành Động Nghẹt Thở, Trinh Thám & Bí Ẩn, Tinh Hoa Điện Ảnh Hồng Kông, Top 10 phim bộ hôm nay, Top 10 phim lẻ hôm nay, Thế giới Anime, Cổ Trang Trung Quốc, Mãn Nhãn với Phim Chiếu Rạp, Sắp Lên Sóng.
- Thêm các catalog điều hướng gần với menu nguồn: Phim Lẻ Mới, Phim Bộ Mới, Phim Lẻ, Phim Bộ, Phim 4K, Chiếu Rạp; thể loại tiếp tục dùng filter catalog của Nuvio/Stremio.
- Phiên bản addon tăng lên `1.7.0`, commit `ddf3e423613ada93fe4978b025e80c1ebd47646a`.

## Cập nhật 14/09/2026 - Search, metadata và trailer

- Sửa search để kết quả của từng hàng catalog không bị nhân sang Hàn Quốc/Hoa Ngữ/Thái khi Nuvio gửi cùng từ khóa cho tất cả catalog.
- Gỡ hai hàng tự thêm `Tìm toàn bộ phim lẻ/phim bộ`; Home chỉ giữ các hàng lấy từ web nguồn.
- Trường Quốc gia ở trang chi tiết ưu tiên đọc trực tiếp từ trang phim nguồn; không dùng nhãn taxonomy kiểu `Phim Âu Mỹ Mới Nhất` làm quốc gia.
- Kiểm tra mã nguồn Nuvio iOS Full và xác nhận trailer YouTube nội bộ có thể resolve ra `googlevideo.com` nhưng ffmpeg phát lại bị HTTP 403.
- Bỏ đường phát trailer native `meta.trailers` cho Ivy để tránh lỗi 403 của extractor Nuvio iOS Full.
- Thêm proxy trailer `/ytproxy/<youtube-id>.mp4`: Ivy dùng `yt-dlp` lấy progressive MP4 có cả hình và tiếng, chuyển tiếp Range/header qua Render rồi trả URL Ivy bình thường cho Nuvio.
- `/stream` thêm nguồn `🎬 Trailer` trỏ vào proxy Ivy; mục tiêu là Nuvio phát như stream MP4 bình thường, không còn tự mở googlevideo bằng ffmpeg.
- Phiên bản runtime hiện tại: `1.10.1`.

## Cập nhật 14/09/2026 - Sắp Lên Sóng và YouTube proxy 1.10.3

- Sửa `ivy_sitemap_crawler.py` để `Sắp Lên Sóng` không còn phụ thuộc 12 poster preview ở Home: ưu tiên link Xem thêm/Xem toàn bộ và fallback `/lich-chieu`, sau đó quét pagination tới khi hết dữ liệu.
- Crawler mở từng phim trong `Sắp Lên Sóng`, lưu cờ Trailer và các YouTube ID tìm được vào `ivy_sitemap.json`; runtime ưu tiên dữ liệu này trước khi fallback trang chi tiết/TMDB.
- Xác nhận log Render của bản cũ trả lỗi `Sign in to confirm you're not a bot` cho các YouTube ID, nên nguyên nhân 502 nằm ở resolver YouTube trên Render chứ không phải Nuvio.
- Đổi YouTube resolver sang ưu tiên client `android_vr` + format `18` (H264+AAC premuxed), sau đó thử `web_embedded` và `tv` nếu cần.
- Bắt buộc probe `Range: bytes=0-1` từ chính Render trước khi cache/trả stream cho Nuvio; URL 401/403/410 sẽ bị xoá cache và resolve lại, tránh đưa URL chết cho player.
- Thêm log `youtube probe`, `youtube proxy hit`, upstream status/client/format để xác định chính xác đường phát đang dùng.
- Runtime hiện tại: `1.10.3`; commit `9978c1c920aa3f0c7e1e50bcedece6916f788d3b`; Render deploy `dep-dajp2e2jnfac73f80d7g` đã `live`.

## Cập nhật 15/09/2026 - Crawler web gốc và baseline đối chiếu

- Phạm vi công việc hiện tại chuyển về web gốc RoPhim và addon phim Ivy❤️; mọi cập nhật catalog phải lấy web nguồn làm chuẩn về membership, thứ tự và nội dung hiển thị.
- Workflow `Ivy catalog update` có một lần chạy thất bại: taxonomy không phát hiện được phim mới (`pages=1`, `movies=0`) và sitemap dừng ở lỗi `cannot fetch source home`. Không coi kết quả `new=0` của lần này là bằng chứng web không có phim mới.
- Sửa `ivy_sitemap_crawler.py` để request web nguồn có retry, luân phiên browser User-Agent và xử lý trường hợp `/phimhay` tạm thời không phản hồi. Commit sửa crawler: `5c03d1ca78484860b7c13a15dad643d62ec1bc2a`.
- Workflow #38 sau sửa đã chạy thành công và publish snapshot mới lên nhánh `catalog-data`; commit snapshot `19002d1d2c7b4b6236aa906b39ffa47e5548d8d7`.
- Lần crawl thành công này quét được 6.703 URL taxonomy; 708 URL chưa có trong cache cũ và catalog tăng từ 6.167 lên 6.865 phim. 708 URL này là URL mới được crawler phát hiện, KHÔNG mặc định coi là 708 phim mới trong ngày vì có thể gồm phim cũ crawler trước đó bỏ sót.
- Playback audit của lần chạy thành công đạt 120/120 mẫu phát được.
- Đã xác định nguyên tắc kiểm tra phim mới: không dựa vào vị trí vài poster đầu Home và không dựa riêng vào `newMovieCount`; phải đối chiếu URL của snapshot với web gốc, kiểm tra URL đã tồn tại trước đó và phân biệt phim mới với phim/tập chỉ vừa cập nhật.
- Snapshot ngày 15/09 hiện được dùng làm baseline ổn định cho các lần crawl tiếp theo để diff URL chính xác. Khi phát hiện thay đổi phải báo riêng: phim mới, tập mới/cập nhật và thay đổi section nếu có.
- Cần tiếp tục tăng độ an toàn crawler: nếu `/phimhay` không lấy được dữ liệu hợp lệ thì không được âm thầm coi trang `/` là tương đương; ưu tiên giữ snapshot cũ hoặc fail workflow để tránh publish membership sai.
- Cần kiểm tra đủ 18 section của `/phimhay`, toàn bộ pagination và số URL thực tế của từng section; runtime không được làm rơi URL chỉ vì URL đó chưa có metadata trong `rophim_catalog.json`.
