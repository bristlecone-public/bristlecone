# Phase 2 Roadmap: Expanding City Safety Spend

**Date:** 2026-09-14  
**Status:** Proposal / Strategic Roadmap  
**Context:** Following the completion of Phase 1 (establishing the standardized 1967–2024 panel of police and fire expenditures across 332 large U.S. municipalities with cross-source validation), this document outlines the high-impact expansions for Phase 2.

---

## Objective

Phase 1 established the baseline financial facts: what each city spends on police and fire, how that spending compares across four standardized denominators, and why Census figures diverge from city budget speeches and ACFR GAAP reports.

Phase 2 transitions the project from a benchmark financial dataset into the definitive reference on municipal public safety operations by connecting **dollars to personnel, service demand, fiscal trade-offs, and economic context.**

---

## 1. Core Data Augmentations

### A. Link Public Employment & Payroll Microdata (Census ASPEP)
In municipal public safety, **85% to 90% of operating expenditures are personnel costs** (salaries, overtime, pensions, and healthcare). Adding headcount data answers whether high spending is driven by high staffing levels or high per-employee costs.
* **Source:** U.S. Census Bureau, *Annual Survey of Public Employment & Payroll (ASPEP)*, Individual Unit Files (which share the same Census government identifiers).
* **Key Metrics:**
  * Full-time and part-time headcounts and monthly payroll for **Function 62 (Police – Sworn vs. Civilian)** and **Function 24 (Fire)**.
  * **Service Intensity:** Sworn police officers and career firefighters per 1,000 residents.
  * **Civilianization Ratio:** Percentage of department personnel who are civilian dispatchers, analysts, and evidence technicians vs. armed sworn officers.
  * **Average Personnel Cost per Employee:** Department expenditure divided by Full-Time Equivalents (FTEs), separating high-staffing departments from high-compensation/high-fringe departments.

### B. Deflation & Cost-of-Living Normalization
* **Inflation Adjustment (1967–2024):** Integrate the Bureau of Labor Statistics (BLS) **CPI-U** (or the Bureau of Economic Analysis State & Local Government Consumption Deflator) to allow users to view historical series in real 2024 dollars alongside nominal dollars.
* **Regional Price Parity (RPP):** An entry-level police officer or firefighter in San Francisco, Seattle, or New York commands more than $150,000–$200,000 in total compensation, while an officer in El Paso or Oklahoma City commands $75,000–$90,000. Integrating BEA **Regional Price Parities** normalizes spending against prevailing regional public-sector labor costs and purchasing power.

---

## 2. Contextual & Operational Datasets

Financial allocations are frequently evaluated against the demand for public services: *Is a high budget allocation a response to high operational demand, or a reflection of legacy cost structures?*

### A. Police Demand: FBI UCR / NIBRS Crime Data
* **Source:** FBI Uniform Crime Reporting (UCR) Program and National Incident-Based Reporting System (NIBRS).
* **Key Metrics:** Violent crime rate and property crime rate per 1,000 residents.
* **Analytical Framework:** A 2×2 classification matrix comparing safety effort to crime burden:
  1. *High spend, high crime:* Resource-intensive response to severe public safety demand.
  2. *Low spend, high crime:* Under-resourced or distressed municipal environments.
  3. *High spend, low crime:* High-amenity, deterrence-focused suburban or affluent municipalities.
  4. *Low spend, low crime:* Low-demand baseline environments.

### B. Fire & Rescue Demand: EMS Call Volume Split
* **Source:** U.S. Fire Administration (USFA) / National Fire Incident Reporting System (NFIRS) annual incident profiles.
* **Key Metrics:** Ratio of emergency medical service (EMS) calls to fire suppression calls (typically 75% to 85% medical in major metropolitan areas).
* **Analytical Value:** Highlights that modern fire department budgets predominantly finance mobile emergency medicine, rescue, and hazardous response, rather than structural firefighting.

---

## 3. Analytical Frameworks & Derived Indexes

### A. The "Municipal Trade-Off" (Crowd-Out) Index
When public safety consumes 35% to 55% of core municipal operating capacity, what services are constrained?
* Construct a standardized metric comparing public safety expenditures against all other municipal functions:
  $$\text{Safety Multiplier} = \frac{\text{Police (62)} + \text{Fire (24)}}{\text{Parks (61)} + \text{Libraries (60)} + \text{Community Dev/Housing (50)} + \text{Roads (44)}}$$
* This metric quantifies the municipal trade-off: in some jurisdictions, public safety outspends community amenities and infrastructure by 4:1; in others, the ratio is close to 1:1.

### B. Capital vs. Operating Expenditure Decomposition
* Census microdata splits current operations (`E`) from construction (`F`) and equipment capital outlay (`G`).
* Separating these characters identifies whether a one-year budgetary spike represents permanent baseline expansion or temporary capital investments (e.g., replacement of a radio dispatch network, new police headquarters, or fire fleet replenishment).

### C. Comprehensive Community Burden (Overlying Governments)
* Phase 1 integrates Lincoln FiSC for 212 legacy cities to account for overlying county and special district spending.
* For the remaining 120 Sunbelt suburban cities not included in FiSC (e.g., Plano, Frisco, Irvine, Lakewood), construct an automated allocation algorithm that apportions home-county sheriff and corrections spending by population to provide an estimated **"Full Community Public Safety Burden"** across all 332 cities.

---

## 4. Product & Dashboard Enhancements

### A. "Find My Peer Cities" Engine
* Rather than sorting strictly by population or state, allow users to select any city and instantly generate a comparison group of 5 to 10 true institutional peers based on:
  1. Population band (±25%).
  2. Governance structure (plain municipality vs. consolidated city-county vs. independent city).
  3. Service delivery model (in-house fire vs. fire district; in-house police vs. sheriff contract).
  4. Regional economic context (RPP cost tier).

### B. Historical Milestone & Policy Annotations
Incorporate interactive policy markers onto the 1967–2024 historical trend charts:
* **1994:** Federal Violent Crime Control and Law Enforcement Act (COPS grant rollout).
* **2008–2010:** Great Recession municipal revenue collapse and austerity reductions.
* **2020–2021:** COVID-19 pandemic, CARES Act, and ARPA State and Local Fiscal Recovery Funds (SLFRF).
* **Local Milestones:** Major consent decrees, state tax limitation caps (e.g., CA Prop 13, TX SB 2), or municipal pension reform acts.

### C. Downloadable "City Fiscal Fact Sheets"
* A one-click export generating an executive 1-page summary for any selected city containing:
  * The four standard denominators side by side.
  * 10-year historical trajectory.
  * Peer group rank and comparative percentiles.
  * Complete institutional metadata, Census imputation status, and ACFR cross-validation citations.

---

## 5. Phase 2 Implementation Matrix

| Milestone | Deliverables | Target Source | Complexity |
| :--- | :--- | :--- | :---: |
| **Phase 2.1** | BLS CPI-U deflation series & real dollar toggles in UI | BLS Series CUUR0000SA0 | Low |
| **Phase 2.2** | Peer Comparison Matching Engine in dashboard | `data/census_out/city_flags.csv` | Low |
| **Phase 2.3** | Municipal Trade-Off (Crowd-Out) index calculation | Census ALFIN microdata | Medium |
| **Phase 2.4** | Public Employment (ASPEP) integration: headcounts, officers/1k, cost/FTE | Census ASPEP Individual Unit Files | Medium |
| **Phase 2.5** | Crime rate context overlay (FBI UCR/NIBRS) | FBI Crime Data Explorer | Medium |
| **Phase 2.6** | Comprehensive Community Burden model (allocating county sheriff to non-FiSC suburbs) | Census County Finance Files | High |
