/**
 * Dictionary mapping Vietnam Stock Tickers to full Company Names & Market Cap across HOSE, HNX, UPCoM.
 */
export const COMPANY_NAMES: Record<string, { name: string; exchange: string; cap: string; industry?: string; description?: string }> = {
  // HOSE VN30 & Midcaps
  ACB: { name: "Ngân hàng Á Châu", exchange: "HOSE", cap: "98.500 tỷ" },
  BCM: { name: "Tổng Công ty Becamex IDC", exchange: "HOSE", cap: "67.800 tỷ" },
  BID: { name: "Ngân hàng BIDV", exchange: "HOSE", cap: "282.000 tỷ", industry: "Ngân hàng", description: "Ngân hàng Thương mại cổ phần Đầu tư và Phát triển Việt Nam (BIDV), ngân hàng thương mại lớn thứ 2 Việt Nam theo tổng tài sản, cung cấp dịch vụ ngân hàng, bảo hiểm và đầu tư tài chính." },
  BVH: { name: "Tập đoàn Bảo Việt", exchange: "HOSE", cap: "30.600 tỷ" },
  CTG: { name: "Ngân hàng VietinBank", exchange: "HOSE", cap: "189.000 tỷ", industry: "Ngân hàng", description: "Ngân hàng Thương mại cổ phần Công thương Việt Nam (VietinBank), một trong 4 ngân hàng thương mại quốc doanh lớn nhất Việt Nam, cung cấp dịch vụ tài chính toàn diện." },
  FPT: { name: "Tập đoàn FPT", exchange: "HOSE", cap: "188.500 tỷ", industry: "Công nghệ thông tin", description: "Tập đoàn FPT là công ty công nghệ lớn nhất Việt Nam, hoạt động trong phần mềm, dịch vụ IT, viễn thông, giáo dục và bán lẻ kỹ thuật số. Là đơn vị số 1 về gia công phần mềm tại Việt Nam." },
  GAS: { name: "Tổng Công ty Khí Việt Nam (PV GAS)", exchange: "HOSE", cap: "179.000 tỷ" },
  GVR: { name: "Tập đoàn CN Cao su Việt Nam", exchange: "HOSE", cap: "137.000 tỷ" },
  HDB: { name: "Ngân hàng HDBank", exchange: "HOSE", cap: "69.500 tỷ" },
  HPG: { name: "Tập đoàn Hòa Phát", exchange: "HOSE", cap: "167.000 tỷ", industry: "Sản xuất thép", description: "Tập đoàn công nghiệp – sản xuất thép lớn nhất Việt Nam, hoạt động trong sản xuất thép xây dựng, thép cuộn cán nóng, ống thép và sản xuất nội thất. Trụ sở tại Hà Nội, nhà máy chính tại Dung Quất (Quảng Ngãi)." },
  MBB: { name: "Ngân hàng Quân Đội (MB)", exchange: "HOSE", cap: "128.000 tỷ" },
  MSN: { name: "Tập đoàn Masan", exchange: "HOSE", cap: "108.000 tỷ", industry: "Hàng tiêu dùng", description: "Tập đoàn Masan là một trong những nhóm công ty hàng tiêu dùng lớn nhất Việt Nam, sở hữu Masan Consumer (nêm, nước mắm), Masan Meat (thịt tươi) và VinCommerce (bán lẻ)." },
  MWG: { name: "Công ty CP Thế Giới Di Động", exchange: "HOSE", cap: "91.500 tỷ", industry: "Bán lẻ", description: "Công ty CP Thế Giới Di Động (Mobile World Group) — chuỗi bán lẻ thiết bị di động & điện máy lớn nhất Việt Nam với thương hiệu Thế Giới Di Động, Điện Máy Xanh và Bach Hoa Xanh." },
  PLX: { name: "Tập đoàn Xăng dầu Việt Nam (Petrolimex)", exchange: "HOSE", cap: "49.500 tỷ" },
  POW: { name: "Tổng Công ty Điện lực Dầu khí Việt Nam", exchange: "HOSE", cap: "29.400 tỷ" },
  SAB: { name: "Tổng Công ty Sabeco", exchange: "HOSE", cap: "74.900 tỷ" },
  SHB: { name: "Ngân hàng SHB", exchange: "HOSE", cap: "42.300 tỷ" },
  SSB: { name: "Ngân hàng SeABank", exchange: "HOSE", cap: "63.200 tỷ" },
  SSI: { name: "Công ty CP Chứng khoán SSI", exchange: "HOSE", cap: "54.800 tỷ", industry: "Chứng khoán", description: "Công ty CP Chứng khoán SSI (Saigon Securities Incorporation) — công ty chứng khoán lớn nhất Việt Nam theo vốn hóa thị trường, cung cấp dịch vụ môi giới, tự doanh và tư vấn đầu tư tài chính." },
  STB: { name: "Ngân hàng Sacombank", exchange: "HOSE", cap: "58.900 tỷ" },
  TCB: { name: "Ngân hàng Techcombank", exchange: "HOSE", cap: "170.000 tỷ", industry: "Ngân hàng", description: "Ngân hàng TMCP Kỹ thương Việt Nam (Techcombank) — ngân hàng tư nhân hàng đầu Việt Nam về công nghệ và trải nghiệm khách hàng, nổi tiếng với ứng dụng ngân hàng số TCB." },
  TPB: { name: "Ngân hàng TPBank", exchange: "HOSE", cap: "41.000 tỷ" },
  VCB: { name: "Ngân hàng Vietcombank", exchange: "HOSE", cap: "518.000 tỷ", industry: "Ngân hàng", description: "Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank) — ngân hàng thương mại lớn nhất Việt Nam theo vốn hóa thị trường, có mạng lưới quốc tế rộng nhất, cung cấp dịch vụ ngân hàng toàn diện." },
  VHM: { name: "Công ty CP Vinhomes", exchange: "HOSE", cap: "184.000 tỷ" },
  VIB: { name: "Ngân hàng VIB", exchange: "HOSE", cap: "59.600 tỷ" },
  VIC: { name: "Tập đoàn Vingroup", exchange: "HOSE", cap: "173.000 tỷ" },
  VJC: { name: "Công ty CP Hàng không Vietjet", exchange: "HOSE", cap: "57.300 tỷ" },
  VNM: { name: "Công ty CP Sữa Việt Nam (Vinamilk)", exchange: "HOSE", cap: "143.000 tỷ", industry: "Sản xuất thực phẩm", description: "Công ty CP Sữa Việt Nam (Vinamilk) — doanh nghiệp sữa lớn nhất Việt Nam, sản xuất và phân phối sữa tươi, sữa công thức, sữa chua và các sản phẩm dinh dưỡng, chiếm hơn 50% thị phần nội địa." },
  VPB: { name: "Ngân hàng VPBank", exchange: "HOSE", cap: "155.000 tỷ" },
  VRE: { name: "Công ty CP Vincom Retail", exchange: "HOSE", cap: "51.400 tỷ" },
  DGC: { name: "Tập đoàn Hóa chất Đức Giang", exchange: "HOSE", cap: "43.700 tỷ" },
  DCM: { name: "Phân bón Dầu khí Cà Mau", exchange: "HOSE", cap: "18.500 tỷ" },
  DPM: { name: "Tổng Công ty Phân bón & Hóa chất Dầu khí", exchange: "HOSE", cap: "13.400 tỷ" },
  DIG: { name: "Tổng Công ty DIC Corp", exchange: "HOSE", cap: "15.900 tỷ" },
  DXG: { name: "Tập đoàn Đất Xanh", exchange: "HOSE", cap: "11.800 tỷ" },
  FRT: { name: "Công ty CP Bán lẻ Kỹ thuật số FPT", exchange: "HOSE", cap: "24.800 tỷ" },
  GEX: { name: "Tập đoàn GELEX", exchange: "HOSE", cap: "18.700 tỷ" },
  HCM: { name: "Chứng khoán TP.HCM (HSC)", exchange: "HOSE", cap: "15.200 tỷ" },
  KBC: { name: "Tổng Công ty Phát triển Đô thị Kinh Bắc", exchange: "HOSE", cap: "23.200 tỷ" },
  KDH: { name: "Công ty CP Đầu tư & KD Nhà Khang Điền", exchange: "HOSE", cap: "29.800 tỷ" },
  LPB: { name: "Ngân hàng Lộc Phát Việt Nam (LPBank)", exchange: "HOSE", cap: "78.400 tỷ" },
  NLG: { name: "Công ty CP Đầu tư Nam Long", exchange: "HOSE", cap: "16.100 tỷ" },
  NVL: { name: "Tập đoàn Đầu tư Địa ốc No Va (Novaland)", exchange: "HOSE", cap: "24.500 tỷ" },
  PC1: { name: "Tập đoàn PC1", exchange: "HOSE", cap: "8.900 tỷ" },
  PDR: { name: "Công ty CP Phát triển BĐS Phát Đạt", exchange: "HOSE", cap: "19.200 tỷ" },
  PNJ: { name: "Công ty CP Vàng bạc Đá quý Phú Nhuận", exchange: "HOSE", cap: "32.600 tỷ" },
  PVD: { name: "Tổng Công ty Khoan Dầu khí (PV Drilling)", exchange: "HOSE", cap: "15.600 tỷ" },
  PVT: { name: "Tổng Công ty Vận tải Dầu khí (PVTrans)", exchange: "HOSE", cap: "9.800 tỷ" },
  REE: { name: "Công ty CP Cơ Điện Lạnh", exchange: "HOSE", cap: "28.300 tỷ" },
  SBT: { name: "Công ty CP Thành Thành Công - Biên Hòa", exchange: "HOSE", cap: "9.400 tỷ" },
  VCI: { name: "Công ty CP Chứng khoán Vietcap", exchange: "HOSE", cap: "21.600 tỷ" },
  VCS: { name: "Công ty CP Vicostone", exchange: "HOSE", cap: "9.800 tỷ" },
  VGC: { name: "Tổng Công ty Viglacera", exchange: "HOSE", cap: "23.800 tỷ" },
  VHC: { name: "Công ty CP Vĩnh Hoàn", exchange: "HOSE", cap: "16.200 tỷ" },
  VND: { name: "Công ty CP Chứng khoán VNDIRECT", exchange: "HOSE", cap: "19.500 tỷ" },
  VIX: { name: "Công ty CP Chứng khoán VIX", exchange: "HOSE", cap: "16.800 tỷ" },
  EIB: { name: "Ngân hàng Eximbank", exchange: "HOSE", cap: "32.500 tỷ" },
  EVF: { name: "Công ty CP Tài chính Điện lực", exchange: "HOSE", cap: "8.900 tỷ" },
  ORS: { name: "Công ty CP Chứng khoán Tiên Phong", exchange: "HOSE", cap: "4.800 tỷ" },
  CTS: { name: "Công ty CP Chứng khoán VietinBank", exchange: "HOSE", cap: "5.400 tỷ" },
  FTS: { name: "Công ty CP Chứng khoán FPT", exchange: "HOSE", cap: "14.200 tỷ" },
  AGR: { name: "Công ty CP Chứng khoán Agribank", exchange: "HOSE", cap: "3.800 tỷ" },
  VCG: { name: "Tổng Công ty Vinaconex", exchange: "HOSE", cap: "12.500 tỷ" },
  TCH: { name: "Công ty CP Đầu tư Dịch vụ Tài chính Hoàng Huy", exchange: "HOSE", cap: "11.600 tỷ" },
  GMD: { name: "Công ty CP Gemadept", exchange: "HOSE", cap: "24.900 tỷ" },
  HAH: { name: "Công ty CP Vận tải & Cảng biển Hải An", exchange: "HOSE", cap: "5.800 tỷ" },
  HAG: { name: "Công ty CP Hoàng Anh Gia Lai", exchange: "HOSE", cap: "13.200 tỷ" },
  HNG: { name: "Công ty CP Nông nghiệp Quốc tế HAGL", exchange: "HOSE", cap: "4.900 tỷ" },
  VSC: { name: "Công ty CP Container Việt Nam (Viconship)", exchange: "HOSE", cap: "6.200 tỷ" },
  ANV: { name: "Công ty CP Nam Việt (Navico)", exchange: "HOSE", cap: "4.300 tỷ" },
  IDI: { name: "Công ty CP Đầu tư & Phát triển Đa Quốc Gia", exchange: "HOSE", cap: "2.900 tỷ" },
  FMC: { name: "Công ty CP Thực phẩm Sao Ta", exchange: "HOSE", cap: "3.400 tỷ" },
  PAN: { name: "Tập đoàn PAN", exchange: "HOSE", cap: "4.800 tỷ" },
  TMS: { name: "CTCP Transimex", exchange: "HOSE", cap: "6.360 tỷ", industry: "Vận tải logistics", description: "Công ty CP Vận tải và Thương mại Transimex — doanh nghiệp logistics lâu đời tại Việt Nam, hoạt động trong vận tải quốc tế, kho bãi, hải quan và dịch vụ chuỗi cung ứng toàn diện." },

  // HNX
  BSI: { name: "Công ty CP Chứng khoán BIDC (BSC)", exchange: "HNX", cap: "7.400 tỷ" },
  CEO: { name: "Tập đoàn C.E.O", exchange: "HNX", cap: "8.900 tỷ" },
  IDC: { name: "Tổng Công ty IDICO", exchange: "HNX", cap: "19.800 tỷ" },
  MBS: { name: "Công ty CP Chứng khoán MB", exchange: "HNX", cap: "14.600 tỷ" },
  NTP: { name: "Công ty CP Nhựa Thiếu niên Tiền Phong", exchange: "HNX", cap: "7.600 tỷ" },
  PVC: { name: "Tổng Công ty Hóa chất & Dịch vụ Dầu khí", exchange: "HNX", cap: "1.620 tỷ" },
  PVS: { name: "Tổng Công ty Dịch vụ Kỹ thuật Dầu khí", exchange: "HNX", cap: "19.500 tỷ" },
  SHS: { name: "Công ty CP Chứng khoán Sài Gòn - Hà Nội", exchange: "HNX", cap: "14.200 tỷ" },
  TNG: { name: "Công ty CP Đầu tư & Thương mại TNG", exchange: "HNX", cap: "3.200 tỷ" },
  VGS: { name: "Công ty CP Thép Việt Đức", exchange: "HNX", cap: "2.850 tỷ" },
  HUT: { name: "Công ty CP Tasco", exchange: "HNX", cap: "15.400 tỷ" },

  // UPCoM
  ACV: { name: "Tổng Công ty Cảng Hàng không Việt Nam", exchange: "UPCOM", cap: "248.000 tỷ" },
  BSR: { name: "Công ty CP Lọc hóa dầu Bình Sơn", exchange: "UPCOM", cap: "74.500 tỷ" },
  C4G: { name: "Tập đoàn CIENCO4", exchange: "UPCOM", cap: "3.400 tỷ" },
  DDV: { name: "Công ty CP DAP - VINACHEM", exchange: "UPCOM", cap: "2.900 tỷ" },
  MCH: { name: "Công ty CP Hàng tiêu dùng Masan", exchange: "UPCOM", cap: "148.000 tỷ" },
  MSR: { name: "Công ty CP Masan High-Tech Materials", exchange: "UPCOM", cap: "18.900 tỷ" },
  OIL: { name: "Tổng Công ty Dầu Việt Nam (PVOIL)", exchange: "UPCOM", cap: "12.800 tỷ" },
  QNS: { name: "Công ty CP Đường Quảng Ngãi", exchange: "UPCOM", cap: "17.400 tỷ" },
  VEA: { name: "Tổng Công ty Máy động lực & Máy nông nghiệp", exchange: "UPCOM", cap: "58.600 tỷ" },
  VGT: { name: "Tập đoàn Dệt May Việt Nam (Vinatex)", exchange: "UPCOM", cap: "6.800 tỷ" },
};

export function getCompanyName(symbol: string): string {
  const sym = (symbol || "").toUpperCase().trim();
  if (!sym) return "";
  return COMPANY_NAMES[sym]?.name || `Công ty CP ${sym}`;
}

export function getMarketCap(symbol: string, locale: "VN" | "EN" = "VN"): string {
  const sym = (symbol || "").toUpperCase().trim();
  if (!sym) return locale === "EN" ? "≥ 100B VND" : "≥ 100 tỷ";
  const rawCap = COMPANY_NAMES[sym]?.cap || "≥ 500 tỷ";
  if (locale === "EN") {
    return rawCap.replace("tỷ", "B VND");
  }
  return rawCap;
}

export function getExchange(symbol: string): string {
  const sym = (symbol || "").toUpperCase().trim();
  if (!sym) return "HOSE";
  const rawEx = COMPANY_NAMES[sym]?.exchange || "HOSE";
  return rawEx === "UPCOM" ? "UPCoM" : rawEx;
}

export function getIndustry(symbol: string): string {
  const sym = (symbol || "").toUpperCase().trim();
  if (!sym) return "";
  return COMPANY_NAMES[sym]?.industry || "";
}

export function getDescription(symbol: string): string {
  const sym = (symbol || "").toUpperCase().trim();
  if (!sym) return "";
  return COMPANY_NAMES[sym]?.description || "";
}
