# -*- coding: utf-8 -*-
"""Builds data/spotcheck/spotcheck_fy2022.csv from figures read out of each city's
own FY2022 ACFR / budget.  Census fiscal year 2022 = the city fiscal year ending
between 1 Jul 2021 and 30 Jun 2022, so Sep-30 and Dec-31 cities contribute their
own 'FY2021' report.  All amounts converted to whole dollars."""
import csv, io

R = "2026-09-14"
K = 1000
rows = []


def add(city, st, fy_end, framing, police, fire, ps, den, den_label, pens, ems, aa, url, page):
    rows.append(dict(city=city, state=st, fiscal_year=2022, fy_end_date=fy_end, framing=framing,
                     police_usd=police, fire_usd=fire, public_safety_usd=ps, denominator_usd=den,
                     denominator_label=den_label, pensions_in_line=pens, fire_includes_ems=ems,
                     actual_or_adopted=aa, source_url=url, page=page, retrieved=R))


# ---------------- HOUSTON ----------------
U = "https://www.houstontx.gov/controller/acfr/acfr2022.pdf"
add("Houston", "TX", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 1205824 * K, 2896148 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.46 (printed 18)")
add("Houston", "TX", "2022-06-30", "acfr_general_fund_by_function", "", "", 1536217 * K, 2272963 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.50 (printed 22)")
add("Houston", "TX", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 1626241 * K, 4018653 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.51 (printed 23)")
add("Houston", "TX", "2022-06-30", "general_fund_budgetary_by_department", 954187 * K, 537300 * K, 1491487 * K, 2129417 * K, "General Operating Fund total expenditures, budgetary basis", "yes", "yes", "actual", U, "PDF p.172-174 (printed 142-144)")

# ---------------- SAN ANTONIO ----------------
U = "https://www.sanantonio.gov/Portals/0/Files/Finance/FY2021-ComprehensiveAnnualFinancialReport.pdf"
add("San Antonio", "TX", "2021-09-30", "acfr_statement_of_activities_governmental", "", "", 834517 * K, 2288186 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.53 (printed 15)")
add("San Antonio", "TX", "2021-09-30", "acfr_general_fund_by_function", "", "", 806554 * K, 1174620 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 18)")
add("San Antonio", "TX", "2021-09-30", "acfr_all_governmental_funds_by_function", "", "", 846099 * K, 2685730 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 18)")
add("San Antonio", "TX", "2021-09-30", "general_fund_budgetary_by_department", 479435 * K, 331762 * K, 811197 * K, 1216504 * K, "General Fund total expenditures, budgetary basis", "yes", "yes", "actual", U, "PDF p.358-360 (printed 266-268)")

# ---------------- DALLAS ----------------
U = "https://dallascityhall.com/departments/budget/financialtransparency/AuditedFinancials/afr_fy2021.pdf"
add("Dallas", "TX", "2021-09-30", "acfr_statement_of_activities_governmental", "", "", 306796 * K, 1451153 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.60 (printed 16)")
add("Dallas", "TX", "2021-09-30", "acfr_general_fund_by_function", "", "", 849288 * K, 1378311 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.64 (printed 20)")
add("Dallas", "TX", "2021-09-30", "acfr_all_governmental_funds_by_function", "", "", 897953 * K, 2636600 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.64 (printed 20)")
add("Dallas", "TX", "2021-09-30", "general_fund_budgetary_by_department", 526602 * K, 324067 * K, 866072 * K, 1477706 * K, "General Fund total expenditures, non-GAAP budgetary basis", "yes", "yes", "actual", U, "PDF p.66-67 (printed 22-23)")

# ---------------- AUSTIN ----------------
U = "https://austin.widen.net/content/hp0lghlmvz/original/annual_comprehensive_financial_report_2021.pdf"
add("Austin", "TX", "2021-09-30", "acfr_statement_of_activities_governmental", "", "", 853434 * K, 2113494 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.48 (printed 20, Exhibit A-2)")
add("Austin", "TX", "2021-09-30", "acfr_general_fund_by_function", "", "", 619373 * K, 1139244 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.52 (printed 24, Exhibit B-2)")
add("Austin", "TX", "2021-09-30", "acfr_all_governmental_funds_by_function", "", "", 640385 * K, 2096506 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.52 (printed 24, Exhibit B-2)")
add("Austin", "TX", "2021-09-30", "general_fund_by_department_gaap_actual", 314340 * K, 189247 * K, 619373 * K, 1139244 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.168 (printed 134, Exhibit E-2)")
add("Austin", "TX", "2021-09-30", "general_fund_by_department_budget_basis", 384835 * K, 212580 * K, 725620 * K, "", "not captured - budget-basis General Fund total not extracted", "yes", "no", "actual", U, "PDF p.168 (printed 134, Exhibit E-2)")

# ---------------- FORT WORTH ----------------
U1 = "https://www.fortworthtexas.gov/files/assets/public/v/2/finance/fy2022-annual-comprehensive-financial-report.pdf"
U2 = "https://www.fortworthtexas.gov/files/assets/public/v/1/the-fwlab/documents/budget-analysis/fy2021-budget/fy2021.pdf"
add("Fort Worth", "TX", "2021-09-30", "acfr_statement_of_activities_governmental_10yr_table", "", "", 812332 * K, 1503522 * K, "total governmental activities expenses", "yes", "no", "actual", U1, "FY2022 ACFR PDF p.205-206 (Table 2, printed 176-177), FY2021 column")
add("Fort Worth", "TX", "2021-09-30", "acfr_all_governmental_funds_by_function_10yr_table", "", "", 545069 * K, 1435678 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U1, "FY2022 ACFR PDF p.211-212 (Table 4, printed 182-183), FY2021 column")
add("Fort Worth", "TX", "2021-09-30", "general_fund_adopted_by_department", 272987345, 169139998, 442127343, 782064036, "General Fund total adopted expenses", "yes", "no", "adopted", U2, "FY2021 Adopted Budget PDF p.68 (printed 68)")

# ---------------- EL PASO ----------------
U = "https://www.elpasotexas.gov/assets/Documents/CoEP/Office-of-the-Comptroller/Fiscal-Reports/Financial-Reports/Previous-Cafrs/FY-2021-ACFR.pdf"
add("El Paso", "TX", "2021-08-31", "acfr_statement_of_activities_governmental", "", "", 303382283, 687412817, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.57 (printed 25)")
add("El Paso", "TX", "2021-08-31", "acfr_general_fund_by_function", "", "", 273071739, 415739917, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.60 (printed 28)")
add("El Paso", "TX", "2021-08-31", "acfr_all_governmental_funds_by_function", "", "", 328153721, 891107549, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.60 (printed 28)")
add("El Paso", "TX", "2021-08-31", "general_fund_budgetary_by_department", 150079146, 125878771, 275957917, 451864615, "General Fund total charges to appropriations, budgetary basis", "yes", "yes", "actual", U, "PDF p.170 (printed 138)")

# ---------------- NEW YORK ----------------
U = "https://comptroller.nyc.gov/wp-content/uploads/documents/ACFR-FY-2022.pdf"
add("New York", "NY", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 21422599 * K, 97116722 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.76 (printed 42)")
add("New York", "NY", "2022-06-30", "acfr_general_fund_by_function", "", "", 11936786 * K, 98933172 * K, "General Fund total expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.82 (printed 48)")
add("New York", "NY", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 12528342 * K, 120615550 * K, "total governmental funds expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.82 (printed 48)")
add("New York", "NY", "2022-06-30", "general_fund_by_agency", 5617677 * K, 2475973 * K, 11936786 * K, 98933172 * K, "General Fund total expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.452 (printed 418), Ten Year Trend, FY2022 column")

# ---------------- LOS ANGELES ----------------
U = "https://controller.lacity.gov/acfr22.pdf"
add("Los Angeles", "CA", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 2624309 * K, 7779395 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.57 (printed 28)")
add("Los Angeles", "CA", "2022-06-30", "acfr_general_fund_by_function", "", "", 3414251 * K, 5760833 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.61 (printed 32)")
add("Los Angeles", "CA", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 3844946 * K, 9695563 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.62 (printed 33)")
add("Los Angeles", "CA", "2022-06-30", "general_fund_budgetary_by_department", 1682653 * K, 746979 * K, 2564905 * K, 7999008 * K, "General Fund grand total expenditures, non-GAAP budgetary basis (includes $2,529,043k transfers to other funds)", "no", "yes", "actual", U, "PDF p.261 (printed 235)")

# ---------------- CHICAGO ----------------
U = "https://www.chicago.gov/content/dam/city/depts/fin/supp_info/CAFR/2021CAFR/ACFR_2021.pdf"
add("Chicago", "IL", "2021-12-31", "acfr_statement_of_activities_governmental", "", "", 4534257 * K, 9003930 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.34 (Exhibit 2)")
add("Chicago", "IL", "2021-12-31", "acfr_general_fund_by_function", "", "", 2372033 * K, 4683948 * K, "General Fund total expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.38-39 (Exhibit 4)")
add("Chicago", "IL", "2021-12-31", "acfr_all_governmental_funds_by_function", "", "", 2565257 * K, 9613478 * K, "total governmental funds expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.39 (Exhibit 4)")
add("Chicago", "IL", "2021-12-31", "general_fund_budgetary_by_department", 1620221941, 653804926, 2368569552, 4971362842, "General Fund total expenditures and encumbrances, budgetary basis", "no", "yes", "actual", U, "PDF p.138-143 (Schedule A-2)")

# ---------------- PHOENIX ----------------
U = "https://www.phoenix.gov/content/dam/phoenix/financesite/documents/acfr/final%20acfr%202022.pdf"
add("Phoenix", "AZ", "2022-06-30", "acfr_statement_of_activities_governmental", "", "", 1284353 * K, 3183079 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.48 (printed 24, Exhibit A-2)")
add("Phoenix", "AZ", "2022-06-30", "acfr_general_fund_by_function", "", "", 951323 * K, 1403406 * K, "General Fund total expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 32, Exhibit B-3)")
add("Phoenix", "AZ", "2022-06-30", "acfr_all_governmental_funds_by_function", "", "", 1172208 * K, 3568652 * K, "total governmental funds expenditures (GAAP)", "yes", "yes", "actual", U, "PDF p.56 (printed 32, Exhibit B-3)")
add("Phoenix", "AZ", "2022-06-30", "general_fund_budgetary_by_department", 577697 * K, 369879 * K, 947598 * K, 1361228 * K, "General Fund total expenditures, budget basis (excludes encumbrances)", "yes", "yes", "actual", U, "PDF p.179-180 (printed 155-156, Exhibit D-1)")

# ---------------- PHILADELPHIA ----------------
U = "https://www.phila.gov/media/20230322104950/annual-comp-financial-report-FY-2022.pdf"
add("Philadelphia", "PA", "2022-06-30", "acfr_statement_of_activities_governmental", 1219818 * K, 471534 * K, "", 7791522 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.42 (printed 22)")
add("Philadelphia", "PA", "2022-06-30", "acfr_general_fund_by_function", 1310837 * K, 503288 * K, "", 4917205 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.44 (printed 24)")
add("Philadelphia", "PA", "2022-06-30", "acfr_all_governmental_funds_by_function", 1316825 * K, 508397 * K, "", 8381245 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.44 (printed 24)")
add("Philadelphia", "PA", "2022-06-30", "general_fund_budgetary_by_department", 774948 * K, 370064 * K, "", 5338527 * K, "General Fund total obligations, budgetary basis", "no", "no", "actual", U, "PDF p.202-203 (printed 182-183)")

# ---------------- NASHVILLE-DAVIDSON ----------------
U = "https://www.nashville.gov/sites/default/files/2023-06/2022_Annual_Comprehensive_Financial_Report_Final_Published_06062023.pdf"
add("Nashville-Davidson", "TN", "2022-06-30", "acfr_statement_of_activities_governmental", 38343330, 18911793, "", 2031263933, "total governmental activities expenses (SEE NOTES - distorted by OPEB credit)", "yes", "yes", "actual", U, "PDF p.46 (Exhibit B-4)")
add("Nashville-Davidson", "TN", "2022-06-30", "acfr_general_fund_by_function", 351730198, 156953762, "", 1117624558, "GSD General Fund total expenditures (GAAP)", "no", "yes", "actual", U, "PDF p.52 (Exhibit B-10)")
add("Nashville-Davidson", "TN", "2022-06-30", "acfr_all_governmental_funds_by_function", 356905001, 157227244, "", 3465612699, "total governmental funds expenditures (GAAP, includes schools)", "no", "yes", "actual", U, "PDF p.52-53 (Exhibit B-10/B-11)")

# ---------------- VIRGINIA BEACH ----------------
U = "https://s3.us-east-1.amazonaws.com/virginia-beach-departments-docs/finance/Financials/AnnualReports/Fiscal-Year-2022-Annual-Report.pdf"
add("Virginia Beach", "VA", "2022-06-30", "acfr_statement_of_activities_governmental", 115206986, 72063215, "", 1409019651, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.72 (Exhibit 2)")
add("Virginia Beach", "VA", "2022-06-30", "acfr_general_fund_by_department", 109068186, 65593948, "", 1113635883, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.76 (Exhibit 4)")
add("Virginia Beach", "VA", "2022-06-30", "acfr_all_governmental_funds_by_department", 109936071, 72785714, "", 1616285220, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.76 (Exhibit 4)")

# ---------------- DENVER ----------------
U = "https://denvergov.org/files/assets/public/v/2/finance/documents/financial-reports/acfr/acfr_denver2021.pdf"
add("Denver", "CO", "2021-12-31", "acfr_statement_of_activities_governmental", "", "", 805223 * K, 2607226 * K, "total governmental activities expenses", "yes", "no", "actual", U, "PDF p.46 (printed 36)")
add("Denver", "CO", "2021-12-31", "acfr_general_fund_by_function", "", "", 574704 * K, 1300691 * K, "General Fund total expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.50 (printed 40)")
add("Denver", "CO", "2021-12-31", "acfr_all_governmental_funds_by_function", "", "", 670637 * K, 2644862 * K, "total governmental funds expenditures (GAAP)", "yes", "no", "actual", U, "PDF p.50 (printed 40)")
add("Denver", "CO", "2021-12-31", "general_fund_budgetary_by_department", 240863 * K, 108711 * K, 575296 * K, 1300690 * K, "General Fund total budget-basis expenditures", "yes", "no", "actual", U, "PDF p.188-189 (printed 178-179)")

# ---------------- SEATTLE ----------------
U = "https://www.seattle.gov/documents/Departments/CityFinance/FinancialServices/CAFR/comprehensive-annual-financial-report-2021.pdf"
add("Seattle", "WA", "2021-12-31", "acfr_statement_of_activities_governmental", "", "", 536517 * K, 2357850 * K, "total governmental activities expenses", "yes", "yes", "actual", U, "PDF p.45 (printed 26, Exhibit B-2)")
add("Seattle", "WA", "2021-12-31", "acfr_general_fund_by_function", "", "", 777206 * K, 1720046 * K, "General Fund total expenditures (GAAP); public safety = 774,534k current + 2,672k capital outlay", "yes", "yes", "actual", U, "PDF p.51 (printed 32, Exhibit B-4)")
add("Seattle", "WA", "2021-12-31", "acfr_all_governmental_funds_by_function", "", "", 781573 * K, 2948156 * K, "total governmental funds expenditures (GAAP); public safety = 778,683k current + 2,890k capital outlay", "yes", "yes", "actual", U, "PDF p.51 (printed 32, Exhibit B-4)")
add("Seattle", "WA", "2021-12-31", "general_fund_budgetary_by_department", 359546 * K, 272706 * K, "", 1974922 * K, "General Fund total expenditures and encumbrances, budget basis", "partly", "yes", "actual", U, "PDF p.148-152 (printed 129-133, Schedule C-1)")

cols = ["city", "state", "fiscal_year", "fy_end_date", "framing", "police_usd", "fire_usd",
        "public_safety_usd", "denominator_usd", "denominator_label", "pensions_in_line",
        "fire_includes_ems", "actual_or_adopted", "source_url", "page", "retrieved"]

with io.open("spotcheck_fy2022.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("rows:", len(rows))
