import {
  NEOTECH_PUBLIC_RULESET,
  accountFingerprint,
  maskedLogin,
  ruleScore,
  type NeoTechConnectorCashFlow,
  type NeoTechConnectorDeal,
  type NeoTechPublicIngestPayload,
  type NeoTechPublicMonth,
  type NeoTechPublicProfile,
  type NeoTechPublicRule,
  type NeoTechPublicRuleCode,
  type NeoTechPublicStatus,
  type NeoTechPublicWeek,
} from "./neotech-public-domain.ts";

const DAY = 86_400;
const MONTH = 30 * DAY;
const WEEK = 7 * DAY;

type ExtraEntry = { timeMsc: number; orderTicket: string; dealTicket: string };

type Episode = {
  positionId: string;
  brokerSymbol: string;
  canonicalSymbol: string;
  productEligible: boolean;
  productReliable: boolean;
  direction: 1 | -1;
  firstEntryMsc: number;
  finalCloseMsc: number;
  openingDealTicket: string;
  openingOrderTicket: string;
  additionalEntries: ExtraEntry[];
  initialVolume: number;
  currentVolume: number;
  weightedPrice: number;
  netProfit: number;
  expertOpenViolation: boolean;
  openingReasonUnknown: boolean;
  open: boolean;
  sltpEvidenceComplete: boolean;
  maxSltpDistancePips: number;
  tradingMonthIndex: number;
  serverUtcOffsetMinutes: 120 | 180;
};

function finite(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

function canonicalSymbol(deal: NeoTechConnectorDeal): { symbol: string; eligible: boolean; reliable: boolean; pipSize: number } {
  const base = deal.baseCurrency.trim().toUpperCase();
  const profit = deal.profitCurrency.trim().toUpperCase();
  const forex = deal.forexCalc && base.length === 3 && profit.length === 3;
  const gold = base === "XAU" && profit === "USD";
  const symbol = base && profit ? `${base}${profit}` : deal.symbol.trim().toUpperCase();
  const eligible = forex || gold;
  const reliable = Boolean(base && profit);
  const override = Number(deal.pipSizeOverride || 0);
  const pipSize = override > 0 ? override : forex && deal.point > 0 ? ((deal.digits === 3 || deal.digits === 5) ? deal.point * 10 : deal.point) : 0;
  return { symbol, eligible, reliable, pipSize };
}

function manualReason(deal: NeoTechConnectorDeal): boolean {
  if (!deal.reasonReliable) return false;
  return ["CLIENT", "MOBILE", "WEB"].includes(deal.dealReason) || ["CLIENT", "MOBILE", "WEB"].includes(deal.orderReason);
}

function expertReason(deal: NeoTechConnectorDeal): boolean {
  if (!deal.reasonReliable) return false;
  return deal.dealReason === "EXPERT" || deal.orderReason === "EXPERT";
}

function observeSltp(episode: Episode, deal: NeoTechConnectorDeal, pipSize: number): void {
  if (!deal.sltpSnapshotReliable || pipSize <= 0) return;
  if (deal.sl > 0) episode.maxSltpDistancePips = Math.max(episode.maxSltpDistancePips, Math.abs(deal.price - deal.sl) / pipSize);
  if (deal.tp > 0) episode.maxSltpDistancePips = Math.max(episode.maxSltpDistancePips, Math.abs(deal.price - deal.tp) / pipSize);
}

function createEpisode(deal: NeoTechConnectorDeal): Episode {
  const meta = canonicalSymbol(deal);
  const episode: Episode = {
    positionId: deal.positionId,
    brokerSymbol: deal.symbol,
    canonicalSymbol: meta.symbol,
    productEligible: meta.eligible,
    productReliable: meta.reliable,
    direction: deal.side === "BUY" ? 1 : -1,
    firstEntryMsc: deal.timeMsc,
    finalCloseMsc: 0,
    openingDealTicket: deal.ticket,
    openingOrderTicket: deal.orderTicket,
    additionalEntries: [],
    initialVolume: deal.volume,
    currentVolume: deal.volume,
    weightedPrice: deal.price,
    netProfit: finite(deal.profit + deal.commission + deal.swap + deal.fee),
    expertOpenViolation: expertReason(deal),
    openingReasonUnknown: !expertReason(deal) && !manualReason(deal),
    open: true,
    sltpEvidenceComplete: deal.sltpTimelineComplete,
    maxSltpDistancePips: 0,
    tradingMonthIndex: -1,
    serverUtcOffsetMinutes: deal.serverUtcOffsetMinutes,
  };
  observeSltp(episode, deal, meta.pipSize);
  return episode;
}

function addEntry(episode: Episode, deal: NeoTechConnectorDeal): void {
  const meta = canonicalSymbol(deal);
  const oldVolume = episode.currentVolume;
  const newVolume = oldVolume + deal.volume;
  const sameOrder = Boolean(deal.orderTicket) && deal.orderTicket === episode.openingOrderTicket;
  if (!sameOrder) episode.additionalEntries.push({ timeMsc: deal.timeMsc, orderTicket: deal.orderTicket, dealTicket: deal.ticket });
  if (newVolume > 0) episode.weightedPrice = (episode.weightedPrice * oldVolume + deal.price * deal.volume) / newVolume;
  episode.currentVolume = newVolume;
  episode.netProfit += finite(deal.profit + deal.commission + deal.swap + deal.fee);
  episode.sltpEvidenceComplete = episode.sltpEvidenceComplete && deal.sltpTimelineComplete;
  observeSltp(episode, deal, meta.pipSize);
}

function closeEpisode(episode: Episode, deal: NeoTechConnectorDeal): void {
  const meta = canonicalSymbol(deal);
  episode.netProfit += finite(deal.profit + deal.commission + deal.swap + deal.fee);
  episode.sltpEvidenceComplete = episode.sltpEvidenceComplete && deal.sltpTimelineComplete;
  observeSltp(episode, deal, meta.pipSize);
  episode.currentVolume = Math.max(0, episode.currentVolume - deal.volume);
  if (episode.currentVolume <= 0.00000001) {
    episode.currentVolume = 0;
    episode.open = false;
    episode.finalCloseMsc = deal.timeMsc;
  }
}

function normalizeEpisodes(deals: NeoTechConnectorDeal[]): Episode[] {
  const sorted = [...deals].sort((a, b) => a.timeMsc - b.timeMsc || a.ticket.localeCompare(b.ticket));
  const episodes: Episode[] = [];
  const findOpen = (deal: NeoTechConnectorDeal) => {
    const meta = canonicalSymbol(deal);
    for (let index = episodes.length - 1; index >= 0; index -= 1) {
      if (episodes[index].open && episodes[index].positionId === deal.positionId && episodes[index].canonicalSymbol === meta.symbol) return episodes[index];
    }
    return undefined;
  };
  for (const deal of sorted) {
    if (!deal.positionId || !deal.symbol) continue;
    const current = findOpen(deal);
    if (deal.entry === "IN") {
      if (current) addEntry(current, deal);
      else episodes.push(createEpisode(deal));
      continue;
    }
    if (deal.entry === "OUT" || deal.entry === "OUT_BY") {
      if (current) closeEpisode(current, deal);
      continue;
    }
    if (deal.entry === "INOUT") {
      let residual = deal.volume;
      if (current) {
        const oldVolume = current.currentVolume;
        residual = Math.max(0, deal.volume - oldVolume);
        closeEpisode(current, { ...deal, volume: Math.min(oldVolume, deal.volume) });
        current.currentVolume = 0;
        current.open = false;
        current.finalCloseMsc = deal.timeMsc;
      }
      if (residual > 0.00000001) episodes.push(createEpisode({ ...deal, volume: residual, profit: 0, commission: 0, swap: 0, fee: 0 }));
    }
  }
  return episodes;
}

function firstEpisodeStart(episodes: Episode[]): number {
  if (!episodes.length) return 0;
  return Math.floor(Math.min(...episodes.map((episode) => episode.firstEntryMsc)) / 1000);
}

function completedMonthCount(programStart: number, now: number): number {
  if (programStart <= 0 || now <= programStart) return 0;
  return Math.floor((now - programStart) / MONTH);
}

function qualificationComplete(programStart: number, now: number): boolean {
  return programStart > 0 && now - programStart >= 365 * DAY && completedMonthCount(programStart, now) >= 12;
}

function serverDayStart(utcSeconds: number, offsetMinutes: number): number {
  const shifted = new Date((utcSeconds + offsetMinutes * 60) * 1000);
  const localMidnightAsUtc = Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate()) / 1000;
  return localMidnightAsUtc - offsetMinutes * 60;
}

function weeklyCountingStart(firstEpisode: Episode): number {
  const seconds = Math.floor(firstEpisode.firstEntryMsc / 1000);
  const offset = firstEpisode.serverUtcOffsetMinutes;
  const shifted = new Date((seconds + offset * 60) * 1000);
  const day = shifted.getUTCDay();
  const dayStart = serverDayStart(seconds, offset);
  if (day === 1) return dayStart;
  const daysUntilMonday = (8 - day) % 7;
  return dayStart + daysUntilMonday * DAY;
}

function buildWeeks(episodes: Episode[], now: number): NeoTechPublicWeek[] {
  if (!episodes.length) return [];
  const sorted = [...episodes].sort((a, b) => a.firstEntryMsc - b.firstEntryMsc);
  const start = weeklyCountingStart(sorted[0]);
  if (now < start) return [];
  const total = Math.floor((now - start) / WEEK) + 1;
  const weeks = Array.from({ length: total }, (_, index): NeoTechPublicWeek => ({
    index,
    startUtc: start + index * WEEK,
    endUtc: start + (index + 1) * WEEK,
    signals: 0,
    target: 3,
    status: now >= start + (index + 1) * WEEK ? "FAIL" : "IN_PROGRESS",
  }));
  for (const episode of episodes) {
    const at = Math.floor(episode.firstEntryMsc / 1000);
    if (at < start) continue;
    const index = Math.floor((at - start) / WEEK);
    if (weeks[index]) weeks[index].signals += 1;
  }
  for (const row of weeks) {
    row.status = now < row.endUtc ? "IN_PROGRESS" : row.signals >= row.target ? "PASS" : "FAIL";
  }
  return weeks;
}

function reconstructOpeningBalance(payload: NeoTechPublicIngestPayload, episodes: Episode[], programStart: number): number {
  if (programStart <= 0) return payload.account.balance;
  let delta = 0;
  for (const episode of episodes) {
    if (!episode.open && episode.finalCloseMsc > 0 && Math.floor(episode.finalCloseMsc / 1000) >= programStart) delta += episode.netProfit;
  }
  for (const cash of payload.cashFlows) if (Math.floor(cash.timeMsc / 1000) >= programStart) delta += cash.amount;
  return Math.max(0.01, payload.account.balance - delta);
}

function cashFlowTotals(cashFlows: NeoTechConnectorCashFlow[], start: number, end: number): { deposits: number; withdrawals: number; other: number } {
  let deposits = 0;
  let withdrawals = 0;
  let other = 0;
  for (const flow of cashFlows) {
    const at = Math.floor(flow.timeMsc / 1000);
    if (at < start || at >= end) continue;
    if (flow.kind === "DEPOSIT") deposits += Math.max(0, flow.amount);
    else if (flow.kind === "WITHDRAWAL") withdrawals += Math.abs(Math.min(0, flow.amount) || flow.amount);
    else other += flow.amount;
  }
  return { deposits, withdrawals, other };
}

function buildMonths(payload: NeoTechPublicIngestPayload, episodes: Episode[], programStart: number, now: number): NeoTechPublicMonth[] {
  if (programStart <= 0) return [];
  const count = completedMonthCount(programStart, now) + 1;
  let balance = reconstructOpeningBalance(payload, episodes, programStart);
  const rows: NeoTechPublicMonth[] = [];
  for (let index = 0; index < count; index += 1) {
    const startUtc = programStart + index * MONTH;
    const endUtc = startUtc + MONTH;
    const tradingNetPL = episodes.reduce((sum, episode) => {
      if (episode.open || episode.finalCloseMsc <= 0) return sum;
      const close = Math.floor(episode.finalCloseMsc / 1000);
      return close >= startUtc && close < endUtc ? sum + episode.netProfit : sum;
    }, 0);
    const cash = cashFlowTotals(payload.cashFlows, startUtc, endUtc);
    const adjustedReturnPct = balance > 0 ? tradingNetPL / balance * 100 : 0;
    const status: NeoTechPublicStatus = now < endUtc ? "IN_PROGRESS" : adjustedReturnPct >= 1 ? "PASS" : "FAIL";
    rows.push({ index, startUtc, endUtc, openingBalance: balance, tradingNetPL, deposits: cash.deposits, withdrawals: cash.withdrawals, adjustedReturnPct, status });
    balance = balance + tradingNetPL + cash.deposits - cash.withdrawals + cash.other;
  }
  return rows;
}

function episodeHoldingSeconds(episode: Episode, nowMsc: number): number {
  const end = episode.open ? nowMsc : episode.finalCloseMsc;
  return Math.max(0, Math.floor((end - episode.firstEntryMsc) / 1000));
}

function c6EpisodeStatus(episode: Episode, nowMsc: number): NeoTechPublicStatus {
  const hold = episodeHoldingSeconds(episode, nowMsc);
  if (episode.open) return hold >= 15 * 60 ? "PASS" : "IN_PROGRESS";
  if (hold >= 15 * 60 || episode.maxSltpDistancePips > 30) return "PASS";
  return episode.sltpEvidenceComplete ? "FAIL" : "NOT_VERIFIABLE";
}

function c5Occurrences(episodes: Episode[], monthIndex = -1): number {
  let count = 0;
  for (let i = 0; i < episodes.length; i += 1) {
    const episode = episodes[i];
    if (monthIndex >= 0 && episode.tradingMonthIndex !== monthIndex) continue;
    let activeBefore = 0;
    for (let j = 0; j < episodes.length; j += 1) {
      if (i === j || episodes[j].canonicalSymbol !== episode.canonicalSymbol) continue;
      const earlier = episodes[j].firstEntryMsc < episode.firstEntryMsc || (episodes[j].firstEntryMsc === episode.firstEntryMsc && episodes[j].openingDealTicket.localeCompare(episode.openingDealTicket) < 0);
      const activeAt = episodes[j].firstEntryMsc <= episode.firstEntryMsc && (episodes[j].open || episodes[j].finalCloseMsc > episode.firstEntryMsc);
      if (earlier && activeAt) activeBefore += 1;
    }
    if (activeBefore > 0) count += 1;
    count += episode.additionalEntries.length;
  }
  return count;
}

function hedgingEvidence(episodes: Episode[], nowMsc: number): string[] {
  const evidence: string[] = [];
  for (let i = 0; i < episodes.length; i += 1) {
    for (let j = i + 1; j < episodes.length; j += 1) {
      const a = episodes[i];
      const b = episodes[j];
      if (a.canonicalSymbol !== b.canonicalSymbol || a.direction === b.direction || a.positionId === b.positionId) continue;
      const aEnd = a.open ? nowMsc : a.finalCloseMsc;
      const bEnd = b.open ? nowMsc : b.finalCloseMsc;
      if (a.firstEntryMsc < bEnd && b.firstEntryMsc < aEnd) evidence.push(`${a.canonicalSymbol}: position ${a.positionId} ↔ ${b.positionId}`);
    }
  }
  return evidence.slice(0, 8);
}

function coverage(payload: NeoTechPublicIngestPayload, now: number): { percent: number; days: number; fullYear: boolean; missing: string[] } {
  const earliest = payload.history.earliestDealUtc;
  const days = earliest ? Math.max(0, (Math.min(now, payload.history.requestedEndUtc) - earliest) / DAY) : 0;
  const percent = Math.min(100, Math.max(0, days / 365 * 100));
  const missing: string[] = [];
  if (!payload.history.complete) missing.push("Lịch sử deal/order chưa được terminal xác nhận đầy đủ");
  if (!payload.history.openingReasonComplete) missing.push("Thiếu evidence nguồn mở lệnh");
  if (!payload.history.productMetadataComplete) missing.push("Thiếu metadata phân loại symbol");
  if (!payload.history.sltpTimelineComplete) missing.push("Thiếu timeline SL/TP hoàn chỉnh");
  if (percent < 100) missing.push(`Mới quan sát ${days.toFixed(0)}/365 ngày`);
  return { percent, days, fullYear: payload.history.complete && percent >= 100, missing };
}

function fdd(payload: NeoTechPublicIngestPayload): NeoTechPublicProfile["fdd"] {
  const points = [...payload.equityPoints].sort((a, b) => a.atUtc - b.atUtc);
  if (!points.length) return { maxFloatingLossPct: null, maxPeakToTroughPct: null, observedAtUtc: null, status: "INSUFFICIENT_DATA", pointCount: 0 };
  let peakEquity = Math.max(0, points[0].equity);
  let maxFloating = 0;
  let maxDrawdown = 0;
  let observedAt = points[0].atUtc;
  for (const point of points) {
    peakEquity = Math.max(peakEquity, point.equity);
    const floating = point.balance > 0 ? Math.max(0, (point.balance - point.equity) / point.balance * 100) : 0;
    const drawdown = peakEquity > 0 ? Math.max(0, (peakEquity - point.equity) / peakEquity * 100) : 0;
    if (Math.max(floating, drawdown) >= Math.max(maxFloating, maxDrawdown)) observedAt = point.atUtc;
    maxFloating = Math.max(maxFloating, floating);
    maxDrawdown = Math.max(maxDrawdown, drawdown);
  }
  return { maxFloatingLossPct: maxFloating, maxPeakToTroughPct: maxDrawdown, observedAtUtc: observedAt, status: points.length >= 2 ? "PASS" : "INSUFFICIENT_DATA", pointCount: points.length };
}

function rule(code: NeoTechPublicRuleCode, group: NeoTechPublicRule["group"], title: string, summary: string, status: NeoTechPublicStatus, measured: string, threshold: string, evidence: string[] = []): NeoTechPublicRule {
  return { code, group, title, summary, status, score: ruleScore(status), measured, threshold, evidence: evidence.slice(0, 12) };
}

function buildRules(payload: NeoTechPublicIngestPayload, episodes: Episode[], months: NeoTechPublicMonth[], weeks: NeoTechPublicWeek[], programStart: number, now: number): NeoTechPublicRule[] {
  const horizon = qualificationComplete(programStart, now);
  const historyComplete = payload.history.complete;
  const nowMsc = now * 1000;

  const expert = episodes.filter((episode) => episode.expertOpenViolation);
  const reasonUnknown = episodes.filter((episode) => episode.openingReasonUnknown);
  const e1: NeoTechPublicStatus = expert.length ? "FAIL" : !episodes.length ? "IN_PROGRESS" : reasonUnknown.length ? "NOT_VERIFIABLE" : payload.history.openingReasonComplete ? "PASS" : "INSUFFICIENT_DATA";

  const e2: NeoTechPublicStatus = payload.account.mode === "REAL" || payload.account.mode === "DEMO" ? "PASS" : "FAIL";

  const unsupported = episodes.filter((episode) => episode.productReliable && !episode.productEligible);
  const unknownProduct = episodes.filter((episode) => !episode.productReliable);
  const e5: NeoTechPublicStatus = unsupported.length ? "FAIL" : !episodes.length ? "IN_PROGRESS" : unknownProduct.length || !payload.history.productMetadataComplete ? "INSUFFICIENT_DATA" : "PASS";

  const c1: NeoTechPublicStatus = programStart <= 0 ? "IN_PROGRESS" : !historyComplete ? "INSUFFICIENT_DATA" : horizon ? "PASS" : "IN_PROGRESS";
  const completedMonths = months.filter((month) => month.status !== "IN_PROGRESS");
  const c2: NeoTechPublicStatus = !historyComplete ? "INSUFFICIENT_DATA" : completedMonths.some((month) => month.status === "FAIL") ? "FAIL" : completedMonths.filter((month) => month.status === "PASS").length >= 12 ? "PASS" : "IN_PROGRESS";

  const completedWeeks = weeks.filter((week) => week.status !== "IN_PROGRESS");
  const c4: NeoTechPublicStatus = completedWeeks.some((week) => week.status === "FAIL") ? "FAIL" : !historyComplete ? "INSUFFICIENT_DATA" : !horizon ? "IN_PROGRESS" : "PASS";

  const c5Count = c5Occurrences(episodes);
  const c5: NeoTechPublicStatus = c5Count > 0 ? "FAIL" : !episodes.length ? "IN_PROGRESS" : !historyComplete ? "INSUFFICIENT_DATA" : horizon ? "PASS" : "IN_PROGRESS";

  const c6States = episodes.map((episode) => c6EpisodeStatus(episode, nowMsc));
  const c6: NeoTechPublicStatus = c6States.includes("FAIL") ? "FAIL" : !episodes.length ? "IN_PROGRESS" : c6States.includes("NOT_VERIFIABLE") ? "NOT_VERIFIABLE" : c6States.includes("IN_PROGRESS") || !horizon ? "IN_PROGRESS" : "PASS";

  const hedge = hedgingEvidence(episodes, nowMsc);
  const c7: NeoTechPublicStatus = hedge.length ? "FAIL" : !episodes.length ? "IN_PROGRESS" : !historyComplete ? "INSUFFICIENT_DATA" : horizon ? "PASS" : "IN_PROGRESS";

  const deposits = payload.cashFlows.filter((flow) => flow.kind === "DEPOSIT" || flow.kind === "WITHDRAWAL");
  const c9: NeoTechPublicStatus = deposits.length ? "FAIL" : !historyComplete ? "INSUFFICIENT_DATA" : horizon ? "PASS" : "IN_PROGRESS";

  return [
    rule("E1", "ELIGIBILITY", "Mở lệnh thủ công", "EA chỉ được quản lý sau khi lệnh đã được mở thủ công.", e1, expert.length ? `${expert.length} lệnh expert` : reasonUnknown.length ? `${reasonUnknown.length} lệnh chưa rõ nguồn` : `${episodes.length} episode`, "0 lệnh mở bởi EA", expert.slice(0, 6).map((item) => `${item.canonicalSymbol} · deal ${item.openingDealTicket}`)),
    rule("E2", "ELIGIBILITY", "Loại tài khoản", "Tài khoản phải ở chế độ Real hoặc Demo.", e2, payload.account.mode, "REAL hoặc DEMO"),
    rule("E3", "ELIGIBILITY", "Vốn ban đầu", "NeoTech không giới hạn vốn ban đầu.", "PASS", payload.account.balance.toFixed(2), "Không giới hạn"),
    rule("E5", "ELIGIBILITY", "Sản phẩm giao dịch", "Chỉ Forex và XAUUSD được xem là hợp lệ.", e5, unsupported.length ? `${unsupported.length} symbol không hợp lệ` : `${episodes.length} episode`, "Forex / XAUUSD", unsupported.slice(0, 8).map((item) => item.brokerSymbol)),
    rule("C1", "CONSISTENCY", "Thời gian theo dõi", "Cần đủ 365 ngày và ít nhất 12 cửa sổ 30 ngày.", c1, programStart > 0 ? `${Math.max(0, Math.floor((now - programStart) / DAY))} ngày · ${completedMonthCount(programStart, now)} tháng` : "Chưa có giao dịch", "≥365 ngày và ≥12 tháng"),
    rule("C2", "CONSISTENCY", "Return mỗi tháng", "Mỗi cửa sổ 30 ngày hoàn tất phải đạt tối thiểu 1% trading return.", c2, `${completedMonths.filter((month) => month.status === "PASS").length}/${completedMonths.length || 0} tháng đạt`, "≥1% / 30 ngày", completedMonths.filter((month) => month.status === "FAIL").slice(-6).map((month) => `Tháng ${month.index + 1}: ${month.adjustedReturnPct.toFixed(2)}%`)),
    rule("C4", "CONSISTENCY", "Tần suất tín hiệu", "Mỗi tuần hoàn tất cần tối thiểu 3 tín hiệu.", c4, `${completedWeeks.filter((week) => week.status === "PASS").length}/${completedWeeks.length || 0} tuần đạt`, "≥3 tín hiệu / tuần", completedWeeks.filter((week) => week.status === "FAIL").slice(-6).map((week) => `Tuần ${week.index + 1}: ${week.signals}/3`)),
    rule("C5", "CONSISTENCY", "Một lệnh mỗi symbol", "Mở thêm lệnh cùng symbol khi vị thế trước còn hoạt động là vi phạm.", c5, `${c5Count} occurrence`, "0 occurrence"),
    rule("C6", "CONSISTENCY", "Giữ lệnh hoặc SL/TP", "Lệnh đóng dưới 15 phút phải từng có SL hoặc TP cách entry hơn 30 pip.", c6, `${c6States.filter((status) => status === "FAIL").length} vi phạm`, "≥15 phút hoặc >30 pip"),
    rule("C7", "CONSISTENCY", "Không hedging", "Không được BUY và SELL đồng thời trên cùng symbol.", c7, hedge.length ? `${hedge.length} overlap` : "0 overlap", "0 overlap", hedge),
    rule("C8", "CONSISTENCY", "Không copy tín hiệu", "Nguồn tín hiệu bên ngoài không thể chứng minh chỉ bằng dữ liệu MT5.", "NOT_VERIFIABLE", "Không có telemetry nguồn tín hiệu", "Xác minh ngoài MT5"),
    rule("C9", "CONSISTENCY", "Không nạp/rút", "Nạp hoặc rút tiền trong giai đoạn đánh giá là vi phạm.", c9, `${deposits.length} cash-flow`, "0 deposit/withdrawal", deposits.slice(0, 8).map((flow) => `${flow.kind} · ${flow.amount.toFixed(2)}`)),
  ];
}

export function buildNeoTechPublicProfile(args: { accountId: string; lastSeenAt: number; payload: NeoTechPublicIngestPayload }): NeoTechPublicProfile {
  const { payload } = args;
  const now = payload.collectedAtUtc;
  const episodes = normalizeEpisodes(payload.deals);
  const programStart = firstEpisodeStart(episodes);
  for (const episode of episodes) episode.tradingMonthIndex = programStart > 0 ? Math.floor((Math.floor(episode.firstEntryMsc / 1000) - programStart) / MONTH) : -1;
  const months = buildMonths(payload, episodes, programStart, now);
  const weeks = buildWeeks(episodes, now);
  const rules = buildRules(payload, episodes, months, weeks, programStart, now);
  const cov = coverage(payload, now);
  const counts = {
    pass: rules.filter((row) => row.status === "PASS").length,
    fail: rules.filter((row) => row.status === "FAIL").length,
    inProgress: rules.filter((row) => row.status === "IN_PROGRESS").length,
    insufficient: rules.filter((row) => row.status === "INSUFFICIENT_DATA").length,
    notVerifiable: rules.filter((row) => row.status === "NOT_VERIFIABLE").length,
  };
  const decisionRules = rules.filter((row) => row.code !== "C8");
  const overall = decisionRules.some((row) => row.status === "FAIL")
    ? "VIOLATION"
    : decisionRules.some((row) => row.status === "INSUFFICIENT_DATA" || row.status === "NOT_VERIFIABLE")
      ? "INSUFFICIENT_DATA"
      : decisionRules.some((row) => row.status === "IN_PROGRESS")
        ? "TRACKING"
        : "CLEAR";
  const currentMonth = programStart > 0 ? Math.max(0, Math.floor((now - programStart) / MONTH)) : -1;
  const c5CurrentMonth = currentMonth >= 0 ? c5Occurrences(episodes, currentMonth) : 0;
  const c6CurrentMonth = currentMonth >= 0 ? episodes.filter((episode) => episode.tradingMonthIndex === currentMonth && c6EpisodeStatus(episode, now * 1000) === "FAIL").length : 0;
  const c6Rule = rules.find((row) => row.code === "C6");
  const countersComplete = payload.history.complete && c6Rule?.status !== "NOT_VERIFIABLE" && c6Rule?.status !== "INSUFFICIENT_DATA";
  const disqualificationRisk = c5CurrentMonth >= 3 || c6CurrentMonth >= 3 || c5CurrentMonth + c6CurrentMonth >= 3 ? "YES" : countersComplete ? "NO" : "UNKNOWN";

  return {
    schemaVersion: "oak-neotech-visual-profile-v1",
    ruleset: NEOTECH_PUBLIC_RULESET,
    generatedAtUtc: now,
    overall,
    account: {
      id: args.accountId,
      maskedLogin: maskedLogin(payload.account.login),
      broker: payload.account.broker,
      server: payload.account.server,
      currency: payload.account.currency,
      mode: payload.account.mode,
      readOnlyVerified: payload.account.tradeAllowed === false,
      connectorVersion: payload.connectorVersion,
      lastSeenAt: args.lastSeenAt,
    },
    coverage: { percent: cov.percent, historyDays: cov.days, fullYear: cov.fullYear, missingReasons: cov.missing },
    counts,
    risk: { c5CurrentMonth, c6CurrentMonth, combinedCurrentMonth: c5CurrentMonth + c6CurrentMonth, disqualificationRisk },
    fdd: fdd(payload),
    months,
    weeks,
    rules,
  };
}

export function profileAccountFingerprint(payload: NeoTechPublicIngestPayload): string {
  return accountFingerprint(payload.account);
}
