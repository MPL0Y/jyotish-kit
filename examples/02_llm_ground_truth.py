"""
Example 02: Generate Deterministic Ground-Truth for LLM System Prompts.
Feed this JSON into Claude, GPT-4o, or local LLMs to eliminate astrology hallucinations.
"""

import json
from jyotish_kit import Jyotish

chart = Jyotish.create(
    dt_local="2001-10-11T05:57:30",
    lat=29.681312,
    lon=77.010063,
    tz_name="Asia/Kolkata",
    place_name="Karnal, Haryana, India",
)

# 1. Generate verified ground truth context for career & wealth
context = chart.to_llm_context(topics=["career", "wealth"])

print("=== GROUND-TRUTH LLM CONTEXT PAYLOAD ===")
print(json.dumps(context, indent=2)[:800] + "\n... [truncated for display]")

# 2. How to use with an LLM (Pseudo-code)
prompt = f"""
You are an expert Vedic astrologer. Answer the user's question using ONLY the verified facts below.
Do not hallucinate planetary positions or dasha dates.

### VERIFIED GROUND TRUTH:
{json.dumps(context, indent=2)}

### USER QUESTION:
Why do I feel suffocated in my current corporate SDE job and want to work from home?
"""

print("\n=== SYSTEM PROMPT READY FOR INJECTION ===")
print("Prompt length:", len(prompt), "characters")
