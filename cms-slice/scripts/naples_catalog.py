"""Complete captured Collier catalog and explicit, reproducible field ordering.

Includes all captured records. No eligibility decision, estimated personal price,
commission input, fitted preference model, or persisted customer information.
"""

from collections import Counter
import copy

from consumer_acceptance import research_or_accepted
import cms_slice as cms
import star_ratings

METRICS = {
    "monthly_premium": ("Published monthly plan premium", "Monthly Consolidated Premium (Part C + D)"),
    "medical_limit": ("In-network medical spending limit", "In-Network Maximum Out-of-Pocket (MOOP) Amount"),
    "drug_deductible": ("Published Part D deductible", "Annual Part D Deductible Amount"),
}
UNSCORED = {"doctors", "medicines", "dental", "vision", "hearing", "travel", "annual_cost"}
CATEGORIES = {"all", "MA-PD", "MA", "PDP", "SNP"}


class NaplesCatalog:
    def __init__(self, tools):
        self.tools = tools
        self.snapshot = tools.snapshot
        self.rows = {r["id"]: r for r in self.snapshot["options"] + self.snapshot["exclusions"]}
        self.premium_checks = {row["id"]: row.get("cross_source_amount_checks", {}).get("PREMIUM", {})
                               for row in tools.rx.report["joins"]}

    def _source(self, row, column):
        return {"url": self.snapshot["sources"]["landscape"]["url"], **row["source"], "column": column,
                **self.tools.review_evidence()}

    def _money(self, row, column):
        return cms.money(row["landscape_raw"].get(column), self._source(row, column))

    def premium_basis(self, row, cross_source):
        """Expose separate published bases; never label the PUF amount LIS-adjusted."""
        if cross_source.get("status") != "conflict":
            return None
        fields = [("Published Part D total before the listed low-income subsidy", "Part D Total Premium"),
                  ("Published Part D low-income premium subsidy (CMS pays)", "Part D LIPS (CMS Pays)"),
                  ("Published low-income beneficiary premium field; eligibility not determined", "Part D Low Income Beneficiary Premium Amount")]
        observations = [{"label": label, "value": self._money(row, column)} for label, column in fields]
        config = self.tools.rx.config
        member = config["members"]["plan"]
        evidence = {"artifact": "monthly_prescription_plan_information", "url": config["source"]["url"],
                    "archive_sha256": config["source"]["sha256"], "outer_member": member["outer_member"],
                    "inner_member": member["inner_member"], "nested_sha256": member["nested_sha256"],
                    "source_row": self.tools.joins[row["id"]]["selected_plan"]["source_row"], "column": "PREMIUM"}
        observations.append({"label": "Monthly Part D PUF PREMIUM; basis unresolved", "value": cms.money("$" + cross_source["puf_raw"], evidence)})
        return {"state": "unresolved_source_basis", "observations": observations,
                "disposition": "Both amounts remain visible. Matching the low-income field does not prove that PUF PREMIUM is subsidy-adjusted. No personal eligibility or premium is determined; this conflict cannot drive premium ordering."}

    @research_or_accepted
    def record(self, plan_id):
        if plan_id not in self.rows:
            raise cms.SourceError("Plan is not in the captured 2027 Collier catalog")
        row = self.rows[plan_id]
        raw, category = row["landscape_raw"], row["category"]
        premium_column = "Part D Total Premium" if category == "PDP" else "Part C Premium" if category == "MA" else "Monthly Consolidated Premium (Part C + D)"
        metrics = {"monthly_premium": self._money(row, premium_column),
                   "medical_limit": self._money(row, METRICS["medical_limit"][1]),
                   "drug_deductible": self._money(row, METRICS["drug_deductible"][1])}
        # Preserve an independently observed source conflict; never reconcile it silently.
        premium_conflict = False
        if category in {"MA-PD", "SNP"}:
            components = [self._money(row, c) for c in ["Part C Premium", "Part D Total Premium"]]
            if metrics["monthly_premium"]["state"] == "value" and all(c["state"] == "value" for c in components):
                premium_conflict = sum(c["value_cents"] for c in components) != metrics["monthly_premium"]["value_cents"]
        cross_source = self.premium_checks.get(plan_id, {})
        premium_basis = self.premium_basis(row, cross_source)
        premium_conflict = premium_conflict or cross_source.get("status") == "conflict"
        notes = ["Plan premium is not total Medicare cost. Personal adjustments and other Medicare obligations are separate."]
        if category == "SNP":
            notes.append("Restricted eligibility: " + raw.get("SNP Type", "special needs requirements") + ". Personal eligibility has not been determined.")
        if not row["comparison_available"]:
            notes.append("Landscape fields are shown; expanded benefit and eligibility validation is still pending for this record.")
        if premium_conflict:
            notes.append("Premium source disagreement remains unresolved. Landscape and Part D source values are preserved; premium ordering treats this record as unresolved.")
            if cross_source.get("status") == "conflict":
                notes.append(f"Part D premium: landscape {cross_source['landscape_raw'].strip()}; Part D PUF {cross_source['puf_raw']}. No source has silently replaced the other.")
                amounts = []
                for observation in premium_basis["observations"]:
                    value = observation["value"]
                    amount = f"${value['value_cents']/100:,.2f}/month" if value["state"] == "value" else value["state"].replace("_", " ")
                    amounts.append(observation["label"] + ": " + amount)
                notes.append("Premium bases: " + "; ".join(amounts) + ". Equal amounts do not establish a shared basis or anyone's subsidy eligibility.")
        if row["plan_type"] == "Regional PPO":
            notes.append("Regional PPO limit and service-area semantics need further validation.")
        return {"id": plan_id, "name": row["name"], "category": category, "plan_type": row["plan_type"],
                "carrier": raw["Organization Marketing Name"], "year": "2027", "county_fips": "12021",
                "metrics": metrics, "star_rating": star_ratings.for_plan(self.tools.star_ratings, row), "premium_source_conflict": premium_conflict,
                "premium_cross_source_check": copy.deepcopy(cross_source),
                "premium_basis": premium_basis,
                "eligibility": "restricted_unconfirmed" if category == "SNP" else "not_assessed",
                "snp_type": raw.get("SNP Type") if category == "SNP" else None,
                "benefit_validation": "selected_fields_checked" if row["comparison_available"] else "landscape_only_pending_expanded_validation",
                "notes": notes, "source": self._source(row, "Plan Name")}

    @research_or_accepted
    def list(self, category="all", priorities=None, year="2027", county_fips="12021"):
        if year != "2027" or county_fips != "12021":
            raise cms.SourceError("The captured catalog currently covers Collier County for 2027")
        if not isinstance(category, str) or category not in CATEGORIES:
            raise cms.SourceError("Unknown coverage category")
        priorities = [] if priorities is None else priorities
        if not isinstance(priorities, list) or len(priorities) > 9 or any(not isinstance(p, str) or p not in set(METRICS) | UNSCORED for p in priorities) or len(set(priorities)) != len(priorities):
            raise cms.SourceError("Specify distinct supported priority names")
        criteria = [p for p in priorities if p in METRICS]
        unscored = [p for p in priorities if p in UNSCORED]
        records = [self.record(pid) for pid in self.rows if category == "all" or self.rows[pid]["category"] == category]
        def sort_key(row):
            key = []
            for criterion in criteria:
                metric = row["metrics"][criterion]
                known = metric["state"] == "value" and not (criterion == "monthly_premium" and row["premium_source_conflict"])
                # An unknown or inapplicable field never becomes a zero or a positive match.
                key.extend((not known, metric["value_cents"] if known else 0))
            return (*key, row["id"])
        records.sort(key=sort_key)
        order = "Then ".join(METRICS[p][0].lower() + ", low to high. " for p in criteria).strip() if criteria else "Source plan ID order."
        return {"kind": "catalog", "title": "2027 Collier County plans", "category": category,
                "count": len(records), "captured_total": len(self.rows), "counts": dict(Counter(r["category"] for r in records)),
                "plans": records, "priorities": priorities, "scored_criteria": criteria, "unscored_priorities": unscored,
                "ordering": order, "ranking_method": "lexicographic published fields; exact plan ID breaks ties",
                "suitability_ranked": False, "missing_values": "Unknown, inapplicable and conflicted values follow known values for each criterion.",
                "scope": "All 70 captured Advantage/SNP and standalone Part D records are available here. Medigap carrier quotes, PACE and employer plans are not represented; this is not a certified complete live market.",
                "cost_scope": "Published plan premiums, deductibles and medical limits are separate measures. Personal annual costs are not available.",
                "snapshot_id": self.tools.version}

    @research_or_accepted
    def compare(self, plan_ids):
        if not isinstance(plan_ids, list) or not 2 <= len(plan_ids) <= 3 or any(not isinstance(p, str) for p in plan_ids) or len(set(plan_ids)) != len(plan_ids):
            raise cms.SourceError("Choose two or three distinct captured plans")
        plans = [self.record(p) for p in sorted(plan_ids)]
        return {"kind": "comparison", "title": "Selected plan comparison", "plans": plans,
                "count": len(plans), "scored_criteria": [], "unscored_priorities": [], "priorities": [],
                "ordering": "Selected plans, in source ID order.", "suitability_ranked": False,
                "scope": "Plan categories have different roles and are not interchangeable. Check compatibility, eligibility and missing evidence.",
                "cost_scope": "No personal annual cost or exact provider participation has been established.", "snapshot_id": self.tools.version}

    @research_or_accepted
    def facts(self, record):
        facts = [self.tools.star_fact(record["id"])]
        for metric, value in record["metrics"].items():
            amount = f"${value['value_cents']/100:,.2f}" if value["state"] == "value" else value["state"].replace("_", " ")
            note = " ".join(record["notes"]) if metric == "monthly_premium" else "A published field; applicability and full plan conditions still need checking."
            evidence = [copy.deepcopy(value["evidence"])]
            if metric == "monthly_premium" and record.get("premium_basis"):
                evidence.extend(copy.deepcopy(o["value"]["evidence"]) for o in record["premium_basis"]["observations"])
            facts.append({"id": "catalog-" + record["id"] + "-" + metric,
                          "text": f"{record['name']} ({record['id']}): {METRICS[metric][0]} is {amount}. {note}",
                          "plan_id": record["id"], "evidence": evidence})
        return facts


def conversation_summary(view):
    """Only aggregate list data or selected numeric fields, never catalog rows."""
    import json
    ref='catalog-view-'+cms.sha256(json.dumps({'ids':[p['id'] for p in view['plans']], 'priorities':view.get('priorities',[]),'kind':view['kind']},sort_keys=True).encode())[:16]
    labels={'monthly_premium':'lowest monthly premium first','medical_limit':'lowest medical spending limit first','drug_deductible':'lowest drug deductible first'}
    criteria=view.get('scored_criteria',[])
    order=', then '.join(labels[c] for c in criteria) or 'source plan ID order'
    common={'display_ref':ref,'sorted_by':order,'unscored_priorities':view.get('unscored_priorities',[]),'source_conflict_count':sum(p['premium_source_conflict'] for p in view['plans'])}
    if view['kind']=='catalog':
        primary=criteria[0] if criteria else None
        values=[p['metrics'][primary]['value_cents'] for p in view['plans'] if primary and p['metrics'][primary]['state']=='value' and not(primary=='monthly_premium' and p['premium_source_conflict'])]
        value_range={'metric':primary,'min_cents':min(values) if values else None,'max_cents':max(values) if values else None,'ties_at_min':values.count(min(values)) if values else 0}
        text=f"{view['count']} published 2027 Collier records in this view, out of 70 captured records; sorted by {order}. Only the requested numeric criteria affect sorting; exact plan ID breaks ties. This isn't a recommendation. Low premium is not low total cost. Medigap prices are unavailable."
        if values:text+=f" Primary metric range: ${min(values)/100:,.2f} to ${max(values)/100:,.2f}; {value_range['ties_at_min']} tie at the minimum."
        if common['unscored_priorities']:text+=' Cannot check '+', '.join(common['unscored_priorities'])+'; these priorities do not affect this order.'
        if view['counts'].get('SNP'):text+=' Special needs plans are only for people who qualify; eligibility remains unconfirmed.'
        text+=f" {common['source_conflict_count']} premium source conflicts remain unresolved."
        fact={'id':ref,'text':text,'evidence':[view['plans'][0]['source']] if view['plans'] else []}
        return {**common,'total':view['count'],'counts_by_category':view['counts'],'primary_metric_range':value_range,'facts':[fact]}
    plans=[];facts=[]
    for plan in view['plans']:
        plan_facts=[]
        for metric,value in plan['metrics'].items():
            fid='catalog-'+plan['id']+'-'+metric
            amount=f"${value['value_cents']/100:,.2f}" if value['state']=='value' else value['state'].replace('_',' ')
            conflict=metric=='monthly_premium' and plan['premium_source_conflict']
            evidence = [value['evidence']]
            if metric == 'monthly_premium' and plan.get('premium_basis'):
                evidence += [o['value']['evidence'] for o in plan['premium_basis']['observations']]
            plan_facts.append({'id':fid,'text':f"{plan['name']} ({plan['id']}): {METRICS[metric][0]} is {amount}. "+('Source conflict: this value remains unresolved. ' if conflict else '')+' '.join(plan['notes']),'evidence':evidence})
        stars=plan.get('star_rating',{})
        if stars.get('rating_year'):
            value=f"{stars['value']:g} of 5 stars" if stars['state']=='rated' else stars['reason']
            plan_facts.append({'id':'stars-'+plan['id'],'text':f"{plan['id']}: CMS {stars['rating_year']} {stars['label']} rating: {value}. Contract-level quality rating; published {stars['published_on']}.",'evidence':[stars['evidence']]})
        facts.extend(plan_facts)
        plans.append({'id':plan['id'],'name':plan['name'],'category':plan['category'],'metrics':{k:{'state':'conflict' if k=='monthly_premium' and plan['premium_source_conflict'] else v['state'],'value_cents':v['value_cents']} for k,v in plan['metrics'].items()},'fact_ids':[f['id'] for f in plan_facts]})
    return {**common,'plans':plans,'facts':facts}
