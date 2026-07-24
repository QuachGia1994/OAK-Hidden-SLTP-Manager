"""VPS TradingView Public Market Data Source — HOSE, HNX, UPCoM.

Fetches real daily OHLCV data from the public VPS TradingView history endpoint.
No API key required. Covers all three Vietnamese stock exchanges.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from eod_collector.sources.base import EODDataSource, RawFetchResult
from eod_collector.sources.http_client import fetch_url

logger = logging.getLogger("eod_collector")

# VPS TradingView public endpoint — works for HOSE, HNX, UPCoM symbols
_VPS_BASE_URL = "https://histdatafeed.vps.com.vn/tradingview/history"

# HOSE Constituents & Mid/Small/Large-caps (220+ symbols)
HOSE_SYMBOLS = [
    "AAA", "AAM", "ABR", "ABS", "ABT", "ACB", "ACC", "ACG", "ACL", "ADG",
    "ADP", "ADS", "AGG", "AGM", "AGR", "ANV", "APC", "APG", "APH", "ASG",
    "ASM", "ASP", "AST", "BAF", "BCE", "BCG", "BCM", "BFC", "BHN", "BIC",
    "BID", "BKG", "BMC", "BMI", "BMP", "BRC", "BSI", "BTP", "BWE", "C32",
    "C47", "CII", "CKG", "CLC", "CLL", "CLW", "CMG", "CMX", "CNG", "COM",
    "CRC", "CRE", "CSM", "CSV", "CTD", "CTF", "CTG", "CTI", "CTR", "CTS",
    "D2D", "DAG", "DAH", "DAT", "DBC", "DBD", "DCM", "DGC", "DGW", "DHA",
    "DHC", "DHG", "DHM", "DIG", "DLG", "DMC", "DPG", "DPM", "DPR", "DRC",
    "DRH", "DRL", "DSN", "DTA", "DTL", "DTD", "DVP", "DXG", "DXS", "EIB",
    "ELC", "EVE", "EVG", "EVF", "FMC", "FPT", "FRT", "FTS", "GAS", "GDA",
    "GDT", "GEG", "GEX", "GIL", "GMC", "GMD", "GVR", "HAG", "HAH", "HAP",
    "HAR", "HAS", "HAX", "HCD", "HCM", "HDB", "HDC", "HDG", "HHP", "HII",
    "HMC", "HNG", "HOM", "HPG", "HQC", "HRC", "HSG", "HSL", "HT1", "HTG",
    "HTI", "HTN", "HTV", "HU1", "HUB", "IJC", "ILB", "IMP", "ITA", "ITC",
    "ITD", "JVC", "KBC", "KDC", "KDH", "KHG", "KHP", "KSB", "LAF", "LCG",
    "LDG", "LEC", "LGC", "LGL", "LIX", "LPB", "MBB", "MIG", "MSB", "MSN",
    "MWG", "NAF", "NBB", "NCT", "NHA", "NHH", "NLG", "NKG", "NLC", "NT2",
    "NTP", "NVL", "OCB", "OGC", "OPC", "ORS", "PAC", "PAN", "PC1", "PDN",
    "PDR", "PET", "PGC", "PGD", "PGI", "PGV", "PHC", "PHR", "PLC", "PLX",
    "PNJ", "POM", "POW", "PPC", "PTB", "PTC", "PTI", "PTL", "PVD", "PVT",
    "PVP", "QCG", "RAL", "REE", "RDP", "SAB", "SAM", "SAV", "SBT", "SC5",
    "SCR", "SCS", "SFC", "SFG", "SGN", "SGR", "SHA", "SHB", "SHP", "SHI",
    "SII", "SJD", "SJF", "SJS", "SKG", "SMB", "SMC", "SPM", "SRC", "SSC",
    "SSI", "STB", "STG", "STK", "SVC", "SVD", "SVT", "SZC", "SZL", "TBC",
    "TCB", "TCH", "TCL", "TCM", "TCO", "TCR", "TDC", "TDH", "TDM", "TDW",
    "TEG", "THG", "TIP", "TIX", "TLD", "TLH", "TMP", "TMS", "TNA", "TNC",
    "TNG", "TNT", "TPC", "TPB", "TRA", "TRC", "TSC", "TTA", "TTH", "TTF",
    "TVB", "TVS", "TVT", "UIC", "VAF", "VCB", "VCF", "VCG", "VCI", "VCS",
    "VDS", "VGC", "VGS", "VHC", "VHM", "VIB", "VIC", "VIP", "VIX", "VJC",
    "VMD", "VND", "VNE", "VNG", "VNL", "VNM", "VNS", "VPB", "VPG", "VPH",
    "VPI", "VPS", "VRC", "VRE", "VSC", "VSI", "VTB", "VTO", "YEG",
]

# HNX Constituents & Mid/Small-caps (100+ symbols)
HNX_SYMBOLS = [
    "AAV", "AMC", "AMV", "API", "APS", "AST", "BBS", "BCF", "BCL", "BCO",
    "BDB", "BKC", "BLF", "BSC", "BSI", "BTS", "BVS", "C69", "CAG", "CAN",
    "CAP", "CEO", "CMS", "CSC", "CSM", "CTS", "CTS", "DAE", "DAM", "DAR",
    "DNC", "DNM", "DP3", "DSD", "DTC", "DTD", "DXP", "EBS", "ECI", "GIC",
    "HAD", "HAT", "HBS", "HCC", "HCT", "HDA", "HEV", "HGM", "HHG", "HLD",
    "HMH", "HND", "HNM", "HOM", "HQB", "HTC", "HTP", "HUT", "HVT", "IDC",
    "IDJ", "ILS", "INA", "ITQ", "IVS", "KB6", "KDM", "KHB", "KMT", "KSQ",
    "KTS", "L14", "L18", "L40", "LAS", "LBC", "LHC", "MAC", "MAS", "MBG",
    "MBS", "MCF", "MCO", "MHL", "MEL", "MNC", "MSC", "MST", "NDN", "NET",
    "NFC", "NRC", "NSS", "NTP", "PAN", "PCF", "PCT", "PDC", "PDS", "PGN",
    "PGS", "PGT", "PHC", "PLC", "PMB", "PMC", "PMT", "PMP", "PPY", "PRE",
    "PSA", "PSC", "PTE", "PTS", "PV2", "PVB", "PVC", "PVI", "PVS", "QTC",
    "RCL", "S55", "S74", "S99", "SAF", "SAT", "SBL", "SCC", "SCO", "SD5",
    "SD6", "SD9", "SEB", "SED", "SFN", "SGD", "SGH", "SHS", "SJ1", "SLS",
    "SMT", "SPI", "SQC", "STC", "STP", "SVN", "SZB", "TA9", "THD", "THG",
    "TIG", "TJN", "TMB", "TMC", "TMG", "TNG", "TOC", "TSB", "TTC", "TVC",
    "TVD", "TXM", "VBC", "VC2", "VC3", "VC7", "VCH", "VCM", "VCS", "VDL",
    "VE1", "VE3", "VFF", "VFR", "VGS", "VHL", "VIC", "VIG", "VIH", "VIU",
    "VMC", "VMI", "VNC", "VND", "VNR", "VNT", "VSA", "VSM", "VTC", "VTH",
    "VTL", "VTJ", "VTM", "VTV", "WCS", "WSS",
]

# UPCoM Constituents & Mid/Large/Small-caps (100+ symbols)
UPCOM_SYMBOLS = [
    "ABB", "ABI", "ACV", "AFX", "AGF", "AMP", "AMS", "APF", "APT", "ART",
    "AAS", "BBS", "BCA", "BCR", "BDB", "BDG", "BHP", "BIW", "BKH", "BLN",
    "BMS", "BNA", "BNW", "BPW", "BRG", "BSA", "BSR", "BTD", "BTH", "BTP",
    "BTT", "BTV", "BVB", "BVN", "C4G", "CAD", "CBP", "CCA", "CCC", "CCL",
    "CCM", "CEN", "CFV", "CID", "CIP", "CLX", "CMC", "CMF", "CNA", "CNN",
    "CPC", "CPI", "CPL", "CPR", "CTA", "CTR", "DDB", "DDH", "DDM", "DDV",
    "DFF", "DGB", "DHD", "DHI", "DHL", "DHN", "DKC", "DL1", "DLD", "DNC",
    "DND", "DNE", "DNH", "DNW", "DOC", "DPC", "DPO", "DPS", "DRG", "DSE",
    "DSP", "DST", "DTA", "DTC", "DTD", "DTK", "DVM", "DVT", "DXD", "EIC",
    "EIV", "FCS", "FHH", "FIC", "FOC", "FOX", "FSO", "G20", "GCM", "GCS",
    "GDT", "GFC", "GGC", "GHC", "GIH", "GLW", "GMX", "GPB", "GTT", "HAP",
    "HAS", "HBC", "HBD", "HBE", "HBH", "HCI", "HCL", "HCM", "HCS", "HD2",
    "HDA", "HDF", "HDM", "HDP", "HEC", "HES", "HFA", "HFC", "HFL", "HFN",
    "HFX", "HGH", "HGS", "HGT", "HHG", "HHN", "HHV", "HIC", "HID", "HIF",
    "HIG", "HIS", "HIT", "HJC", "HJE", "HJS", "HKB", "HKS", "HLB", "HLC",
    "HLD", "HLO", "HLT", "HLY", "HMC", "HMH", "HMI", "HNB", "HND", "HNG",
    "HNM", "HNP", "HNR", "HNT", "HOB", "HPA", "HPB", "HPD", "HPG", "HPI",
    "HPM", "HPN", "HPO", "HPP", "HPS", "HPT", "HPW", "HQB", "HRA", "HRC",
    "HRT", "HSA", "HSB", "HSC", "HSI", "HSL", "HSM", "HSN", "HSP", "HST",
    "HTC", "HTE", "HTG", "HTH", "HTI", "HTL", "HTM", "HTP", "HTR", "HTT",
    "HTV", "HTW", "HUD", "HUE", "HUG", "HUN", "HUR", "HUT", "HVA", "HVC",
    "HVD", "HVG", "HVH", "HVM", "HVN", "HVT", "ICF", "ICH", "IDA", "IDC",
    "IDP", "IFS", "ILS", "INA", "IN4", "ISG", "IST", "ITC", "ITD", "ITP",
    "IVS", "KAC", "KBC", "KBL", "KCB", "KCE", "KCM", "KCP", "KCS", "KDF",
    "KDH", "KDJ", "KDN", "KHL", "KHM", "KHW", "KIA", "KIP", "KLD", "KLB",
    "KMC", "KMR", "KMT", "KSE", "KSQ", "KSS", "KST", "KTC", "KTS", "KTT",
    "L14", "L18", "L35", "L45", "L61", "L62", "LAF", "LAN", "LAT", "LBC",
    "LBH", "LCM", "LCS", "LDC", "LDG", "LDP", "LFC", "LGC", "LGH", "LGL",
    "LGM", "LGS", "LHC", "LHD", "LHG", "LID", "LO5", "LOW", "LPC", "LPB",
    "LPE", "LPG", "LPH", "LPM", "LPT", "LSG", "LSS", "LTC", "LTG", "LTS",
    "MAC", "MCH", "MCF", "MCL", "MCM", "MCO", "MCP", "MCS", "MDF", "MEC",
    "MED", "MEF", "MEL", "MGG", "MGH", "MGL", "MHL", "MIC", "MIG", "MIM",
    "MKV", "MLC", "MLM", "MNC", "MNB", "MPC", "MSR", "MST", "MTA", "MTB",
    "MTG", "MTH", "MTL", "MTP", "MTS", "MTU", "MTV", "MVB", "MVC", "MVD",
    "MVN", "MWS", "NAB", "NAC", "NAD", "NAF", "NAG", "NAP", "NAS", "NBC",
    "NBD", "NBE", "NBH", "NBM", "NBP", "NBW", "NCC", "NCG", "NCT", "NDC",
    "NDF", "NDP", "NDT", "NDX", "NEP", "NET", "NFC", "NGB", "NGC", "NGM",
    "NHA", "NHC", "NHP", "NHT", "NIC", "NID", "NII", "NIP", "NKG", "NLG",
    "NLP", "NMC", "NME", "NMF", "NMN", "NND", "NNG", "NNC", "NNT", "NO1",
    "NPC", "NPG", "NPH", "NPI", "NPL", "NPM", "NPN", "NPO", "NPP", "NPT",
    "NPV", "NRC", "NRG", "NRR", "NS2", "NS3", "NSA", "NSC", "NSG", "NSL",
    "NSP", "NSS", "NST", "NSV", "NTC", "NTD", "NTF", "NTG", "NTH", "NTL",
    "NTP", "NTR", "NTT", "NTV", "NTW", "NU1", "NVD", "NFC", "OIL", "OIL",
    "ONE", "ONT", "ORD", "ORS", "PAB", "PAC", "PAD", "PAI", "PAN", "PAS",
    "PBC", "PBD", "PBI", "PBM", "PBP", "PBR", "PBT", "PBV", "PBW", "PCC",
    "PCE", "PCF", "PCH", "PCI", "PCM", "PCN", "PCT", "PDC", "PDD", "PDN",
    "PDR", "PDT", "PDU", "PDV", "PEA", "PEC", "PED", "PEG", "PEQ", "PET",
    "PFV", "PGB", "PGC", "PGD", "PGH", "PGI", "PGM", "PGN", "PGR", "PGS",
    "PGT", "PGV", "PHA", "PHC", "PHE", "PHH", "PHN", "PHS", "PIA", "PIC",
    "PID", "PIE", "PIG", "PII", "PIS", "PIV", "PJA", "PJC", "PJD", "PJN",
    "PJP", "PJT", "PLC", "PLD", "PLP", "PLS", "PMC", "PMD", "PME", "PMG",
    "PMJ", "PMM", "PMP", "PMS", "PMT", "PMW", "PNC", "PND", "PNE", "PNG",
    "PNH", "PNP", "PNS", "PNT", "POD", "POR", "POS", "POT", "POV", "POW",
    "PPA", "PPB", "PPC", "PPD", "PPH", "PPI", "PPK", "PPM", "PPN", "PPO",
    "PPP", "PPY", "PRC", "PRE", "PRO", "PRT", "PSA", "PSB", "PSC", "PSD",
    "PSE", "PSG", "PSH", "PSI", "PSL", "PSN", "PSO", "PSP", "PST", "PSW",
    "PTA", "PTC", "PTD", "PTE", "PTG", "PTH", "PTI", "PTL", "PTM", "PTN",
    "PTO", "PTP", "PTS", "PTT", "PTV", "PVA", "PVB", "PVC", "PVD", "PVE",
    "PVF", "PVH", "PVI", "PVL", "PVM", "PVN", "PVP", "PVR", "PVS", "PVT",
    "PVV", "PVY", "PWA", "PX1", "PXC", "PXD", "PXH", "PXI", "PXL", "PXM",
    "PXN", "PXS", "PXT", "QBS", "QCC", "QCS", "QCT", "QHD", "QHW", "QLD",
    "QNC", "QNS", "QNU", "QPH", "QSP", "QST", "QTC", "QTD", "RAD", "RAL",
    "RBG", "RCD", "RCL", "RCS", "RDN", "RDP", "REA", "REC", "RED", "REE",
    "RFC", "RGD", "RGG", "RGB", "RHC", "RHD", "RIC", "RIG", "RKH", "ROS",
    "S12", "S27", "S74", "S96", "SA8", "SAB", "SAF", "SAG", "SAL", "SAM",
    "SAP", "SAR", "SAT", "SBB", "SBC", "SBL", "SBN", "SBP", "SBS", "SBT",
    "SBV", "SCC", "SCD", "SCE", "SCG", "SCH", "SCI", "SCL", "SCN", "SCO",
    "SCP", "SCR", "SCS", "SDA", "SDB", "SDC", "SDD", "SDE", "SDF", "SDG",
    "SDH", "SDI", "SDJ", "SDK", "SDL", "SDN", "SDP", "SDQ", "SDR", "SDS",
    "SDT", "SDU", "SDV", "SDY", "SEA", "SEB", "SED", "SEE", "SEG", "SEI",
    "SEP", "SFB", "SFC", "SFG", "SFI", "SFN", "SGB", "SGC", "SGD", "SGH",
    "SGI", "SGK", "SGL", "SGM", "SGN", "SGP", "SGR", "SGS", "SGT", "SGV",
    "SHA", "SHB", "SHC", "SHG", "SHI", "SHN", "SHP", "SHS", "SHV", "SIB",
    "SIC", "SID", "SIG", "SII", "SIM", "SIP", "SIR", "SIS", "SIT", "SIV",
    "SJ1", "SJA", "SJC", "SJD", "SJF", "SJH", "SJM", "SJP", "SJR", "SJS",
    "SJT", "SKG", "SKH", "SKN", "SKV", "SLC", "SLD", "SLS", "SMA", "SMB",
    "SMC", "SME", "SMI", "SMP", "SMT", "SNA", "SNC", "SNE", "SNG", "SNH",
    "SNK", "SNT", "SOA", "SOC", "SOF", "SON", "SPA", "SPC", "SPD", "SPF",
    "SPI", "SPM", "SPP", "SPT", "SPV", "SQC", "SRB", "SRC", "SRF", "SRT",
    "SSB", "SSC", "SSD", "SSG", "SSH", "SSI", "SSM", "SSN", "SSP", "SSS",
    "ST8", "STB", "STC", "STD", "STE", "STG", "STH", "STI", "STK", "STL",
    "STN", "STP", "STR", "STS", "STT", "STU", "STV", "SUN", "SUZ", "SV1",
    "SVA", "SVC", "SVD", "SVG", "SVH", "SVN", "SVT", "SWC", "SXD", "SZB",
    "SZC", "SZE", "SZG", "SZL", "TA6", "TA9", "TAB", "TAC", "TAD", "TAG",
    "TFC", "TAI", "TAM", "TAN", "TAW", "TAX", "TBB", "TBC", "TBD", "TBH",
    "TBN", "TBP", "TBT", "TBW", "TCA", "TCB", "TCC", "TCD", "TCE", "TCF",
    "TCG", "TCH", "TCI", "TCL", "TCM", "TCN", "TCO", "TCP", "TCR", "TCS",
    "TCT", "TDA", "TDB", "TDC", "TDD", "TDF", "TDG", "TDH", "TDI", "TDJ",
    "TDM", "TDN", "TDP", "TDS", "TDT", "TDW", "TEC", "TED", "TEG", "TEP",
    "TET", "TFC", "TGG", "TGH", "TGI", "TGM", "TGN", "TGP", "TGR", "TGS",
    "TGT", "TH1", "THA", "THB", "THD", "THE", "THG", "THN", "THP", "THS",
    "THT", "THV", "THW", "TIB", "TIC", "TID", "TIE", "TIF", "TIG", "TIH",
    "TIP", "TIS", "TIX", "TJC", "TJN", "TKC", "TKG", "TKU", "TLA", "TLB", "TLD",
    "TLG", "TLH", "TLI", "TLP", "TLT", "TMA", "TMB", "TMC", "TMD", "TME",
    "TMG", "TMI", "TMN", "TMP", "TMS", "TMT", "TMX", "TNA", "TNB", "TNC",
    "TND", "TNG", "TNH", "TNK", "TNL", "TNM", "TNP", "TNQ", "TNR", "TNS",
    "TNT", "TNV", "TNW", "TOA", "TOB", "TOC", "TOD", "TOP", "TOS", "TOW",
    "TPC", "TPH", "TPI", "TPN", "TPS", "TPW", "TQ1", "TQA", "TQP", "TR1",
    "TRA", "TRB", "TRC", "TRG", "TRH", "TS1", "TS4", "TSB", "TSC", "TSD",
    "TSE", "TSG", "TSJ", "TSM", "TSP", "TSS", "TST", "TTA", "TTB", "TTC",
    "TTD", "TTE", "TTF", "TTG", "TTH", "TTI", "TTJ", "TTL", "TTN", "TTO",
    "TTP", "TTS", "TTT", "TTZ", "TUG", "TV2", "TV3", "TV4", "TVA", "TVB",
    "TVC", "TVD", "TVE", "TVG", "TVH", "TVI", "TVM", "TVN", "TVP", "TVS",
    "TVT", "TVU", "TW3", "TXM", "TYN", "UBC", "UDC", "UDJ", "UDL", "UEM",
    "UIC", "UMC", "UNI", "UPC", "USD", "USC", "UTI", "V12", "V21", "VAB",
    "VAF", "VAG", "VAL", "VAS", "VAT", "VAV", "VBA", "VBC", "VBG", "VBH",
    "VBL", "VBN", "VBP", "VBS", "VBV", "VCA", "VCB", "VCC", "VCD", "VCE",
    "VCF", "VCG", "VCH", "VCI", "VCL", "VCM", "VCN", "VCP", "VCS", "VCT",
    "VCV", "VCX", "VDD", "VDG", "VDI", "VDL", "VDN", "VDS", "VDT", "VEC",
    "VED", "VEF", "VEG", "VEH", "VEI", "VES", "VF3", "VFC", "VFF", "VFH",
    "VFR", "VGC", "VGD", "VGE", "VGG", "VGH", "VGI", "VGL", "VGP", "VGR",
    "VGS", "VGT", "VGU", "VGV", "VGW", "VHC", "VHD", "VHE", "VHF", "VHG",
    "VHH", "VHI", "VHL", "VHM", "VHN", "VHO", "VIB", "VIC", "VID", "VIE",
    "VIF", "VIG", "VIH", "VII", "VIJ", "VIK", "VIN", "VIP", "VIR", "VIS",
    "VIT", "VIX", "VJC", "VJC", "VJG", "VJI", "VJS", "VKC", "VKE", "VKP",
    "VLA", "VLB", "VLC", "VLD", "VLF", "VLG", "VLH", "VLO", "VLP", "VLS",
    "VLT", "VMC", "VMD", "VMG", "VMI", "VML", "VMS", "VMT", "VNA", "VNB",
    "VNC", "VND", "VNE", "VNF", "VNG", "VNH", "VNI", "VNJ", "VNL", "VNM",
    "VNP", "VNQ", "VNR", "VNS", "VNT", "VNU", "VNV", "VOC", "VPA", "VPB",
    "VPC", "VPD", "VPG", "VPH", "VPI", "VPK", "VPL", "VPM", "VPN", "VPO",
    "VPP", "VPS", "VPK", "VQC", "VRA", "VRC", "VRD", "VRE", "VRG", "VRI",
    "VRL", "VRN", "VRP", "VSA", "VSB", "VSC", "VSE", "VSF", "VSG", "VSI",
    "VSJ", "VSL", "VSM", "VSN", "VSO", "VSP", "VSR", "VST", "VTA", "VTC",
    "VTD", "VTE", "VTF", "VTG", "VTH", "VTI", "VTK", "VTL", "VTM", "VTN",
    "VTO", "VTP", "VTR", "VTS", "VTT", "VTU", "VTV", "VTX", "VTZ", "VUA",
    "VUC", "VUE", "VUX", "VXB", "VXA", "X18", "X20", "X77", "XHC", "XMD",
    "XMC", "XMP", "XPH", "YBC", "YEG", "YTC"
]

# Deduplicate: HOSE takes precedence over HNX & UPCoM lists
_hose_set = set(HOSE_SYMBOLS)
HNX_SYMBOLS = [s for s in HNX_SYMBOLS if s not in _hose_set]
_hnx_set = set(HNX_SYMBOLS)
UPCOM_SYMBOLS = [s for s in UPCOM_SYMBOLS if s not in _hose_set and s not in _hnx_set]

ALL_VN_SYMBOLS = list(dict.fromkeys(HOSE_SYMBOLS + HNX_SYMBOLS + UPCOM_SYMBOLS))


def _guess_exchange(symbol: str) -> str:
    sym = symbol.upper()
    if sym in HOSE_SYMBOLS:
        return "HOSE"
    if sym in HNX_SYMBOLS:
        return "HNX"
    if sym in UPCOM_SYMBOLS:
        return "UPCOM"
    return "HOSE"


def fetch_live_vn_symbols() -> list[str]:
    """Fetch current live symbol list from VPS public API endpoints.

    Returns a clean list of uppercase stock symbols.
    """
    discovered: list[str] = []
    # 1. VPS bgapidatafeed endpoint
    url = "https://bgapidatafeed.vps.com.vn/getallstockonep/ALL"
    try:
        content, status, _ = fetch_url(url, timeout_seconds=6, max_retries=1)
        if status == 200 and content:
            raw_data = json.loads(content)
            if isinstance(raw_data, list):
                for item in raw_data:
                    if isinstance(item, dict):
                        sym = str(item.get("sym", "")).strip().upper()
                        # Keep standard 3-letter stock symbols, ignore derivatives (VN30F...), CWs, and index tickers
                        if sym and len(sym) == 3 and sym.isalpha() and sym not in ("CW", "INDEX"):
                            discovered.append(sym)
    except Exception as err:
        logger.debug("[VPS DISCOVERY] Live symbol fetch notice: %s", err)

    return list(dict.fromkeys(discovered))


def get_active_symbols(data_dir: Path | str | None = None) -> list[str]:
    """Load active symbols merging static base, dynamic cache (data/symbols.json), and live API discovery."""
    from pathlib import Path

    base_dir = Path(data_dir) if data_dir else Path("data")
    cache_file = base_dir / "symbols.json"

    cached_symbols: list[str] = []
    if cache_file.exists():
        try:
            raw = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                cached_symbols = [str(s).strip().upper() for s in raw if str(s).strip()]
        except Exception as err:
            logger.warning("[VPS DISCOVERY] Failed to read %s: %s", cache_file, err)

    # Combine static base list with cached symbols
    combined = list(dict.fromkeys(ALL_VN_SYMBOLS + cached_symbols))
    initial_count = len(combined)

    # Attempt dynamic live discovery for newly listed IPO tickers
    live_discovered = fetch_live_vn_symbols()
    new_tickers: list[str] = []
    if live_discovered:
        existing_set = set(combined)
        for sym in live_discovered:
            if sym not in existing_set:
                combined.append(sym)
                new_tickers.append(sym)
                existing_set.add(sym)

    if new_tickers:
        logger.info("[VPS DISCOVERY] Found %d new ticker(s) listed: %s", len(new_tickers), ", ".join(new_tickers))

    # Persist updated universe into data/symbols.json
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as err:
        logger.warning("[VPS DISCOVERY] Could not save %s: %s", cache_file, err)

    return combined



def _date_to_ts(d: date) -> int:
    """Convert a date to a UTC unix timestamp (start of day)."""
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def fetch_vps_history(
    symbol: str,
    from_date: date,
    to_date: date,
    *,
    timeout_seconds: int = 12,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """Fetch real daily OHLCV rows from VPS for one symbol.

    Returns a list of dicts with keys:
        date (str YYYY-MM-DD), symbol, open, high, low, close, volume, value, source
    """
    # VPS TradingView API requires a lookback window (minimum ~5-7 days) to return data
    req_from_date = from_date - timedelta(days=7)
    from_ts = _date_to_ts(req_from_date)
    to_ts = _date_to_ts(to_date) + 86400  # inclusive end
    url = f"{_VPS_BASE_URL}?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}"

    content, status_code, _ = fetch_url(url, timeout_seconds=timeout_seconds, max_retries=max_retries)
    if status_code != 200 or not content:
        logger.warning("VPS fetch failed for %s (status %s)", symbol, status_code)
        return []

    try:
        payload = json.loads(content) if isinstance(content, (str, bytes)) else {}
    except (json.JSONDecodeError, ValueError):
        logger.warning("VPS parse error for %s", symbol)
        return []

    if payload.get("s") != "ok":
        logger.debug("VPS no data for %s: status=%s", symbol, payload.get("s"))
        return []

    timestamps = payload.get("t") or []
    opens      = payload.get("o") or []
    highs      = payload.get("h") or []
    lows       = payload.get("l") or []
    closes     = payload.get("c") or []
    volumes    = payload.get("v") or []

    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        try:
            trading_date_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
            trading_date = trading_date_dt.strftime("%Y-%m-%d")

            # Filter to requested date window
            if trading_date < from_str or trading_date > to_str:
                continue

            close_price  = float(closes[i])
            open_price   = float(opens[i])  if i < len(opens)   else close_price
            high_price   = float(highs[i])  if i < len(highs)   else close_price
            low_price    = float(lows[i])   if i < len(lows)    else close_price
            volume       = float(volumes[i]) if i < len(volumes) else 0.0
            value        = close_price * volume * 1000.0
            rows.append({
                "date":            trading_date,
                "symbol":          symbol.upper(),
                "exchange":        _guess_exchange(symbol),
                "open":            open_price,
                "high":            high_price,
                "low":             low_price,
                "close":           close_price,
                "reference_price": open_price,
                "ceiling_price":   round(open_price * 1.07, 3),
                "floor_price":     round(open_price * 0.93, 3),
                "volume":          volume,
                "value":           value,
                "source":          "VPS_PUBLIC",
            })
        except (IndexError, TypeError, ValueError) as err:
            logger.debug("VPS row parse error for %s at index %d: %s", symbol, i, err)
            continue

    return rows


def _guess_exchange(symbol: str) -> str:
    sym = symbol.upper()
    if sym in HNX_SYMBOLS:
        return "HNX"
    if sym in UPCOM_SYMBOLS:
        return "UPCOM"
    return "HOSE"


class VPSMarketDataSource(EODDataSource):
    """Unified EOD data source for HOSE, HNX and UPCoM via VPS public API.

    Replaces the synthetic HOSE/HNX/UPCoM fallback with real price data.
    """

    def __init__(self, symbols: list[str] | None = None, rate_limit_seconds: float = 0.15) -> None:
        self.symbols = symbols or ALL_VN_SYMBOLS
        self.rate_limit_seconds = rate_limit_seconds
        self._last_fetch_time: float = 0.0

    @property
    def exchange_name(self) -> str:
        return "VN_ALL"

    def fetch(self, trading_date: date) -> RawFetchResult:
        """Fetch one day's EOD for all symbols, rate-limited to avoid throttling."""
        rows: list[dict[str, Any]] = []
        for symbol in self.symbols:
            # Rate-limit between requests
            elapsed = time.monotonic() - self._last_fetch_time
            if elapsed < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - elapsed)

            day_rows = fetch_vps_history(symbol, trading_date, trading_date)
            rows.extend(day_rows)
            self._last_fetch_time = time.monotonic()

        content = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        return RawFetchResult.create(
            content=content,
            status_code=200 if rows else 204,
            content_type="application/json",
            source_url=_VPS_BASE_URL,
        )

    def parse(self, raw_data: bytes | str) -> list[dict[str, Any]]:
        text = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else raw_data
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []


def get_exchange(symbol: str) -> str:
    """Return exchange name for stock symbol: HOSE, HNX, or UPCoM."""
    sym = (symbol or "").strip().upper()
    if sym in HOSE_SYMBOLS:
        return "HOSE"
    if sym in HNX_SYMBOLS:
        return "HNX"
    if sym in UPCOM_SYMBOLS:
        return "UPCoM"
    return "HOSE"
