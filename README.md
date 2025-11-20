# Vimeo Video Downloader

> Download Vimeo videos with metadata extraction and direct download links. Perfect for content creators, researchers, and businesses needing to archive or analyze Vimeo content.

## 🎯 What This Actor Does

This powerful Vimeo video downloader extracts videos from Vimeo URLs and provides comprehensive metadata along with direct download links. Whether you need to download single videos, process entire playlists, or archive content for research, this actor handles it all with enterprise-grade reliability.

**Key Benefits:**
- ⚡ **Fast & Reliable**: Download videos in various quality options
- 🔐 **Authentication Support**: Access private and protected Vimeo content
- 📊 **Rich Metadata**: Extract titles, descriptions, view counts, and more
- 🔗 **Direct Downloads**: Get API URLs for easy file access
- 📈 **Batch Processing**: Handle multiple videos and playlists efficiently

## ✨ Features

- **Multiple Quality Options**: Download in best quality, 720p, 1080p, or extract audio only
- **Authentication Methods**: Support for browser cookies (JSON format)
- **Playlist Support**: Process entire Vimeo channels and playlists
- **Metadata Extraction**: Comprehensive video information including:
  - Video title and description
  - Author/uploader information
  - Upload date and duration
  - View count and engagement metrics
  - Thumbnail URLs
- **Proxy Support**: Built-in proxy rotation for large-scale downloads
- **Error Handling**: Robust error recovery and detailed logging
- **API Integration**: Direct download URLs for seamless integration

## 📥 Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `urls` | string | ✅ | - | Vimeo video URLs. Supports single URLs, multiple URLs (one per line), comma-separated, or JSON array format |
| `downloadMode` | string | ❌ | `"videos"` | Download mode: `"videos"` to download full videos, `"metadata_only"` to extract metadata without downloading |
| `quality` | string | ❌ | `"best"` | Video quality preference: `"best"`, `"720p"`, `"1080p"`, or `"audio_only"` |
| `maxItems` | integer | ❌ | `10` | Maximum number of videos to process from playlists/channels (0 = unlimited) |
| `cookies` | string | ❌ | - | Vimeo authentication cookies. Supports JSON, Netscape, or raw cookie string formats |
| `proxyConfiguration` | object | ❌ | - | Proxy settings for downloading videos |

## 📤 Output Format

The actor outputs structured JSON data for each processed video:

```json
{
  "video_id": "352492210",
  "title": "Sample Vimeo Video",
  "author": "Vimeo User",
  "description": "Video description text",
  "url": "https://vimeo.com/352492210",
  "download_url": "https://api.apify.com/v2/key-value-stores/STORE_ID/records/VIDEO_KEY?raw=1",
  "publish_date": "2021-05-15",
  "duration": 120,
  "view_count": 15000,
  "like_count": 250,
  "thumbnail": "https://i.vimeocdn.com/video/thumbnail.jpg",
  "file_size": 52428800,
  "file_extension": "mp4",
  "quality_requested": "best",
  "downloaded_format": "best[height<=1080]",
  "collected_at": "2025-11-20T12:00:00Z"
}
```

## 🚀 Usage Examples

### Download a Single Video

```json
{
  "urls": "https://vimeo.com/352492210"
}
```

### Download Multiple Videos

```json
{
  "urls": "https://vimeo.com/352492210\nhttps://vimeo.com/123456789\nhttps://vimeo.com/987654321"
}
```

### Download with Authentication

```json
{
  "urls": "https://vimeo.com/352492210",
  "cookies": "session=your_session_cookie_here; vuid=your_vuid_cookie_here; __cfruid=your_cfruid_if_present",
  "quality": "1080p"
}
```

### Process Vimeo Playlist

```json
{
  "urls": "https://vimeo.com/album/123456",
  "maxItems": 50,
  "downloadMode": "videos",
  "quality": "best"
}
```

### Extract Metadata Only

```json
{
  "urls": "https://vimeo.com/352492210",
  "downloadMode": "metadata_only"
}
```

## ⚙️ Configuration Options

### Quality Settings

- **`"best"`**: Downloads the highest available quality
- **`"1080p"`**: Limits download to 1080p or lower
- **`"720p"`**: Limits download to 720p or lower
- **`"audio_only"`**: Extracts audio as MP3

### Authentication Methods

For private or login-required Vimeo videos, provide authentication cookies:

**How to get cookies:**
1. Open Vimeo in Chrome/Firefox and log in to your account
2. Press F12 → Network tab
3. Visit any Vimeo video page
4. Right-click any network request → Copy → Copy as cURL
5. Extract the `Cookie:` header value from the cURL command
6. Paste the cookie string directly (format: `session=abc123; vuid=def456; ...`)

**Supported cookie formats:**
- Raw cookie string: `session=abc123; vuid=def456`
- JSON array: `[{"name": "session", "value": "abc123", "domain": ".vimeo.com"}]`
- JSON object: `{"session": "abc123", "vuid": "def456"}`
- Netscape format (from browser export)

### Proxy Configuration

For large-scale downloads, configure proxies to avoid rate limiting:

```json
{
  "proxyConfiguration": {
    "useApifyProxy": true,
    "apifyProxyGroups": ["RESIDENTIAL"]
  }
}
```

## 💰 Cost & Limits

- **Free Tier**: 1 compute unit per video download
- **Paid Plans**: Reduced costs with higher concurrency
- **Rate Limits**: Respects Vimeo's terms of service
- **File Size**: No artificial limits on video sizes

## 🔍 Use Cases

### Content Archiving
Archive important Vimeo videos for long-term storage and offline access.

### Research & Analysis
Extract metadata from Vimeo videos for content analysis, trend research, or academic studies.

### Content Creation
Download Vimeo videos for editing, remixing, or creating derivative content.

### Media Monitoring
Monitor Vimeo channels and playlists for new content and engagement metrics.

### Backup Solutions
Create backups of valuable Vimeo content before potential removal.

## 📋 Requirements & Compatibility

- **Vimeo Access**: Public videos work without authentication
- **Private Videos**: Require proper authentication (cookies or login)
- **Formats**: Supports all Vimeo video formats and qualities
- **Playlists**: Compatible with Vimeo albums and user uploads

## 🆘 Troubleshooting

### Authentication Issues
- Ensure cookies are fresh and properly formatted
- Check that your Vimeo account has access to the video

### Download Failures
- Verify the Vimeo URL is correct and accessible
- Try different quality settings
- Check proxy configuration for large downloads

### Rate Limiting
- Use proxy rotation for bulk downloads
- Add delays between requests if needed
- Consider upgrading to paid plans for higher limits

## 📚 Resources

- [Apify Platform Documentation](https://docs.apify.com/platform)
- [Vimeo Terms of Service](https://vimeo.com/help/guidelines)
- [Apify Proxy Documentation](https://docs.apify.com/proxy)
- [API Reference](https://docs.apify.com/api)

## 🏷️ Tags

Vimeo, video downloader, content extraction, metadata scraper, video archiving, Vimeo API, content backup, media download, video processing, Vimeo scraper
