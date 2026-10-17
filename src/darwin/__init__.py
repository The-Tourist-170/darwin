"""Darwin: an autonomous general-purpose agent."""

import os

# Quiet external-library noise before anything imports it.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("MEM0_TELEMETRY", "False")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="posthog")
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*", module="huggingface_hub")

try:  # huggingface load-progress bars ("Loading weights: 100%")
    from transformers.utils import logging as _hf_logging

    _hf_logging.disable_progress_bar()
    from huggingface_hub.utils import logging as _hub_logging

    _hub_logging.set_verbosity_error()
except Exception:
    pass
