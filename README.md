# MemeDeliveryBot

Automation for sourcing meme images and short Reddit-hosted videos from Reddit and publishing them to Instagram with the Instagram Graph API.

This version supports image posts and Reddit-sourced Instagram Reels. It does not run AI video generation, TTS, account splitting, or a hosted database. Repost tracking, performance history, and generated optimization config are handled by files on a dedicated Git branch.

## How It Works

1. Fetch image posts from configured Reddit subreddits using hot, rising, and new listings by default.
2. Filter out unsafe or unsupported content: NSFW, spoiler, stickied, gallery, video, GIF, and non-image URLs.
3. Fetch top Reddit comments when available and score each candidate for Instagram fit.
4. Load `state/posted.jsonl` and `state/performance.json` from the `bot-state` branch.
5. Skip any candidate already seen by Reddit id, permalink, normalized source/media URL, normalized title, or image SHA-256 hash.
6. Generate a rotating, attribution-preserving caption with minimal hashtags.
7. Publish the selected image to Instagram.
8. Append the successful post to `state/posted.jsonl`, update `state/performance.json`, append run history, and push the state update back to `bot-state`.

The tracker is only written after Instagram returns a published media id.

Reel posting uses a parallel flow:

1. Fetch Reddit-hosted video posts from configured Reel subreddits using hot, rising, and new listings by default.
2. Filter out unsafe, unsupported, too short, too long, very low-resolution, or weird-aspect candidates when metadata is available.
3. Score candidates for fast payoff, discussion/reaction potential, duration, freshness, duplicate risk, and historical performance.
4. Download and lightly normalize the selected video with `yt-dlp` and `ffmpeg`.
5. Skip any candidate already seen by Reddit id, permalink, normalized source/media URL, normalized title, or video SHA-256 hash.
6. Generate a rotating Reel caption and publish the local MP4 through Instagram's Reels resumable upload flow.
7. Append the successful Reel to `state/reels-posted.jsonl`, update `state/performance.json`, append run history, and push the state update back to `bot-state`.

## Instagram Scoring

Candidates are no longer ranked only by Reddit score. The scorer combines:

- Reddit score, comment count, upvote ratio, post age, and listing freshness.
- Title clarity, shareability, quick-payoff language, Reddit-only context risk, and top-comment reaction signals.
- Media type, Reel duration, and available video width/height/aspect metadata.
- Duplicate/repost risk from tracker and performance history.
- Generated historical weights for subreddit, posting hour, media type, caption template, hashtag pool, and Reel duration bucket.

The default scorer prefers posts from the last 6-12 hours, downranks older content, soft-downranks Reels over 45 seconds, and rejects exact duplicates. Thresholds are configurable through env vars or `state/optimized-config.json` on `bot-state`.

## Captions

Captions use the Reddit title, subreddit attribution, media type, score signals, and top-comment reaction signals. The bot rotates CTA templates such as "Send this to the friend who needs to see it.", "Rate this 1-10.", and "The comments were ruthless." It avoids recently used templates, keeps hashtags minimal, randomizes hashtag pools, and preserves `via r/{subreddit} on Reddit` attribution.

## Project Structure

```text
meme_bot/
  config.py          Environment configuration and validation
  instagram.py       Instagram Graph API client for images and Reels
  analytics_runner.py Scheduled Instagram metric collection
  captions.py        Caption template and hashtag generation
  optimizer.py       Scheduled config self-optimization
  performance_store.py Versioned JSON performance history and duplicate index
  reel_runner.py     Reels orchestration
  reel_source.py     Reddit video candidate fetching and filtering
  reddit_source.py   Reddit candidate fetching and filtering
  retry.py           HTTP retry and Retry-After handling
  runner.py          Main orchestration
  scoring.py         Instagram-focused candidate scoring
  tuning.py          Generated config, env overrides, and tuning defaults
  token_manager.py   Instagram token expiry check and refresh
  tracker.py         JSONL audit trail loading, duplicate checks, and hashing
  video_processing.py yt-dlp/ffmpeg download, normalization, and hashing
scripts/
  refresh_instagram_token.py
.github/workflows/
  post-meme.yml
  post-reel.yml
  refresh-instagram-token.yml
main.py              Thin image entrypoint wrapper
publish.py           Thin image-publishing compatibility wrapper
```

## Requirements

- Python 3.10 or newer.
- `ffmpeg` and `ffprobe` for Reel posting.
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
- `IMAGE_LISTING_MODES`: comma-separated Reddit listings, default `hot,rising,new`; supports `hot`, `rising`, `new`, and `top`
- `POST_TIME_FILTER`: Reddit listing period, default `day`
- `POST_LIMIT`: posts scanned per subreddit, default `100`
- `MIN_SCORE`: minimum Reddit score, default `0`
- `TRACKER_PATH`: default `state/posted.jsonl`
- `PERFORMANCE_STORE_PATH`: default `state/performance.json`
- `RUN_HISTORY_PATH`: default `state/run-history.jsonl`
- `OPTIMIZED_CONFIG_PATH`: default `state/optimized-config.json`
- `GRAPH_VERSION`: default `v22.0`
- `REQUEST_TIMEOUT_SECONDS`: default `20`
- `MAX_RETRY_ATTEMPTS`: default `3`
- `RETRY_BASE_SECONDS`: default `2`
- `REFRESH_THRESHOLD_DAYS`: default `21`
- `DRY_RUN`: when true, selects and hashes a candidate but does not publish or write tracker state
- `USE_REDDIT_SAVED_GUARD`: skip Reddit submissions already saved by the authenticated Reddit account
- `MARK_REDDIT_SAVED`: save the Reddit submission after Instagram publish succeeds
- `REEL_SUBREDDITS`: comma-separated list, defaults to `SUBREDDITS`, then `memes`
- `REEL_LISTING_MODES`: comma-separated Reddit listings, default `hot,rising,new`
- `REEL_POST_TIME_FILTER`: Reddit listing period for Reels, default `day`
- `REEL_POST_LIMIT`: posts scanned per Reel subreddit, default `100`
- `REEL_MIN_SCORE`: minimum Reddit score for Reels, defaults to `MIN_SCORE`
- `REEL_TRACKER_PATH`: default `state/reels-posted.jsonl`
- `REEL_MAX_DURATION_SECONDS`: default `90`
- `REEL_SOFT_MAX_DURATION_SECONDS`: scoring downrank starts above this duration, default `45`
- `REEL_MAX_BYTES`: default `100000000`
- `REEL_MIN_WIDTH`: reject detectable videos below this width, default `240`
- `REEL_MIN_HEIGHT`: reject detectable videos below this height, default `240`
- `REEL_MIN_ASPECT_RATIO`: reject detectable videos below this aspect ratio, default `0.35`
- `REEL_MAX_ASPECT_RATIO`: reject detectable videos above this aspect ratio, default `3.0`
- `REEL_SHARE_TO_FEED`: default `false`; keep false to force Reels-only publishing instead of also sharing to the feed
- `REELS_DRY_RUN`: when true, selects/downloads/hashes a Reel candidate but does not publish or write tracker state
- `TOP_COMMENTS_LIMIT`: top Reddit comments fetched per candidate, default `5`
- `SCORING_MINIMUM_TOTAL_SCORE`: default `35`
- `SCORING_PREFERRED_AGE_HOURS`: default `12`
- `SCORING_MAX_AGE_HOURS`: default `48`
- `INSTAGRAM_INSIGHT_METRICS`: default `likes,comments,saved,shares,reach,views,plays,total_interactions,follows`
- `ANALYTICS_LOOKBACK_DAYS`: default `14`
- `ANALYTICS_MAX_MEDIA_PER_RUN`: default `50`
- `SELF_OPTIMIZATION_ENABLED`: default `true`; set `false` to disable scheduled config updates
- `OPTIMIZER_MIN_TOTAL_SAMPLES`: default `20`
- `OPTIMIZER_MIN_GROUP_SAMPLES`: default `5`
- `OPTIMIZER_MAX_WEIGHT_CHANGE`: default `0.15`

## GitHub Actions

### Posting

`.github/workflows/post-meme.yml` runs twice daily at 14:17 and 23:17 UTC and supports manual dispatch.

For a manual dry run, use workflow dispatch with `dry_run` set to `true`. The workflow still loads the tracker and hashes the selected image, but it does not publish to Instagram or append tracker state.

The first successful live run creates the `bot-state` branch if it does not exist.

Posting workflows now commit `state/posted.jsonl` or `state/reels-posted.jsonl`, `state/performance.json`, and `state/run-history.jsonl` back to `bot-state`. Dry runs do not publish or commit state.

### Reel Posting

`.github/workflows/post-reel.yml` runs three times daily at 03:43, 11:43, and 19:43 UTC and supports manual dispatch.

For a manual dry run, use workflow dispatch with `dry_run` set to `true`. The workflow still loads the tracker, downloads, normalizes, and hashes the selected video, but it does not publish to Instagram or append tracker state.

### Token Refresh

`.github/workflows/refresh-instagram-token.yml` runs weekly and supports manual dispatch.

The workflow checks token validity and expiry. If the token is inside the refresh threshold, it writes the refreshed token to a workflow-local temp file and updates the GitHub Actions `ACCESS_TOKEN` secret using `GH_SECRETS_TOKEN`.

Weekly is intentional: Meta long-lived tokens are a multi-week expiry concern, and the script no-ops unless the token is inside `REFRESH_THRESHOLD_DAYS`.

`GH_SECRETS_TOKEN` should be a fine-grained token or GitHub App token with permission to update Actions secrets for this repository.

### Analytics Collection

`.github/workflows/collect-instagram-analytics.yml` runs daily and supports manual dispatch. It reads recent Instagram media IDs from `state/performance.json`, requests available Instagram insights, records unsupported metrics in `unavailable_metrics`, recalculates normalized performance scores, and commits updates to `bot-state`.

Metric availability varies by Instagram account type, media type, API version, and token permissions. Missing metrics are treated as unavailable rather than fatal.

### Self-Optimization

`.github/workflows/self-optimize.yml` runs weekly and supports manual dispatch. It reads `state/performance.json` and `state/run-history.jsonl`, then writes generated overrides to `state/optimized-config.json` on `bot-state`.

Safeguards:

- No changes before `OPTIMIZER_MIN_TOTAL_SAMPLES` total scored posts and `OPTIMIZER_MIN_GROUP_SAMPLES` samples for a group.
- Weight changes are capped by `OPTIMIZER_MAX_WEIGHT_CHANGE` per run and clamped between `0.5` and `1.5`.
- Threshold changes are small and based on recent posting rate/performance.
- Every generated update is appended to `state/optimization-changelog.jsonl`.
- Set `SELF_OPTIMIZATION_ENABLED=false` to no-op safely.

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

Reel dry run:

```bash
$env:REELS_DRY_RUN="true"
python -m meme_bot.reel_runner
```

Live Reel run:

```bash
python -m meme_bot.reel_runner
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

Each successful Reel appends one JSON object to `state/reels-posted.jsonl`:

```json
{"reddit_id":"abc123","source_url":"https://v.redd.it/example","video_hash":"...","title":"Example","subreddit":"memes","instagram_media_id":"178...","posted_at":"2026-06-02T00:00:00Z"}
```

## Performance Store

`state/performance.json` is a compact versioned JSON file committed to `bot-state`. It stores each published Reddit post/Reel with:

- Reddit id, Reddit URL, source/media URLs, normalized title, subreddit, media type, and optional media hash.
- Instagram media id and permalink when available.
- Posted timestamp, posting hour/day, generated score, and score breakdown.
- Caption template id, hashtag pool id, and hashtags used.
- Reel duration when available.
- Latest analytics metrics, unavailable metric names, metric snapshots, and final normalized performance score.

The store is pruned automatically by `PERFORMANCE_MAX_POSTS`, `PERFORMANCE_MAX_AGE_DAYS`, and `PERFORMANCE_MAX_SNAPSHOTS_PER_POST`.

To reset history, edit or remove files on the `bot-state` branch:

- Reset duplicate/performance learning: remove or replace `state/performance.json` with `{"version":1,"meta":{},"posts":[]}`.
- Reset image duplicates only: edit `state/posted.jsonl`.
- Reset Reel duplicates only: edit `state/reels-posted.jsonl`.
- Reset generated tuning: remove `state/optimized-config.json` and optionally `state/optimization-changelog.jsonl`.

## Recovery

If Instagram publishing succeeds but the workflow fails before pushing `bot-state`, inspect the workflow logs for the Reddit id, Instagram media id, caption template, score breakdown, and media hash, then manually add the corresponding record to the tracker and performance files on the `bot-state` branch. Enabling `MARK_REDDIT_SAVED=true` provides a secondary guard when Reddit user credentials are configured.
