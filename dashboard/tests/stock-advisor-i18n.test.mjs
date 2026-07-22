import assert from "node:assert/strict";
import test from "node:test";

import { localizeAdvisorWarning } from "../src/lib/stock-advisor-i18n.ts";

test("localizes every advisor warning emitted by the scanner", () => {
  const cases = [
    [
      "Khuyến nghị mặc định; User phải xác nhận riêng trước mọi giao dịch thật.",
      "Advisory only; the user must confirm separately before every real trade.",
    ],
    [
      "Backtest dùng thành phần VN30 hiện tại nên có survivorship bias.",
      "The backtest uses current VN30 constituents and is subject to survivorship bias.",
    ],
    [
      "Backtest mới đánh giá 187/250; chưa đủ 250 quyết định.",
      "The backtest has evaluated 187/250 decisions; the 250-decision target has not been met.",
    ],
    [
      "Hurdle đang bằng 0; kết quả chưa khấu trừ chi phí và biên an toàn thực tế.",
      "The hurdle is 0; results do not yet deduct actual costs or the safety margin.",
    ],
  ];

  for (const [warning, expected] of cases) {
    const localized = localizeAdvisorWarning(warning, "EN");
    assert.equal(localized, expected);
    assert.doesNotMatch(localized, /Khuyến nghị|phải xác nhận|thành phần|mới đánh giá|chưa đủ|đang bằng|chi phí|biên an toàn/iu);
  }
});

test("keeps VN and unknown server warnings intact", () => {
  const vietnamese = "Khuyến nghị mặc định; User phải xác nhận riêng trước mọi giao dịch thật.";
  const unknown = "SSI returned incomplete data for one symbol.";

  assert.equal(localizeAdvisorWarning(vietnamese, "VN"), vietnamese);
  assert.equal(localizeAdvisorWarning(unknown, "EN"), unknown);
});
