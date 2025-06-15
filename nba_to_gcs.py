import praw
import pandas as pd
from datetime import datetime
from google.cloud import storage

client_id = "v2irum4i08Av02DRHCsRnQ"
client_secret = "u5H__Gb2URhKXjqOln6y_8QRLExJVA"
user_agent = "nba-data-bot by /u/DogRemarkable4848"
username = "DogRemarkable4848"

reddit = praw.Reddit(
    client_id=client_id,
    client_secret=client_secret,
    user_agent=user_agent
)


posts = []
subreddit = reddit.subreddit("nba")
for post in subreddit.new(limit=500): 
    posts.append({
        "title": post.title,
        "score": post.score,
        "url": post.url,
        "num_comments": post.num_comments,
        "created_utc": datetime.utcfromtimestamp(post.created_utc),
        "id": post.id
    })

df = pd.DataFrame(posts)
filename = f"nba_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df.to_csv(filename, index=False)


bucket_name = "nba-reddit-data-2025-ruchi"
blob_name = f"nba_data/{filename}"

client = storage.Client()
bucket = client.bucket(bucket_name)
blob = bucket.blob(blob_name)
blob.upload_from_filename(filename)
print(f"Uploaded {filename} to gs://{bucket_name}/{blob_name}")
