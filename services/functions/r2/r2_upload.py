from services.functions.r2.r2_client import get_r2_client
from time import time
import os
import uuid


def upload_video(file_input):
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
    R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")

    if not all([R2_BUCKET_NAME, R2_PUBLIC_URL]):
        raise ValueError("R2 environment variables are missing (R2_BUCKET_NAME, R2_PUBLIC_URL)")

    s3 = get_r2_client()

    randomId = uuid.uuid4().hex
    key = f"uploads/file-{randomId}.mp4"
    
    print(f"Uploading to bucket: {R2_BUCKET_NAME}")
    print(f"Key: {key}")

    if isinstance(file_input, str) and os.path.exists(file_input):
        with open(file_input, "rb") as f:
            s3.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=key,
                Body=f,
                ContentType="video/mp4",
            )
    else:
        s3.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=key,
            Body=file_input,
            ContentType="video/mp4",
        )

    if os.path.exists(file_input):
        os.remove(file_input)

    while os.path.exists(file_input):
        time.sleep(1)

    return f"{R2_PUBLIC_URL}/{key}"

