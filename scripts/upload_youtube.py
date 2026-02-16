import json
import os
import pathlib
import sys
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

CURRENT_VERSE_JSON = Path("current_verse.json")

CLIENT_SECRETS_FILE = "client_secrets.json"   # from Google Cloud Console[web:76][web:78]
TOKEN_FILE = "oauth_token.json"               # will be created after first auth
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]  # upload scope[web:76][web:78]


def load_current_verse():
    if not CURRENT_VERSE_JSON.exists():
        print("current_verse.json not found.", file=sys.stderr)
        sys.exit(1)
    with CURRENT_VERSE_JSON.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_credentials():
    creds = None
    token_path = Path(TOKEN_FILE)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no valid credentials, do the OAuth flow.[web:76][web:78][web:82]
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # refresh using refresh token
            from google.auth.transport.requests import Request

            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            # This opens a browser on first run (locally). In CI, you'd use a pre-generated token.
            creds = flow.run_console()

        # Save the credentials for the next run
        with open(TOKEN_FILE, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    return creds


def build_youtube_client(creds):
    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, video_path: Path, title: str, description: str, tags=None, privacy_status="public"):
    if tags is None:
        tags = []

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",  # People & Blogs, reasonable default
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    try:
        print("Uploading video to YouTube...")
        response = request.execute()
    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred:\n{e.content}", file=sys.stderr)
        sys.exit(1)

    video_id = response.get("id")
    print(f"Upload successful. Video ID: {video_id}")
    return video_id


def main():
    data = load_current_verse()

    video_path_str = data.get("video_path")
    reference = data.get("reference")
    summary_en = data.get("summary_en", "")
    summary_te = data.get("summary_te", "")
    title_te = data.get("title_te", "")

    if not video_path_str or not reference:
        print("current_verse.json must contain 'video_path' and 'reference'.", file=sys.stderr)
        sys.exit(1)

    video_path = Path(video_path_str)
    if not video_path.exists():
        print(f"Video file not found: {video_path}", file=sys.stderr)
        sys.exit(1)

    # Build title & description
    # For example: Telugu title + reference.
    title = f"{title_te} | {reference}" if title_te else reference

    # Simple bilingual description (short).[web:76][web:78]
    desc_lines = [
        f"Bible verse: {reference}",
        "",
        "English meaning (for teens):",
        summary_en,
        "",
        "తెలుగు వివరణ:",
        summary_te,
        "",
        "#BibleVerse #TeluguChristian #Shorts",
    ]
    description = "\n".join(desc_lines)

    tags = ["Bible", "Bible Verse", "Christian", "Telugu", "Shorts"]

    creds = get_credentials()
    youtube = build_youtube_client(creds)
    upload_video(youtube, video_path, title, description, tags)


if __name__ == "__main__":
    main()
