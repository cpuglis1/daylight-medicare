"""Conservative matching of explicit catalog actions; never interprets advice."""
import re


def match_catalog_action(message, on_screen=None):
    if not isinstance(message,str):return None
    text=' '.join(message.casefold().strip().rstrip('.!').split())
    text=re.sub(r'^(?:yes,? i live in collier county[.!]?\s*|then[, ]+|okay[, ]+|ok[, ]+)','',text)
    ids=re.findall(r'[hrs]\d{4}-\d{3}-\d{3}-2027',text)
    if ids and re.fullmatch(r'(?:compare|show comparison of) [hrs]\d{4}-\d{3}-\d{3}-2027(?:(?:, ?| and | with )[hrs]\d{4}-\d{3}-\d{3}-2027){1,2}',text):
        return {'action':'compare','plan_ids':[pid.upper() for pid in ids]}
    if re.fullmatch(r'(?:show|view|select)(?: plan)?(?: details)? [hrs]\d{4}-\d{3}-\d{3}-2027',text):
        return {'action':'plan','plan_ids':[ids[0].upper()]}
    if re.fullmatch(r'(?:sort|order)(?: these| plans)? by (?:monthly )?premium',text):
        return {'category':(on_screen or {}).get('category') or 'all','priorities':['monthly_premium']}
    if text in {'just show me plans','browse plans','show plans','show me plans','browse all plans','show all plans'}:
        return {'category':'all','priorities':[]}
    if not re.fullmatch(r'(?:show|browse|list|sort|re-sort)(?: me)?(?: the| all| these| published| captured| local| collier county| naples| 2027)*(?: advantage| medicare advantage| drug| standalone drug| pdp| special needs| snp)? plans(?: with(?:out)? drug coverage)?(?: sorted| ordered)?(?: by (?:monthly )?premium| by monthly cost| lowest premium first)?(?:,? with doctors as my first priority)?',text):
        return None
    category='SNP' if re.search(r'special needs|snp',text) else 'PDP' if re.search(r'\bdrug plans|pdp',text) else 'MA' if 'without drug' in text else 'MA-PD' if 'advantage' in text and 'with drug' in text else 'all'
    priorities=['monthly_premium'] if 'premium' in text or 'monthly cost' in text else []
    if 'doctors as my first priority' in text: priorities.insert(0,'doctors')
    return {'category':category,'priorities':priorities}
