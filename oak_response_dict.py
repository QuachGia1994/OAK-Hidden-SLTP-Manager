# -*- coding: utf-8 -*-
import random

def get_random_response(key, **kwargs):
    """
    Lấy một mẫu phản hồi ngẫu nhiên từ từ điển và format với các tham số truyền vào.
    """
    templates = RESPONSE_TEMPLATES.get(key, ["✅ Xong rồi ạ."])
    template = random.choice(templates)
    try:
        # Debug: Print keys being passed
        # print(f"DEBUG: Key={key}, Args={kwargs.keys()}")
        return template.format(**kwargs)
    except Exception as e:
        # If formatting fails, try to return a simplified version or the raw template
        # print(f"DEBUG: Format Error: {e}")
        return template

RESPONSE_TEMPLATES = {
    # --- PNL / DỰ BÁO LÃI LỖ ---
    "pnl_profit": [
        "<c=#2ecc71>🚀</c> Kèo {symbol}{acc} đang rất sáng cửa!\nNếu giá chạm {price}, ví bạn sẽ dày thêm {pnl:,.2f}$.\n🔥 Đang gồng lãi {lots:.2f} lots cực căng.",
        "<c=#2ecc71>💰</c> Thơm phức! {symbol}{acc} về {price} là lụm lúa.\nDự kiến chốt lãi: +{pnl:,.2f}$.\n😎 {lots:.2f} lots đang chạy mượt.",
        "<c=#2ecc71>💎</c> Kim cương đây rồi! {symbol}{acc} chạm {price} là ấm.\nLợi nhuận dự tính: {pnl:,.2f}$.\n✨ Hold chặt {lots:.2f} lots nhé sếp!",
        "<c=#2ecc71>📈</c> Xanh mướt luôn! Kèo {symbol}{acc} mà về {price} thì tuyệt vời.\nTổng lãi sẽ là: {pnl:,.2f}$.\n💪 {lots:.2f} lots đang chiến đấu.",
        "🥂 Kèo này uy tín quá sếp ơi! {symbol}{acc} hit {price} là có ngay {pnl:,.2f}$. Quá đã! 🥳",
    ],
    "pnl_loss": [
        "<c=#e74c3c>💀</c> Căng rồi sếp ơi! {symbol}{acc} đang hơi run.\nNếu giá về {price}, tài khoản sẽ bay {pnl:,.2f}$.\n<c=#f1c40f>⚠️</c> Đang kẹt {lots:.2f} lots. Cân nhắc xử lý nhé!",
        "<c=#e74c3c>💸</c> Báo động đỏ! {symbol}{acc} chạm {price} là đau ví.\nDự kiến lỗ: -{pnl:,.2f}$.\n🥶 {lots:.2f} lots đang 'xa bờ'.",
        "<c=#e74c3c>📉</c> Tình hình không ổn lắm với {symbol}{acc}.\nVề giá {price} là đi mất {pnl:,.2f}$.\n<c=#e74c3c>🛑</c> Tổng {lots:.2f} lots đang gồng lỗ.",
        "🚑 Gọi cấp cứu! Kèo {symbol}{acc} rủi ro cao.\nNếu chạm {price} sẽ âm {pnl:,.2f}$.\n🤔 {lots:.2f} lots này cần xem lại chiến thuật.",
        "🌧️ Trời đang mưa trên kèo {symbol}{acc}...\nHit {price} là mất {pnl:,.2f}$.\n☔ Cẩn thận củi lửa nhé sếp.",
    ],
    "pnl_error_no_pos": [
        "<c=#3498db>🔍</c> Soi nát mắt mà không thấy lệnh {symbol} nào đang chạy cả sếp ơi!",
        "👻 {symbol} đang 'tàng hình' à? Em tìm không ra lệnh nào cả.",
        "❓ Sếp có nhầm không? Em check {count} tài khoản rồi mà không thấy {symbol} đâu.",
        "🤷‍♂️ Lệnh {symbol} đâu mất tiêu rồi? Không tìm thấy sếp ạ.",
    ],

    # --- LIST / STATUS (DANH SÁCH LỆNH) ---
    "list_header": [
        "<c=#3498db>📊</c> **TỔNG HỢP VỊ THẾ HIỆN TẠI**\n",
        "<c=#3498db>📋</c> **DANH SÁCH LỆNH ĐANG CHẠY**\n",
        "<c=#3498db>📝</c> **BÁO CÁO TRẠNG THÁI (STATUS)**\n",
        "<c=#3498db>🧐</c> **SOI KÈO CÙNG BOT**\n",
        "🏰 **TÌNH HÌNH CHIẾN SỰ LÚC NÀY:**\n",
    ],
    "list_item": [
        "<c=#3498db>🔹</c> {symbol}: {type} {lot} (Lãi: {pnl:,.2f}$)",
        "<c=#e67e22>🔸</c> {symbol} (#{ticket_id}): {type} {lot} ➔ {pnl:,.2f}$",
        "<c=#f1c40f>⚡</c> {symbol} {lot} {type} | {pnl:,.2f}$",
    ],
    "list_empty": [
        "🕸️ Tài khoản đang trống trơn, chưa có lệnh nào cả.",
        "💤 Bot đang thất nghiệp đây, sếp chưa vào lệnh nào hết.",
        "🏖️ Sàn vắng tanh như chùa bà Đanh. Chưa có vị thế nào.",
        "🤷‍♂️ Không có lệnh nào đang chạy sếp ơi. Nghỉ ngơi thôi!",
    ],
    "list_summary": [
        "\n<c=#2ecc71>💰</c> **Tổng PnL:** {total_pnl:,.2f}$",
        "\n<c=#2ecc71>💎</c> **Balance:** {balance:,.2f}$ | **Equity:** {equity:,.2f}$",
        "\n🔥 **Kết quả:** {total_pnl:,.2f}$ | **Ví:** {balance:,.2f}$",
    ],

    # --- CLOSE / CHỐT LỆNH ---
    "close_success": [
        "<c=#2ecc71>✂️</c> Xong! Đã cắt lệnh {symbol} #{ticket_id} gọn gàng.",
        "<c=#2ecc71>✅</c> Đã chốt {symbol} (#{ticket_id}). Tiền về túi!",
        "<c=#e74c3c>🗑️</c> Đã dọn dẹp xong lệnh {symbol} #{ticket_id} theo chỉ đạo.",
        "<c=#2ecc71>👌</c> Done! Lệnh {symbol} #{ticket_id} đã được xử lý.",
        "<c=#2ecc71>💰</c> 'Lụm lúa'! Lệnh {symbol} #{ticket_id} đã được đóng lại.",
    ],
    "close_all_success": [
        "🌪️ Bão táp đã qua! Đã đóng TOÀN BỘ lệnh theo yêu cầu.",
        "🧹 Nhà cửa sạch sẽ! Đã clear all positions.",
        "<c=#e74c3c>🛑</c> Đã dừng cuộc chơi. Toàn bộ lệnh đã được đóng lại.",
        "🧼 Sạch bóng quân thù! Không còn lệnh nào đang chạy.",
        "🏁 Finish! Em đã tiễn tất cả các lệnh lên đường.",
    ],
    "close_fail": [
        "<c=#e74c3c>❌</c> Ối! Không đóng được lệnh #{ticket_id}. Sếp check lại giúp em.",
        "<c=#e74c3c>⚠️</c> Lỗi rồi! Lệnh #{ticket_id} cứng đầu quá không chịu đóng.",
        "<c=#e74c3c>🚫</c> Failed to close #{ticket_id}. Có biến sếp ơi!",
    ],

    # --- DELETE / HỦY LỆNH CHỜ ---
    "del_success": [
        "<c=#e74c3c>🗑️</c> Đã hủy lệnh chờ #{ticket_id} thành công.",
        "<c=#e74c3c>⛔</c> Lệnh chờ #{ticket_id} đã bị xóa sổ.",
        "👋 Bye bye lệnh chờ #{ticket_id}. Đã xóa xong.",
        "🧹 Đã gỡ lệnh #{ticket_id} ra khỏi danh sách chờ rồi ạ.",
        "👌 Đã 'khai tử' lệnh chờ #{ticket_id} theo ý sếp.",
    ],
    "del_all_success": [
        "<c=#e74c3c>🗑️</c> Đã xóa sạch sành sanh các lệnh chờ (Pending Orders).",
        "🧹 List lệnh chờ đã được dọn sạch.",
        "<c=#e74c3c>⛔</c> Đã hủy toàn bộ lệnh pending.",
        "🌪️ Đã giải tán toàn bộ quân dự bị (lệnh chờ)!",
    ],
    "all_ticket_close_deleted": [
        "<c=#e74c3c>🗑️</c> Đã xóa {p_count} lệnh chốt lời (Partial) và {s_count} lệnh hẹn giờ đóng. Sạch sẽ!",
        "🧹 Xong! Đã dọn {p_count} nhiệm vụ Partial & {s_count} lịch đóng lệnh.",
        "👌 Đã hủy bỏ {p_count} kèo 'xẻ thịt' và {s_count} lệnh hẹn giờ theo ý sếp.",
    ],

    # --- MODIFY / DỜI SL TP ---
    "modify_success": [
        "<c=#2ecc71>✅</c> Đã cập nhật {type} cho {count} lệnh {symbol} về mức {val} rồi ạ. Cực kỳ chuẩn xác!",
        "<c=#2ecc71>🎯</c> Đã chỉnh sửa mục tiêu cho {symbol} ({count} lệnh) thành công.",
        "<c=#2ecc71>🛠️</c> Đã sửa xong {type} cho các lệnh {symbol}. Chúc sếp win!",
        "<c=#2ecc71>👌</c> Đã kéo {type} của {symbol} về {val} rồi nhé đại ca.",
        "<c=#2ecc71>✨</c> Update xong! {count} lệnh {symbol} đã có {type} mới là {val}.",
    ],
    "modify_fail": [
        "<c=#e74c3c>❌</c> Không sửa được lệnh {symbol}. Sếp xem lại mức giá nhé.",
        "<c=#e74c3c>⚠️</c> Lỗi khi modify. Giá {type} có vẻ không hợp lệ sếp ạ.",
        "<c=#e74c3c>🚫</c> Sàn không cho sửa lệnh rồi. Sếp check lại kết nối nhé.",
    ],

    # --- ORDER PLACED (ĐẶT LỆNH) ---
    "order_placed": [
        "<c=#2ecc71>✅</c> Đã ghi sổ: {type} {symbol} {lot} lot lúc {time} (ID: #{ticket_id}). Chúc sếp thắng lớn!",
        "<c=#2ecc71>🎯</c> Nhận lệnh! Sếp đã đặt {type} {symbol} {lot} lot vào lúc {time}. ID lệnh: #{ticket_id}.",
        "<c=#3498db>🚀</c> Lệnh chờ đã sẵn sàng: {type} {symbol} {lot} lot, hẹn sếp lúc {time} nhé! (ID: #{ticket_id})",
        "<c=#2ecc71>👌</c> Đã cài xong: {type} {symbol} {lot} lot lúc {time}. ID: #{ticket_id}. Em sẽ canh cho sếp!",
        "<c=#3498db>📝</c> Đã lưu lịch: {type} {symbol} {lot} lot @ {time}. Mã lệnh: #{ticket_id}.",
    ],

    # --- PARTIAL CLOSE (CHỐT TỪNG PHẦN) ---
    "partial_task_added": [
        "<c=#3498db>📝</c> Đã ghi sổ: Lệnh #{ticket_id} ({symbol}) lãi {profit}$ em sẽ 'lụm' {vol} lot.",
        "<c=#2ecc71>🎯</c> Nhận nhiệm vụ! #{ticket_id} lãi {profit}$ là em tự động 'bỏ túi' {vol} lot ngay.",
        "🕵️‍♂️ Em sẽ canh giúp sếp, #{ticket_id} đạt lãi {profit}$ là em cắt {vol} lot liền.",
        "<c=#2ecc71>👌</c> Ok anh, đã cài kèo 'lụm' {vol} lot cho lệnh #{ticket_id} khi lãi đạt {profit}$.",
        "🔥 Kèo 'xẻ thịt' {vol} lot cho #{ticket_id} khi lãi {profit}$ đã sẵn sàng!",
    ],
    "partial_success": [
        "<c=#2ecc71>💰</c> Chốt lãi từng phần thành công! Đã cắt {vol} lot cho lệnh {ticket_id}.",
        "<c=#2ecc71>✂️</c> Đã 'lụm' bớt {vol} lot cho #{ticket_id}. Tiền tươi thóc thật!",
        "🍗 Đã xẻ bớt {vol} lot cho lệnh {ticket_id}. Chúc mừng sếp!",
    ],

    # --- CHECK / KIỂM TRA GIÁ ---
    "check_price": [
        "<c=#3498db>👀</c> Giá {symbol} hiện tại: Bid {bid} | Ask {ask}",
        "<c=#3498db>🏷️</c> {symbol} đang chạy ở mức: {bid} / {ask}",
        "<c=#3498db>📡</c> Cập nhật {symbol}: {bid} (Bán) - {ask} (Mua)",
        "<c=#3498db>📊</c> Soi giá: {symbol} đang là {bid}/{ask} sếp ơi.",
    ],
    
    # --- ERROR / LỖI CHUNG ---
    "error_general": [
        "😵 Bot đang chóng mặt, có lỗi xảy ra rồi sếp: {error}",
        "🐛 Có con bọ (bug) vừa cắn em: {error}. Lỗi rồi!",
        "🤖 System Error: {error}. Sếp thử lại sau nhé.",
        "<c=#e74c3c>⚠️</c> Gay quá, hệ thống báo lỗi: {error}. Đại ca xem giúp em!",
    ],
    "error_syntax": [
        "gõ sai rồi đại ca ơi, cú pháp là: {syntax}",
        "❓ Em không hiểu. Sếp gõ lại theo mẫu này nhé: {syntax}",
        "✍️ Sai chính tả rồi. Thử lại: {syntax}",
        "🤨 Câu lệnh này lạ quá, sếp thử lại nhé: {syntax}",
    ]
}
