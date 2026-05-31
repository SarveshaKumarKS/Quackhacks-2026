#!/usr/bin/env python3
import os
import sys
from google.cloud import bigquery
from google.api_core.exceptions import Conflict

# Simple helper to load .env manually if python-dotenv isn't loaded yet
def load_env_fallback():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Strip trailing inline comments safely
                if " #" in line:
                    line = line.split(" #", 1)[0].strip()
                elif "\t#" in line:
                    line = line.split("\t#", 1)[0].strip()
                
                if "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip('"').strip("'")
                    os.environ[key.strip()] = val

def setup_bigquery():
    print("[*] Loading environment variables...")
    load_env_fallback()

    project_id = os.getenv("GCP_PROJECT_ID")
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if not project_id:
        print("[!] Error: GCP_PROJECT_ID is not set in environment or .env file.")
        sys.exit(1)

    print(f"[*] Target GCP Project: {project_id}")
    if credentials_path:
        print(f"[*] Using credentials at: {credentials_path}")
        # Google Cloud Client Library will auto-detect GOOGLE_APPLICATION_CREDENTIALS in env
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    else:
        print("[!] Warning: GOOGLE_APPLICATION_CREDENTIALS not specified. Relying on default ambient auth.")

    # Initialize client
    try:
        client = bigquery.Client(project=project_id)
    except Exception as e:
        print(f"[!] Error initializing BigQuery client: {e}")
        sys.exit(1)

    # 1. Create dataset if not exists
    dataset_id = f"{project_id}.doppelganger_dataset"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"

    print(f"[*] Checking/Creating dataset: {dataset_id}...")
    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"[x] Dataset {dataset_id} is ready.")
    except Exception as e:
        print(f"[!] Failed to create/locate dataset: {e}")
        sys.exit(1)

    # 2. Create table if not exists
    table_id = f"{dataset_id}.agent_memory"
    schema = [
        bigquery.SchemaField("id", "INT64", mode="NULLABLE", description="Unique incremental memory ID"),
        bigquery.SchemaField("session_id", "STRING", mode="NULLABLE", description="Active session context"),
        bigquery.SchemaField("memory_type", "STRING", mode="NULLABLE", description="Type of memory: persona, preference, correction, action_log"),
        bigquery.SchemaField("content", "STRING", mode="NULLABLE", description="Learned value or structured fact"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="NULLABLE", description="Record creation timestamp"),
    ]

    table = bigquery.Table(table_id, schema=schema)
    print(f"[*] Checking/Creating table: {table_id}...")
    try:
        table = client.create_table(table, exists_ok=True)
        print(f"[x] Table {table_id} is ready and matches required schema.")
    except Exception as e:
        print(f"[!] Failed to create/locate table: {e}")
        sys.exit(1)

    print("[x] BigQuery self-bootstrapping completed successfully.")

if __name__ == "__main__":
    setup_bigquery()
