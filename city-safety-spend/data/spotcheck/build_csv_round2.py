# -*- coding: utf-8 -*-
"""Builds data/spotcheck/spotcheck_fy2022_round2.csv (second, non-Texas round) from
figures read out of each city's own FY2022 ACFR / budget.  Same schema and rules as
build_csv.py: Census fiscal year 2022 = the city fiscal year ending between 1 Jul 2021
and 30 Jun 2022, so Sep-30 and Dec-31 cities contribute their own 'FY2021' report.
All amounts converted to whole dollars.  See NOTES.md, section 'Round 2 (non-Texas)'."""
import csv, io

R = "2026-09-14"
K = 1000
rows = []


def add(city, st, fy_end, framing, police, fire, ps, den, den_label, pens, ems, aa, url, page):
    rows.append(dict(city=city, state=st, fiscal_year=2022, fy_end_date=fy_end, framing=framing,
                     police_usd=police, fire_usd=fire, public_safety_usd=ps, denominator_usd=den,
                     denominator_label=den_label, pensions_in_line=pens, fire_includes_ems=ems,
                     actual_or_adopted=aa, source_url=url, page=page, retrieved=R))


# ---------------- SAN DIEGO ----------------
U = "https://www.sandiego.gov/sites/default/files/acfr-2022.pdf"
add("San Diego", "CA", "2022-06-30", "acfr_statement_of_activities_governmental", 532695 * K, 305596 * K, "", 2226072 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.56 (printed 52)")
add("San Diego", "CA", "2022-06-30", "acfr_general_fund_by_function", 592198 * K, 327026 * K, "", 1877289 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.60 (printed 56)")
add("San Diego", "CA", "2022-06-30", "acfr_all_governmental_funds_by_function", 602919 * K, 341393 * K, "", 2581373 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.60 (printed 56)")
add("San Diego", "CA", "2022-06-30", "general_fund_budgetary_by_department", 600763 * K, 327701 * K, "", 1669283 * K, "General Fund total expenditures, budgetary basis (budgeted General Fund only; the GAAP General Fund folds in additional non-budgeted funds)", "yes", "yes", "actual", U, "PDF p.194 (printed 190)")

# ---------------- SAN JOSE ----------------
U = "https://www.sanjoseca.gov/home/showpublisheddocument/92712/638055767362200000"
U2 = "https://www.sanjoseca.gov/home/showpublisheddocument/90025/638001720644200000"
add("San Jose", "CA", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 614802 * K, 1997994 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.59 (printed 28)")
add("San Jose", "CA", "2022-06-30", "acfr_general_fund_by_function", "", "", 724909 * K, 1219138 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.64 (printed 33)")
add("San Jose", "CA", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 727257 * K, 2116941 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.64-65 (printed 33-34)")
add("San Jose", "CA", "2022-06-30", "general_fund_budgetary_by_function", "", "", 730982 * K, 1289291 * K, "General Fund total expenditures, budgetary basis (includes encumbrances)", "yes", "no", "actual", U, "PDF p.223 (printed 192)")
add("San Jose", "CA", "2022-06-30", "general_fund_by_department_annual_report", 486209322, 269091701, "", 1606749398, "General Fund total expenditures incl. encumbrances, budget basis (City Manager's 2021-2022 Annual Report, Table D; departmental subtotal 1,101,885,452 + non-departmental 504,863,946)", "yes", "no", "actual", U2, "PDF p.5 (printed 55, Table D)")

# ---------------- COLUMBUS ----------------
U = "https://www.columbus.gov/files/sharedassets/city/v/1/finance/financial-reports/2021_acfr.pdf"
add("Columbus", "OH", "2021-12-31", "acfr_statement_of_activities_governmental", "", "", 680449 * K, 1385119 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.52 (printed 44)")
add("Columbus", "OH", "2021-12-31", "acfr_general_fund_by_function", "", "", 662740 * K, 954434 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 48, Exhibit 4)")
add("Columbus", "OH", "2021-12-31", "acfr_all_governmental_funds_by_function", "", "", 673479 * K, 1876394 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 48, Exhibit 4)")
add("Columbus", "OH", "2021-12-31", "general_fund_budgetary_by_department", 386375712, 273109487, 687075297, 925286013, "General Fund total expenditures, budget basis (Exhibit A-1; includes 1,305,927 expenditures paid through county auditor)", "yes", "yes", "actual", U, "PDF p.154-156 (printed 146-148, Exhibit A-1); fund total also PDF p.141 (printed 133, Exhibit 10)")

# ---------------- CHARLOTTE ----------------
U = "https://www.charlottenc.gov/files/sharedassets/city/v/1/city-government/departments/documents/finance/publications/2023/cacfr/acfr-2022-web-final.pdf"
U2 = "https://www.charlottenc.gov/files/sharedassets/city/v/1/city-government/documents/fy_2022_adopted_budget.pdf"
add("Charlotte", "NC", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 500627 * K, 1019221 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.48 (printed 22)")
add("Charlotte", "NC", "2022-06-30", "acfr_general_fund_by_function", "", "", 455788 * K, 736376 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.52 (printed 26)")
add("Charlotte", "NC", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 470984 * K, 1389405 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.52 (printed 26)")
add("Charlotte", "NC", "2022-06-30", "general_fund_budgetary_by_function", "", "", 457539 * K, 769566 * K, "General Fund total charges to appropriations, budgetary basis (includes 32,597k transfers out)", "yes", "no", "actual", U, "PDF p.54 (printed 28)")
add("Charlotte", "NC", "2022-06-30", "general_fund_adopted_by_department", 300877459, 144575666, "", 750720000, "General Fund total adopted expenditures FY2022 (includes 58,187,804 non-departmental)", "yes", "no", "adopted", U2, "FY2022 Adopted Budget PDF p.59 (printed 19)")

# ---------------- INDIANAPOLIS (City of Indianapolis, component unit of the Consolidated City-County) ----------------
U = "https://www.in.gov/sboa/WebReports/B59599.pdf"
add("Indianapolis", "IN", "2021-12-31", "acfr_statement_of_activities_governmental", "", "", 480821 * K, 1082029 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.70 (printed 27)")
add("Indianapolis", "IN", "2021-12-31", "acfr_general_fund_by_function", "", "", 507373 * K, 794012 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.73 (printed 30)")
add("Indianapolis", "IN", "2021-12-31", "acfr_all_governmental_funds_by_function", "", "", 531564 * K, 1347896 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.73 (printed 30)")
add("Indianapolis", "IN", "2021-12-31", "acfr_general_fund_subfund_gaap", 270450 * K, 195005 * K, 507373 * K, 794012 * K, "General Fund total expenditures (GAAP); police/fire = public safety expenditures of the Metropolitan Police and Fire subfunds of the General Fund", "yes", "no", "actual", U, "PDF p.163-164 (printed 114-115)")
add("Indianapolis", "IN", "2021-12-31", "general_fund_budgetary_by_department", 245906 * K, 168925 * K, 458762 * K, 834885 * K, "General Fund total expenditures, budgetary basis; police/fire = public safety expenditures of the Metropolitan Police and Fire subfunds", "yes", "no", "actual", U, "PDF p.166-167 (printed 117-118); fund total PDF p.140 (printed 95)")

# ---------------- JACKSONVILLE (Duval consolidated; police = Office of the Sheriff) ----------------
U = "https://www.jacksonville.gov/getContentAsset/7ac7f919-94de-4170-a8b8-b105d54cb1eb/135b97c9-84fa-4e82-b956-0fbccec4aa1f/jacksonville-2021-ACFR.pdf?language=en"
add("Jacksonville", "FL", "2021-09-30", "acfr_statement_of_activities_governmental", "", "", 1161203 * K, 1934545 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.58 (printed 27)")
add("Jacksonville", "FL", "2021-09-30", "acfr_general_fund_by_function", "", "", 779318 * K, 1184133 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.67 (printed 36)")
add("Jacksonville", "FL", "2021-09-30", "acfr_all_governmental_funds_by_function", "", "", 880594 * K, 1950277 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.67-68 (printed 36-37)")
add("Jacksonville", "FL", "2021-09-30", "general_fund_budgetary_by_department", 484725 * K, 287609 * K, "", 1184133 * K, "General Fund total expenditures, actual (GAAP column of the budgetary schedule); police = Office of the Sheriff, fire = Fire/Rescue; budgetary basis adds encumbrances (Sheriff 8,945k, Fire 914k, fund 1,210,969k)", "yes", "yes", "actual", U, "PDF p.195 (printed 164)")

# ---------------- DETROIT ----------------
U = "https://detroitmi.gov/sites/detroitmi.localhost/files/2022-12/City%20of%20Detroit%20FY22%20ACFR%20FINAL%2012.22.2022.pdf"
U2 = "https://detroitmi.gov/sites/detroitmi.localhost/files/2023-03/FY%202024-2027%20Mayor%27s%20Proposed%20Four-Year%20Financial%20Plan%20Section%20B%20%203.2.23.pdf"
add("Detroit", "MI", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 593992170, 1741359983, "total governmental activities expenses (function = Public protection)", "partly", "yes", "actual", U, "PDF p.49 (printed 21)")
add("Detroit", "MI", "2022-06-30", "acfr_general_fund_by_function", "", "", 503652166, 981932844, "General Fund total expenditures (GAAP) (function = Public protection)", "partly", "yes", "actual", U, "PDF p.54 (printed 26)")
add("Detroit", "MI", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 546197997, 1603125255, "total governmental funds expenditures (GAAP) (function = Public protection)", "partly", "yes", "actual", U, "PDF p.54 (printed 26)")
add("Detroit", "MI", "2022-06-30", "general_fund_by_department_four_year_plan", 322030865, 136894832, "", 1207859359, "General Fund total expenditures, budgetary basis (ACFR budgetary schedule); police/fire = FY2022 actual General Fund department totals from the FY2024-27 Four-Year Financial Plan department budget summaries", "partly", "yes", "actual", U2, "Section B PDF p.125 (B24-4, Fire) and B37-7 (Police); denominator ACFR PDF p.153 (printed 125)")
add("Detroit", "MI", "2022-06-30", "all_funds_by_department_four_year_plan", 337163285, 137096085, "", "", "not captured - all-funds city total is not on the departmental pages", "partly", "yes", "actual", U2, "Section B PDF p.125 (B24-4, Fire) and B37-7 (Police)")
add("Detroit", "MI", "2022-06-30", "general_fund_budgetary_appropriation_lines", 270816113, 133838476, "", 1207859359, "General Fund total expenditures, budgetary basis; police/fire = sums of ACFR appropriation lines labelled Police/Fire (UNDERSTATES police by ~51m vs the department total - see notes)", "partly", "yes", "actual", U, "PDF p.152-153 (printed 124-125)")

# ---------------- BOSTON ----------------
U = "https://www.boston.gov/sites/default/files/file/2023/03/2022-2023-ACFR_Final.pdf"
add("Boston", "MA", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 1172308 * K, 4327037 * K, "total governmental activities expenses (includes schools 2,123,695k)", "yes", "no", "actual", U, "PDF p.44 (printed 21)")
add("Boston", "MA", "2022-06-30", "acfr_general_fund_by_function", "", "", 797386 * K, 3977082 * K, "General Fund total expenditures (GAAP); retirement costs 502,585k and other employee benefits 258,112k are separate lines", "no", "no", "actual", U, "PDF p.48 (printed 25)")
add("Boston", "MA", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 826121 * K, 4882523 * K, "total governmental funds expenditures (GAAP, includes schools 1,509,522k)", "no", "no", "actual", U, "PDF p.48 (printed 25)")
add("Boston", "MA", "2022-06-30", "general_fund_budgetary_by_department", 420412 * K, 289514 * K, 784791 * K, 3838630 * K, "General Fund total expenditures, budgetary basis (includes Boston Public Schools 1,294,706k, charter tuition 229,842k; pension costs 327,014k separate)", "no", "no", "actual", U, "PDF p.112-113 (printed 89-90)")

# ---------------- BALTIMORE ----------------
U = "https://s3.amazonaws.com/baltimorecity.gov.if-us-east-1/s3fs-public/2024-02/acfr_cy_22.pdf"
add("Baltimore", "MD", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 495295 * K, 2210501 * K, "total governmental activities expenses (function = Public safety and regulation; SEE NOTES - accrual pension credit)", "yes", "yes", "actual", U, "PDF p.45 (printed 21)")
add("Baltimore", "MD", "2022-06-30", "acfr_general_fund_by_function", "", "", 867723 * K, 2170834 * K, "General Fund total expenditures (GAAP) (function = Public safety and regulation)", "yes", "yes", "actual", U, "PDF p.47 (printed 23)")
add("Baltimore", "MD", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 912725 * K, 2702306 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.47 (printed 23)")
add("Baltimore", "MD", "2022-06-30", "general_fund_budgetary_by_department", 513796 * K, 271684 * K, "", 1999523 * K, "General Fund total expenditures and encumbrances, budgetary basis (includes 275,514k Baltimore City Public School System)", "yes", "yes", "actual", U, "PDF p.121 (printed 97)")

# ---------------- MEMPHIS ----------------
U = "https://memphistn.gov/wp-content/uploads/2025/01/FY22-Printable_Complete-Book_Annual-Comprehensive-Financial-Report-1.pdf"
add("Memphis", "TN", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 614942 * K, 1399380 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.68 (printed 47, Exhibit A-2)")
add("Memphis", "TN", "2022-06-30", "acfr_general_fund_by_function", "", "", 483645 * K, 747177 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.72 (printed 51, Exhibit A-5)")
add("Memphis", "TN", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 508638 * K, 1353785 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.72 (printed 51, Exhibit A-5)")
add("Memphis", "TN", "2022-06-30", "general_fund_budgetary_by_department", 283012 * K, 202506 * K, 485518 * K, 746812 * K, "General Fund total expenditures, basis of budgeting (Exhibit A-8; excludes 4,061k transfers out)", "yes", "yes", "actual", U, "PDF p.78-79 (printed 57-58, Exhibit A-8)")

# ---------------- LAS VEGAS (police = joint Las Vegas Metropolitan Police Department) ----------------
U = "https://files.lasvegasnevada.gov/finance/2022-CLV_Annual_Comprehensive_Financial_Report-Final-Updated-Feb-9-2023.pdf"
add("Las Vegas", "NV", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 268545568, 666560763, "total governmental activities expenses (SEE NOTES - accrual PERS credit; fund-level public safety is 403m)", "yes", "yes", "actual", U, "PDF p.50 (printed 40)")
add("Las Vegas", "NV", "2022-06-30", "acfr_general_fund_by_function", "", "", 403404813, 589757774, "General Fund total expenditures (GAAP); public safety current expenditures only (public safety capital outlay 66,037 shown separately)", "yes", "yes", "actual", U, "PDF p.56 (printed 46)")
add("Las Vegas", "NV", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 409076733, 900939412, "total governmental funds expenditures (GAAP); public safety current only (public safety capital outlay 17,626,994 shown separately)", "yes", "yes", "actual", U, "PDF p.56 (printed 46)")
add("Las Vegas", "NV", "2022-06-30", "general_fund_budgetary_by_department", 167253759, 155609043, 403470850, 567887104, "General Fund total expenditures, budget basis; police = 151,525,764 LVMPD contribution + 15,727,995 city marshals; fire = 155,410,514 fire and rescue + 198,529 emergency management; public safety also includes corrections 57,299,066", "yes", "yes", "actual", U, "PDF p.59-60 (printed 49-50); detail PDF p.152-153 (printed 136-137)")
add("Las Vegas", "NV", "2022-06-30", "lvmpd_city_contribution", 151464415, "", "", 567887104, "General Fund total expenditures, budget basis; police = amount the City paid Metro in FY2022 per the joint-venture note (City funding share 36.4%)", "yes", "yes", "actual", U, "PDF p.91 (printed 81, Note 6.A)")
add("Las Vegas", "NV", "2022-06-30", "lvmpd_joint_venture_total_expenditures", 648345618, "", "", 648345618, "LVMPD total expenditures FY2022 (joint venture with Clark County, all funding partners; City of Las Vegas funds 36.4%) - NOT a city denominator", "yes", "yes", "actual", U, "PDF p.91 (printed 81, Note 6.A)")

# ---------------- LOUISVILLE (Metro consolidated) - FY2022 ACFR not retrievable; see notes ----------------
U = "https://louisvilleky.gov/sites/default/files/2024-02/fy23_acfr.pdf"
U2 = "https://louisvilleky.gov/sites/default/files/2022-05/2022-2023%20MAYOR'S%20RECOMMENDED%20EXECUTIVE%20BUDGET%20with%20Bookmarks.pdf"
add("Louisville", "KY", "2022-06-30", "acfr_statement_of_activities_governmental_10yr_table", 213042242, "", 209217583, 1070721978, "total governmental activities expenses, FY2022 column of the FY2023 ACFR ten-year table; police = Louisville Metro Police Department; public_safety_usd = 'Public Protection' group (Fire, EMS, MetroSafe, Corrections, Youth Transitional Services, Animal Services, CJC, closed police/fire pension funds) which EXCLUDES LMPD", "yes", "no", "actual", U, "FY2023 ACFR PDF p.167 (printed 167), FY2022 column")
add("Louisville", "KY", "2022-06-30", "acfr_all_governmental_funds_by_department_10yr_table", 199758816, "", 193090835, 1139550025, "total governmental funds expenditures (GAAP), FY2022 column of the FY2023 ACFR ten-year table; public_safety_usd = 'Public Protection' group excluding LMPD (see above)", "yes", "no", "actual", U, "FY2023 ACFR PDF p.170 (printed 170), FY2022 column")
add("Louisville", "KY", "2022-06-30", "all_funds_adopted_by_department", 195895700, 72346000, "", 830291200, "All-funds operating appropriations, FY2021-22 original budget (total appropriations 1,089,108,834 less 258,817,634 capital/debt service)", "yes", "no", "adopted", U2, "FY2022-23 Recommended Executive Budget PDF p.88 (printed 81); p.73-75 (printed 66-68)")
add("Louisville", "KY", "2022-06-30", "general_fund_adopted_by_department", 185295900, 69355000, "", 717305100, "General Fund group (General Fund/Municipal Aid/County Road Aid/Community Development/Capital-Other) operating appropriations, FY2021-22 original budget = 771,577,998 total appropriations less 54,272,898 capital/debt service", "yes", "no", "adopted", U2, "FY2022-23 Recommended Executive Budget PDF p.65-67 (printed 58-60)")

# ---------------- ST. LOUIS ----------------
U = "https://www.stlouis-mo.gov/government/departments/comptroller/documents/upload/CityofStLouisMissouri_ACFR-FY22.pdf"
add("St. Louis", "MO", "2022-06-30", "acfr_statement_of_activities_governmental", 170281 * K, 81272 * K, "", 824931 * K, "total governmental activities expenses (a third public safety line, 'Other', is 54,349k)", "yes", "yes", "actual", U, "PDF p.37 (printed 23)")
add("St. Louis", "MO", "2022-06-30", "acfr_general_fund_by_function", 155724 * K, 72435 * K, "", 503228 * K, "General Fund total expenditures (GAAP) (public safety 'Other' 35,378k)", "yes", "yes", "actual", U, "PDF p.40 (printed 26)")
add("St. Louis", "MO", "2022-06-30", "acfr_all_governmental_funds_by_function", 198236 * K, 85847 * K, "", 911821 * K, "total governmental funds expenditures (GAAP) (public safety 'Other' 53,563k)", "yes", "yes", "actual", U, "PDF p.40 (printed 26)")
add("St. Louis", "MO", "2022-06-30", "general_fund_budgetary_by_department", 152793 * K, 71371 * K, "", 483095 * K, "General Fund total expenditures, budgetary basis; police = Police Department 125,625k + Police Retirement System 26,340k + prior-year encumbrance 828k; fire = Fire Department Operations 62,668k + Firemen's Retirement System 8,703k", "yes", "yes", "actual", U, "PDF p.173-174 (printed 158-159, Schedule 1)")

# ---------------- ATLANTA ----------------
U = "https://www.atlantaga.gov/home/showpublisheddocument/57848/638083685314830000"
add("Atlanta", "GA", "2022-06-30", "acfr_statement_of_activities_governmental", 195638 * K, 79966 * K, "", 943369 * K, "total governmental activities expenses (separate Corrections line 11,712k)", "yes", "no", "actual", U, "PDF p.54 (printed 26)")
add("Atlanta", "GA", "2022-06-30", "acfr_general_fund_by_function", 226073 * K, 102902 * K, "", 640760 * K, "General Fund total expenditures (GAAP) (Corrections 14,397k separate)", "yes", "no", "actual", U, "PDF p.58 (printed 30)")
add("Atlanta", "GA", "2022-06-30", "acfr_all_governmental_funds_by_function", 255441 * K, 105015 * K, "", 1174612 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.58 (printed 30)")
add("Atlanta", "GA", "2022-06-30", "general_fund_budgetary_by_department", 226073 * K, 102902 * K, "", 640760 * K, "General Fund total expenditures, budget basis (Atlanta budgets on the GAAP basis, so identical to the fund statement)", "yes", "no", "actual", U, "PDF p.199 (printed 166)")

cols = ["city", "state", "fiscal_year", "fy_end_date", "framing", "police_usd", "fire_usd",
        "public_safety_usd", "denominator_usd", "denominator_label", "pensions_in_line",
        "fire_includes_ems", "actual_or_adopted", "source_url", "page", "retrieved"]

with io.open("spotcheck_fy2022_round2.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("rows:", len(rows))
