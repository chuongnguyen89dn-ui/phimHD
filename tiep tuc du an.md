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
