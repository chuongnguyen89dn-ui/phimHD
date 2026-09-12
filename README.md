# phimHD / RoPhim catalog addon

Bộ khung hiện tại gồm:

- `rophim_catalog_crawler.py`: quét sitemap + các danh mục RoPhim, thu thập URL, slug, title, poster/backdrop, mô tả, năm, thời lượng, thể loại, chất lượng và loại movie/series nếu trang công khai các trường đó.
- `rophim_catalog.json`: file dữ liệu duy nhất mà addon đọc. File đang là placeholder rỗng cho tới khi crawler trên máy Windows chạy xong.
- `app.py`: addon catalog/meta tương thích kiểu Stremio/Nuvio.
- `requirements.txt`: dependencies để deploy.

## Chạy crawler trên Windows

```bat
py -u rophim_catalog_crawler.py
```

Crawler ghi file vào:

```text
C:\Users\<user>\Desktop\rophim_catalog.json
```

Sau khi crawler hoàn tất, thay file `rophim_catalog.json` trong repo bằng file kết quả.

## Chạy addon local

```bash
pip install -r requirements.txt
python app.py
```

Manifest:

```text
http://localhost:10000/manifest.json
```

## Trạng thái

Đã xác nhận scanner local bắt được HLS trực tiếp trên một phim RoPhim và các segment trả HTTP 200. Phần repo hiện tập trung vào catalog + metadata trước; phần playback chỉ được nối cho các nguồn mà người vận hành có quyền sử dụng.
