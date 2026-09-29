"""One-off export of the opus-mt models to OpenVINO IR with 8-bit weights.

Run through scripts/export_mt.sh (a throwaway container with the older
transformers the exporter needs). Skips pairs already exported.
"""

from __future__ import annotations

import os
import sys

from optimum.intel import OVModelForSeq2SeqLM, OVWeightQuantizationConfig
from transformers import AutoTokenizer

from app.translate import PAIRS, model_dir

for pair in PAIRS or sys.argv[1:]:
    out = model_dir(pair)
    if os.path.exists(os.path.join(out, "config.json")):
        print(f"{pair}: already exported")
        continue
    mid = f"Helsinki-NLP/opus-mt-{pair}"
    OVModelForSeq2SeqLM.from_pretrained(
        mid, export=True, compile=False, quantization_config=OVWeightQuantizationConfig(bits=8)
    ).save_pretrained(out)
    AutoTokenizer.from_pretrained(mid).save_pretrained(out)
    print(f"{pair}: exported to {out}")
