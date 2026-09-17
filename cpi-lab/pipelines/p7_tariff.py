#!/usr/bin/env python3
"""P7 - tariff-exposed vs domestic CPI.

Splits the CPI leaf-item basket by *import content* (BEA input-output accounts) and
publishes three December-chained Laspeyres aggregates built exactly like the P0/P1
replica so they are comparable with the headline, plus an event-study panel around
US tariff effective dates.

  p7_tariff.py [--refresh-bea] [--no-event] [--no-mxp] [--basis=2017]

  --refresh-bea  force re-download of the BEA workbooks (they are ~35 MB total)
  --no-event     skip the event study (timeline + panel + coefficients)
  --no-mxp       skip the BLS import-price-by-locality companion series
  --basis=YYYY   benchmark year used for the tier cutoffs (2007|2012|2017, default 2017)

TIER 1 output is descriptive: the three aggregates are re-weightings of published CPI
item indexes, nothing more.  The ONLY causal-flavoured output is the event study, which
is TIER 2: it carries pre-trend checks and HAC standard errors and must be reported,
never headlined.

---------------------------------------------------------------------------
METHOD (which BEA path ran is logged and written to the JSON as method flags)
---------------------------------------------------------------------------
PRIMARY PATH ("bridge") - used when the BEA PCE Bridge resolves:

  1. Benchmark detail I-O year B (2007/2012/2017, ~400 commodities, producers' prices):
       U   = Use table, Before Redefinitions, producers' prices   (commodity x industry+final use)
       M   = Import matrix, Before Redefinitions                  (same shape)
       V   = Make table, Before Redefinitions                     (industry x commodity)
       L   = Commodity-by-commodity TOTAL requirements            (domestic, producers' prices)

     direct import share of a dollar of PCE on commodity c
         sd_c = M[c, F01000] / U[c, F01000]                        (clipped to [0,1])
       falling back to total-use basis when PCE use of c is negligible.

     imported intermediates embodied in a dollar of *domestic* commodity c:
         mi_j = (sum_c M[c,j]) / x_j             direct imports per $ of industry j output
         mc   = mi @ D,  D[j,c] = V[j,c] / q_c   re-expressed per $ of commodity output
         t    = mc @ L                           Leontief total (direct + indirect)

     total import content of a dollar of PCE on commodity c
         st_c = sd_c + (1 - sd_c) * t_c

  2. PCE Bridge for the same benchmark year maps each NIPA PCE category p to commodities
     with Producers' Value (PV), Transportation (TR), Wholesale (WS), Retail (RT) and
     Purchasers' Value (PU).  Margins and transport are *domestic services*: they carry
     no direct import content, only the embodied content of the trade/transport
     commodities.  Per purchaser dollar of PCE category p:

         share_direct_p = sum_c PV_pc * sd_c / PU_p
         share_total_p  = ( sum_c PV_pc * st_c + WS_p*t_ws + RT_p*t_rt + TR_p*t_tr ) / PU_p

     This replaces the uniform "goods at retail are 30-40% margin" haircut with the
     actual, category-specific margin split BEA publishes (it ranges from 12% to 100%
     producer share across the goods categories).

  3. Hand concordance P7_MAP (below) maps each CPI leaf item to one or more NIPA PCE
     categories with shares; the item's import share is the share-weighted mean.

FALLBACK PATH ("commodity") - if the PCE Bridge cannot be obtained:
     share is computed at producer-commodity level only and a uniform documented margin
     haircut per CPI major group (MARGIN_HAIRCUT below, from BEA margin aggregates) is
     applied.  The JSON records method='commodity_haircut' so consumers can tell.
     As of 2026-08 the bridge resolves and the primary path runs; the fallback is kept
     live so the pipeline degrades instead of dying if BEA moves the file.

Per-item shares are BENCHMARK-YEAR quantities (2007/2012/2017): BEA only publishes the
detail Use/Make/import/total-requirements set for benchmark years.  That is a feature for
the event study - exposure is measured in 2017, years before any of the 2018+ tariffs, so
it cannot be contaminated by the tariffs themselves.  The annual summary import matrix
(1997-2023) is loaded separately and used only for the economy-wide import-content-of-PCE
context series and for validation (a); it is NOT crosswalked to items.

---------------------------------------------------------------------------
Tables
  p7_import_share(basis_year, item_code, share_direct, share_total, method)
  p7_tier(weight_year, item_code, tier, share_used)        tier in high|mid|low
  p7_index(scheme, ym, idx, yoy)                           exposed|mid|domestic|official_replica
  p7_event(event_date, item_code, rel_month, yoy_demeaned, mom_demeaned, exposed_flag)
  p7_event_coef(event_date, rel_month, coef, se, t, pretrend_ok)
  p7_mxp(series_id, ym, value)                             BLS import price index by locality of origin

out/p7_tariff.json schema
  generated_at        ISO-8601 UTC
  latest_month        'YYYY-MM' of the last month with a YoY for every scheme
  basis_year          benchmark I-O year behind the tier assignment
  method              {path: bridge|commodity_haircut, bea_files: {label: url}, cutoffs: {...},
                       leontief: bool, margin_rates: {...}, notes: [str]}
  cutoffs             {high: float, low: float, rationale: str}
  series              [{ym, official_replica_yoy, exposed_yoy, mid_yoy, domestic_yoy,
                        exposed_idx, mid_idx, domestic_idx, official_replica_idx}]
  tier_weights        [{weight_year, tier, weight, n_items}]
  treemap             [{item_code, name, weight, share_total, share_direct, tier, major_group}]
  events              [{effective_date, action, scope, ad_valorem_change_pp, hts_note,
                        source_url, confidence, used_in_event_study}]
  event_study         [{event_date, action, n_exposed, n_domestic,
                        coefs: [{rel_month, coef, se, t}],
                        cum_0_12, cum_0_12_se, pretrend_slope, pretrend_t, pretrend_ok}]
  import_prices       [{series_id, label, series: [{ym, value}]}]
  pce_import_content  [{year, direct_share_pce, source}]      economy-wide context
  validation          [{check, ours, published_or_expected, diff, ok, note}]
  notes               [str]
"""
import sys, os, io, json, csv, zipfile, datetime as dt, pathlib, re
import pandas as pd, numpy as np
from common import *

# ---------------------------------------------------------------------------
# BEA sources.  Every URL here was verified to resolve on 2026-08-24; the code
# probes the newer annual filename first and falls back (see bea_annual_url()).
# ---------------------------------------------------------------------------
BEA = "https://apps.bea.gov/industry/xls/"
BEA_IM_SUM_FMT = BEA + "io-annual/ImportMatrices_Before_Redefinitions_SUM_1997-{end}.xlsx"
BEA_IM_SUM_ENDS = [2024, 2023]        # try the Sept-refresh filename first
BEA_IM_DET = BEA + "io-annual/ImportMatrices_Before_Redefinitions_DET_2017.xlsx"      # sheets 2007/2012/2017
BEA_USE_DET_0712 = BEA + "io-annual/IOUse_Before_Redefinitions_PRO_DET.xlsx"          # sheets 2007/2012
BEA_USE_DET_2017 = BEA + "io-annual/IOUse_Before_Redefinitions_PRO_2017_Detail.xlsx"  # sheet 2017
BEA_MAKE_DET_0712 = BEA + "io-annual/IOMake_Before_Redefinitions_DET.xlsx"
BEA_MAKE_DET_2017 = BEA + "io-annual/IOMake_Before_Redefinitions_2017_Detail.xlsx"
BEA_BRIDGE = BEA + "underlying-estimates/PCEBridge_2017_DET.xlsx"                     # sheets 2007/2012/2017
BEA_SUP_ZIP = "https://apps.bea.gov/industry/iTables%20Static%20Files/AllTablesSUP.zip"
SUP_TR_DET = "CxC_TR_2017_PRO_DET.xlsx"                       # sheets 2007/2012/2017
SUP_USE_SUM = "Use_Tables_Supply-Use_Framework_1997-2023_Summary.xlsx"

EI = BLS_TS + "ei/"

PCE_COL = "F01000"        # detail Use / import matrix column: personal consumption expenditures
PCE_COL_SUM = "F010"      # summary equivalent

# BEA allocates imports of a commodity proportionally across its users, so "New foreign
# autos" does not come out 100% imported.  These NIPA PCE lines are imported by
# construction and are overridden to a direct share of 1.0 at producers' value.
PCE_DIRECT_OVERRIDE = {8: ("New foreign autos", 1.0)}

# Fallback path only: producers' share of the purchaser dollar by CPI major group, from
# BEA margin aggregates (goods bought at retail run 30-40% margin+transport; services and
# utilities are billed direct).  Used ONLY when the PCE Bridge cannot be obtained.
MARGIN_HAIRCUT = {"SEA": 0.35, "SEF": 0.57, "SEG": 0.45, "SEH": 0.45, "SEM": 0.60,
                  "SER": 0.45, "SET": 0.55, "SEE": 0.60, "_default": 0.60}

# Tier cutoffs on total (Leontief) import content of a purchaser dollar.  Justified from
# the realised distribution in docs/P7.md; the split is logged every run.
CUT_HI = 0.25
CUT_LO = 0.10

MIN_COV = 0.90            # Chainer coverage gate, identical to P1
EVENT_MIN_PP = 5.0        # an event needs at least this many pp of ad-valorem change
EVENT_LO = (-6, 12)       # relative-month window written to p7_event
HAC_LAGS = 6

SCHEMA7 = """
CREATE TABLE IF NOT EXISTS p7_import_share(basis_year INT, item_code TEXT, share_direct REAL, share_total REAL, method TEXT, PRIMARY KEY(basis_year, item_code));
CREATE TABLE IF NOT EXISTS p7_tier(weight_year INT, item_code TEXT, tier TEXT, share_used REAL, PRIMARY KEY(weight_year, item_code));
CREATE TABLE IF NOT EXISTS p7_index(scheme TEXT, ym TEXT, idx REAL, yoy REAL, PRIMARY KEY(scheme, ym));
CREATE TABLE IF NOT EXISTS p7_event(event_date TEXT, item_code TEXT, rel_month INT, yoy_demeaned REAL, mom_demeaned REAL, exposed_flag INT, PRIMARY KEY(event_date, item_code, rel_month));
CREATE TABLE IF NOT EXISTS p7_event_coef(event_date TEXT, rel_month INT, coef REAL, se REAL, t REAL, pretrend_ok INT, PRIMARY KEY(event_date, rel_month));
CREATE TABLE IF NOT EXISTS p7_mxp(series_id TEXT, ym TEXT, value REAL, PRIMARY KEY(series_id, ym));
"""

# ---------------------------------------------------------------------------
# HAND CONCORDANCE: CPI leaf item -> NIPA PCE category line(s) with shares.
#
# Keyed on the NIPA line numbers used by the BEA PCE Bridge (NIPA table 2.4.5U).  Line
# numbers move at comprehensive NIPA revisions, so every mapped line is also checked
# against the description recorded here; a mismatch is logged loudly and the row is
# dropped rather than silently mapped to the wrong category.  Services are mapped even
# where the import share is ~0 so the domestic tier is built from real numbers, not from
# "everything we did not map".
#
# Shares within an item sum to 1 and are judgement calls about how a CPI stratum splits
# across PCE categories; they only matter where the mapped categories differ in import
# content.  ~179 rows = the full leaf universe.
# ---------------------------------------------------------------------------
P7_MAP = {
    # ---- Apparel ----------------------------------------------------------
    "SEAA01": [(107, "Men's and boys' clothing", 1.0)],
    "SEAA02": [(107, "Men's and boys' clothing", 1.0)],
    "SEAA03": [(107, "Men's and boys' clothing", 1.0)],
    "SEAA04": [(107, "Men's and boys' clothing", 1.0)],
    "SEAB":   [(107, "Men's and boys' clothing", 1.0)],
    "SEAC01": [(106, "Women's and girls' clothing", 1.0)],
    "SEAC02": [(106, "Women's and girls' clothing", 1.0)],
    "SEAC03": [(106, "Women's and girls' clothing", 1.0)],
    "SEAC04": [(106, "Women's and girls' clothing", 1.0)],
    "SEAD":   [(106, "Women's and girls' clothing", 1.0)],
    "SEAE01": [(112, "Shoes and other footwear", 1.0)],
    "SEAE02": [(112, "Shoes and other footwear", 1.0)],
    "SEAE03": [(112, "Shoes and other footwear", 1.0)],
    "SEAF":   [(108, "Children's and infants' clothing", 1.0)],
    "SEAG01": [(65, "Watches", 1.0)],
    "SEAG02": [(64, "Jewelry", 1.0)],
    # ---- Education and communication --------------------------------------
    "SEEA":   [(69, "Educational books", 0.70), (144, "Stationery and miscellaneous printed materials", 0.30)],
    "SEEB01": [(292, "Proprietary and public higher education", 0.60), (293, "Nonprofit private higher education services to households", 0.40)],
    "SEEB02": [(295, "Elementary and secondary schools", 1.0)],
    "SEEB03": [(296, "Day care and nursery schools", 0.50), (316, "Child care", 0.50)],
    "SEEC01": [(287, "First-class postal service (by U.S. Postal Service)", 1.0)],
    "SEEC02": [(288, "Other delivery services (by non-U.S. postal facilities)", 1.0)],
    "SEED03": [(285, "Cellular telephone services", 1.0)],
    "SEED04": [(283, "Land-line telephone services, local charges", 0.70), (284, "Land-line telephone services, long-distance charges", 0.30)],
    "SEEE01": [(49, "Personal computers/tablets and peripheral equipment", 1.0)],
    "SEEE02": [(50, "Computer software and accessories", 1.0)],
    "SEEE03": [(289, "Internet access", 1.0)],
    "SEEE04": [(71, "Telephone and related communication equipment", 0.85), (51, "Calculators, typewriters, and other information processing equipment", 0.15)],
    # ---- Food at home -----------------------------------------------------
    "SEFA01": [(77, "Cereals", 1.0)],
    "SEFA02": [(77, "Cereals", 1.0)],
    "SEFA03": [(77, "Cereals", 1.0)],
    "SEFB01": [(78, "Bakery products", 1.0)],
    "SEFB02": [(78, "Bakery products", 1.0)],
    "SEFB03": [(78, "Bakery products", 1.0)],
    "SEFB04": [(78, "Bakery products", 1.0)],
    "SEFC01": [(80, "Beef and veal", 1.0)],
    "SEFC02": [(80, "Beef and veal", 1.0)],
    "SEFC03": [(80, "Beef and veal", 1.0)],
    "SEFC04": [(80, "Beef and veal", 1.0)],
    "SEFD01": [(81, "Pork", 1.0)],
    "SEFD02": [(81, "Pork", 1.0)],
    "SEFD03": [(81, "Pork", 1.0)],
    "SEFD04": [(81, "Pork", 1.0)],
    "SEFE":   [(82, "Other meats", 1.0)],
    "SEFF01": [(83, "Poultry", 1.0)],
    "SEFF02": [(83, "Poultry", 1.0)],
    "SEFG01": [(84, "Fish and seafood", 1.0)],
    "SEFG02": [(84, "Fish and seafood", 1.0)],
    "SEFH":   [(88, "Eggs", 1.0)],
    "SEFJ01": [(86, "Fresh milk", 1.0)],
    "SEFJ02": [(87, "Processed dairy products", 1.0)],
    "SEFJ03": [(87, "Processed dairy products", 1.0)],
    "SEFJ04": [(87, "Processed dairy products", 1.0)],
    "SEFK01": [(91, "Fruit (fresh)", 1.0)],
    "SEFK02": [(91, "Fruit (fresh)", 1.0)],
    "SEFK03": [(91, "Fruit (fresh)", 1.0)],
    "SEFK04": [(91, "Fruit (fresh)", 1.0)],
    "SEFL01": [(92, "Vegetables (fresh)", 1.0)],
    "SEFL02": [(92, "Vegetables (fresh)", 1.0)],
    "SEFL03": [(92, "Vegetables (fresh)", 1.0)],
    "SEFL04": [(92, "Vegetables (fresh)", 1.0)],
    "SEFM01": [(93, "Processed fruits and vegetables", 1.0)],
    "SEFM02": [(93, "Processed fruits and vegetables", 1.0)],
    "SEFM03": [(93, "Processed fruits and vegetables", 1.0)],
    "SEFN01": [(98, "Mineral waters, soft drinks, and vegetable juices", 1.0)],
    "SEFN02": [(98, "Mineral waters, soft drinks, and vegetable juices", 1.0)],
    "SEFN03": [(98, "Mineral waters, soft drinks, and vegetable juices", 1.0)],
    "SEFP01": [(97, "Coffee, tea, and other beverage materials", 1.0)],
    "SEFP02": [(97, "Coffee, tea, and other beverage materials", 1.0)],
    "SEFR01": [(94, "Sugar and sweets", 1.0)],
    "SEFR02": [(94, "Sugar and sweets", 1.0)],
    "SEFR03": [(94, "Sugar and sweets", 1.0)],
    "SEFS01": [(89, "Fats and oils", 1.0)],
    "SEFS02": [(89, "Fats and oils", 1.0)],
    "SEFS03": [(89, "Fats and oils", 1.0)],
    "SEFT01": [(95, "Food products, not elsewhere classified", 1.0)],
    "SEFT02": [(95, "Food products, not elsewhere classified", 1.0)],
    "SEFT03": [(95, "Food products, not elsewhere classified", 1.0)],
    "SEFT04": [(95, "Food products, not elsewhere classified", 1.0)],
    "SEFT05": [(95, "Food products, not elsewhere classified", 1.0)],
    "SEFT06": [(95, "Food products, not elsewhere classified", 1.0)],
    # ---- Food away from home / alcohol ------------------------------------
    "SEFV01": [(243, "Meals at other eating places", 1.0)],
    "SEFV02": [(242, "Meals at limited service eating places", 1.0)],
    "SEFV03": [(239, "Elementary and secondary school lunches", 0.40), (240, "Higher education school lunches", 0.30),
               (246, "Food furnished to employees (including military)", 0.30)],
    "SEFV04": [(242, "Meals at limited service eating places", 1.0)],
    "SEFV05": [(243, "Meals at other eating places", 1.0)],
    "SEFW01": [(102, "Beer", 1.0)],
    "SEFW02": [(100, "Spirits", 1.0)],
    "SEFW03": [(101, "Wine", 1.0)],
    "SEFX":   [(245, "Alcohol in purchased meals", 1.0)],
    # ---- Other goods and services -----------------------------------------
    "SEGA01": [(141, "Tobacco", 1.0)],
    "SEGA02": [(141, "Tobacco", 1.0)],
    "SEGB01": [(138, "Hair, dental, shaving, and miscellaneous personal care products except electrical products", 0.85),
               (140, "Electric appliances for personal care", 0.15)],
    "SEGB02": [(139, "Cosmetic/perfumes/bath/nail preparations and implements", 1.0)],
    "SEGC01": [(309, "Hairdressing salons and personal grooming establishments", 0.60), (310, "Miscellaneous personal care services", 0.40)],
    "SEGD01": [(299, "Legal services", 1.0)],
    "SEGD02": [(306, "Funeral and burial services", 1.0)],
    "SEGD03": [(312, "Laundry and drycleaning services", 1.0)],
    "SEGD04": [(313, "Clothing repair, rental, and alterations", 0.80), (314, "Repair and hire of footwear", 0.20)],
    "SEGD05": [(259, "Financial service charges and fees", 0.60), (301, "Tax preparation and other related services", 0.40)],
    "SEGE":   [(70, "Luggage and similar personal items", 1.0)],
    # ---- Housing ----------------------------------------------------------
    "SEHA":   [(156, "Tenant landlord durables", 1.0)],     # tenant-occupied dwelling space
    "SEHB02": [(250, "Hotels and motels", 0.80), (251, "Housing at schools", 0.20)],
    "SEHC01": [(162, "Owner-occupied stationary homes", 1.0)],
    "SEHD":   [(272, "Net household insurance", 1.0)],
    "SEHE01": [(118, "Fuel oil", 1.0)],
    "SEHE02": [(119, "Other fuels", 1.0)],
    "SEHF01": [(170, "Electricity", 1.0)],
    "SEHF02": [(171, "Natural gas", 1.0)],
    "SEHG01": [(167, "Water supply and sewage maintenance", 1.0)],
    "SEHG02": [(168, "Garbage and trash collection", 1.0)],
    "SEHH01": [(27, "Carpets and other floor coverings", 1.0)],
    "SEHH02": [(28, "Window coverings", 1.0)],
    "SEHH03": [(134, "Household linens", 1.0)],
    "SEHJ01": [(25, "Furniture", 1.0)],
    "SEHJ02": [(25, "Furniture", 1.0)],
    "SEHJ03": [(25, "Furniture", 1.0)],
    "SEHK01": [(30, "Major household appliances", 1.0)],
    "SEHK02": [(31, "Small electric household appliances", 1.0)],
    "SEHL01": [(26, "Clocks, lamps, lighting fixtures, and other household decorative items", 1.0)],
    "SEHL02": [(129, "Flowers, seeds, and potted plants", 1.0)],
    "SEHL03": [(33, "Dishes and flatware", 1.0)],
    "SEHL04": [(34, "Nonelectric cookware and tableware", 1.0)],
    "SEHM01": [(36, "Tools, hardware, and supplies", 1.0)],
    "SEHM02": [(37, "Outdoor equipment and supplies", 1.0)],
    "SEHN01": [(132, "Household cleaning products", 1.0)],
    "SEHN02": [(133, "Household paper products", 1.0)],
    "SEHN03": [(136, "Miscellaneous household products", 1.0)],
    "SEHP01": [(328, "Domestic services", 1.0)],
    "SEHP02": [(332, "Other household services", 1.0)],
    "SEHP03": [(329, "Moving, storage, and freight services", 1.0)],
    "SEHP04": [(331, "Repair of household appliances", 0.70), (330, "Repair of furniture, furnishings, and floor coverings", 0.30)],
    # ---- Medical ----------------------------------------------------------
    "SEMC01": [(174, "Physician services", 1.0)],
    "SEMC02": [(175, "Dental services", 1.0)],
    "SEMC03": [(68, "Corrective eyeglasses and contact lenses", 0.70), (181, "All other professional medical services", 0.30)],
    "SEMC04": [(181, "All other professional medical services", 0.60), (178, "Medical laboratories", 0.20),
               (180, "Specialty outpatient care facilities and health and allied services", 0.20)],
    "SEMD01": [(184, "Nonprofit hospitals' services to households", 0.60), (185, "Proprietary hospitals", 0.20),
               (186, "Government hospitals", 0.20)],
    "SEMD02": [(189, "Proprietary and government nursing homes", 0.65), (188, "Nonprofit nursing homes' services to households", 0.35)],
    "SEME":   [(276, "Medical care and hospitalization", 1.0)],
    "SEMF01": [(122, "Pharmaceutical products", 1.0)],
    "SEMF02": [(122, "Pharmaceutical products", 0.85), (125, "Other medical products", 0.15)],
    "SEMG":   [(67, "Therapeutic medical equipment", 1.0)],
    # ---- Recreation -------------------------------------------------------
    "SERA01": [(41, "Televisions", 1.0)],
    "SERA02": [(219, "Cable, satellite, and other live television services", 1.0)],
    "SERA03": [(42, "Other video equipment", 1.0)],
    "SERA04": [(223, "Video and audio streaming and rental", 0.60), (46, "Video discs, tapes, and permanent digital downloads", 0.40)],
    "SERA05": [(43, "Audio equipment", 1.0)],
    "SERA06": [(45, "Audio discs, tapes, vinyl, and permanent digital downloads", 1.0)],
    "SERB01": [(128, "Pets and related products", 1.0)],
    "SERB02": [(231, "Veterinary and other services for pets", 1.0)],
    "SERC01": [(55, "Bicycles and accessories", 0.50), (54, "Motorcycles", 0.25), (59, "Other recreational vehicles", 0.25)],
    "SERC02": [(52, "Sporting equipment, supplies, guns, and ammunition", 1.0)],
    "SERD01": [(47, "Photographic equipment", 0.70), (130, "Film and photographic supplies", 0.30)],
    "SERD02": [(221, "Photo studios", 0.70), (220, "Photo processing", 0.30)],
    "SERE01": [(127, "Games, toys, and hobbies", 1.0)],
    "SERE02": [(135, "Sewing items", 0.60), (110, "Clothing materials", 0.40)],
    "SERE03": [(61, "Musical instruments", 1.0)],
    "SERF01": [(211, "Membership clubs and participant sports centers", 1.0)],
    "SERF02": [(215, "Live entertainment, excluding sports", 0.35), (216, "Spectator sports", 0.35),
               (214, "Motion picture theaters", 0.20), (217, "Museums and libraries", 0.10)],
    "SERF03": [(297, "Commercial and vocational schools", 1.0)],
    "SERG01": [(143, "Newspapers and periodicals", 1.0)],
    "SERG02": [(60, "Recreational books", 1.0)],
    # ---- Transportation ---------------------------------------------------
    "SETA01": [(9, "New light trucks", 0.65), (7, "New domestic autos", 0.25), (8, "New foreign autos", 0.10)],
    "SETA02": [(17, "Used light trucks", 0.60), (13, "Used autos", 0.40)],
    "SETA03": [(195, "Auto leasing", 0.70), (196, "Truck leasing", 0.30)],
    "SETA04": [(197, "Motor vehicle rental", 1.0)],
    "SETB01": [(115, "Gasoline and other motor fuel", 1.0)],
    "SETB02": [(116, "Lubricants and fluids", 1.0)],
    "SETC01": [(21, "Tires", 1.0)],
    "SETC02": [(22, "Accessories and parts", 1.0)],
    "SETD01": [(192, "Motor vehicle maintenance and repair", 1.0)],
    "SETD02": [(192, "Motor vehicle maintenance and repair", 1.0)],
    "SETD03": [(192, "Motor vehicle maintenance and repair", 1.0)],
    "SETE":   [(279, "Net motor vehicle and other transportation insurance", 1.0)],
    # state registration/licence fees are a government charge with no PCE-bridge row of
    # their own; mapped to parking fees and tolls, the nearest domestic-services analogue.
    "SETF01": [(198, "Parking fees and tolls", 1.0)],
    "SETF03": [(198, "Parking fees and tolls", 1.0)],
    "SETG01": [(207, "Air transportation", 1.0)],
    "SETG02": [(203, "Intercity buses", 0.40), (201, "Railway transportation", 0.30), (208, "Water transportation", 0.30)],
    "SETG03": [(204, "Taxicabs and ride sharing services", 0.50), (205, "Intracity mass transit", 0.50)],
}

MAJOR_GROUP = {"SEA": "Apparel", "SEE": "Education and communication", "SEF": "Food and beverages",
               "SEG": "Other goods and services", "SEH": "Housing", "SEM": "Medical care",
               "SER": "Recreation", "SET": "Transportation"}


# ===========================================================================
# December-chained Laspeyres - copied verbatim from p1_salience.Chainer so the
# three aggregates are arithmetically identical to the official replica.
# ===========================================================================
class Chainer:
    """Vectorised December-chained Laspeyres; arithmetic identical to p1_salience.Chainer.

    A month is skipped unless leaves carrying at least MIN_COV of the scheme's total weight
    have both a December base index and a current index (this is what keeps October 2025,
    which has no CPI release, out of every series).
    """

    def __init__(self, im, leaves_by_year, pub_sa0):
        self.pub = pub_sa0
        self.skipped = {}
        self.years = sorted(leaves_by_year)
        piv = im.pivot_table(index="item_code", columns="ym", values="idx_nsa")
        self.items, self.months, self.R, self.M = {}, {}, {}, {}
        for y in self.years:
            items = list(leaves_by_year[y])
            self.items[y] = items
            bym = f"{y}-12"
            b = piv[bym].reindex(items).values if bym in piv.columns else np.full(len(items), np.nan)
            ms, rows = [], []
            for mo in range(1, 13):
                ym = f"{y+1}-{mo:02d}"
                if ym not in piv.columns:
                    continue
                ms.append(ym)
                rows.append(piv[ym].reindex(items).values / b)
            R = np.array(rows) if rows else np.zeros((0, len(items)))
            self.months[y] = ms
            self.M[y] = np.isfinite(R).astype(float)
            self.R[y] = np.where(np.isfinite(R), R, 0.0)

    def run(self, weights_by_year, note=None):
        out, skipped = {}, []
        for y in self.years:
            if y not in weights_by_year or not self.months[y]:
                continue
            w = pd.Series(weights_by_year[y]).reindex(self.items[y]).fillna(0.0).values.astype(float)
            tot = w.sum()
            if tot <= 0:
                continue
            den = self.M[y] @ w
            num = self.R[y] @ w
            for k, ym in enumerate(self.months[y]):
                if den[k] >= MIN_COV * tot:
                    out[ym] = num[k] / den[k]
                elif den[k] > 0:
                    skipped.append((ym, den[k] / tot))
        for ym, c in skipped:
            self.skipped[ym] = max(self.skipped.get(ym, 0.0), c)
        if note and skipped:
            log.info("%s: dropped %d month(s) with leaf coverage < %.0f%%: %s", note, len(skipped), MIN_COV * 100,
                     [(ym, f"{100*c:.1f}%") for ym, c in skipped])
        s = pd.Series(out).sort_index()
        level, last_dec = {}, None
        for ym, rel in s.items():
            y = int(ym[:4]) - 1
            if last_dec is None or last_dec[0] != y:
                last_dec = (y, level.get(f"{y}-12", self.pub.get(f"{y}-12")))
            level[ym] = last_dec[1] * rel
        lv = pd.Series(level).sort_index()
        p = pd.PeriodIndex(lv.index, freq="M")
        prev = pd.Series(lv.values, index=(p + 12).astype(str))
        yoy = (lv / prev.reindex(lv.index) - 1) * 100
        return lv, yoy


# ===========================================================================
# BEA workbook plumbing
# ===========================================================================
def _is_codeish(v):
    s = str(v).strip()
    return bool(s) and s != "None" and len(s) <= 8 and " " not in s


def read_bea_matrix(src, sheet):
    """Read one BEA I-O sheet into a DataFrame indexed by row code, columns = column codes.

    Handles both header layouts BEA ships: some sheets put the column *codes* on the row
    whose first cell is 'Code'/'IOCode', others put the codes one row above and the names
    on the 'IOCode' row.  '...' and blanks become 0.0.
    """
    import openpyxl
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb[sheet]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    hr = None
    for i, r in enumerate(rows[:12]):
        if r and str(r[0]).strip() in ("Code", "IOCode"):
            hr = i
            break
    if hr is None:
        raise RuntimeError(f"no Code/IOCode header row in sheet {sheet}")
    cand = [hr, hr - 1] if hr > 0 else [hr]
    best, score = hr, -1
    for c in cand:
        s = sum(1 for v in rows[c][2:] if v is not None and _is_codeish(v))
        if s > score:
            best, score = c, s
    cols = [str(v).strip() if v is not None else "" for v in rows[best][2:]]
    data, idx = [], []
    for r in rows[hr + 1:]:
        if not r or r[0] is None:
            continue
        code = str(r[0]).strip()
        if not code or code.lower().startswith("note"):
            continue
        idx.append(code)
        vals = []
        for v in r[2:2 + len(cols)]:
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                vals.append(0.0)
        vals += [0.0] * (len(cols) - len(vals))
        data.append(vals)
    df = pd.DataFrame(data, index=idx, columns=cols)
    df = df.loc[~df.index.duplicated(), ~df.columns.duplicated()]
    return df


def read_bea_names(src, sheet):
    """{code: description} for a BEA I-O sheet's row stubs."""
    import openpyxl
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = wb[sheet]
    out = {}
    started = False
    for r in ws.iter_rows(min_col=1, max_col=2, values_only=True):
        if r[0] is None:
            continue
        c = str(r[0]).strip()
        if c in ("Code", "IOCode"):
            started = True
            continue
        if started and c and not c.lower().startswith("note"):
            out[c] = str(r[1]).strip() if r[1] else ""
    wb.close()
    return out


def bea_annual_url():
    """Try the newer ImportMatrices annual filename first (BEA adds a year each September).

    Returns (url, end_year).  A 404 at apps.bea.gov comes back as 200 text/html, so the
    content type is what decides.
    """
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = UA
    for end in BEA_IM_SUM_ENDS:
        u = BEA_IM_SUM_FMT.format(end=end)
        try:
            r = s.head(u, timeout=60, allow_redirects=True)
            if "html" not in r.headers.get("Content-Type", ""):
                log.info("BEA annual import matrix: %s resolved (%s bytes)", u.split("/")[-1], r.headers.get("Content-Length"))
                return u, end
            log.info("BEA annual import matrix: %s not published yet", u.split("/")[-1])
        except Exception as e:
            log.warning("probe %s failed: %s", u, e)
    raise RuntimeError("no ImportMatrices annual file resolved")


def bea_fetch_all(force=False):
    """Download every BEA workbook P7 needs.  Returns (paths dict, method flags dict)."""
    d = RAW / "bea"
    got, urls = {}, {}
    def g(key, url, name):
        p, _ = fetch(url, d / name, force=force)
        got[key] = p
        urls[key] = url
        return p
    im_url, im_end = bea_annual_url()
    g("im_sum", im_url, f"ImportMatrices_SUM_1997-{im_end}.xlsx")
    g("im_det", BEA_IM_DET, "ImportMatrices_DET_2017.xlsx")
    g("use_det_0712", BEA_USE_DET_0712, "IOUse_PRO_DET.xlsx")
    g("use_det_2017", BEA_USE_DET_2017, "IOUse_PRO_2017_Detail.xlsx")
    g("make_det_0712", BEA_MAKE_DET_0712, "IOMake_DET.xlsx")
    g("make_det_2017", BEA_MAKE_DET_2017, "IOMake_2017_Detail.xlsx")
    g("sup_zip", BEA_SUP_ZIP, "AllTablesSUP.zip")
    bridge = None
    try:
        bridge = g("bridge", BEA_BRIDGE, "PCEBridge_2017_DET.xlsx")
    except Exception as e:
        log.warning("PCE Bridge unavailable (%s) - falling back to the commodity+haircut path", e)
    flags = {"path": "bridge" if bridge else "commodity_haircut",
             "annual_import_matrix_end_year": im_end,
             "bea_files": {k: v for k, v in urls.items()}}
    return got, flags


def det_tables(paths, year):
    """Use (producers'), Make, Import matrix and CxC total requirements for a benchmark year."""
    y = str(year)
    use_src = paths["use_det_2017"] if year == 2017 else paths["use_det_0712"]
    make_src = paths["make_det_2017"] if year == 2017 else paths["make_det_0712"]
    U = read_bea_matrix(use_src, y)
    V = read_bea_matrix(make_src, y)
    M = read_bea_matrix(paths["im_det"], y)
    z = zipfile.ZipFile(paths["sup_zip"])
    L = read_bea_matrix(io.BytesIO(z.read(SUP_TR_DET)), y)
    names = read_bea_names(paths["im_det"], y)
    log.info("detail %s: Use %s, Make %s, Imports %s, CxC_TR %s", y, U.shape, V.shape, M.shape, L.shape)
    return U, V, M, L, names


TRADE_RE = re.compile(r"wholesale", re.I)
RETAIL_RE = re.compile(r"retail|stores|dealers|nonstore", re.I)
TRANSP_RE = re.compile(r"transportation|transit|warehousing|couriers|pipeline", re.I)


def commodity_shares(U, V, M, L, names):
    """Direct and Leontief-total import content per dollar of commodity delivered to PCE.

    Returns (sd, st, t, margin_rates, diag) all indexed by commodity code.
    """
    # Commodity universe = codes present in EVERY table.  The 2007/2012 sheets of the Use
    # and Make workbooks carry a slightly different detail commodity list from the import
    # matrix and the total-requirements table, so the intersection is taken explicitly.
    coms = [c for c in U.index if c in M.index and c in L.index and c in L.columns and c in V.columns]
    # ---- industry columns: everything that is not a final-use (F*), total (T*) or
    #      value-added (V*) row/column.  Totals must be excluded before summing or the
    #      Make table's total column double-counts every industry's output.
    def _real(codes):
        return [c for c in codes if not str(c).startswith(("F", "T0", "V0", "VA"))]
    # industries must exist in the Use columns, the Make rows AND the import-matrix columns:
    # the 2007/2012 sheets of the Use/Make workbooks carry a few industries the import
    # matrix does not (33391A, 3352xx), and indexing across them raises.
    ind = [c for c in _real(U.columns) if c in V.index and c in M.columns]
    vcols = [c for c in _real(V.columns)]
    x = V.loc[ind, vcols].sum(axis=1)                     # industry output
    q = V.loc[ind, coms].sum(axis=0)                      # commodity output

    # ---- direct import share of the PCE delivery of each commodity
    use_pce = U[PCE_COL].reindex(coms).fillna(0.0) if PCE_COL in U.columns else pd.Series(0.0, index=coms)
    imp_pce = M[PCE_COL].reindex(coms).fillna(0.0) if PCE_COL in M.columns else pd.Series(0.0, index=coms)
    # total-use fallback denominator: every use column except the totals and the negative
    # "imports" final-use column the I-O Use table carries to reconcile to domestic output.
    ucols = [c for c in _real(U.columns) if not str(c).startswith("F05")] + \
            [c for c in U.columns if str(c).startswith(("F0", "F1")) and not str(c).startswith("F05")]
    ucols = list(dict.fromkeys(ucols))
    use_all = U.loc[coms, [c for c in ucols if c in U.columns]].sum(axis=1)
    imp_all = M.loc[coms, [c for c in ucols if c in M.columns]].sum(axis=1)
    sd = pd.Series(0.0, index=coms, dtype=float)
    n_pce, n_all = 0, 0
    for c in coms:
        if use_pce[c] > 1.0:                              # $1M of PCE use: enough to divide
            sd[c] = imp_pce[c] / use_pce[c]; n_pce += 1
        elif use_all[c] > 1.0:
            sd[c] = imp_all[c] / use_all[c]; n_all += 1
    sd = sd.clip(0.0, 1.0)

    # ---- Leontief total import content of a dollar of DOMESTIC commodity output
    Mi = M.loc[coms, ind].sum(axis=0)                     # imported intermediates by industry
    mi = (Mi / x.reindex(ind).replace(0.0, np.nan)).fillna(0.0)
    D = V.loc[ind, coms].div(q.reindex(coms).replace(0.0, np.nan), axis=1).fillna(0.0)  # industry x commodity
    mc = mi.values @ D.values                             # imports per $ of commodity output
    Lm = L.loc[coms, coms].values
    t = pd.Series(np.clip(mc @ Lm, 0.0, 1.0), index=coms)
    st = (sd + (1.0 - sd) * t).clip(0.0, 1.0)

    # ---- margin / transport commodities carry no direct imports, only embodied ones
    def grp(rx, exclude=None):
        sel = [c for c in coms if rx.search(names.get(c, "")) and not (exclude and exclude.search(names.get(c, "")))]
        if not sel:
            return float(t.mean()), 0
        w = q.reindex(sel).fillna(0.0)
        return (float((t[sel] * w).sum() / w.sum()) if w.sum() > 0 else float(t[sel].mean())), len(sel)
    t_ws, n_ws = grp(TRADE_RE)
    t_rt, n_rt = grp(RETAIL_RE, exclude=TRADE_RE)
    t_tr, n_tr = grp(TRANSP_RE)
    margin_rates = {"wholesale": t_ws, "retail": t_rt, "transport": t_tr,
                    "n_commodities": {"wholesale": n_ws, "retail": n_rt, "transport": n_tr}}
    diag = {"n_commodities": len(coms), "sd_from_pce_column": n_pce, "sd_from_total_use": n_all,
            "mean_t": float(t.mean()), "max_t": float(t.max())}
    log.info("commodity shares: %d commodities, sd from PCE column %d / total-use fallback %d; "
             "Leontief t mean %.3f max %.3f; margin embodied rates wholesale %.3f retail %.3f transport %.3f",
             len(coms), n_pce, n_all, t.mean(), t.max(), t_ws, t_rt, t_tr)
    return sd, st, t, margin_rates, diag


def bridge_shares(bridge_path, year, sd, st, margin_rates):
    """Per NIPA PCE category: import content of a purchaser dollar, via the BEA PCE Bridge."""
    import openpyxl
    wb = openpyxl.load_workbook(bridge_path, read_only=True, data_only=True)
    ws = wb[str(year)]
    rows = list(ws.iter_rows(min_row=6, values_only=True))
    wb.close()
    t_ws, t_rt, t_tr = margin_rates["wholesale"], margin_rates["retail"], margin_rates["transport"]
    acc, unknown = {}, set()
    for r in rows:
        if r is None or r[0] is None or r[2] is None:
            continue
        try:
            line = int(str(r[0]).strip())
        except ValueError:
            continue
        com = str(r[2]).strip()
        desc = str(r[1]).strip() if r[1] else ""
        def f(i):
            try:
                return float(r[i] or 0.0)
            except (TypeError, ValueError):
                return 0.0
        pv, tr, wsm, rt, pu = f(4), f(5), f(6), f(7), f(8)
        a = acc.setdefault(line, {"desc": desc, "pv": 0.0, "tr": 0.0, "ws": 0.0, "rt": 0.0, "pu": 0.0,
                                  "dir": 0.0, "tot": 0.0})
        a["pv"] += pv; a["tr"] += tr; a["ws"] += wsm; a["rt"] += rt; a["pu"] += pu
        if com in sd.index:
            s_d, s_t = float(sd[com]), float(st[com])
        else:
            unknown.add(com)
            s_d = s_t = 0.0
        a["dir"] += pv * s_d
        a["tot"] += pv * s_t
    out = {}
    for line, a in acc.items():
        if abs(a["pu"]) < 1e-9:
            continue
        ovr = PCE_DIRECT_OVERRIDE.get(line)
        if ovr:
            a["dir"] = a["pv"] * ovr[1]
            a["tot"] = max(a["tot"], a["pv"] * ovr[1])
        emb = a["ws"] * t_ws + a["rt"] * t_rt + a["tr"] * t_tr
        out[line] = {"desc": a["desc"], "pu": a["pu"],
                     "prod_share": a["pv"] / a["pu"],
                     "share_direct": max(0.0, min(1.0, a["dir"] / a["pu"])),
                     "share_total": max(0.0, min(1.0, (a["tot"] + emb) / a["pu"]))}
    if unknown:
        log.warning("PCE bridge: %d commodity codes had no import share (%s...)", len(unknown), sorted(unknown)[:6])
    log.info("PCE bridge %s: %d categories, total purchasers' value $%.0fB", year, len(out),
             sum(v["pu"] for v in out.values()) / 1000.0)
    return out


def item_shares_bridge(pce, leaf_codes):
    """CPI leaf item -> (share_direct, share_total) through P7_MAP."""
    rows, bad = {}, []
    for item, targets in P7_MAP.items():
        num_d = num_t = wsum = 0.0
        for line, desc, share in targets:
            p = pce.get(line)
            if p is None:
                bad.append((item, line, desc, "line missing from bridge"))
                continue
            if _norm(p["desc"])[:28] != _norm(desc)[:28]:
                bad.append((item, line, desc, f"description drift -> '{p['desc']}'"))
                continue
            num_d += share * p["share_direct"]
            num_t += share * p["share_total"]
            wsum += share
        if wsum <= 0:
            continue
        rows[item] = (num_d / wsum, num_t / wsum)
    for b in bad:
        log.warning("P7_MAP: %s -> NIPA line %s (%s): %s", *b)
    missing = sorted(set(leaf_codes) - set(rows))
    if missing:
        log.warning("P7_MAP covers %d/%d leaves; unmapped: %s", len(rows), len(leaf_codes), missing)
    else:
        log.info("P7_MAP covers all %d leaf items", len(leaf_codes))
    return rows, bad


def item_shares_haircut(sd, st, names, leaf_codes):
    """FALLBACK: no PCE bridge.  Commodity-level shares + uniform per-major-group haircut.

    Without the bridge there is no commodity composition per PCE category either, so the
    concordance is applied at the level of the *major group* average commodity share for
    goods and 0 for services.  This is a lower-quality path kept only so the pipeline
    degrades rather than dying; it is labelled method='commodity_haircut' everywhere.
    """
    goods = {c: float(st[c]) for c in st.index if st[c] > 0}
    avg = float(np.mean(list(goods.values()))) if goods else 0.0
    rows = {}
    for item in P7_MAP:
        h = MARGIN_HAIRCUT.get(item[:3], MARGIN_HAIRCUT["_default"])
        base = avg if item[:3] in ("SEA", "SEF", "SEH", "SER", "SET", "SEG") else 0.0
        rows[item] = (base * h * 0.7, base * h)
    log.warning("fallback path: item shares built from a %.3f economy-average commodity share and "
                "per-major-group margin haircuts %s", avg, MARGIN_HAIRCUT)
    return rows, []


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def annual_pce_import_content(paths, end_year):
    """Economy-wide direct import content of PCE by year, from the annual SUMMARY tables.

    Used for validation and as a context series only - it is never crosswalked to items.
    """
    z = zipfile.ZipFile(paths["sup_zip"])
    out = []
    import openpyxl
    wb = openpyxl.load_workbook(paths["im_sum"], read_only=True, data_only=True)
    years = [s for s in wb.sheetnames if re.fullmatch(r"\d{4}", s)]
    wb.close()
    use_bytes = io.BytesIO(z.read(SUP_USE_SUM))
    for y in years:
        try:
            M = read_bea_matrix(paths["im_sum"], y)
            use_bytes.seek(0)
            U = read_bea_matrix(use_bytes, y)
        except Exception as e:
            log.warning("annual summary %s failed: %s", y, e)
            continue
        if PCE_COL_SUM not in M.columns or PCE_COL_SUM not in U.columns:
            continue
        coms = [c for c in M.index if c in U.index and not c.startswith(("T0", "V0", "VA"))]
        num = float(M.loc[coms, PCE_COL_SUM].sum())
        den = float(U.loc[coms, PCE_COL_SUM].sum())
        if den > 0:
            out.append({"year": int(y), "direct_share_pce": num / den,
                        "source": "BEA annual summary import matrix / SUT use table"})
    log.info("annual PCE direct import content: %d years, %s -> %s",
             len(out), f"{out[0]['year']}:{out[0]['direct_share_pce']:.4f}" if out else "-",
             f"{out[-1]['year']}:{out[-1]['direct_share_pce']:.4f}" if out else "-")
    return out


# ===========================================================================
# Tariff timeline + event study
# ===========================================================================
def load_timeline():
    for p in (ROOT / "tariff_timeline.csv", pathlib.Path(__file__).with_name("tariff_timeline.csv")):
        if p.exists():
            df = pd.read_csv(p, dtype=str, keep_default_na=False)
            df["ad_valorem_change_pp"] = pd.to_numeric(df.ad_valorem_change_pp, errors="coerce")
            log.info("tariff timeline: %d rows from %s (%d high, %d medium, %d low confidence)",
                     len(df), p, (df.confidence == "high").sum(), (df.confidence == "medium").sum(),
                     (df.confidence == "low").sum())
            return df
    log.warning("no tariff_timeline.csv found - event study skipped")
    return pd.DataFrame(columns=["effective_date", "action", "scope", "ad_valorem_change_pp",
                                 "hts_note", "source_url", "confidence"])


SCOPE_VALUE_BN = {"global": 3100, "universal": 3100, "all countries": 3100, "trading partners": 2200,
                  "china": 440, "canada": 410, "mexico": 505, "european union": 550, "eu": 550,
                  "japan": 150, "korea": 130, "india": 90, "brazil": 43, "uk": 65, "united kingdom": 65}
PRODUCT_VALUE_BN = 10.0     # placeholder for a product-specific action with no stated value
_DOLLARS = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s?B", re.I)
# an action only gets the partner's whole import total if its scope really is everything
_BROAD = re.compile(r"all goods|all shipments|all modes|universal|all countries|of us imports|"
                    r"broad product list|broad intermediate and consumer goods|most goods|"
                    r"reciprocal rate|certain goods|country-specific reciprocal", re.I)


def scope_value_bn(scope):
    """Approximate annual import value covered by an action, in $bn.

    Read off the scope text when it states one (most rows do).  When it does not, a
    product-specific action gets a small placeholder rather than the named partner's
    entire import total - without that guard "China, electric vehicles" would be scored
    as if it covered all $440B of Chinese imports.  Used to rank same-month events; the
    chosen event's value and duty impulse are also emitted per event in event_study
    (covered_import_value_bn / duty_impulse_bn), so for a product-specific action with no
    stated value that published field carries this placeholder - it is ranking metadata,
    not a measured trade volume, and must not be read as one.
    """
    m = _DOLLARS.search(str(scope))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    s = str(scope).lower()
    if _BROAD.search(s):
        for k, v in SCOPE_VALUE_BN.items():
            if k in s:
                return float(v)
    return PRODUCT_VALUE_BN


def pick_events(tl):
    """Major, verifiable events, de-duplicated to one per calendar month.

    Monthly CPI cannot separate two actions that took effect in the same month, so each
    month contributes at most one event.  The representative action is the one with the
    largest *duty impulse* - |rate change in pp| x annual import value covered - rather
    than the largest rate change, because a 50pp rate on one partner moves the consumer
    basket far less than a 10pp rate on everything.  Every other timeline row that shares
    the month is recorded as a bundled action so nothing is silently hidden.
    """
    if tl.empty:
        return tl
    d = tl.copy()
    d["ym"] = d.effective_date.str[:7]
    d["value_bn"] = d.scope.map(scope_value_bn)
    d["impulse"] = d.ad_valorem_change_pp.abs() * d.value_bn / 100.0
    elig = d[(d.confidence.isin(["high", "medium"])) & (d.ad_valorem_change_pp.abs() >= EVENT_MIN_PP)]
    if elig.empty:
        return elig
    # ties on impulse go to the action with the broader base: an aggregate CPI can see a
    # small rate on everything far better than a large rate on one partner.
    pick = (elig.sort_values(["impulse", "value_bn"], ascending=False)
                .drop_duplicates("ym", keep="first"))
    bundles = d.groupby("ym").action.apply(list).to_dict()
    pick = pick.assign(bundled=pick.ym.map(lambda m: bundles.get(m, [])))

    def label(row):
        """Name a month by the family when it is one legal action split over many rows."""
        pre = "_".join(row.action.split("_")[:2])
        kin = [a for a in row.bundled if a.startswith(pre + "_")]
        return pre if len(kin) >= 3 else row.action
    pick = pick.assign(event_label=[label(r) for r in pick.itertuples()]).sort_values("effective_date")
    log.info("event study: %d of %d timeline rows selected (|change| >= %.0fpp, confidence high/medium, "
             "one per month by duty impulse)", len(pick), len(tl), EVENT_MIN_PP)
    for r in pick.itertuples():
        log.info("  event %s %-26s impulse $%6.1fB  bundled with %s", r.effective_date, r.event_label, r.impulse,
                 [a for a in r.bundled if a != r.action] or "-")
    return pick


def build_panel(im, tiers, weights, events):
    """Item x relative-month panel of calendar-month-demeaned MoM and YoY (NSA throughout).

    NSA is used for every item so the exposed and domestic legs are on the same basis
    (mixing SA and NSA items would put a seasonal wedge into the difference).  Seasonality
    is removed by subtracting each item's own mean for that calendar month, computed
    excluding the +/-12 months around the event so the event cannot demean itself away.
    """
    base_all = im[im.item_code.isin(tiers.index)].copy()
    base_all["mo"] = base_all.ym.str[5:7]
    base_all["ord"] = base_all.ym.str[:4].astype(int) * 12 + base_all.ym.str[5:7].astype(int)
    base_all["tier"] = base_all.item_code.map(tiers)
    base_all["w"] = base_all.item_code.map(weights)
    rows, gaps = [], {}
    for ev in events.itertuples():
        e = int(ev.effective_date[:4]) * 12 + int(ev.effective_date[5:7])
        d = base_all.copy()
        d["rel"] = d["ord"] - e
        # calendar-month means computed away from the event so it cannot demean itself away
        mu = (d[d.rel.abs() > 12].groupby(["item_code", "mo"])[["mom_nsa", "yoy"]]
              .mean().rename(columns={"mom_nsa": "mu_mom", "yoy": "mu_yoy"}).reset_index())
        d = d.merge(mu, on=["item_code", "mo"], how="left")
        d["mom_d"] = d.mom_nsa - d.mu_mom
        d["yoy_d"] = d.yoy - d.mu_yoy
        w = d[(d.rel >= EVENT_LO[0]) & (d.rel <= EVENT_LO[1]) & d.tier.isin(["high", "low"])]
        for r in w.dropna(subset=["mom_d"]).itertuples():
            rows.append((ev.effective_date, r.item_code, int(r.rel),
                         None if pd.isna(r.yoy_d) else float(r.yoy_d), float(r.mom_d),
                         1 if r.tier == "high" else 0))
        # full-sample weighted exposed-minus-domestic gap series, for the HAC regression
        g = {}
        for ym, sub in d.dropna(subset=["mom_d", "w"]).groupby("ym"):
            hi = sub[sub.tier == "high"]; lo = sub[sub.tier == "low"]
            if hi.w.sum() > 0 and lo.w.sum() > 0:
                g[ym] = (hi.mom_d * hi.w).sum() / hi.w.sum() - (lo.mom_d * lo.w).sum() / lo.w.sum()
        gaps[ev.effective_date] = pd.Series(g).sort_index()
    return rows, gaps


def event_regression(gap, event_date):
    """Event study on the exposed-minus-domestic gap series with Newey-West HAC SEs.

    Sample: +/-24 months around the event.  Dummies for rel_month -6..+12; rel -24..-7 is
    the omitted baseline.  The pre-trend check regresses the gap on a linear term over
    rel -6..-1 and flags |t| > 2.
    """
    import statsmodels.api as sm
    if gap.empty:
        return None
    e = int(event_date[:4]) * 12 + int(event_date[5:7])
    rel = np.array([int(ym[:4]) * 12 + int(ym[5:7]) - e for ym in gap.index])
    m = (rel >= -24) & (rel <= 24)
    y = gap.values[m]
    r = rel[m]
    ok = np.isfinite(y)
    y, r = y[ok], r[ok]
    if len(y) < 24 or not ((r >= 0) & (r <= 12)).any():
        return None
    hs = [h for h in range(EVENT_LO[0], EVENT_LO[1] + 1) if (r == h).any()]
    X = np.column_stack([np.ones(len(y))] + [(r == h).astype(float) for h in hs])
    res = sm.OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
    coefs = [{"rel_month": h, "coef": float(res.params[i + 1]), "se": float(res.bse[i + 1]),
              "t": float(res.tvalues[i + 1])} for i, h in enumerate(hs)]
    post = [i + 1 for i, h in enumerate(hs) if 0 <= h <= 12]
    cum = float(res.params[post].sum()) if post else float("nan")
    cv = res.cov_params()
    cum_se = float(np.sqrt(cv[np.ix_(post, post)].sum())) if post else float("nan")
    pre = (r >= -6) & (r <= -1)
    slope = t_pre = float("nan")
    if pre.sum() >= 4:
        Xp = sm.add_constant(r[pre].astype(float))
        rp = sm.OLS(y[pre], Xp).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        slope, t_pre = float(rp.params[1]), float(rp.tvalues[1])
    ok_pre = bool(np.isfinite(t_pre) and abs(t_pre) <= 2.0)
    return {"coefs": coefs, "cum_0_12": cum, "cum_0_12_se": cum_se,
            "pretrend_slope": slope, "pretrend_t": t_pre, "pretrend_ok": ok_pre, "n_obs": int(len(y))}


# ===========================================================================
# BLS import price indexes by locality of origin
# ===========================================================================
def load_mxp(con, force=False):
    d = RAW / "ei"
    sp, _ = fetch(EI + "ei.series", d / "ei.series", force=force)
    dp, changed = fetch(EI + "ei.data.0.Current", d / "ei.data.0.Current", force=force)
    ser = pd.read_csv(sp, sep="\t", dtype=str, keep_default_na=False)
    ser.columns = [c.strip() for c in ser.columns]
    for c in ser.columns:
        ser[c] = ser[c].str.strip()
    co = ser[ser.index_code == "CO"]
    keep = set(co.series_id)
    dat = pd.read_csv(dp, sep="\t", dtype=str, keep_default_na=False)
    dat.columns = [c.strip() for c in dat.columns]
    dat["series_id"] = dat.series_id.str.strip()
    dat = dat[dat.series_id.isin(keep) & dat.period.str.strip().str.startswith("M") & (dat.period.str.strip() != "M13")]
    dat["ym"] = dat.year.str.strip() + "-" + dat.period.str.strip().str[1:]
    dat["value"] = pd.to_numeric(dat.value, errors="coerce")
    dat = dat.dropna(subset=["value"])
    con.execute("DELETE FROM p7_mxp")
    con.executemany("INSERT OR REPLACE INTO p7_mxp VALUES(?,?,?)",
                    dat[["series_id", "ym", "value"]].values.tolist())
    con.commit()
    log.info("p7_mxp: %d locality-of-origin import price series, %d observations, latest %s",
             dat.series_id.nunique(), len(dat), dat.ym.max())
    return ser.set_index("series_id")


# ===========================================================================
def main(argv):
    args = set(a for a in argv if a.startswith("--"))
    force = "--refresh-bea" in args
    basis = next((int(a.split("=")[1]) for a in args if a.startswith("--basis=")), 2017)
    con = init_db(); con.executescript(SCHEMA7); con.commit()
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    notes, valid = [], []

    # ---- CPI foundation ---------------------------------------------------
    im = pd.read_sql("SELECT item_code, ym, idx_nsa, mom_nsa, yoy, weight FROM cpi_item_month", con)
    names = pd.read_sql("SELECT item_code, item_name FROM cu_item", con).set_index("item_code").item_name
    wexp = pd.read_sql("SELECT weight_year, item_code, weight_u FROM cpi_weight WHERE is_leaf=1 AND matched=1", con)
    pub = im[im.item_code == "SA0"].set_index("ym").idx_nsa
    wyears = sorted(int(y) for y in wexp.weight_year.unique())
    leaf_by = {wy: wexp[wexp.weight_year == wy].set_index("item_code").weight_u for wy in wyears}
    top = max(wyears)
    log.info("CPI: weight years %s, %d leaves in %d, latest month %s", wyears, len(leaf_by[top]), top,
             im[im.idx_nsa.notna()].ym.max())

    # ---- BEA import content ----------------------------------------------
    paths, flags = bea_fetch_all(force=force)
    U, V, M, L, comnames = det_tables(paths, basis)
    sd, st, t, margin_rates, diag = commodity_shares(U, V, M, L, comnames)
    flags["leontief"] = True
    flags["margin_rates"] = margin_rates
    flags["commodity_diagnostics"] = diag
    flags["basis_year"] = basis

    share_rows, pce_basis = {}, {}
    if flags["path"] == "bridge":
        for by in (2007, 2012, 2017):
            try:
                Ub, Vb, Mb, Lb, nb = (U, V, M, L, comnames) if by == basis else det_tables(paths, by)
                sdb, stb, _, mrb, _ = (sd, st, t, margin_rates, diag) if by == basis else commodity_shares(Ub, Vb, Mb, Lb, nb)
                pce = bridge_shares(paths["bridge"], by, sdb, stb, mrb)
                rows, bad = item_shares_bridge(pce, list(leaf_by[top].index))
                share_rows[by] = rows
                if by == basis:
                    pce_basis = pce
                    flags["bridge_map_problems"] = [list(b) for b in bad]
                    flags["pce_categories"] = len(pce)
            except Exception as e:
                log.warning("benchmark %d failed (%s); skipping that basis year", by, e)
        method = "det{}_bridge_leontief".format(basis)
    else:
        share_rows[basis] = item_shares_haircut(sd, st, comnames, list(leaf_by[top].index))[0]
        method = "commodity_haircut"
        notes.append("PCE Bridge unavailable; ran the documented fallback path.")
    flags["method"] = method

    con.execute("DELETE FROM p7_import_share")
    for by, rows in share_rows.items():
        m = method if by == basis else method.replace(f"det{basis}", f"det{by}")
        con.executemany("INSERT OR REPLACE INTO p7_import_share VALUES(?,?,?,?,?)",
                        [(by, k, float(v[0]), float(v[1]), m) for k, v in rows.items()])
    con.commit()
    shares = pd.DataFrame(share_rows[basis], index=["share_direct", "share_total"]).T
    log.info("p7_import_share: %d basis years, %d items on basis %d; share_total median %.3f, p90 %.3f, max %.3f (%s)",
             len(share_rows), len(shares), basis, shares.share_total.median(), shares.share_total.quantile(0.9),
             shares.share_total.max(), shares.share_total.idxmax())

    # ---- tiers ------------------------------------------------------------
    def tier_of(s):
        return "high" if s >= CUT_HI else ("mid" if s >= CUT_LO else "low")
    con.execute("DELETE FROM p7_tier")
    tier_weight_rows, tiers_top = [], None
    for wy in wyears:
        lw = leaf_by[wy]
        rows = [(wy, c, tier_of(shares.share_total.get(c, 0.0)), float(shares.share_total.get(c, 0.0)))
                for c in lw.index]
        con.executemany("INSERT OR REPLACE INTO p7_tier VALUES(?,?,?,?)", rows)
        s = pd.Series({c: t for _, c, t, _ in rows})
        if wy == top:
            tiers_top = s
        for tname in ("high", "mid", "low"):
            sel = [c for c in lw.index if s[c] == tname]
            tier_weight_rows.append({"weight_year": wy, "tier": tname,
                                     "weight": float(lw[sel].sum()), "n_items": len(sel)})
    con.commit()
    tw = pd.DataFrame(tier_weight_rows)
    for r in tw[tw.weight_year == top].itertuples():
        log.info("tier %-4s (weight year %d): %6.3f%% of the basket across %d items", r.tier, top, r.weight, r.n_items)
    q = shares.share_total.describe(percentiles=[0.5, 0.75, 0.9, 0.95])
    log.info("share_total distribution over %d leaves: %s", len(shares),
             {k: round(float(v), 4) for k, v in q.items()})
    flags["cutoffs"] = {"high": CUT_HI, "low": CUT_LO,
                        "rationale": "high = import content of a purchaser dollar at or above 25%; low = below 10%. "
                                     "These are round a-priori thresholds, not natural breaks: the realised "
                                     "distribution is single-peaked near 0.05-0.10 with a long right tail and no gap "
                                     "at either cutoff, and 0.25 falls close to its 75th percentile, so tier "
                                     "membership near a boundary is sensitive to the exact threshold. Read the tiers "
                                     "as coarse buckets; services and shelter dominate the low tier, durable goods "
                                     "the high tier.",
                        "distribution": {k: float(v) for k, v in q.items()}}

    # ---- three aggregates + replica ---------------------------------------
    ch = Chainer(im[["item_code", "ym", "idx_nsa"]], {wy: list(leaf_by[wy].index) for wy in wyears}, pub)
    schemes = {}
    for name, want in (("exposed", "high"), ("mid", "mid"), ("domestic", "low")):
        wb = {}
        for wy in wyears:
            lw = leaf_by[wy]
            sel = [c for c in lw.index if tier_of(shares.share_total.get(c, 0.0)) == want]
            wb[wy] = (lw[sel] / lw[sel].sum() * 100) if sel and lw[sel].sum() > 0 else pd.Series(dtype=float)
        schemes[name] = wb
    schemes["official_replica"] = {wy: leaf_by[wy] / leaf_by[wy].sum() * 100 for wy in wyears}
    res = {}
    con.execute("DELETE FROM p7_index")
    for name, wb in schemes.items():
        lv, yoy = ch.run(wb, note=f"scheme {name}")
        res[name] = (lv, yoy)
        con.executemany("INSERT OR REPLACE INTO p7_index VALUES(?,?,?,?)",
                        [(name, ym, float(lv[ym]), None if pd.isna(yoy[ym]) else float(yoy[ym])) for ym in lv.index])
    con.commit()
    months = [ym for ym in res["official_replica"][1].index
              if all(not pd.isna(res[s][1].get(ym, np.nan)) for s in res)]
    latest = months[-1] if months else None
    if latest:
        log.info("latest month %s YoY: exposed %+.2f, mid %+.2f, domestic %+.2f, official replica %+.2f "
                 "(exposed-domestic gap %+.2fpp)", latest, res["exposed"][1][latest], res["mid"][1][latest],
                 res["domestic"][1][latest], res["official_replica"][1][latest],
                 res["exposed"][1][latest] - res["domestic"][1][latest])

    # ---- validation -------------------------------------------------------
    ann = annual_pce_import_content(paths, flags["annual_import_matrix_end_year"])
    lw = leaf_by[top]
    # A CPI item counts as "goods" when the PCE categories behind it carry trade margins,
    # i.e. they are physically distributed rather than billed as a service.
    is_good = {}
    for item, targets in P7_MAP.items():
        ps = [pce_basis[l]["prod_share"] for l, _, _ in targets if l in pce_basis]
        is_good[item] = bool(ps) and float(np.mean(ps)) < 0.98
    goods = [c for c in lw.index if is_good.get(c)]
    wmean_all = float((lw * shares.share_total.reindex(lw.index).fillna(0.0)).sum() / lw.sum())
    wmean_goods = float((lw[goods] * shares.share_total.reindex(goods)).sum() / lw[goods].sum()) if goods else 0.0
    # apples-to-apples with the published ballpark: weight by PCE purchasers' value, not
    # by CPI relative importance (the CPI basket is far more shelter-heavy than PCE).
    pw = [(v["pu"], v["share_total"]) for v in pce_basis.values() if v["pu"] > 0]
    pce_weighted = float(sum(p * s for p, s in pw) / sum(p for p, _ in pw)) if pw else float("nan")
    latest_ann = ann[-1]["direct_share_pce"] if ann else float("nan")
    flags["goods_items"] = len(goods)
    flags["weighted_means"] = {"cpi_basket_all": wmean_all, "cpi_basket_goods": wmean_goods,
                               "pce_weighted": pce_weighted}
    log.info("import-share validation: PCE-weighted total content %.4f; CPI-basket-weighted %.4f; "
             "CPI goods-only (%d items, %.1f%% of basket weight) %.4f",
             pce_weighted, wmean_all, len(goods), lw[goods].sum(), wmean_goods)
    if pce_basis:
        valid.append({"check": "pce_weighted_total_import_content", "ours": pce_weighted,
                      "published_or_expected": 0.11, "diff": pce_weighted - 0.11,
                      "ok": bool(0.08 <= pce_weighted <= 0.15),
                      "note": "Total (Leontief) import content of PCE, weighted by PCE purchasers' value. "
                              "The published ballpark is 10-12% of PCE. Accepted band 8-15%."})
        valid.append({"check": "cpi_goods_basket_import_content", "ours": wmean_goods,
                      "published_or_expected": wmean_all, "diff": wmean_goods - wmean_all,
                      "ok": bool(wmean_goods > wmean_all),
                      "note": "Goods must carry more import content than the basket as a whole "
                              "(the whole-basket figure is %.4f and is dragged down by shelter)." % wmean_all})
    valid.append({"check": "annual_direct_import_share_of_pce_latest_bea_year", "ours": latest_ann,
                  "published_or_expected": 0.11, "diff": latest_ann - 0.11, "ok": bool(0.04 <= latest_ann <= 0.16),
                  "note": "Direct (not Leontief) import content of PCE from the BEA annual summary tables, "
                          "year %s. Direct-only is a lower bound on total content." % (ann[-1]["year"] if ann else "-")})
    for wy in wyears:
        s = tw[tw.weight_year == wy].weight.sum()
        want = float(leaf_by[wy].sum())
        valid.append({"check": f"tier_weights_sum_{wy}", "ours": s, "published_or_expected": want,
                      "diff": s - want, "ok": bool(abs(s - want) < 1e-6),
                      "note": "exposed + mid + domestic must equal the leaf-universe weight"})
    p1 = pd.read_sql("SELECT ym, yoy FROM p1_index WHERE scheme='official_replica'", con).set_index("ym").yoy
    worst, worst_ym = 0.0, None
    for ym in res["official_replica"][1].index:
        a, b = res["official_replica"][1].get(ym), p1.get(ym)
        if pd.notna(a) and pd.notna(b) and abs(a - b) > worst:
            worst, worst_ym = abs(a - b), ym
    valid.append({"check": "official_replica_matches_p1", "ours": worst, "published_or_expected": 0.0,
                  "diff": worst, "ok": bool(worst <= 0.02),
                  "note": f"max |YoY difference| vs p1_index.official_replica over all months (worst at {worst_ym})"})
    for v in valid:
        log.info("validate %-42s ours %.4f vs %.4f (diff %+.4f) %s", v["check"], v["ours"],
                 v["published_or_expected"], v["diff"], "OK" if v["ok"] else "CHECK")
        con.execute("INSERT INTO validation VALUES(?,?,?,?,?,?,?)",
                    (now, "p7_" + v["check"], latest, v["ours"], v["published_or_expected"], v["diff"], int(v["ok"])))
    con.commit()

    # ---- event study ------------------------------------------------------
    tl = load_timeline()
    ev_json, used = [], set()
    if "--no-event" not in args and not tl.empty:
        evs = pick_events(tl)
        used = set(evs.effective_date)
        panel, gaps = build_panel(im, tiers_top, leaf_by[top], evs)
        con.execute("DELETE FROM p7_event")
        con.executemany("INSERT OR REPLACE INTO p7_event VALUES(?,?,?,?,?,?)", panel)
        con.execute("DELETE FROM p7_event_coef")
        n_hi = int((tiers_top == "high").sum()); n_lo = int((tiers_top == "low").sum())
        log.info("p7_event: %d panel rows over %d events (%d exposed items vs %d domestic items)",
                 len(panel), len(evs), n_hi, n_lo)
        for ev in evs.itertuples():
            r = event_regression(gaps.get(ev.effective_date, pd.Series(dtype=float)), ev.effective_date)
            if not r:
                log.info("event %s (%s): insufficient months, skipped", ev.effective_date, ev.event_label)
                continue
            con.executemany("INSERT OR REPLACE INTO p7_event_coef VALUES(?,?,?,?,?,?)",
                            [(ev.effective_date, c["rel_month"], c["coef"], c["se"], c["t"], int(r["pretrend_ok"]))
                             for c in r["coefs"]])
            ev_json.append({"event_date": ev.effective_date, "action": ev.event_label,
                            "representative_row": ev.action, "scope": ev.scope,
                            "ad_valorem_change_pp": float(ev.ad_valorem_change_pp),
                            "covered_import_value_bn": float(ev.value_bn),
                            "duty_impulse_bn": float(ev.impulse),
                            "bundled_actions": [a for a in ev.bundled if a != ev.action],
                            "confidence": ev.confidence, "source_url": ev.source_url,
                            "n_exposed": n_hi, "n_domestic": n_lo, **r})
            log.info("event %s %-26s cum(0..12) %+.2fpp (se %.2f)  pre-trend slope %+.4f (t %+.2f) %s",
                     ev.effective_date, ev.event_label, r["cum_0_12"], r["cum_0_12_se"],
                     r["pretrend_slope"], r["pretrend_t"], "OK" if r["pretrend_ok"] else "FAILS")
        con.commit()

    # ---- import prices by locality ---------------------------------------
    mxp_json = []
    if "--no-mxp" not in args:
        try:
            ser = load_mxp(con, force=force)
            want = ["EIUCOCHNTOT", "EIUCOCANTOT", "EIUCOMEXTOT", "EIUCOEECTOT", "EIUCOJPNTOT",
                    "EIUCOASEANTOT", "EIUCOCHNMANU", "EIUCOMEXMANU", "EIUCOCANMANU"]
            d = pd.read_sql("SELECT series_id, ym, value FROM p7_mxp", con)
            for sid in want:
                sub = d[d.series_id == sid].sort_values("ym")
                if sub.empty:
                    continue
                mxp_json.append({"series_id": sid,
                                 "label": ser.series_name.get(sid, sid) if hasattr(ser, "series_name") else sid,
                                 "series": [{"ym": r.ym, "value": float(r.value)} for r in sub.itertuples()]})
            miss = [s for s in want if s not in {m["series_id"] for m in mxp_json}]
            log.info("import price companion: %d of %d series exported%s", len(mxp_json), len(want),
                     f" (not published by BLS: {miss})" if miss else "")
        except Exception as e:
            log.warning("import price load failed: %s", e)
            notes.append(f"BLS import price series unavailable this run: {e}")

    # ---- JSON -------------------------------------------------------------
    series = []
    for ym in sorted(set().union(*[set(res[s][0].index) for s in res])):
        row = {"ym": ym}
        for s in res:
            lv, yoy = res[s]
            row[f"{s}_idx"] = None if ym not in lv.index or pd.isna(lv[ym]) else float(lv[ym])
            row[f"{s}_yoy"] = None if ym not in yoy.index or pd.isna(yoy[ym]) else float(yoy[ym])
        series.append(row)
    treemap = [{"item_code": c, "name": names.get(c, c), "weight": float(lw[c]),
                "share_total": float(shares.share_total.get(c, 0.0)),
                "share_direct": float(shares.share_direct.get(c, 0.0)),
                "tier": tier_of(shares.share_total.get(c, 0.0)),
                "major_group": MAJOR_GROUP.get(c[:3], "Other")}
               for c in lw.index]
    notes += [
        "Tier 1 (the three aggregates) is descriptive: it re-weights published CPI item indexes by "
        "import content. It is not an estimate of the price effect of any tariff.",
        "The event study is Tier 2. Read the pre-trend flag before reading the coefficient: an event "
        "whose pre-trend fails is telling you the two tiers were already diverging.",
        "Exposure is measured on the %d benchmark input-output year, before the 2018+ tariffs, so it "
        "cannot be contaminated by the tariffs being studied. It is also therefore stale with respect "
        "to any post-2017 re-sourcing." % basis,
        "BEA allocates a commodity's imports proportionally across its users, so an item's import "
        "share is the import share of its commodities, not of the specific varieties in the CPI sample.",
        "October 2025 has no CPI release; every series here is calendar-aligned and simply has no "
        "October 2025 observation.",
    ]
    out = {"generated_at": now, "latest_month": latest, "basis_year": basis, "method": flags,
           "cutoffs": flags["cutoffs"], "series": series,
           "tier_weights": tier_weight_rows, "treemap": treemap,
           "events": [{"effective_date": r.effective_date, "action": r.action, "scope": r.scope,
                       "ad_valorem_change_pp": None if pd.isna(r.ad_valorem_change_pp) else float(r.ad_valorem_change_pp),
                       "hts_note": r.hts_note, "source_url": r.source_url, "confidence": r.confidence,
                       "used_in_event_study": r.effective_date in used} for r in tl.itertuples()],
           "event_study": ev_json, "import_prices": mxp_json,
           "pce_import_content": ann, "validation": valid, "notes": notes}
    (OUT / "p7_tariff.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    log.info("wrote %s (%d KB)", OUT / "p7_tariff.json", (OUT / "p7_tariff.json").stat().st_size // 1024)
    return 0 if all(v["ok"] for v in valid) else 2


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)
    sys.exit(main(sys.argv[1:]))
