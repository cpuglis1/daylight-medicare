"""r9 guard around the sealed r8 complete-meaning comparator.

Inventory scope markers identify work to interpret. Equal markers are not
known values and cannot become agreement or a released reference entry.
"""
from __future__ import annotations
from l03_comparison_contract import compare as compare_meaning,DIMENSIONS

SOURCE_PLACEHOLDERS={
    'source_default_network','network_not_explicit_in_clause',
    'source_category_and_controls','source_published_basis','CMS_submission_basis',
    'source_selected_type_not_yet_interpreted','base_or_document_default',
    'named_optional_rider_section','source_named_network','rider_source_context',
    'standard_or_source_default_mail_order','standard_or_source_default_retail',
    'not_yet_verified',
}


def has_source_placeholder(value):
    if isinstance(value,str):return value in SOURCE_PLACEHOLDERS
    if isinstance(value,dict):return any(has_source_placeholder(v)for v in value.values())
    if isinstance(value,list):return any(has_source_placeholder(v)for v in value)
    return False


def compare(cms,carrier,**kwargs):
    for side in [cms,carrier]:
        if side and any(has_source_placeholder(side.get(k))for k in DIMENSIONS):
            return {'schema':'l03-meaning-comparison-r9/1','outcome':'insufficient_evidence',
                    'differences':['uninterpreted_source_scope'],'accepted_for_reference':False}
    return compare_meaning(cms,carrier,**kwargs)
