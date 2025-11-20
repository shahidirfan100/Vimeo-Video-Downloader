# Vimeo Video Downloader

> Apify Actor for downloading videos from Vimeo by providing URLs.

## What does this actor do?

This actor downloads videos from Vimeo when you provide the video URLs. It extracts metadata and stores the videos in the key-value store with **direct download links** (API URLs) inside the dataset.

### Features

- Download videos from provided Vimeo URLs
- Extract video metadata
- Store videos in key-value store
- Provide download URLs in dataset

## Input

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `urls` | string | Required | Vimeo video URL(s). Can provide multiple URLs one per line, comma-separated, or as JSON array. |

## Output

The actor outputs metadata for each processed video to the dataset, including a download URL for the stored video.

```json
{
  "video_id": "VIDEO_ID",
  "title": "Video Title",
  "author": "Channel Name",
  "url": "https://vimeo.com/VIDEO_ID",
  "download_url": "https://api.apify.com/v2/key-value-stores/STORE_ID/records/VIDEO_KEY?raw=1",
  "collected_at": "2025-11-07T12:00:00"
}
```

## Usage

### Download a single video
```json
{
  "urls": "https://vimeo.com/123456789"
}
```

### Download multiple videos
```
https://vimeo.com/123456789
https://vimeo.com/987654321
```

## Resources

- [Apify Platform Documentation](https://docs.apify.com/platform)
