"""D96 versioned Collier PDP/Medigap source research. Consumer release is held."""

VERSION = "collier-plan-types/1"
SCOPE = {"reference_year": 2026, "county_fips": "12021", "pdp_region": "11"}


class PlanTypeError(ValueError):
    """A rejected source, scope, authority or bounded query."""
