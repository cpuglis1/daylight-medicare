"""Research-only arithmetic for explicitly assumed, already-qualified synthetic cases.
Never imports user profiles, assesses eligibility or sends enrollment transactions.
A null is an unknown, not a rejection or zero. There is no production API.
"""
import calendar
from datetime import date,timedelta
from decimal import Decimal,ROUND_HALF_UP

def month(d,offset=0):
    n=d.year*12+d.month-1+offset
    return date(n//12,n%12+1,1)
def last(d):return date(d.year,d.month,calendar.monthrange(d.year,d.month)[1])
def ordinary_age65_iep(born):
    # Assumes every non-age requirement and ordinary age-based IEP; deemed relief is separate.
    eligibility=date(born.year+65,born.month,1)
    if born.day==1:eligibility=month(eligibility,-1)
    return eligibility,month(eligibility,-3),last(month(eligibility,3))
def iep_coverage(eligibility,enrollment):
    if eligibility.year<2023:raise ValueError('Historical formula deliberately unsupported')
    if not month(eligibility,-3)<=enrollment<=last(month(eligibility,3)):raise ValueError('Outside assumed ordinary IEP')
    return month(eligibility) if enrollment<month(eligibility) else month(enrollment,1)
def gep_coverage(enrollment):
    if enrollment.year<2023 or not date(enrollment.year,1,1)<=enrollment<=date(enrollment.year,3,31):raise ValueError('Not post-2023 GEP')
    return month(enrollment,1)
def free_a_retro(eligibility,application):
    if application<eligibility:raise ValueError('This fixture models applications after eligibility only')
    return max(month(eligibility),month(application,-6))
def ghp_deadline(last_qualifying_covered_month):return last(month(last_qualifying_covered_month,8))
def ghp_coverage_options(last_qualifying_covered_month,enrollment):
    # Assumes all months after that month are wholly uncovered, no restored/retro-notice exception.
    if enrollment>ghp_deadline(last_qualifying_covered_month):raise ValueError('Outside assumed SEP')
    if enrollment<=last(month(last_qualifying_covered_month,1)):
        return [month(enrollment,i) for i in range(4)]
    return [month(enrollment,1)]
def volunteer_window(cessation):return month(cessation),last(month(cessation,5))
def release_window(release):return release,last(month(release,12))
def ma_icep(first_ab,b_iep_end):return month(first_ab,-3),max(last(month(first_ab,2)),b_iep_end)
def initial_cd_coverage(eligibility,election):return max(month(eligibility),month(election,1))
def aep(coverage_year):return date(coverage_year-1,10,15),date(coverage_year-1,12,7),date(coverage_year,1,1)
def institutional_end(discharge):return last(month(discharge,2))
def disaster_cd_end(event_end):return last(month(event_end,2))
def full_calendar_months(start,end):
    if end<start:raise ValueError('Negative interval')
    cursor=month(start) if start.day==1 else month(start,1);n=0
    while last(cursor)<=end:n+=1;cursor=month(cursor,1)
    return n

def _count(n):
    if n is None:return False
    if type(n) is not int or n<0:raise ValueError('Need nonnegative integer of already countable months')
    return True

def part_a_increment(countable_months):
    if not _count(countable_months):return None
    blocks=countable_months//12
    return {'percent':10 if blocks else 0,'surcharge_months':blocks*24}
def part_b_increment(countable_months):
    if not _count(countable_months):return None
    return (countable_months//12)*10

def part_d_gap(start,end,*,coverage_year=2026,after_iep=None,d_eligible=None,no_creditable=None,no_d=None,reset_applies=None):
    # Single continuous interval. Known complete evidence flags are mandatory; no personal inference.
    if coverage_year!=2026:raise ValueError('Only published 2026 national base retained')
    if any(x is None for x in [after_iep,d_eligible,no_creditable,no_d,reset_applies]):return None
    if any(type(x) is not bool for x in [after_iep,d_eligible,no_creditable,no_d,reset_applies]):raise ValueError('Evidence flags must be bool or unknown')
    days=(end-start).days+1
    if days<=0:raise ValueError('Negative interval')
    trigger=days>=63 and after_iep and d_eligible and no_creditable and no_d and not reset_applies
    months=full_calendar_months(start,end) if trigger else 0
    value=(Decimal('38.99')*Decimal('0.01')*months/Decimal('0.10')).quantize(Decimal('1'),rounding=ROUND_HALF_UP)*Decimal('0.10')
    return {'consecutive_days':days,'trigger':trigger,'full_countable_months':months,'monthly_2026_usd':format(value,'.2f')}
