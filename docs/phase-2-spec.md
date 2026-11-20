# Phase 2 · Ticket-02

Tiêu chí dưới đây dựa trên phần Ticket-02 đã nhận. Cần đối chiếu bản đầy đủ trước khi chốt tuning và màu.

| Mục | Tiêu chí nghiệm thu | Cách thử |
|---|---|---|
| Thứ tự tick | Logic chạy 60 Hz theo thứ tự đã nêu. Gió Lạc cướp trước khi Bóng Mực đánh. Thực thể mới chỉ tương tác từ tick kế tiếp. | Đặt cả hai địch cùng vị trí với Mây và đối chiếu thứ tự sự kiện. |
| Điểm | Nạp mỗi đom đóm được 10 điểm. Thắp đèn được 100 điểm. Pulse được 5 điểm mỗi Bóng Mực trúng, kể cả đang choáng. Thắng được thêm `floor(time_left_s) * 2 + flames * 50`. Tổng hành trình chỉ gồm các Đêm đã thắng. | Đặt đèn cuối gần Mây, nạp và đối chiếu công thức. |
| Đêm 1 | Bán kính 40 m, 5 đèn theo tọa độ chuẩn, 24 điểm sinh đom đóm và 12 điểm sinh Bóng Mực. Sinh hai Bóng Mực ở giây 5, sau đó theo lịch 8 giây, tối đa 6 con và cách Mây ít nhất 15 m. | Đối chiếu snapshot và sự kiện quanh mốc sinh. Thử bước qua mép đảo. |
| Đêm 2 | Hai đảo bán kính 28 m có tâm cách nhau 70 m, nối bằng cầu đúng tọa độ. Có 6 đèn, 2 bục phóng và lịch Bóng Mực 7 giây, tối đa 8 con. Bục giữ vận tốc ngang đến khi tiếp đất, vẫn cho phép lướt. | Bước trên cầu và bước ra khỏi cầu. Chạy qua bục rồi đổi hướng input giữa không trung. |
| Đêm 3 | Ba tầng đúng cao độ và phạm vi, hai dốc, một bục phóng và tháp không leo được. Có 7 đèn và lịch Bóng Mực 6 giây, tối đa 10 con. Gió theo seed có chu kỳ 30 giây, kéo dài 5 giây, tốc độ đẩy 2 m/s, báo trước 2 giây. | Đi qua dốc, thử leo vách, bước khỏi tầng, dùng bục và so sánh hai lần chạy cùng seed. Quan sát cảnh báo trong giao diện. |
| Gió Lạc | Chỉ xuất hiện ở Đêm 2 và 3 theo mốc 1200 tick, tối đa 2 con. Chuyển trạng thái theo khoảng cách và lượng đang mang. Cướp tối đa 3 đom đóm đúng một lần. Pulse đuổi con đang chase và thu hồi vật bị cướp từ con đang flee. | Thử ranh giới chase, va chạm trong vùng an toàn và pulse ở cả hai trạng thái. |
| Bùa Gió | Bùa tại các tọa độ quy định, tăng chạy lên 7,2 m/s trong 600 tick, lướt 14 m/s trong 12 tick và bỏ hồi chiêu khi bùa còn hiệu lực. Bùa hồi sau 2700 tick. | Nhặt bùa, lướt liên tiếp bằng các lần nhấn riêng, kiểm tra hết hiệu lực và hồi sinh. |
| Chuỗi ba Đêm | Từ menu đến giới thiệu, chơi và kết quả. Thua cho chơi lại Đêm hiện tại. Thắng Đêm 3 hiện Bình Minh và tổng điểm. | Chạy luồng UI qua từng màn kết quả. |
| Tạm dừng | Esc/P hoặc input `pause` theo cạnh nhấn. Trong pause chỉ `tick` tăng, `sim_tick` và các bộ đếm đứng yên. Menu có tiếp tục, chơi lại Đêm, cài đặt và về menu. | Pause giữa lúc có bộ đếm, so snapshot rồi tiếp tục. |
| Cài đặt và âm thanh | Âm lượng và độ nhạy chuột tồn tại sau khi mở lại. Có nhạc nền, âm thanh theo sự kiện trong ticket và đếm ngược 10 giây cuối. | Kiểm tra lưu và tải cài đặt, kiểm tra sự kiện có âm thanh tương ứng. |
| HUD và màu | HUD đủ chỉ số, thanh 10 ô, hồi chiêu, nhắc nạp và chỉ hướng đèn. Đồng hồ đỏ nhấp nháy từ 30 giây. Ánh sáng môi trường theo công thức ticket. Màu tuân mức sai lệch 10% mỗi kênh theo bảng chuẩn. | Kiểm tra giao diện tại thời điểm và vị trí liên quan, đối chiếu RGB sau khi có bảng. |
| Contract và hiệu năng | v1.1 hỗ trợ cả ba Đêm, đủ input, snapshot, scenario và event mới. Chạy lại ca Phase 1 với số chuẩn. Headless 21.600 tick trong 30 giây. Giao diện trung bình ít nhất 30 FPS ở 1280×720. | Đo thời gian chạy và FPS thực tế, lưu cấu hình và kết quả. |

## Dữ liệu cần đối chiếu với slide

- Giá trị đang dùng tạm: hồi chiêu lướt 1 giây, TTL đom đóm rơi 600 tick, rơi mất một Ngọn Lửa và đưa Mây về điểm xuất phát.
- Tạm bổ sung tối đa một đom đóm mỗi hai giây tại điểm chuẩn đang trống. Cơ chế này chỉ chạy khi bật sinh đom đóm mặc định, để ba Đêm có đủ ánh sáng nạp đèn trong lúc chờ bảng chuẩn.

- Bảng tuning **Phần 1**. Bản đã nhận nhắc đến bảng nhưng thiếu các giá trị chuẩn, gồm thời lượng từng Đêm và các thông số lướt, va chạm, rơi, hồi chiêu.
- Bảng RGB **mục 8**. Bản đã nhận có dung sai và công thức ánh sáng, thiếu màu gốc của từng thành phần.

## Kiểm chứng lại

Chạy `python3 tests/check_phase2.py` (Windows dùng `python`). Bộ kiểm tra gọi CLI thật để kiểm tra ba bản đồ, cầu và bục, rơi, pause, lướt với bùa, Gió Lạc, gió Đêm 3, điểm thắng và phép đo 21.600 tick trong kịch bản kiểm soát.

Đêm 2 và 3 hiện khai báo thời lượng tạm 300 giây. Bài đo 21.600 tick ghi đè thời lượng thành 360 giây và tắt sinh thực thể để đo được đủ số bước. Chưa kiểm tra bộ test ẩn hoặc đối chiếu bảng màu.

[Số đo FPS trên Windows](proof/phase-2/fps-windows.json) ghi một đoạn chơi 5 giây ở Đêm 3, dùng vòng lặp Tkinter bình thường với thao tác đi và xoay camera. Cửa sổ là 1280×720, vùng vẽ là 1280×635 vì HUD và điều khiển nằm bên dưới. Ca thử tắt tiếng và đạt 30,68 FPS, đồng thời xác nhận nút Tiếp tục hoạt động. Cần đo lại ở độ phân giải vùng vẽ đầy đủ và trên macOS hoặc Linux.
