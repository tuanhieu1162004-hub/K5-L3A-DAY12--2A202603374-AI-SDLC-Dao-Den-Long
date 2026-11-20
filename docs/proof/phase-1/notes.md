# Phase 1

- Chọn Python vì môi trường Windows đã có Python 3.11. Giao diện dùng Tkinter để chiếu tọa độ 3D lên màn hình, và gọi cùng vòng mô phỏng với headless.
- Chọn 300 giây, 3 máu, 5 đom đóm mỗi đèn. E nạp tối đa lượng đèn còn thiếu vào đèn chưa sáng gần nhất. Q tác động theo mặt phẳng XZ.
- Bằng chứng nhảy dùng cùng seed và scenario trống. Kiểm tra độ cao tăng sau khi bấm, tiếp đất khi vẫn giữ nút và chỉ nhảy lại khi nhả rồi bấm.
- `final-lantern.jsonl` ghi thắng ở tick 1 khi nạp đủ đèn cuối. `last-flame.jsonl` ghi thua ở tick 1 khi Bóng Mực chạm Mây còn một máu. Cả hai ca đã chạy qua cửa sổ Tkinter trên Windows và kiểm tra nút Chơi lại đưa trạng thái về đầu màn.
- Nhật ký AI. Codex chia công việc thành từng thay đổi nhỏ và kiểm tra CLI sau mỗi luật. Lượt thử vùng an toàn ban đầu so sánh lớn hơn 2,5 với tọa độ đã làm tròn. Phép thử sau kiểm tra cả vị trí và trạng thái flee. Chưa có số liệu token để ước tính chi phí đáng tin cậy.
