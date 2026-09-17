"""Configuration for the hackathon app.

In particular, the following constants are 
  GROUNDTRUTH_FILENAME - filename of the answer key in the private GT dataset
  LEADERBOARD_HEADERS - columns displayed on the leaderboard
  CHALLENGE_ACTIVE - set to False to hide leaderboard submission tabs
  MAX_TRACK1_SUBMISSIONS - how many Track 1 uploads each participant (a HF user) is allowed
  MAX_TRACK2_SUBMISSIONS - how many Track 2 uploads each participant (a HF user) is allowed
"""

from dotenv import load_dotenv

load_dotenv()

# URLs
DATASET_URL = "https://huggingface.co/datasets/SageBio/mva-hackathon-2026-data"
DISCUSSIONS_URL = "https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/discussions"

# Sponsor logos
# Each entry: (path_to_static_file, alt_text, optional_extra_css_class)
# These logos will be loaded in app.py.
SPONSOR_LOGOS = [
    ("static/logos/mva-society-logo.jpg", "MVA Society", "sponsor-logo-rounded"),
    ("static/logos/sage-logo.svg", "Sage Bionetworks", "sponsor-logo-rounded"),
    ("static/logos/hf-logo.svg", "Hugging Face", "sponsor-logo-rounded"),
    ("static/logos/powered-by-aws.svg", "Powered by AWS", "sponsor-logo-wide"),
    ("static/logos/anthropic-logo.svg", "Anthropic", "sponsor-logo-rounded"),
    ("static/logos/BEACON_dark.png", "BEACON", ""),
]

# HF private datasets
LEADERBOARD_DATASET = "SageBio/mva-hackathon-2026-leaderboard"
GROUNDTRUTH_DATASET = "SageBio/mva-hackathon-2026-gt"
GROUNDTRUTH_FILENAME = "gold_standard_track1.json"

# HF submission folders
# Folder paths inside LEADERBOARD_DATASET; one JSON file is created per submission.
TRACK1_SUBMISSIONS_FOLDER = "track1/"
TRACK2_SUBMISSIONS_FOLDER = "track2/"

# Leaderboard display columns
LEADERBOARD_HEADERS = ["#", "Participant", "Rank Points", "F-max", "Model", "Submitted"]

# Challenge control
CHALLENGE_ACTIVE = True
MAX_TRACK1_SUBMISSIONS = 6
MAX_TRACK2_SUBMISSIONS = 3
