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
