"""Build the finite L03 claim/condition inventory from source assertions.

Keep r8 roots as lineage, not the semantic denominator. Cost fields form whole
schedules; explicit published clauses form scoped propositions. No new source
agreement, personal applicability, or release acceptance is asserted here.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import re
import sqlite3
import zipfile

from l03_inventory import DATA, REPO, R1, R7, load, rows, packed, ident, sha
from l03_semantic_context import financial_context,source_question_target,printed_attribute_headers,plan_cost_question,pharmacy_column_questions,pharmacy_table_rows,pharmacy_columns_by_line
from l03_pdf_geometry import pdf_words, bind_page_words
from l03_semantic_clauses import clean, page_context, decompose, source_cells, detect_table_columns, required_propositions, sb_row_frames, MONEY, VERB

ROOT=DATA/"semantic-inventory-r9"
PARENT=DATA/"inventory-r8"
PACKAGE="L03-SEMANTIC-INVENTORY-COLLIER-2026-r9"
COMPONENT_ROLES={
    "InpatientHospitalAcuteBenefitPeriodComponent":"benefit_period",
    "PriorAuthorizationReferralNmBenefitComponent":"authorization_referral",
    "TierCoinsuranceComponent":"coinsurance_schedule",
    "TierCopaymentComponent":"copayment_schedule",
    "MoopAmountComponent":"spending_limit",
    "OpsupOonCostShareComponent":"out_of_network_schedule",
    "OptSupPartBCostSharingComponent":"cost_sharing_relationship",
    "CostSharingTierComponent":"tier_structure",
    "PartABTierDeductibleComponent":"deductible_schedule",
    "CostShareABComponent":"out_of_network_schedule",
    "CostShareABPOSComponent":"point_of_service_schedule",
    "OutOfNetworkCostShareComponent":"out_of_network_schedule",
    "OutOfNetworkCostShareMaxPlanBenComponent":"out_of_network_limit",
    "CopaymentComponent":"copayment_schedule",
    "CoinsuranceComponent":"coinsurance_schedule",
    "BenefitUnlimitedComponent":"frequency_quantity",
    "BenefitUnlimitedNoPeriodicityComponent":"frequency_quantity",
    "DeductibleAmountComponent":"deductible_schedule",
    "MoopCostTypeComponent":"spending_limit_basis",
    "MaximumPlanBenefitCoverageComponent":"plan_payment_limit",
    "MaximumPlanBenefitCoverageUnlimitedComponent":"plan_payment_limit",
    "PlanBenefitCoverageComponent":"plan_payment_limit",
    "MaxPlancoverageAmountPeriodicityEyewearComponent":"eyewear_limit_frequency",
    "MaxPlancoverageHearingAidsComponent":"hearing_aid_limit",
    "MaxPlancoverageComprehensiveDentalComponent":"comprehensive_dental_limit",
    "DentalCopaymentComponent":"dental_copayment_schedule",
    "DentalCoinsuranceComponent":"dental_coinsurance_schedule",
    "CopaymentAdmissionWaivedHospitalComponent":"admission_waiver_and_copayment",
    "CoinsuranceAdmissionWaivedHospitalComponent":"admission_waiver_and_coinsurance",
    "CopayAdmWaivedTimelineComponent":"admission_waiver_timeline",
    "CoinsAdmWaivedTimelineComponent":"admission_waiver_timeline",
    "CopayAdmissionWaivedHospitalComponent":"admission_waiver",
    "CoinAdmissionWaivedHospitalComponent":"admission_waiver",
    "CopayObservationServiceComponent":"observation_cost_schedule",
    "OutpatientBloodServicesWaiveComponent":"blood_service_waiver",
    "SnfAdmissionComponent":"prior_hospitalization_condition",
    "StepTherapyComponent":"step_therapy_condition",
    "CostShareGroupsComponent":"shared_budget_membership",
    "TransportationTypeAndModeComponent":"transportation_definition",
    "FitnessBenefitComponent":"fitness_definition",
    "ModeOfDeliveryComponent":"benefit_delivery_definition",
    "MealBenefitsComponent":"meal_qualification",
    "RemoteAccessTechnologiesComponent":"remote_access_definition",
    "RemoteAccessTechnologiesCopayCoinsuranceComponent":"remote_access_cost_schedule",
    "TypeOfBenefitComponent":"benefit_definition",
    "NumberOfTreatmentsComponent":"frequency_quantity",
    "NumberOfVisitsOfferedComponent":"frequency_quantity",
    "AdditionalDays1a1Component":"additional_hospital_days",
    "AdditionalPreventiveServicesComponent":"preventive_service_definition",
    "OneToggleQuestionComponent":"category_specific_source_selection",
    "DrugsOnCMSOTCListComponent":"OTC_definition_qualification",
    "NRTAttestationComponent":"NRT_published_benefit_attestation",
    "AttestComponent":"published_benefit_attestation",
    "CopayMultiServiceLocationComponent":"setting_specific_copayment",
    "CopayMultiServiceLocation8BComponent":"setting_specific_copayment",
}
FINANCIAL_ROLES={name for name in COMPONENT_ROLES.values()if any(t in name for t in ["schedule","spending_limit","payment_limit","eyewear_limit","hearing_aid_limit","dental_limit"])}
CONTEXT_FIELDS={"planName","planDeleted","planSegmentDeleted","contractLegalName","organizationMarketingName",
    "geographicName","organizationType","segmentName","planTypeLabel","hpmsPlanType","isNetworkPlan",
    "isEmployerOnlyPlan","isOfferRx","contractIsOfferPartD","offerPos","isVbid","isOutOfNetwork",
    "isPdssm","isSnp","snpType","snpInstitutionalType","chronicOrDisablingConditions"}


def not_empty(x):return x is not None and x!="" and x!=[]


def human(key):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])"," ",key).replace("Component","").replace("/"," / ")


def json_value(obj,pointer):
    for part in pointer.split("/")[1:]:
        part=part.replace("~1","/").replace("~0","~")
        obj=obj[int(part)]if isinstance(obj,list)else obj[part]
    return obj


def source_network(text):
    low=text.lower()
    if "outofnetwork"in low or "_oon"in low:return "out_of_network"
    if "pos"in low or "pointofservice"in low:return "point_of_service"
    return "source_default_network"


def cms_condition_role(label, fallback):
    low=label.lower()
    for role,pattern in [
        ("authorization",r"authoriz|precertif"),("referral",r"referral"),
        ("waiver_exception",r"waiv|except|replac|admitted|admission"),
        ("deductible_application",r"count.*deduct|apply.*deduct|subject.*deduct"),
        ("frequency_quantity",r"frequency|periodicity|how often|visits|number of|treatments|limit.*days|how many"),
        ("coverage_selection",r"provide|offer|mandatory|optional|which.*benefit|type of benefit"),
        ("shared_budget",r"shared|combined|group|wallet"),
        ("qualification",r"eligib|qualif|chronic|low.income|Medicaid|QMB|attest"),
    ]:
        if re.search(pattern,low):return role
    return fallback


class SemanticInventory:
    def __init__(self,parent,path):
        self.parent=sqlite3.connect(f"file:{parent}?mode=ro",uri=True)
        self.db=sqlite3.connect(path)
        self.db.executescript("""
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE semantic_unit(id TEXT PRIMARY KEY,offering_id TEXT NOT NULL,
          kind TEXT NOT NULL,subject TEXT NOT NULL,predicate TEXT NOT NULL,context TEXT NOT NULL,
          state TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE observation(id TEXT PRIMARY KEY,unit_id TEXT,source_id TEXT NOT NULL,
          layer TEXT NOT NULL,disposition TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE source_disposition(source_id TEXT PRIMARY KEY,layer TEXT NOT NULL,
          disposition TEXT NOT NULL,rule TEXT NOT NULL);
        CREATE TABLE source_target(source_id TEXT NOT NULL,unit_id TEXT NOT NULL,
          PRIMARY KEY(source_id,unit_id));
        CREATE TABLE lineage(root_id TEXT NOT NULL,unit_id TEXT NOT NULL,PRIMARY KEY(root_id,unit_id));
        CREATE TABLE root_disposition(root_id TEXT PRIMARY KEY,kind TEXT NOT NULL,disposition TEXT NOT NULL,reason TEXT NOT NULL);
        CREATE TABLE clause(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,unit_id TEXT,
          kind TEXT NOT NULL,rule TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE relationship(parent_id TEXT NOT NULL,child_id TEXT NOT NULL,relation TEXT NOT NULL,
          source_id TEXT NOT NULL,PRIMARY KEY(parent_id,child_id,relation,source_id));
        CREATE TABLE equivalence(id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,decision TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE canonical_unit(unit_id TEXT PRIMARY KEY,canonical_id TEXT NOT NULL);
        CREATE INDEX canonical_identity ON canonical_unit(canonical_id);
        CREATE TABLE work_obligation(id TEXT PRIMARY KEY,offering_id TEXT NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX unit_offering ON semantic_unit(offering_id,kind);
        CREATE INDEX target_unit ON source_target(unit_id);
        CREATE INDEX obs_unit ON observation(unit_id);
        CREATE INDEX obs_source ON observation(source_id);
        CREATE INDEX clause_source ON clause(source_id);
        """)
        self.units={}
        self.service={x["id"]:x for x in rows(R7/"service-reconciliation.jsonl.gz")}
        self.by_index={(x["offering_id"],int(x["PBP_source"]["pointer"].split("/")[-1])):x for x in self.service.values()}
        self.field_services=collections.defaultdict(set)
        for x in rows(R7/"field-dispositions.jsonl.gz"):
            s=x["source"];self.field_services[(x["offering_id"],s["member"],s["record_ordinal"],s["field"])].add(x["benefit_record_id"])
        self.dictionary={tuple(json.loads(k)):json.loads(v)for k,v in self.parent.execute("SELECT key,payload FROM dictionary_entry")}
        self.parents={oid:json.loads(payload)for oid,payload in self.parent.execute("SELECT id,payload FROM offering")}
        self.native={}
        manifest=load(R1/"pbp-plan-manifest.json")
        archive=REPO/"docs/data/l02-ma-availability-2026-10-25/acquisition-r1/raw"/manifest[0]["archive_sha256"]
        with zipfile.ZipFile(archive)as z:
            for x in manifest:self.native[x["offering_id"]]=json.loads(z.read(x["member"]))
        self.table_rows={(r["offering_id"],r["source"]["member"],r["source"]["record_ordinal"]):r["raw"]for r in rows(R1/"table-rows.jsonl.gz")}
        self.cms_groups=collections.defaultdict(list)
        self.source_documents={x["document_sha256"]:x["source"]for x in load(PARENT/"source-index.json")}
        self.geometry_cache=pathlib.Path("/private/tmp/l03-r9-work/geometry")

    def unit(self,oid,kind,subject,predicate,context,payload):
        signature={"offering_id":oid,"kind":kind,"subject":subject,"predicate":predicate,"context":context}
        uid=ident("SEM",signature)
        if uid not in self.units:
            self.units[uid]=signature
            self.db.execute("INSERT INTO semantic_unit VALUES (?,?,?,?,?,?,?,?)",(
                uid,oid,kind,subject,predicate,packed(context),"evidence_reconciliation_pending",packed(payload)))
        return uid

    def observe(self,uid,sid,layer,payload,disposition="required_semantic_observation",suffix=None):
        identifier=ident("OBS",sid,uid,suffix or "whole")
        self.db.execute("INSERT OR IGNORE INTO observation VALUES (?,?,?,?,?,?)",(
            identifier,uid,sid,layer,disposition,packed(payload)))
        if uid:self.db.execute("INSERT OR IGNORE INTO source_target VALUES (?,?)",(sid,uid))
        return identifier

    def disposition(self,sid,layer,disposition,rule):
        self.db.execute("INSERT INTO source_disposition VALUES (?,?,?,?)",(sid,layer,disposition,rule))

    def service_frame(self,oid,services):
        exact=[self.service[x]for x in sorted(services)]
        subject="; ".join(f"{x['category_code']} ({x['category_type_interpretation']}): {x['service_name']}"for x in exact)
        return subject or "Published plan-level benefit",{
            "service_ids":[x["id"]for x in exact],"variant":"base_source_model",
            "population_basis":"CMS_submission_basis","setting":"source_category_and_controls",
            "network":"source_default_network"}

    def cms(self):
        for sid,oid,layer,prior,loc,value in self.parent.execute("SELECT id,offering_id,layer,disposition,locator,payload FROM source_unit WHERE layer LIKE 'cms_%'"):
            loc,value=json.loads(loc),json.loads(value)
            if layer=="cms_service_record":
                self.disposition(sid,layer,"supporting_source_identity","native_service_record_identity")
                continue
            if prior.startswith("retained_blank"):
                self.disposition(sid,layer,"retained_empty","blank_null_empty_not_zero_no")
                continue
            if prior in {"technical_metadata","retained_other_layer_L02","technical_identity_or_structure","documented_grouping_control"}:
                self.disposition(sid,layer,"retained_source_context",prior)
                continue
            if layer=="cms_table":
                definition=self.dictionary.get(tuple(value["dictionary_key"]),{})
                label=definition.get("field_title")or definition.get("json_question")or loc["field"]
                if label in {'Label for this Service Category','Enter Label for this Group (Optional)'}:
                    self.disposition(sid,layer,"retained_source_context","CMS_service_or_group_identity_label_not_independent_benefit_condition")
                    continue
                services=self.field_services.get((oid,loc["member"],loc["record_ordinal"],loc["field"]),set())
                subject,context=self.service_frame(oid,services)
                context["network"]=source_network(loc["member"]+"/"+loc["field"])
                if not services:
                    context.update(source_table_scope=loc["member"],source_record_ordinal=loc["record_ordinal"])
                row=self.table_rows[(oid,loc["member"],loc["record_ordinal"])]
                detailed=financial_context(loc["field"],label,row)
                context.update(detailed)
                if row.get("pbp_d_opt_identifier")not in[None,""]:
                    context.update(variant="optional_rider",rider_id=row["pbp_d_opt_identifier"],rider_name=row.get("pbp_d_opt_name"))
                if "mrx"in loc["member"]:
                    context["source_question_target"]=source_question_target(label)
                    context["source_record_context"]={k:v for k,v in row.items()if re.search(r"tier.*(?:id|label_list)$",k)and v not in["",None]}
                if re.search(r"insulin|chemotherapy|group sessions|individual sessions",label,re.I):
                    context["explicit_service_subtype"]=source_question_target(label)
                norm=value["normalized"];label_role=cms_condition_role(label,"source_defined_condition")
                cost_match=re.search(r"copay|coinsurance|premium|deductible amount|deductible amt|MOOP (?:amount|amt)|maximum.*amount|plan.*coverage.*amount",label,re.I)
                material_condition=label_role in {"authorization","referral","waiver_exception","deductible_application","frequency_quantity","shared_budget","qualification"}
                if cost_match and not material_condition:
                    financial="member_cost"if re.search(r"copay|coinsurance",label,re.I)else"premium"if"premium"in label.lower()else"deductible"if"deduct"in label.lower()else"plan_payment_limit"
                    # A full schedule is the inventory unit. Ranges, day bands,
                    # selectors and qualifiers remain attached observations.
                    if not services:context["source_scope"]=definition.get("service_category")or loc["member"]
                    uid=self.unit(oid,"claim",subject,financial+"_schedule",context,
                        {"meaning":"Complete source-selected schedule; individual fields are attributes, not extra claims.","source_semantics":"official_CMS_dictionary","comparison_gate":"Full activation/network/period/condition review required."})
                elif norm.get("type")in {"enum","enum_set","opaque_code"}or label_role!="source_defined_condition":
                    # The question, its subject and controls establish the
                    # predicate; its code alone never means universal No.
                    predicate=clean(label)
                    uid=self.unit(oid,"condition",subject,predicate,context,
                        {"family":label_role,"source_semantics":"official_CMS_question_and_codes","unknown_codes_stay_uninterpreted":True})
                else:
                    uid=self.unit(oid,"condition",subject,clean(label),context,
                        {"family":"source_defined_qualification_or_detail","source_semantics":"official_CMS_field_definition"})
                self.observe(uid,sid,layer,{"locator":loc,"raw":value["raw"],"normalized":norm,"dictionary_question":label})
                self.disposition(sid,layer,"required_semantic_observation","official_dictionary_predicate_and_subject")
                continue
            pointer=loc["pointer"];parts=pointer.split("/")
            if parts[-1]in {"categoryCode","categoryTypeId","categoryEditedName","optSupPkgId","optSupPkgDesc","optSupPkgName","optSupPkgStatus","optSupPkgNum"}:
                self.disposition(sid,layer,"retained_source_context","exact_category_or_rider_identity_not_independent_assertion")
                continue
            if pointer.startswith("/pbp/0/planCharacteristics/moopLimits/"):
                self.disposition(sid,layer,"retained_schema_constraint","CMS_named_lower_intermediate_mandatory_threshold_bands_not_selected_plan_MOOP")
                continue
            if pointer.startswith("/pbp/0/planCharacteristics/")and parts[-1]in CONTEXT_FIELDS:
                self.disposition(sid,layer,"retained_source_context","L02_identity_plan_class_and_population_context")
                continue
            m=re.match(r"/pbp/0/benefitDetails/benefitDetailsInfo/(\d+)/benefitDetails/([^/]+)(.*)",pointer)
            if m:
                s=self.by_index[(oid,int(m.group(1)))];component=m.group(2)
                if component not in COMPONENT_ROLES:raise ValueError("Unclassified source component "+component)
                subject,context=self.service_frame(oid,[s["id"]]);context["network"]=source_network(component)
                role=COMPONENT_ROLES[component]
                key=(oid,subject,packed(context),component)
                self.cms_groups[key].append((sid,loc,value,role))
                continue
            # A named optional package/category/component is a distinct scope;
            # neither its costs nor its frequency are merged into base benefits.
            opt=re.match(r"(.*/optSupPackagesData/(\d+))(?:/benefitPackages/(\d+))?",pointer)
            offering=re.match(r"(.*/(?:nonMedicare|medicare)BenefitOfferingDetails/(\d+))",pointer)
            group=pointer.rsplit("/",1)[0]
            context={"network":source_network(pointer),"population_basis":"CMS_submission_basis","variant":"base_source_model"}
            role="source_plan_condition"
            if opt:
                pkg=json_value(self.native[oid],opt.group(1))
                context.update(variant="optional_rider",rider_id=pkg.get("optSupPkgId"),
                               rider_name=pkg.get("optSupPkgName"),rider_source=opt.group(1))
                subject="Optional rider "+str(pkg.get("optSupPkgId"))+": "+str(pkg.get("optSupPkgName"))
                if opt.group(3)is not None:
                    base=opt.group(0);benefit=json_value(self.native[oid],base)
                    code=benefit["categoryCode"];typ="Medicare"if benefit.get("categoryTypeId")==1 else"non-Medicare"
                    names=sorted({x["service_name"]for x in self.service.values()if x["category_code"]==code})
                    subject+=" / "+code+" ("+typ+"): "+("; ".join(names)or"source-named category")
                    context.update(category_code=code,category_type=typ)
                    tail=pointer[len(base):].split("/")
                    if len(tail)>2 and tail[1]=="benefitPackagesInfo":
                        group=base+"/benefitPackagesInfo/"+tail[2]
                        role=COMPONENT_ROLES.get(tail[2])
                        if role is None:raise ValueError("Unknown rider component "+tail[2])
                    else:group=base;role="coverage_selection"
                else:
                    group=opt.group(1)
                    role="optional_package_activation_and_relationships"
            elif offering:
                group=offering.group(1);control=json_value(self.native[oid],group)
                code=control["categoryCode"];names=sorted({x["service_name"]for x in self.service.values()if x["category_code"]==code})
                subject=code+": "+("; ".join(names)or"source-named category")
                context.update(category_code=code,coverage_model="nonMedicare"if"nonMedicareBenefit"in pointer else"medicare")
                role="coverage_selection"
            else:
                subject=human(group.removeprefix("/pbp/0/"))
                if re.search(r"premium|deduct|moop|maximum|costShare|copay|coinsurance|rxTier|rxInsulin",pointer,re.I):role="published_plan_schedule"
                elif "priorAuthorization"in pointer:role="authorization"
                elif "priorReferral"in pointer:role="referral"
                elif "visitorTravel"in pointer:role="visitor_travel_definition"
                elif "vbid"in pointer:role="published_qualification"
            if pointer.startswith("/pbp/0/rx/"):
                detail=financial_context(pointer)
                context.update(detail)
                leaf=parts[-1]
                if re.search(r"Copayment|Coinsurance",leaf,re.I):
                    stem=re.sub(r"Copayment|Coinsurance|Daily|Amount|Percentage|Percent","",leaf,flags=re.I)
                    context["source_cost_question"]=stem
                    group=pointer.rsplit("/",1)[0]+"/"+stem
                    role="published_plan_schedule"
                else:
                    group=pointer;role="source_plan_condition"
            elif role in {"source_plan_condition","optional_package_activation_and_relationships"}:
                group=pointer
            elif role=="coverage_selection"and offering:
                if parts[-1]=="boOutOfNetwork":context["network"]="out_of_network"
                elif parts[-1]in {"boInNetwork","inNetworkOptionSelected"}:context["network"]="in_network"
                group=pointer
                if parts[-1]=="inNetworkOptionSelected":role="source_plan_condition"
            if pointer.startswith("/pbp/0/planLevelCostSharing/"):
                group,role,plan_context=plan_cost_question(pointer,self.native[oid])
                context.update(plan_context)
                if plan_context.get("category_code"):
                    subject="Plan cost-limit/deductible membership: "+plan_context["category_code"]+" ("+plan_context["category_type"]+")"
            context["source_container"]=group
            self.cms_groups[(oid,subject,packed(context),group)].append((sid,loc,value,role))
        for (oid,subject,ctx,component),items in self.cms_groups.items():
            context=json.loads(ctx);role=items[0][3]
            if role=="authorization_referral":
                partitions=collections.defaultdict(list)
                for item in items:
                    leaf=item[1]["pointer"].rsplit("/",1)[-1]
                    partitions["authorization"if"Authorization"in leaf else"referral"].append(item)
            else:partitions={role:items}
            for predicate,values in partitions.items():
                kind="claim"if predicate in FINANCIAL_ROLES or predicate in {"published_plan_schedule","coverage_selection","transportation_definition","fitness_definition","benefit_definition","remote_access_definition","benefit_delivery_definition","preventive_service_definition","visitor_travel_definition"}else"condition"
                if predicate in {"copayment_schedule","coinsurance_schedule","out_of_network_schedule","point_of_service_schedule","dental_copayment_schedule","dental_coinsurance_schedule"}:
                    predicate="member_cost_schedule"
                if predicate in {"authorization","referral"}:
                    predicate="Authorization required for this benefit?"if predicate=="authorization"else"Referral required for this benefit?"
                if predicate in {"source_plan_condition","optional_package_activation_and_relationships"}:
                    predicate="Source question: "+human(component.rsplit("/",1)[-1])
                if context.get("membership_question"):
                    predicate="Selected category membership question: "+human(context["membership_question"])
                uid=self.unit(oid,kind,subject,predicate,context,
                    {"meaning":"One complete source schedule, source selection or published condition; component attributes remain inseparable.","source_component":component,"source_basis":"CMS_JSON","individual_applicability":False})
                for sid,loc,value,_ in values:
                    self.observe(uid,sid,"cms_json",{"locator":loc,"raw":value["raw"],"source_role":predicate})
                    self.disposition(sid,"cms_json","required_semantic_observation","named_CMS_component_proposition")
                    raw=value["raw"]
                    if isinstance(raw,str)and len(raw)>90 and re.search(r"description|notes?|other",loc["pointer"].rsplit("/",1)[-1],re.I):
                        for atom in decompose(raw,{"chapter_role":"medical_benefits"},subject=subject):
                            for atom_kind,atom_role in required_propositions(atom):
                                child=self.unit(oid,atom_kind,subject,atom_role+": "+clean(atom["quote"]).casefold(),context,
                                    {"assertion":atom["quote"],"parent_sentence":atom["parent_sentence"],"source_rule":atom["rule"],
                                     "condition_family":atom_role if atom_kind=="condition"else None,"source_basis":"CMS_narrative_field"})
                                self.observe(child,sid,"cms_json_narrative",{"locator":loc,"source_character_range":[atom["start"],atom["end"]],"quote":atom["quote"]})
                                self.db.execute("INSERT OR IGNORE INTO relationship VALUES (?,?,?,?)",(uid,child,"source_schedule_narrative_predicate",sid))
        # Published premiums and Part-D plan amounts were outside r8's PBP-only
        # field ledger. Account for all 1,014 retained observations explicitly.
        for item in load(R1/"normalized-amount-observations.json"):
            sid=ident("SOURCE_AMOUNT",item["offering_id"],item["source"])
            context={"network":item["network"],"period":item.get("period"),"unit":item.get("unit"),
                     "population_basis":item["basis"],"variant":"source_named_plan_amount"}
            uid=self.unit(item["offering_id"],"claim","Published plan amount: "+item["field"],item["field"],context,
                {"qualification":item["qualifications"],"source_basis":"retained_normalized_source_amount","unknown_remains_unknown":True})
            self.observe(uid,sid,"cms_named_amount",item)
            self.disposition(sid,"cms_named_amount","required_semantic_observation","source_named_premium_limit_or_deductible")
        self.db.commit()

    def carrier(self):
        """Reconstruct document/column streams before proposition segmentation.

        r8 discovery-container boundaries do not determine sentence boundaries.
        Each assertion can therefore span several original passages/pages while
        retaining exact character ranges back to every original source unit.
        """
        import bisect
        import itertools
        source_pages=collections.defaultdict(list)
        for sid,oid,layer,loc,value in self.parent.execute("SELECT id,offering_id,layer,locator,payload FROM source_unit WHERE layer LIKE 'carrier_%'"):
            if layer=="carrier_original_shared_columns":
                self.disposition(sid,layer,"retained_other_plan_columns","original_shared_SB_page_supports_exact_offering_view")
                continue
            loc,value=json.loads(loc),json.loads(value)
            source_pages[(oid,loc["document_sha256"],loc["kind"],loc["pdf_page"])].append((sid,loc,value["text"]))
        families=collections.defaultdict(set)
        for item in rows(R7/"carrier-chart-rows.jsonl.gz"):
            for fragment in item["fragments"]:
                families[(item["offering_id"],fragment["source_page"]["document_sha256"],fragment["pdf_page"],fragment["line"])].add(item["section"])
        views=self.parent.execute("SELECT offering_id,document_sha256,kind,pdf_page,text FROM carrier_view ORDER BY offering_id,document_sha256,kind,pdf_page")
        self.layout_inventory=[]
        for document,document_views in itertools.groupby(views,key=lambda r:r[:3]):
            oid,h,kind=document
            streams={};previous_context=None;section="source_front_matter";variant="base_or_document_default"
            word_pages=None
            sid_seen=set();sid_required=set();sid_atoms=collections.Counter()
            def append_stream(key,text,segment,context):
                st=streams.setdefault(key,{"parts":[],"segments":[],"length":0,"context":context,"scope_resets":[]})
                start=st["length"];st["parts"].append(text);st["length"]+=len(text)
                if segment is not None:
                    st["segments"].append({**segment,"a":start,"b":start+len(text.rstrip("\n"))})
            for _,_,_,page,text in document_views:
                context=page_context(text,previous_context,kind);previous_context=context
                lines=text.splitlines(keepends=True);starts=[0]
                for line in lines:starts.append(starts[-1]+len(line))
                sid_for_line={};raw_by_sid={};loc_by_sid={};source_line_starts={}
                for sid,loc,raw in source_pages[(oid,h,kind,page)]:
                    sid_seen.add(sid);raw_by_sid[sid]=raw;loc_by_sid[sid]=loc
                    source_line_starts[sid]=starts[loc["line_start"]-1]
                    for line_number in range(loc["line_start"],loc["line_end"]+1):sid_for_line[line_number]=sid
                geometry=detect_table_columns(text)
                header_lines={e["line"]for e in geometry["evidence"]}
                chart=any((oid,h,page,n)in families for n in range(1,len(lines)+1))
                sb_frames=sb_row_frames(text,geometry)if kind=="SB"else{}
                sb_networks=geometry["roles"]if kind=="SB"and set(geometry["roles"])=={"in_network","out_of_network"}else[]
                bounds=geometry["boundaries"]if chart else[]
                native={"method":"not_a_printed_cost_chart","cuts":{}}
                if bounds:
                    if word_pages is None:
                        word_pages=pdf_words(self.source_documents[h]["path"],self.geometry_cache/(h+".json.gz"))
                    native=bind_page_words(text,word_pages[page-1],h,page,ROOT/"ocr-word-coordinates")
                cells=source_cells(text,bounds,geometry["roles"],native["cuts"])
                self.layout_inventory.append({"offering_id":oid,"document_sha256":h,"kind":kind,"pdf_page":page,
                    "chapter_role":context["chapter_role"],"chart_family_present":chart,"boundaries":bounds,
                    "column_roles":geometry["roles"]if bounds else[],"header_evidence":geometry["evidence"],
                    "coordinate_binding":native})
                printed_headers=printed_attribute_headers(text)
                pharmacy_questions=pharmacy_column_questions(text)
                pharmacy_frames,pharmacy_starts=pharmacy_table_rows(text)if pharmacy_questions or context["chapter_role"]=="drug_costs"else({}, {})
                pharmacy_headers_by_line=pharmacy_columns_by_line(text)
                line_frames={}
                for n,line in enumerate(lines,1):
                    t=clean(line)
                    if re.match(r"Section\s+\d",t,re.I):
                        section=t
                        if not re.search(r"optional|platinum|rider",t,re.I):variant="base_or_document_default"
                    if len(t)<140 and re.match(r"(?:Section\s+[\d.]+\s+)?(?:Extra\s+optional|Optional\s+(?:Dental|Supplemental)|Platinum\s+Dental|Dental\s+Platinum)",t,re.I):
                        variant="named_optional_rider_section";section=t
                    fs=families.get((oid,h,page,n),set())
                    subject="; ".join("Published service family: "+f for f in sorted(fs))or"Published plan terms: "+context["chapter_role"]
                    if n in sb_frames:subject="Published SB financial row: "+sb_frames[n]
                    if n in pharmacy_frames:subject=pharmacy_frames[n]
                    line_frames[n]={**context,"source_section":section,"variant":variant,"source_subject":subject,"printed_SB_networks":sb_networks,"printed_attribute_headers":printed_headers.get(n,{}),"pharmacy_column_questions":pharmacy_headers_by_line.get(n)or pharmacy_questions,"pharmacy_table_row":n in pharmacy_frames,"pharmacy_row_start":n in pharmacy_starts}
                for cell in cells:
                    pos=0
                    for projected_line in cell["text"].splitlines(keepends=True):
                        length=len(projected_line);offsets=cell["offsets"][pos:pos+length];pos+=length
                        body=projected_line.rstrip("\r\n")
                        if not body.strip():
                            key=(context["chapter_role"],cell["column"])
                            if key in streams:append_stream(key,"\n",None,context)
                            continue
                        first=next(i for i,c in enumerate(body)if not c.isspace())
                        original=offsets[first];line_number=bisect.bisect_right(starts,original)
                        sid=sid_for_line.get(line_number)
                        if sid is None:raise ValueError("Unmapped printed source line")
                        frame={**line_frames[line_number],"source_column":cell["column"]}
                        metadata=(context["chapter_role"]=="contents"or cell["column"]=="page_structure"or
                                  line_number in header_lines or
                                  (line_number>=len(lines)-1 and re.fullmatch(r"\s*\d+\s*",body)))
                        source_start=offsets[0]-source_line_starts[sid]
                        if raw_by_sid[sid][source_start:source_start+len(body)]!=body:
                            raise ValueError("Source column projection lost exact character identity")
                        segment={"source_id":sid,"source_start":source_start,"frame":frame,
                                 "locator":loc_by_sid[sid],"line":line_number}
                        if metadata:
                            atom_id=ident("CLAUSE",sid,source_start,"printed_metadata")
                            payload={"quote":body,"source_character_ranges":[[source_start,source_start+len(body)]],
                                     "context":frame,"physical_header":True}
                            self.db.execute("INSERT OR IGNORE INTO clause VALUES (?,?,?,?,?,?)",(atom_id,sid,None,"retained_structure","printed_page_table_header_or_contents",packed(payload)))
                            sid_atoms[sid]+=1
                            continue
                        key=(context["chapter_role"],cell["column"])
                        st=streams.get(key)
                        # A new printed service family starts a new proposition
                        # context; a false repeat of the same family does not.
                        if st and st["segments"]and (st["segments"][-1]["frame"]["source_subject"]!=frame["source_subject"]or frame.get("pharmacy_row_start")):
                            previous_text=st["parts"][-1].strip()if st["parts"]else""
                            title=clean(body)
                            bullet=bool(re.match(r"[•●▪◦*¢]|e\s*(?=[A-Z])|[-–—]\s",title))
                            heading_like=bool(title and title[0].isupper()and len(title)<110 and not VERB.search(title)and not bullet)
                            genuine_boundary=(frame.get("pharmacy_row_start")or frame["source_subject"].startswith("Published SB financial row:")or heading_like or
                                              bool(re.search(r"[.!?]\s*$",previous_text))or
                                              (st["parts"]and st["parts"][-1]=="\n"))
                            if genuine_boundary:
                                append_stream(key,"\n",None,frame)
                                st["scope_resets"].append(st["length"])
                        append_stream(key,body+"\n",segment,frame)
            for stream_key,st in streams.items():
                stream="".join(st["parts"]);segments=st["segments"];begins=[s["a"]for s in segments]
                clauses=decompose(stream,{"chapter_role":stream_key[0],"source_column":stream_key[1],"scope_resets":st["scope_resets"]})
                prior_uid=None
                for atom in clauses:
                    relevant=[]
                    index=max(0,bisect.bisect_right(begins,atom["start"])-1)
                    for seg_index in range(index,len(segments)):
                        seg=segments[seg_index]
                        if seg["a"]>=atom["end"]:break
                        a=max(atom["start"],seg["a"]);b=min(atom["end"],seg["b"])
                        if a<b:
                            relevant.append((seg,a,b))
                    if not relevant:continue
                    first_frame=relevant[0][0]["frame"]
                    subject=first_frame["source_subject"]
                    if stream_key[1]=="spanning_source_note"and re.search(r"Qualified Medicare Beneficiary|\bQMB\b",atom["parent_sentence"],re.I):
                        subject="Published Medicare-covered assistance cost-sharing qualification"
                    source_refs=[]
                    for seg,a,b in relevant:
                        source_refs.append({"source_id":seg["source_id"],"start":seg["source_start"]+a-seg["a"],
                            "end":seg["source_start"]+b-seg["a"],"locator":seg["locator"],"printed_line":seg["line"]})
                    parent_refs=[]
                    parent_index=max(0,bisect.bisect_right(begins,atom["parent_start"])-1)
                    for seg_index in range(parent_index,len(segments)):
                        seg=segments[seg_index]
                        if seg["a"]>=atom["parent_end"]:break
                        a=max(atom["parent_start"],seg["a"]);b=min(atom["parent_end"],seg["b"])
                        if a<b:parent_refs.append({"source_id":seg["source_id"],"start":seg["source_start"]+a-seg["a"],"end":seg["source_start"]+b-seg["a"],"locator":seg["locator"],"printed_line":seg["line"]})
                    atom["parent_source_fragments"]=parent_refs
                    atom_id=ident("CLAUSE",oid,h,stream_key,source_refs)
                    atom["source_fragments"]=source_refs;atom["source_column"]=stream_key[1]
                    atom["source_header_subject"]=subject
                    uid=None
                    if atom["kind"]in {"claim","condition"}:
                        t=clean(atom["quote"])
                        assist=bool(re.search(r"Medicaid|QMB|low.income|qualif.*assist",atom["parent_sentence"],re.I))
                        inn=bool(re.search(r"\bin.network\b",atom["parent_sentence"],re.I));oon=bool(re.search(r"\bout.of.network\b",atom["parent_sentence"],re.I))
                        network="both_networks_source_statement"if inn and oon else"in_network"if inn else"out_of_network"if oon else"network_not_explicit_in_clause"
                        if stream_key[1].endswith(":in_network"):network="in_network"
                        if stream_key[1].endswith(":out_of_network"):network="out_of_network"
                        sc={"chapter_role":stream_key[0],"source_subject":subject,"source_column":stream_key[1],
                            "network":network,"population_basis":"assistance_qualified"if assist else"source_published_basis",
                            "variant":first_frame["variant"],"source_section":first_frame["source_section"],
                            "printed_attribute_headers":first_frame.get("printed_attribute_headers",{}),
                            "published_list_intro":clean(atom["list_intro"]["quote"])if atom.get("list_intro")else None,
                            "rider_named_in_proposition":bool(re.search(r"optional|rider|platinum dental|dental platinum",atom["parent_sentence"],re.I)),
                            "conditional_relation":atom["relation"],
                            "complete_source_proposition_scope":hashlib.sha256(clean(atom["parent_sentence"]).casefold().encode()).hexdigest()}
                        if network=="network_not_explicit_in_clause":sc["unresolved_scope_discriminator"]=h
                        if stream_key[1]=="source_text"and re.search(r"\$\s*\d|\d+\s*%",t)and not first_frame.get("printed_attribute_headers"):
                            sc["unreviewed_financial_context_not_equated_by_price"]=atom_id
                        if re.fullmatch(r"(?:yes|no|none|not applicable|n/a|unlimited)[.!]?",t,re.I):
                            sc["selection_context_not_silently_equated"]=atom_id
                        if re.search(r"\b(?:this|these|those|it|its)\b",t,re.I):
                            sc["source_antecedent_scope_preserved"]=ident("ANTECEDENT",source_refs)
                        atom_units=[]
                        propositions=required_propositions(atom)
                        scoped_propositions=[]
                        for proposition_kind,proposition_role in propositions:
                            networks=first_frame.get("printed_SB_networks",[])if network=="network_not_explicit_in_clause"else[]
                            for required_network in networks or[network]:scoped_propositions.append((proposition_kind,proposition_role,required_network))
                        expanded=[]
                        is_pharmacy_row=bool(first_frame.get("pharmacy_table_row")and re.search(r"\$\s*\d|\d+\s*%",t))
                        for pk,pr,rn in scoped_propositions:
                            for pharmacy in (first_frame.get("pharmacy_column_questions",[])if is_pharmacy_row else[])or[None]:expanded.append((pk,pr,rn,pharmacy))
                        for proposition_kind,proposition_role,required_network,pharmacy_scope in expanded:
                            scoped_context={**sc,"network":required_network}
                            if pharmacy_scope:
                                scoped_context["pharmacy_scope"]=pharmacy_scope
                                scoped_context["pharmacy_value_binding"]="Required printed pharmacy-column question; exact value/cell mapping not yet verified"
                            if first_frame.get("printed_SB_networks"):
                                scoped_context["network_value_binding"]="Required printed-column question; exact value/cell mapping not yet verified"
                            if first_frame.get("pharmacy_column_questions")and re.search(r"\btier\s*\d",t,re.I)and re.search(r"\$\s*\d|\d+\s*%",t):
                                scoped_context["printed_pharmacy_questions"]=first_frame["pharmacy_column_questions"]
                            uid=self.unit(oid,proposition_kind,subject,proposition_role+": "+t.casefold(),scoped_context,
                                {"assertion":t,"condition_family":proposition_role if proposition_kind=="condition"else None,
                                 "condition_families":atom["condition_families"],"source_rule":atom["rule"],
                                 "source_basis":"carrier_only_blind_to_CMS_expected_amounts","comparison_outcome":"not_yet_verified"})
                            atom_units.append(uid)
                            for sid in {r["source_id"]for r in source_refs}:
                                self.observe(uid,sid,"carrier_clause",{"clause_id":atom_id,
                                    "quote_sha256":hashlib.sha256(atom["quote"].encode()).hexdigest()},suffix=atom_id)
                                sid_required.add(sid)
                            if prior_uid and prior_uid!=uid and atom["relation"]!="assertion":
                                self.db.execute("INSERT OR IGNORE INTO relationship VALUES (?,?,?,?)",(prior_uid,uid,atom["relation"],source_refs[0]["source_id"]))
                        atom["required_unit_ids"]=atom_units
                        if atom_units:
                            for child in atom_units[1:]:
                                self.db.execute("INSERT OR IGNORE INTO relationship VALUES (?,?,?,?)",(atom_units[0],child,"same_published_clause_individual_predicate",source_refs[0]["source_id"]))
                            uid=atom_units[0];prior_uid=uid
                    for sid in {r["source_id"]for r in source_refs}:sid_atoms[sid]+=1
                    self.db.execute("INSERT INTO clause VALUES (?,?,?,?,?,?)",(atom_id,source_refs[0]["source_id"],uid,atom["kind"],atom["rule"],packed(atom)))
            for sid in sid_seen:
                if not sid_atoms[sid]:raise ValueError("No proposition/context disposition for original passage "+sid)
                self.disposition(sid,"carrier_passage","decomposed_required_and_retained"if sid in sid_required else"retained_nonbenefit_source_material","exact_cross_passage_proposition_or_structural_disposition")
            print("Carrier document inventoried: "+oid+" "+kind+" "+h[:12],flush=True)
            self.db.commit()
        self.db.commit()

    def required_unknown(self,oid,subject,predicate,context,payload,parent_root=None):
        uid=self.unit(oid,"condition",subject,predicate,context,payload)
        self.db.execute("UPDATE semantic_unit SET state='required_evidence_missing' WHERE id=?",(uid,))
        sid=ident("SOURCE_REQUIREMENT",oid,subject,predicate,context)
        self.observe(uid,sid,"named_source_requirement",payload)
        self.disposition(sid,"named_source_requirement","required_unknown_value","named_required_predicate_not_an_unclassified_passage")
        if parent_root:self.db.execute("INSERT OR IGNORE INTO lineage VALUES (?,?)",(parent_root,uid))
        return uid

    def lineage_and_work(self):
        definitions=load(R7/"remaining-service-source-definitions.json")["unmodeled_supplemental_source_definitions"]
        service_roots={json.loads(payload).get("service_record_id"):root for root,payload in self.parent.execute("SELECT id,payload FROM obligation WHERE basis='cms_service'")}
        for item in definitions:
            self.required_unknown(item["offering_id"],item["category_code"]+": "+item["service_name"],
                "Exact published carrier definition, included service subtypes and qualifications",
                {"service_id":item["id"],"variant":"base_source_model","network":"source_default_network"},
                {"known_source":item["PBP_source"],"source_control":item["PBP_coverage_controls"],
                 "owner":"L03 data maintainer","next_action":"Bind exact carrier definition and all named service/qualification children; retain positive PBP controls.",
                 "closure_evidence":"Exact applicable carrier passages and complete independently reviewed meaning; no inference of noncoverage from absent mapping."},service_roots[item["id"]])
        for root,oid,basis,payload in self.parent.execute("SELECT id,offering_id,basis,payload FROM obligation WHERE basis IN ('amendment_applicability','rider_frequency')"):
            if basis=="amendment_applicability":
                self.required_unknown(oid,"Published amendments and benefit-change applicability",
                    "Exact applicable amendment, effective interval and affected clauses, or evidenced absence",
                    {"variant":"all_applicable_source_variants","network":"all_source_contexts"},
                    {"source_boundary":json.loads(payload),"owner":"L03 data maintainer",
                     "next_action":"Resolve retained amendment/alternate-document references without bypassing source stops.",
                     "closure_evidence":"Applicable exact source and clause/date binding, or documented permitted source limitation."},root)
            else:
                native=self.native[oid]
                packages=native['pbp'][0]['costShareGroups']['optionalSupplementalPackages']['optionalSupplementalPackagesDetails']['optSupPackagesData']
                for pkg in packages:
                    for benefit in pkg['benefitPackages']:
                        frequency=benefit['benefitPackagesInfo'].get('BenefitUnlimitedComponent')
                        if not frequency:continue
                        code=benefit['categoryCode']
                        self.required_unknown(oid,"Optional rider "+pkg['optSupPkgId']+": "+pkg['optSupPkgName']+" / "+code,
                            "Exact procedure-specific frequency, lookback/history and reset schedule",
                            {"variant":"optional_rider","rider_id":pkg['optSupPkgId'],"category_code":code,"network":"rider_source_context"},
                            {"published_CMS_frequency":frequency,"existing_gap_root":root,
                             "owner":"L03 data maintainer","next_action":"Bind the referenced exact procedure guide, preserving each existing CMS frequency and source discrepancy.",
                             "closure_evidence":"Applicable procedure-level schedule with frequencies/history and full source citations; category ranges alone do not close it."},root)
        # Bind all 153 historical holds to the precise CMS field-backed
        # semantic schedule(s), preserving the accepted treatment as a work item.
        held_fields=collections.defaultdict(set)
        for root,oid,payload in self.parent.execute("SELECT id,offering_id,payload FROM obligation WHERE basis='preserved_conflict'"):
            for field in json.loads(payload)['issue']['source_fields']:
                src=field['source'];held_fields[(oid,src['member'],src['record_ordinal'],src['field'])].add(root)
        matched_holds=set()
        for sid,oid,loc in self.parent.execute("SELECT id,offering_id,locator FROM source_unit WHERE layer='cms_table'"):
            loc=json.loads(loc);key=(oid,loc['member'],loc['record_ordinal'],loc['field'])
            for root in held_fields.get(key,()):
                for uid, in self.db.execute("SELECT unit_id FROM source_target WHERE source_id=?",(sid,)).fetchall():
                    self.db.execute("INSERT OR IGNORE INTO lineage VALUES (?,?)",(root,uid))
                    self.db.execute("UPDATE semantic_unit SET state='preserved_source_conflict' WHERE id=?",(uid,))
                    matched_holds.add(root)
        if len(matched_holds)!=153:raise ValueError("Every historical hold needs exact semantic lineage")
        self.db.execute("ATTACH DATABASE ? AS parentdb",(str(pathlib.Path(self.parent.execute("PRAGMA database_list").fetchone()[2])),))
        self.db.execute("""INSERT OR IGNORE INTO lineage SELECT b.obligation_id,t.unit_id
            FROM parentdb.binding b JOIN source_target t ON t.source_id=b.source_id""")
        for root,oid,kind,basis,payload in self.parent.execute("SELECT id,offering_id,kind,basis,payload FROM obligation"):
            n=self.db.execute("SELECT count(*) FROM lineage WHERE root_id=?",(root,)).fetchone()[0]
            if basis in {"amendment_applicability","rider_frequency","preserved_conflict"}:
                self.db.execute("INSERT INTO work_obligation VALUES (?,?,?,?)",(root,oid,basis,payload))
            if n:
                disposition="semantic_units_enumerated";reason="All source observations retained and routed to named semantic units; no evidence acceptance inferred."
            elif basis in {"amendment_applicability","rider_frequency","preserved_conflict"}:
                disposition="explicit_named_audit_obligation";reason=basis
            else:
                disposition="retained_source_control_or_nonbenefit_context";reason="Source rows are fully retained and have explicit source/individual clause dispositions; no standalone benefit assertion from this discovery container."
            self.db.execute("INSERT INTO root_disposition VALUES (?,?,?,?)",(root,kind,disposition,reason))
        self.db.commit()

    def reconcile(self):
        # Geometry is not a material semantic difference when the full
        # literal proposition explicitly fixes its network and all other scope
        # attributes agree. Unknown network/antecedent contexts remain distinct.
        for uid,oid,kind,subject,predicate,ctx,payload in self.db.execute("SELECT id,offering_id,kind,subject,predicate,context,payload FROM semantic_unit"):
            context=json.loads(ctx);data=json.loads(payload)
            if data.get('source_basis')=='carrier_only_blind_to_CMS_expected_amounts'and context.get('network')!='network_not_explicit_in_clause':
                context.pop('source_column',None)
            canonical=ident('CANONICAL',oid,kind,subject,predicate,context)
            self.db.execute("INSERT INTO canonical_unit VALUES (?,?)",(uid,canonical))
        # Inventory subject equivalence is separate from factual agreement.
        # Every multi-source unit gets an explicit, reproducible disposition.
        for uid,kind,subject,predicate,ctx in self.db.execute("SELECT id,kind,subject,predicate,context FROM semantic_unit"):
            observations=list(self.db.execute("SELECT source_id,layer,payload FROM observation WHERE unit_id=?",(uid,)))
            if len(observations)<2:continue
            layers={x[1]for x in observations}
            values=[]
            for sid,layer,payload in observations:
                item=json.loads(payload)
                values.append({"source_id":sid,"layer":layer,"value":item.get("normalized",{}).get("value",item.get("raw")),
                               "locator":item.get("locator",item.get("source"))})
            if layers=={"carrier_clause"}:
                decision="same_scoped_literal_proposition; retain_all_occurrences"
            elif layers<={"cms_table","cms_json"}:
                decision="same_inventory_question_or_schedule; full_value_equivalence_held"
            else:
                decision="source_basis_or_grain_distinction_preserved; no_factual_agreement_inferred"
            self.db.execute("INSERT INTO equivalence VALUES (?,?,?,?)",(ident("EQ",uid),uid,decision,
                packed({"subject":subject,"predicate":predicate,"context":json.loads(ctx),"observations":values,
                        "amount_presence_used":False,"accepted_for_reference":False})))
        self.db.commit()

    def finish(self):
        self.db.execute("ANALYZE");self.db.commit()
        counts=dict(self.db.execute("SELECT u.kind,count(DISTINCT c.canonical_id) FROM semantic_unit u JOIN canonical_unit c ON c.unit_id=u.id GROUP BY u.kind"))
        summary={"package_id":PACKAGE,"required_claims":counts.get("claim",0),"required_conditions":counts.get("condition",0),
            "stored_unit_representations":self.db.execute("SELECT count(*) FROM semantic_unit").fetchone()[0],
            "canonical_equivalences":self.db.execute("SELECT count(*)-count(DISTINCT canonical_id) FROM canonical_unit").fetchone()[0],
            "source_dispositions":dict(self.db.execute("SELECT disposition,count(*) FROM source_disposition GROUP BY disposition")),
            "carrier_clause_classes":dict(self.db.execute("SELECT kind,count(*) FROM clause GROUP BY kind")),
            "equivalence_dispositions":dict(self.db.execute("SELECT decision,count(*) FROM equivalence GROUP BY decision")),
            "root_dispositions":dict(self.db.execute("SELECT disposition,count(*) FROM root_disposition GROUP BY disposition")),
            "named_work_obligations":dict(self.db.execute("SELECT kind,count(*) FROM work_obligation GROUP BY kind")),
            "inventory_validation_complete":False,"semantic_inventory_frozen":False,"new_verified_claims":0,"new_accepted_entries":0}
        self.db.close();self.parent.close();return summary


def build(parent,path):
    if pathlib.Path(path).exists():raise ValueError("Use a new unsealed work path")
    inv=SemanticInventory(parent,path)
    inv.cms();print("CMS named proposition inventory built",flush=True)
    inv.carrier();print("Carrier proposition decomposition built",flush=True)
    inv.lineage_and_work();print("All prior roots have explicit lineage dispositions",flush=True)
    inv.reconcile();print("Inventory source equivalence dispositions built",flush=True)
    return inv.finish()


def build_with_carrier_cache(parent,path,carrier_cache):
    """Rebuild CMS scope while reusing unchanged, source-only carrier clauses.

    Cache reuse copies only carrier units/evidence, never CMS interpretations,
    named missing-source predicates, aliases or prior completion/acceptance.
    """
    if pathlib.Path(path).exists():raise ValueError("Use a new unsealed work path")
    inv=SemanticInventory(parent,path);inv.cms();print("CMS inventory rebuilt",flush=True)
    inv.db.execute("ATTACH DATABASE ? AS cached",(str(carrier_cache),))
    inv.db.executescript("""
    CREATE TEMP TABLE carrier_ids(id TEXT PRIMARY KEY);
    INSERT INTO carrier_ids SELECT id FROM cached.semantic_unit
      WHERE json_extract(payload,'$.source_basis')='carrier_only_blind_to_CMS_expected_amounts';
    INSERT INTO semantic_unit SELECT * FROM cached.semantic_unit WHERE id IN (SELECT id FROM carrier_ids);
    INSERT INTO observation SELECT * FROM cached.observation WHERE layer='carrier_clause';
    INSERT INTO source_target SELECT * FROM cached.source_target WHERE unit_id IN (SELECT id FROM carrier_ids);
    INSERT INTO source_disposition SELECT * FROM cached.source_disposition WHERE layer LIKE 'carrier_%';
    INSERT INTO clause SELECT * FROM cached.clause;
    INSERT INTO relationship SELECT * FROM cached.relationship WHERE parent_id IN (SELECT id FROM carrier_ids) AND child_id IN (SELECT id FROM carrier_ids);
    """)
    inv.db.commit();print("Unchanged source-only carrier extraction copied",flush=True)
    inv.lineage_and_work();inv.reconcile();return inv.finish()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--parent",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    args=p.parse_args();print(json.dumps(build(args.parent,args.output),indent=2))
