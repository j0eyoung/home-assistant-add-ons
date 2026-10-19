"""Uploads the yoga pictures (data/yoga-flat-5) to the private bucket, one at a time, with retries.

Run it yourself in a terminal so your keys never go anywhere else:
    python -m pip install boto3
    python C:\\AntiGravity\\WorkoutTracker\\tools\\upload_yoga.py

It asks for the bucket endpoint, bucket name and key (the secret is typed hidden). Pictures already in the
bucket are skipped, so it is safe to run again if it stops halfway.
"""
import getpass
import os
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

HERE = os.path.dirname(os.path.abspath(__file__))
FOLDER = os.path.join(HERE, "..", "data", "yoga-flat-5")
PREFIX = "workout/yoga/"


def ask(name, env, default="", secret=False):
    value = os.environ.get(env, "").strip()
    if value:
        return value
    prompt = f"{name}" + (f" [{default}]" if default else "") + ": "
    value = (getpass.getpass(prompt) if secret else input(prompt)).strip()
    return value or default


def main():
    endpoint = ask("Bucket endpoint (like https://s3.us-west-004.backblazeb2.com)", "S3_ENDPOINT")
    bucket = ask("Bucket name", "S3_BUCKET", "lpchag")
    key_id = ask("Key ID", "S3_ACCESS_KEY")
    secret = ask("Application key (hidden as you type)", "S3_SECRET_KEY", secret=True)
    if not (endpoint and bucket and key_id and secret):
        sys.exit("Endpoint, bucket and both keys are needed.")

    client = boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=key_id, aws_secret_access_key=secret, region_name="auto",
        # same setting the Trading Terminal uses: Backblaze can refuse boto3's default checksum headers
        config=Config(retries={"max_attempts": 8, "mode": "standard"}, request_checksum_calculation="when_required",
                      response_checksum_validation="when_required"))

    files = sorted(f for f in os.listdir(FOLDER) if f.lower().endswith(".jpg"))
    print(f"{len(files)} pictures to check in {os.path.normpath(FOLDER)}")
    uploaded = skipped = 0
    failed = []
    for i, name in enumerate(files, 1):
        key = PREFIX + name
        try:
            client.head_object(Bucket=bucket, Key=key)
            skipped += 1
            continue
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                sys.exit(f"Could not check the bucket ({e.response['Error']['Code']}). Check the endpoint, bucket and key.")
        for attempt in range(1, 7):
            try:
                with open(os.path.join(FOLDER, name), "rb") as f:
                    client.put_object(Bucket=bucket, Key=key, Body=f, ContentType="image/jpeg")
                uploaded += 1
                break
            except ClientError as e:
                wait = min(2 ** attempt, 30)  # "too many requests": slow down and try again
                print(f"  {name}: {e.response['Error']['Code']}, retrying in {wait}s")
                time.sleep(wait)
        else:
            failed.append(name)
        if i % 20 == 0:
            print(f"  {i}/{len(files)} done")
        time.sleep(0.15)  # gentle pace

    print(f"\nUploaded {uploaded}, already there {skipped}, failed {len(failed)}.")
    if failed:
        print("Run the script again to retry:", ", ".join(failed))
    else:
        print("All 213 pictures are in the bucket. Now tap Test connection in the app's Settings.")


if __name__ == "__main__":
    main()
