# MCP Monitor — Audit Ledger (Phase 1) & Live Read-only (Phase 2)

`mt5_mcp_server.py` là một **MCP server stdio chỉ-đọc** cho phép các MCP host (Claude Desktop, IDE agent, CLI host…) truy vấn báo cáo hiệu suất và lịch sử giao dịch của hệ thống OAK.

`mt5_mcp_live_server.py` (Phase 2, xem mục 6) là một **tiến trình MCP tách biệt**, đọc trực tiếp terminal MT5 đang chạy. Nó **mặc định bị TẮT** và chỉ bật được bằng thao tác thủ công của người dùng.

## 1. Phạm vi & giới hạn an toàn (BẮT BUỘC đọc)

- **Phase 1 = audit ledger only.** Toàn bộ dữ liệu lấy từ sổ cái append-only cục bộ `data/trade_audit.db`.
- Server **không kết nối terminal**, **không khởi chạy terminal**, **không đăng nhập tài khoản**, **không import thư viện broker**, và **không có bất kỳ tool giao dịch/điều khiển nào** (kể cả dạng stub).
- SQLite được mở bằng URI tuyệt đối `file:///...?immutable=1&mode=ro` kèm `PRAGMA query_only=ON`. Adapter không ghi vào file ledger và không tạo file phụ `-wal` / `-shm`.
  - Hệ quả: adapter đọc ảnh chụp đã checkpoint của ledger. Nếu tiến trình ghi đang giữ dữ liệu trong `-wal` chưa checkpoint, kết quả có thể cũ hơn thực tế — vì vậy mọi báo cáo đều kèm nhãn thời gian quan sát.
- Đường dẫn database và danh sách profile **chỉ đến từ biến môi trường**, không bao giờ nhận từ tham số tool. Không có tool nào trả về `account_uid`, login, server, đường dẫn terminal, ticket, magic, comment hay thông tin đăng nhập.
- Mọi kết quả đều có `source: "audit_ledger"` cùng `observed_at_utc` / `data_age_seconds` để client tự đánh giá độ trễ dữ liệu.

## 2. Cài đặt trên Windows

```powershell
# Trong thư mục gốc repo
python -m pip install -r requirements-mcp.txt
```

`requirements-mcp.txt` gồm `mcp` (SDK MCP, dùng cho cả hai server) và `psutil` (**chỉ** Phase 2 dùng, để xác minh terminal đã chạy sẵn). Phase 1 không cần `psutil`.

Biến môi trường (Phase 1):

| Biến | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `OAK_MCP_AUDIT_DB` | Không | Đường dẫn tuyệt đối tới file ledger. Mặc định: `<repo>\data\trade_audit.db`. File phải tồn tại. |
| `OAK_MCP_PROFILES` | **Có** | Danh sách profile được phép báo cáo, phân tách bằng dấu phẩy (ví dụ `Vantage,ICMarkets`). Nếu rỗng, mọi tool theo profile trả về lỗi cấu hình (fail closed) và `list_accounts` trả `{"configured": false, "accounts": []}`. |

Kiểm tra nhanh bộ test an toàn (tự tạo ledger tạm, không cần MT5, không cần tài khoản thật):

```powershell
python -m pytest tests/test_mt5_mcp_monitor.py
```

Chạy server thủ công cho một profile thật (host sẽ nói chuyện qua stdin/stdout; log chỉ ra stderr):

```powershell
$env:OAK_MCP_AUDIT_DB = "C:\path\to\ROBOT SLTP\data\trade_audit.db"
$env:OAK_MCP_PROFILES = "Vantage"
python "C:\path\to\ROBOT SLTP\mt5_mcp_server.py"
```

## 3. Khai báo MCP server

### 3.1. OpenCode (cấu hình của repo này)

Repo đã có sẵn cấu hình **phạm vi dự án** tại `.opencode/opencode.json` (theo schema `https://opencode.ai/config.json`):

| MCP server | Lệnh | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| `oak-mt5-audit` | `python mt5_mcp_server.py` | **`enabled: true`** | Chỉ đọc sổ cái `data/trade_audit.db`. Không chạm terminal. |
| `oak-mt5-live` | `python mt5_mcp_live_server.py` | **`enabled: true`** | Đọc live trực tiếp; **đã BẬT theo yêu cầu rõ ràng của người dùng** cho profile `Vantage`, kèm `OAK_MCP_LIVE_ENABLED: "1"` và `OAK_MCP_LIVE_REQUIRE_DEMO: "0"`. Vẫn chỉ là attach-only / read-only: không khởi chạy terminal, không đăng nhập, không có tool lệnh. |

Cấu hình dùng đường dẫn tương đối (`cwd: "."`) và **không chứa** secret, login hay đường dẫn tuyệt đối theo máy.

> OpenCode chỉ đọc file cấu hình **một lần lúc khởi động**. Sau khi sửa `.opencode/opencode.json`, phải **thoát hẳn OpenCode và mở lại** thì thay đổi mới có hiệu lực.

### 3.2. MCP host khác (ví dụ dạng `mcpServers`)

Ví dụ **tham khảo** theo định dạng cấu hình stdio kiểu Claude Desktop. Tài liệu này **không tự động sửa** file cấu hình của bất kỳ client nào — hãy tự dán vào file cấu hình của bạn và thay đường dẫn tuyệt đối cho đúng máy.

```json
{
  "mcpServers": {
    "oak-mt5-audit": {
      "command": "C:\\Python314\\python.exe",
      "args": ["C:\\path\\to\\ROBOT SLTP\\mt5_mcp_server.py"],
      "env": {
        "OAK_MCP_AUDIT_DB": "C:\\path\\to\\ROBOT SLTP\\data\\trade_audit.db",
        "OAK_MCP_PROFILES": "Vantage"
      }
    }
  }
}
```

## 4. Danh sách tool (đúng 8 tool, tất cả read-only)

| Tool | Tham số | Mô tả |
| --- | --- | --- |
| `list_accounts` | — | Metadata an toàn của các profile trong allowlist: `profile`, `broker`, `currency`, `account_type`, `available`, `latest_sampled_at_utc`. |
| `account_overview` | `profile` | Balance / equity / margin / free margin / margin level / open profit mới nhất. |
| `performance_summary` | `profile` | Net profit, realized P/L, profit factor, win rate, expectancy, drawdown, phí… (`null` nếu ledger chưa đủ dữ liệu). |
| `trade_history` | `profile`, `limit` (1–200), `from_utc`, `to_utc`, `symbol` | Deal BUY/SELL mới nhất trước; chỉ trả symbol/deal_type/entry_type/reason_category/volume/price/profit/commission/swap/fee/deal_time_utc. |
| `equity_curve` | `profile`, `limit` (1–1000) | Chuỗi `t/equity/balance` theo thứ tự thời gian tăng dần. |
| `checkpoint_history` | `profile`, `limit` (1–100) | Lịch sử checkpoint run (broker_date, checkpoint_hour, interval, capture_mode, status). |
| `risk_summary` | `profile` | Exposure theo symbol/hướng, chuỗi thắng-thua, drawdown, recovery factor. **Suy ra từ ledger**, không phải ảnh chụp vị thế live. |
| `audit_integrity` | `profile` | Kiểm tra chuỗi hash append-only: `ok`, `events`, `first_broken` (`ok: null` nếu profile chưa có tài khoản trong ledger). |

Tham số vượt biên, timestamp sai định dạng ISO-8601, symbol không hợp lệ hoặc profile ngoài allowlist đều bị từ chối bằng lỗi rõ ràng (fail closed).

## 5. Tài liệu tham khảo đã tra cứu

- MCP — Build an MCP server (hướng dẫn server + transport stdio): <https://modelcontextprotocol.io/docs/develop/build-server>
- MCP — Transports (stdio: JSON-RPC trên stdout, log trên stderr): <https://modelcontextprotocol.io/docs/concepts/transports>
- MCP Specification — Server Tools: <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
- MCP Python SDK (`FastMCP`, `mcp.run(transport="stdio")`): <https://github.com/modelcontextprotocol/python-sdk>
- MQL5 — Python integration overview: <https://www.mql5.com/en/docs/python_metatrader5>
- MQL5 — `account_info()`: <https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py>
- MQL5 — `history_deals_get()`: <https://www.mql5.com/en/docs/python_metatrader5/mt5historydealsget_py>

Các tài liệu MQL5 được tra cứu để đối chiếu ngữ nghĩa trường dữ liệu (deal/entry/reason, số dư, ký quỹ) với schema ledger — **Phase 1 không gọi bất kỳ API nào trong số đó**.

## 6. Phase 2 — `mt5_mcp_live_server.py` (đọc live, MẶC ĐỊNH TẮT)

Phase 2 là **tiến trình riêng**, không dùng chung code với Phase 1: `mt5_mcp_server.py` vẫn chỉ đọc sổ cái, `mt5_mcp_live_server.py` là nơi duy nhất chạm tới terminal.

### 6.1. Mô hình an toàn (fail closed ở mọi cửa)

Thứ tự kiểm tra trước **mỗi** request; sai bất kỳ bước nào là từ chối, chưa hề gọi broker:

1. `OAK_MCP_LIVE_ENABLED` phải đúng bằng `1`. Mặc định (không đặt / `0` / `true` / `yes`) là **từ chối**.
2. Profile phải nằm trong allowlist `OAK_MCP_PROFILES`.
3. Profile phải tồn tại trong `OAK_MCP_PROFILES_FILE` (mặc định `profiles.json`) và có `path` trỏ tới một `terminal64.exe` tuyệt đối, có thật.
4. `psutil` phải thấy **đúng** file `terminal64.exe` đó đang chạy sẵn. Không có `psutil`, sai đường dẫn, hoặc terminal chưa chạy ⇒ từ chối. Server **không bao giờ tự khởi chạy terminal** và không có code khởi tạo tiến trình.
5. Nếu profile khai `login_id`/`login`/`server`, tài khoản đang gắn phải khớp; lệch là ngắt.
6. Trừ khi `OAK_MCP_LIVE_REQUIRE_DEMO` được đặt tường minh bằng `0`, tài khoản phải có `trade_mode` đúng bằng hằng số demo của gói broker. Mọi giá trị khác (real, contest, không đọc được) đều bị từ chối.

Ngoài ra: gói `MetaTrader5` **chỉ được import bên trong session đã qua đủ cửa** (import module server không kéo theo broker); mỗi request giữ một khoá tiến trình vì kết nối MT5 là trạng thái toàn cục; `mt5.shutdown()` luôn chạy trong `finally`; không có API đăng nhập, đặt/sửa/đóng lệnh nào được import hay tham chiếu; lỗi trả về đã được làm sạch (không kèm chi tiết lỗi broker, login, server, đường dẫn hay credential).

### 6.2. Cách bật (người dùng tự làm, không tự động hoá)

> **Trạng thái hiện tại (theo yêu cầu rõ ràng của người dùng):** live read mode **đã được BẬT** cho profile `Vantage` trong `.opencode/opencode.json` — `enabled: true`, `OAK_MCP_LIVE_ENABLED: "1"`, `OAK_MCP_LIVE_REQUIRE_DEMO: "0"`. Mọi cửa an toàn khác (allowlist, profile store, terminal phải đang chạy, không login, không tool lệnh) **vẫn giữ nguyên**. Server vẫn chỉ là **attach-only / read-only**: không tự khởi chạy terminal, không đăng nhập, không có bất kỳ tool giao dịch/điều khiển nào.
>
> **Cảnh báo tài khoản REAL — cần phê duyệt vận hành của người dùng.** Vì `OAK_MCP_LIVE_REQUIRE_DEMO=0`, server giờ **cho phép đọc một tài khoản thật (REAL)** đang gắn vào terminal, không chỉ demo. Điều này chỉ được bật sau khi người dùng **trực tiếp xác nhận bằng phê duyệt vận hành** rằng họ chấp nhận rủi ro đọc tài khoản thực. Việc bật công tắc này **không** cấp quyền ghi/lệnh — server vẫn không thể đặt, sửa, đóng lệnh hay đăng nhập.
>
> **Chưa có bằng chứng runtime.** Phase 2 mới chỉ được kiểm thử bằng broker/psutil giả lập và unit test. Chưa từng có lần đọc live nào được thực hiện hay xác minh trên máy này — **không được hiểu là đã chạy thật**.

1. **Tự tay mở terminal** MT5 muốn đọc và để nó chạy — server sẽ không mở giúp.
2. **Tự xác nhận tài khoản đang đăng nhập** (DEMO hay REAL) là tài khoản bạn có ý định cho phép đọc. Với `OAK_MCP_LIVE_REQUIRE_DEMO=0`, tài khoản REAL cũng được phép đọc — chỉ làm khi bạn đã phê duyệt vận hành rủi ro đó.
3. `OAK_MCP_LIVE_ENABLED` đã là `1` và `OAK_MCP_LIVE_REQUIRE_DEMO` đã là `0` trong cấu hình repo.
4. `mcp["oak-mt5-live"].enabled` đã là `true` trong `.opencode/opencode.json`.
5. **Thoát hẳn OpenCode rồi mở lại** (cấu hình chỉ nạp lúc khởi động) — thay đổi mới có hiệu lực.

Chưa làm đủ bước 1 và 5 thì mọi tool live đều trả lỗi (terminal chưa chạy, hoặc cấu hình chưa nạp).

### 6.3. Ba tool live (đều read-only)

| Tool | Tham số | Trả về |
| --- | --- | --- |
| `live_account_overview` | `profile` | `profile`, `available`, `account_mode` (`DEMO`/`REAL`/`UNKNOWN`), `currency`, `balance`, `equity`, `margin`, `free_margin`, `margin_level`, `open_profit`. |
| `live_positions` | `profile` | `count` + danh sách vị thế, mỗi vị thế chỉ có `symbol`, `direction`, `volume`, `open_price`, `current_price`, `profit`, `sl`, `tp`, `open_time_utc`. |
| `live_trade_history` | `profile`, `from_utc`, `to_utc` (bắt buộc, ISO-8601), `limit` (1–200, mặc định 100), `symbol` | Deal BUY/SELL mới nhất trước, mỗi deal chỉ có `symbol`, `deal_type`, `entry_type`, `reason_category`, `volume`, `price`, `profit`, `commission`, `swap`, `fee`, `deal_time_utc`. |

Ràng buộc: khoảng thời gian tối đa **31 ngày**, tối đa **200 dòng**, `symbol` phải khớp `[A-Za-z0-9._#-]{1,32}`, `from_utc` ≤ `to_utc`. Sai tham số là lỗi ngay, chưa mở session.

Mọi kết quả kèm `source: "mt5_live"` + `observed_at_utc` (thời điểm đọc) và `account_mode`. **Không** có `data_age_seconds` vì đây là ảnh chụp tại thời điểm đọc.

Các trường bị lược bỏ có chủ đích (không tool nào trả về): số tài khoản/login, tên chủ tài khoản, server/broker, đường dẫn terminal, deal/order/position ticket, `position_id`, `magic`, `comment`, `external_id`, và mọi thông tin đăng nhập.

### 6.4. Chế độ tài khoản REAL — đã được cấu hình theo phê duyệt rủi ro

Đọc live trên tài khoản **REAL** hiện **đã được bật** qua `OAK_MCP_LIVE_REQUIRE_DEMO=0` trong `.opencode/opencode.json`, theo **yêu cầu rõ ràng và phê duyệt vận hành của người dùng** (không tự động, không ngầm). Lưu ý quan trọng:

- `OAK_MCP_LIVE_REQUIRE_DEMO=0` **cho phép đọc một tài khoản thật (REAL)** đang gắn vào terminal — không còn giới hạn ở demo. Đây là quyết định rủi ro đã được người dùng xác nhận trực tiếp; không được bật lại một cách ngẫu nhiên.
- Công tắc này **chỉ mở rộng phạm vi đọc**, không cấp bất kỳ quyền ghi/lệnh nào. Server vẫn không import hay tham chiếu `order_send`, không đăng nhập, không khởi chạy terminal.
- **Chưa có bằng chứng runtime/live.** Mọi kiểm thử Phase 2 đều dùng broker/psutil giả lập và unit test; chưa từng có lần đọc live nào được thực hiện hay xác minh trên máy này — **không được hiểu là đã chạy thật**. Tuyên bố "production-ready" hay "đã đọc live thành công" chỉ được đưa ra sau khi có bằng chứng runtime thực tế do người dùng xác nhận.

### 6.5. Kiểm thử

```powershell
python -m pytest tests/test_mt5_mcp_monitor.py tests/test_mt5_mcp_live_monitor.py
```

Toàn bộ test Phase 2 chạy với broker giả lập, `psutil` giả lập, `profiles.json` tạm và file `terminal64.exe` giả — **không cần MT5, không kết nối tài khoản, không có lệnh nào được gửi**.
