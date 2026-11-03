"""Optional live proposal extraction, sharing the existing provider/budget boundary."""
import copy
from guide_agent import GuideAgent
from guest_profiles import ProfileError
class ReadinessAgent(GuideAgent):
    def __init__(self,contract,facts,content,**kwargs):
        contract=copy.deepcopy(contract);self.details={t['id']:t for t in content['triggers']}
        for t in content['triggers']:
            contract['nodes'].append({'id':t['id'],'kind':'single_choice','question':t['question'],'writes':['readiness.'+t['id']],'options':[{'id':v,'label':label} for v,label in t['choices']]})
        super().__init__(contract,facts,**kwargs);self.fields={'readiness.'+id for id in self.details}
    def validate_output(self,value,message,guide,facts,eligible,owner):
        allowed={'readiness.'+id for id in eligible if id in self.details}
        if any(p.get('field')not in allowed for p in value.get('patches',[]) if isinstance(p,dict)):raise ProfileError('The interpretation is for a different detail. Your reports are unchanged.')
        result=super().validate_output(value,message,guide,facts,eligible,owner)
        for patch in result['patches']:
            id=patch['field'].split('.')[-1]
            if patch['value']not in dict(self.details[id]['choices']):raise ProfileError('Choose a supported answer or leave it unknown.')
        return result
