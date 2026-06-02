# MemeDeliveryBot

Image-only automation for sourcing meme images from Reddit and publishing them to Instagram with the Instagram Graph API.

This version intentionally does not support Instagram Reels, videos, TTS, ffmpeg processing, or a hosted database. Repost tracking is handled by an audit trail file on a dedicated Git branch.

## How It Works

1. Fetch top image posts from configured Reddit subreddits.
2. Filter out unsafe or unsupported content: NSFW, spoiler, stickied, gallery, video, GIF, and non-image URLs.
3. Load `state/posted.jsonl` from the `bot-state` branch.
4. Skip any candidate already seen by Reddit id, normalized image URL, or image SHA-256 hash.
5. Publish the selected image to Instagram.
6. Append the successful post to `state/posted.jsonl`.
7. Commit and push that tracker update back to `bot-state`.

The tracker is only written after Instagram returns a published media id.

## Project Structure

```text
meme_bot/
  config.py          Environment configuration and validation
  instagram.py       Image-only Instagram Graph API client
  reddit_source.py   Reddit candidate fetching and filtering
  retry.py           HTTP retry and Retry-After handling
  runner.py          Main orchestration
  token_manager.py   Instagram token expiry check and refresh
  tracker.py         JSONL audit trail loading, duplicate checks, and hashing
scripts/
  refresh_instagram_token.py
.github/workflows/
  post-meme.yml
  refresh-instagram-token.yml
main.py              Thin entrypoint wrapper
publish.py           Thin image-publishing compatibility wrapper
```

## Requirements

- Python 3.10 or newer.
- Reddit API credentials for a script app.
- Instagram Business or Creator account connected for Instagram Graph API publishing.
- GitHub Actions secrets for scheduled automation.

Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Required GitHub Actions secrets:

- `ACCESS_TOKEN`
- `INSTAGRAM_ACCOUNT_ID`
- `FB_APP_ID`
- `FB_APP_SECRET`
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- `GH_SECRETS_TOKEN`

Optional secrets:

- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`

Optional GitHub Actions variables or local environment variables:

- `SUBREDDITS`: comma-separated list, default `memes`
- `POST_TIME_FILTER`: Reddit listing period, default `day`
- `POST_LIMIT`: posts scanned per subreddit, default `100`
- `MIN_SCORE`: minimum Reddit score, default `0`
- `TRACKER_PATH`: default `state/posted.jsonl`
- `GRAPH_VERSION`: default `v22.0`
- `REQUEST_TIMEOUT_SECONDS`: default `20`
- `MAX_RETRY_ATTEMPTS`: default `3`
- `RETRY_BASE_SECONDS`: default `2`
- `REFRESH_THRESHOLD_DAYS`: default `21`
- `DRY_RUN`: when true, selects and hashes a candidate but does not publish or write tracker state
- `USE_REDDIT_SAVED_GUARD`: skip Reddit submissions already saved by the authenticated Reddit account
- `MARK_REDDIT_SAVED`: save the Reddit submission after Instagram publish succeeds

## GitHub Actions

### Posting

`.github/workflows/post-meme.yml` runs daily and supports manual dispatch.

For a manual dry run, use workflow dispatch with `dry_run` set to `true`. The workflow still loads the tracker and hashes the selected image, but it does not publish to Instagram or append tracker state.

The first successful live run creates the `bot-state` branch if it does not exist.

### Token Refresh

`.github/workflows/refresh-instagram-token.yml` runs weekly and supports manual dispatch.

The workflow checks token validity and expiry. If the token is inside the refresh threshold, it writes the refreshed token to a workflow-local temp file and updates the GitHub Actions `ACCESS_TOKEN` secret using `GH_SECRETS_TOKEN`.

`GH_SECRETS_TOKEN` should be a fine-grained token or GitHub App token with permission to update Actions secrets for this repository.

## Local Use

Dry run:

```bash
$env:DRY_RUN="true"
python main.py
```

Live run:

```bash
python main.py
```

Refresh token locally:

```bash
python scripts/refresh_instagram_token.py
```

## Tracker Format

Each successful post appends one JSON object to `state/posted.jsonl`:

```json
{"reddit_id":"abc123","image_url":"https://i.redd.it/example.jpg","image_hash":"...","title":"Example","subreddit":"memes","instagram_media_id":"178...","posted_at":"2026-06-02T00:00:00Z"}
```

Malformed lines are ignored with a warning so one bad audit line does not stop posting.

## Recovery

If Instagram publishing succeeds but the workflow fails before pushing `bot-state`, inspect the workflow logs for the Reddit id and Instagram media id, then manually add the corresponding record to `state/posted.jsonl` on the `bot-state` branch. Enabling `MARK_REDDIT_SAVED=true` provides a secondary guard when Reddit user credentials are configured.
