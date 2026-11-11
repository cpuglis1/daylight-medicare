# D91 experiment result

**Passed.** November 4, 2026. Elapsed time approximately 9 minutes (09:24 to 09:33 ET), within the 30-minute cap. Scope was the exact two 2026 Collier offerings and one fictional profile in the [approved experiment plan](../MVP_WORKFLOW.md).

- **Premium.** The two exact Collier Landscape records support $0 per month and $0 for twelve months on both plans.
- **Ordinary PCP visits.** The MPF and retained office evidence support $0 per visit and $0 for four covered in-network visits on both plans. Erickson’s selective deductible excludes these office visits.
- **Acute inpatient admission.** Humana’s first band supports $540 for three covered days and $720 for four. The fourth day adds $180. Erickson’s subtotal stays held for both lengths. The $375 daily rate applies within days 1–7, and the fictional scenario leaves the $1,000 annual medical deductible status unspecified at admission. Five of the six plan/component cells have numeric results and one has a named hold.
- **Verification.** The correction recomputes the hospital component alone. The premium and PCP results, fictional profile binding and source references compare equal before and after. The runner declined the Erickson specialist range (MPF row 343137) and out-of-network 40% coinsurance without a charge base (row 343153). Source replay and 68 existing benefit-normalization, profile and comparison-mechanics tests passed.

The [readable comparison](COMPARISON.md), [JSON result](comparison.json), [fictional input](fictional-profile.json) and [bound evidence](evidence.json) are in this directory. Run these commands from this directory with Python 3.10 or later. The calculation reads the compact evidence snapshot. The check replays the retained source records and validates the correction and negative cases.

```sh
python3 -B run.py
python3 -B run.py --hospital-days 4
python3 -B run.py --check
```

Source work used the selected MPF workbook rows and September 2026 Landscape Collier records, the existing office and premium review artifacts, and two targeted EOC sections per plan. These were Chapter 4 out-of-pocket rules (Humana physical page 43, Erickson 39–40) and the inpatient chart entry (Humana 56–57, Erickson 68–70). The exact versions, records and conditions are bound in the JSON. Subsequent review must check later amendments and any state-variant applicability. The three calculations remain scoped to the stated fictional assumptions.

**Next integration step.** Submit the exact two-offering evidence and method snapshot for independent interpretation, method review and internal-purpose acceptance. Once reviewed, add a server-owned projection of this JSON into the existing `:8893` [ComparisonService](../../../../alternatives/advisor-first/comparison_service.py) research response and render the same three component rows in the [local research view](../../../../alternatives/advisor-first/web/research.js). Use the existing [research route guard](../../../../alternatives/advisor-first/research_http.py), and verify that the four-day correction, named deductible hold and held consumer authority survive the projection.

This packet is research-only. It grants zero new acceptance and leaves the source stops, 41 meanings, r9/r4 inventories, privacy and all runtime boundaries in force.
