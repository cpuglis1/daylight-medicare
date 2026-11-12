"""Private CSG evidence for the D128 eight-ZIP backend scope."""

SCOPE = {
    'reference_year': 2026, 'county_fips': '12021',
    'zips': [str(n) for n in range(34101, 34109)],
    'ages': list(range(65, 75)),
    'genders': ['Female', 'Male'], 'tobacco': ['Non-Tobacco', 'Tobacco User'],
    'requested_effective_date': '2026-11-10',
}
VARIANTS = ('A', 'B', 'C', 'D', 'F', 'HDF', 'G', 'HDG', 'K', 'L', 'M', 'N')


class CsgError(ValueError):
    pass
