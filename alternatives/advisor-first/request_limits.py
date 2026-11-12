"""Owner-approved :8893 request bounds; independent of shared price verification.

The pinned engine/rate receipt and other variants keep their original limits.
These bounds do not change the $5 UTC-day cap, output allowance or stage count.
"""
# Owner removed the local input-token ceiling on November 4, 2026.
# Count and fund the actual request before submission; retain the daily cap.
INPUT_TOKENS = None
OUTPUT_TOKENS = 900
REQUEST_BYTES = 96_000
