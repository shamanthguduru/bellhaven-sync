import os
from dotenv import load_dotenv

load_dotenv()
CRM_TOKEN = os.environ["CRM_TOKEN"]
CRM_BASE = os.environ["CRM_BASE"]
SITE_URL = os.environ["SITE_URL"]
HEADERS = {"Authorization": f"Bearer {CRM_TOKEN}"}