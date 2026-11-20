# Đảo Đèn Lồng

- Kiểm tra Python bằng `python3 --version` và Tkinter bằng `python3 -m tkinter`.
- Mở game 3D bằng `python3 src/panda_game.py` sau khi cài `requirements-render.txt`. Lệnh headless và ca thử nhảy nằm trong README.
- Giao diện và headless dùng chung logic tại `src/headless.py`.
- Giữ mô phỏng 60 tick/giây, seed tất định và đồng bộ tuning với game.contract.json.
- Phase 2: dữ liệu bản đồ nằm tại `src/night_maps.py`. Dùng `--night 1|2|3` để kiểm tra từng Đêm và đối chiếu `tick` với `sim_tick` ở ca pause.
- Ghi rõ tuning tạm trong spec cho đến khi đối chiếu được bảng chuẩn.
- Chạy các ca liên quan trước khi kết luận. Lưu đầu ra thật và ghi rõ ca chưa kiểm tra.
