"""Cohort residual tracing through U.S. decennial census data.

Traces synthetic birth cohorts across decennial censuses (2000 -> 2010 -> 2020)
using the census survival ratio method: each cohort's national survival between
censuses sets the expectation, and the county-level deviation from that
expectation is the net migration residual.
"""

__version__ = "0.1.0"
