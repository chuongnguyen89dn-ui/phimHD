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

## Việc tiếp theo

- Nhận file `rophim_catalog.json` hoàn chỉnh từ crawler Windows.
- Kiểm tra số lượng sitemap, URL, phim/series, metadata thiếu và lỗi crawl.
- Thay placeholder catalog bằng dữ liệu thật.
- Deploy addon và kiểm tra manifest/catalog/meta trên Nuvio.
