# Retro · Đảo Đèn Lồng

Phase 1 dựng được vòng lặp 60 Hz và dùng JSONL để khóa hành vi có thể kiểm chứng. Các ca nhỏ giúp xác định lỗi ranh giới bán kính và nút giữ mà không phải chơi lại cả màn. Tkinter cho phép mở bản chơi sớm, nhưng giới hạn vật liệu và ánh sáng.

Phase 2 mở rộng sang ba bản đồ, tách thời gian mô phỏng khỏi tick khi tạm dừng và thêm kẻ địch, bùa, gió. Bản trích ticket thiếu bảng tuning và RGB. Những giá trị tạm được ghi trong spec. Lần đo FPS đầu chạy thừa callback cập nhật nên kết quả bị loại. Phép đo sau dùng đúng một vòng lặp Tkinter.

Phase 3 thay luật thắng sớm bằng chấm ở bình minh. Cách dùng số nguyên cho nhiên liệu giúp kiểm tra đúng thời điểm tắt đèn và tránh sai số tích lũy. Thay test thắng sớm bằng test đi qua bình minh và giữ bằng chứng cũ ở tag tương ứng. Panda3D cho phép giữ cùng lõi mô phỏng trong khi đổi giao diện.

Phase 4 dùng benchmark có 200 Bóng Mực và 100 đom đóm để phát hiện chi phí nhiều nút vẽ nhỏ. Gộp các chi tiết mắt và chỉ cập nhật màu khi trạng thái đổi cải thiện số khung hình. Ca thử giao diện cũng phát hiện chuỗi đường dẫn Windows không dùng được trực tiếp để nạp âm thanh trong Panda3D. Soak giúp đo bộ nhớ ngay trong một tiến trình qua nhiều lần khởi tạo màn.

`AGENTS.md` hữu ích nhất ở việc lưu lệnh và quy ước kiểm chứng. Chưa có thống kê token từ các lượt đã chạy nên tổng token và chi phí chưa xác định. Đã giảm ngữ cảnh bằng việc kiểm tra từng luật với scenario nhỏ, giữ mô phỏng dùng chung và chạy lại bộ ca qua một lệnh. Nếu làm lại, chọn renderer ngay đầu lab, ghi usage sau từng phase và xác nhận bảng chuẩn trước khi triển khai tuning.
