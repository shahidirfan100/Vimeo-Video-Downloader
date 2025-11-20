"""
Vimeo Video Downloader Apify Actor
Stack: Python 3.10+ + Apify SDK + yt-dlp + ffmpeg-python
Author: Shahid Irfan
"""

from __future__ import annotations
import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from datetime import datetime, UTC

import yt_dlp
from apify import Actor

# Optional helper libraries: import defensively and expose availability flags
try:
    import ffmpeg
    FFMPEG_AVAILABLE = True
except Exception:
    ffmpeg = None
    FFMPEG_AVAILABLE = False
    Actor.log.info("ffmpeg-python not available — post-processing disabled.")


# Common extension lookups
VIDEO_FILE_EXTENSIONS = {'.mp4', '.mkv', '.webm', '.mov', '.m4v'}
AUDIO_FILE_EXTENSIONS = {'.mp3', '.m4a', '.aac', '.opus', '.ogg', '.wav', '.flac'}
MEDIA_FILE_EXTENSIONS = VIDEO_FILE_EXTENSIONS | AUDIO_FILE_EXTENSIONS

CONTENT_TYPE_BY_EXTENSION = {
    '.mp4': 'video/mp4',
    '.mkv': 'video/x-matroska',
    '.webm': 'video/webm',
    '.mov': 'video/quicktime',
    '.m4v': 'video/x-m4v',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
    '.opus': 'audio/ogg',
    '.ogg': 'audio/ogg',
    '.wav': 'audio/wav',
    '.flac': 'audio/flac',
    '.mp3': 'audio/mpeg',
}


# ============================================================ #
#                        CONFIGURATION                         #
# ============================================================ #

# Base yt-dlp options
BASE_YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'ignoreerrors': False,
    'no_color': True,
    'merge_output_format': 'mp4',
    'retries': 3,
    'fragment_retries': 3,
    # Add headers to mimic a real browser for Vimeo
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    },
}

# Quality labels retained for reference (fallback helper uses these)
QUALITY_FORMATS = {
    'best': 'best',
    '720p': 'best[height<=720]',
    '1080p': 'best[height<=1080]',
    'audio_only': 'bestaudio/best',
}


def _build_format_candidates(quality: str | None) -> List[str]:
    """Return ordered yt-dlp format strings with graceful fallbacks."""
    q = (quality or 'best').lower()

    if q in {'audio_only', 'audio'}:
        candidates = ['bestaudio/best', 'best']
    elif q in {'1080p', '1080'}:
        candidates = [
            'bestvideo*[height<=1080][fps<=60]+bestaudio/best[height<=1080]',
            'bestvideo*[height<=1080]+bestaudio/best',
            'bestvideo[height<=1440]+bestaudio/best',
            'best',
        ]
    elif q in {'720p', '720'}:
        candidates = [
            'bestvideo*[height<=720][fps<=60]+bestaudio/best[height<=720]',
            'bestvideo*[height<=720]+bestaudio/best',
            'bestvideo[height<=1080]+bestaudio/best',
            'best',
        ]
    else:
        candidates = [
            'bestvideo*+bestaudio/best',
            'bestvideo+bestaudio/best',
            'best',
        ]

    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: List[str] = []
    for fmt in candidates:
        if fmt not in seen:
            ordered.append(fmt)
            seen.add(fmt)
    return ordered


def _clear_directory(directory: str) -> None:
    """Remove files created by previous download attempts in a temp directory."""
    for entry in Path(directory).iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        except Exception:
            continue


def _find_downloaded_media(directory: str) -> Path | None:
    """Locate the most recent media file produced by yt-dlp."""
    candidates = []
    for entry in Path(directory).iterdir():
        if entry.is_file() and entry.suffix.lower() in MEDIA_FILE_EXTENSIONS:
            candidates.append(entry)

    if not candidates:
        return None

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[0]


def _generate_safe_key(video_id: str, extension: str) -> str:
    """
    Generate a safe key for the key-value store.
    
    Args:
        video_id: The video ID
        extension: File extension
        
    Returns:
        Safe key string (max 256 chars, only allowed characters)
    """
    # Use video ID and extension for the key
    key = f"{video_id}.{extension}"
    
    # Ensure it's within length limits (Apify allows up to 256 chars)
    if len(key) > 256:
        # Truncate if necessary (unlikely for video IDs)
        key = key[:256]
        # Make sure we don't cut off in the middle of extension
        if not key.endswith(f".{extension}"):
            key = f"{video_id[:256-len(extension)-1]}.{extension}"
    
    return key


def _guess_content_type(extension: str | None) -> str:
    """Infer content type for storing files in the key-value store."""
    if not extension:
        return 'application/octet-stream'
    ext = extension.lower()
    if not ext.startswith('.'):
        ext = f'.{ext}'
    return CONTENT_TYPE_BY_EXTENSION.get(ext, 'application/octet-stream')

def get_ydl_opts(download_mode: str, quality: str, proxy_url: str = None, max_items: int = 0) -> Dict[str, Any]:
    """
    Build yt-dlp options based on input parameters.

    Args:
        download_mode: 'videos' or 'metadata_only'
        quality: Quality preference
        proxy_url: Optional proxy URL
        max_items: Maximum items to extract from playlists

    Returns:
        yt-dlp options dictionary
    """
    opts = BASE_YDL_OPTS.copy()

    # For metadata extraction we never request specific formats to avoid validation issues.
    # Actual download format selection is handled by dedicated helpers.
    opts.pop('format', None)

    if download_mode == 'videos':
        opts['outtmpl'] = '%(id)s.%(ext)s'

    # Handle playlists/channels
    if max_items > 0:
        opts['playlistend'] = max_items
    opts['noplaylist'] = False  # Allow playlist processing

    # Only add proxy if explicitly provided
    if proxy_url:
        opts['proxy'] = proxy_url

    return opts


def _convert_json_cookies_to_netscape(json_cookies: str) -> str:
    """
    Convert JSON cookies to Netscape format for yt-dlp.

    Args:
        json_cookies: Cookies in JSON format

    Returns:
        Cookies in Netscape format
    """
    if not json_cookies:
        return ''

    if "# Netscape HTTP Cookie File" in json_cookies:
        return json_cookies

    try:
        import json
        cookies_data = json.loads(json_cookies)

        # Netscape format header
        netscape_cookies = [
            "# Netscape HTTP Cookie File",
            "# https://curl.se/docs/http-cookies.html",
            "# This file was generated by Vimeo Video Downloader Actor",
            ""
        ]

        # Handle different JSON formats
        if isinstance(cookies_data, list):
            for cookie in cookies_data:
                if isinstance(cookie, dict):
                    netscape_line = _format_cookie_as_netscape(cookie)
                    if netscape_line:
                        netscape_cookies.append(netscape_line)
        elif isinstance(cookies_data, dict) and 'name' in cookies_data:
            netscape_line = _format_cookie_as_netscape(cookies_data)
            if netscape_line:
                netscape_cookies.append(netscape_line)

        return '\n'.join(netscape_cookies)

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        Actor.log.warning(f"Failed to parse JSON cookies: {e}. Assuming already Netscape format.")
        return json_cookies


def _format_cookie_as_netscape(cookie: Dict[str, Any]) -> str:
    """
    Format a single cookie dict as Netscape format line.

    Args:
        cookie: Cookie dictionary

    Returns:
        Netscape format line or None if invalid
    """
    try:
        domain = cookie.get('domain') or '.vimeo.com'
        include_subdomains = 'TRUE' if domain.startswith('.') else 'FALSE'
        path = cookie.get('path') or '/'
        secure_flag = 'TRUE' if cookie.get('secure', False) else 'FALSE'
        expires = cookie.get('expirationDate') or cookie.get('expires') or 2147483647
        http_only = '#HttpOnly_' if cookie.get('httpOnly') or cookie.get('http_only') else ''

        name = cookie.get('name')
        value = cookie.get('value')
        if not name or value is None:
            return None

        return f"{http_only}{domain}\t{include_subdomains}\t{path}\t{secure_flag}\t{expires}\t{name}\t{value}"

    except Exception:
        return None


# ============================================================ #
#                        CORE FUNCTIONS                       #
# ============================================================ #

async def process_url(
    url: str,
    download_mode: str,
    quality: str,
    max_items: int,
    proxy_url: str | None = None,
    cookies: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Process a single Vimeo URL (video, playlist, or channel) and extract metadata/videos.

    Args:
        url: Vimeo URL (video, playlist, or channel)
        download_mode: 'videos' or 'metadata_only'
        quality: Quality preference
        max_items: Maximum items to process
        proxy_url: Optional proxy URL
        cookies: Optional cookies string

    Returns:
        List of metadata dictionaries for each processed item
    """
    try:
        Actor.log.info(f"Processing: {url}")

        # Get yt-dlp options
        opts = get_ydl_opts(download_mode, quality, proxy_url, max_items)

        # Use temp directory for cookie file if provided
        temp_dir = None
        cookie_path = None
        if cookies:
            temp_dir = tempfile.mkdtemp()
            cookie_path = os.path.join(temp_dir, 'cookies.txt')
            try:
                netscape_cookies = _convert_json_cookies_to_netscape(cookies)
                with open(cookie_path, 'w', encoding='utf-8') as cf:
                    cf.write(netscape_cookies)
                opts['cookiefile'] = cookie_path
                Actor.log.info('Using provided cookies for authenticated extraction')
            except Exception as e:
                Actor.log.warning(f'Could not write cookies file: {e}')
                cookie_path = None

        results = []

        # Extract info using yt-dlp
        try:
            Actor.log.info(f"Extracting info for {url}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError(f"Could not extract info for {url}")
        except Exception as e:
            error_msg = str(e)
            # Check for authentication-related errors
            if "logged-in" in error_msg.lower() or "authentication" in error_msg.lower() or "cookies" in error_msg.lower():
                Actor.log.error(f"Vimeo authentication required for {url}. Please provide cookies.")
            else:
                Actor.log.error(f"Failed to extract info for {url}: {e}")
            raise

        # Handle different types of content
        if 'entries' in info:
            entries = info['entries']
            if entries is None:
                Actor.log.warning(f"No entries found in playlist/channel: {url}")
                entries = []
            else:
                entries = [e for e in entries if e is not None]
                Actor.log.info(f"Found {len(entries)} valid items in playlist/channel")

            for entry in entries:
                if entry:
                    metadata = await process_single_video(entry, download_mode, quality, proxy_url, cookies)
                    results.append(metadata)
        else:
            metadata = await process_single_video(info, download_mode, quality, proxy_url, cookies)
            results.append(metadata)

        return results

    except Exception as e:
        Actor.log.error(f"Failed to process {url}: {e}")
        return [{
            'url': url,
            'error': str(e),
            'quality_requested': quality,
            'collected_at': datetime.now(UTC).isoformat(),
        }]

    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass


async def process_single_video(
    info: Dict[str, Any],
    download_mode: str,
    quality: str,
    proxy_url: str | None = None,
    cookies: str | None = None,
) -> Dict[str, Any]:
    """
    Process a single video's metadata and optionally download it.

    Args:
        info: yt-dlp extracted info for the video
        download_mode: 'videos' or 'metadata_only'
        quality: Quality preference
        proxy_url: Optional proxy URL
        cookies: Optional cookies string

    Returns:
        Metadata dictionary
    """
    try:
        # Extract metadata
        metadata = {
            'video_id': info.get('id'),
            'title': info.get('title'),
            'author': info.get('uploader'),
            'publish_date': info.get('upload_date'),
            'duration': info.get('duration'),
            'view_count': info.get('view_count'),
            'like_count': info.get('like_count'),
            'description': info.get('description'),
            'thumbnail': info.get('thumbnail'),
            'url': info.get('webpage_url') or info.get('url'),
            'collected_at': datetime.now(UTC).isoformat(),
            'quality_requested': quality,
        }

        # Download video if requested
        if download_mode == 'videos':
            video_data, extension, filename, used_format = await download_video_file(info, quality, proxy_url, cookies)
            
            # Generate safe key for storage
            key = _generate_safe_key(info.get('id', 'unknown'), extension)
            
            metadata.update({
                'file_size': len(video_data),
                'file_extension': extension,
                'file_path': key,  # Use the safe key instead of filename
                'downloaded_format': used_format,
            })

            # Store video in key-value store
            content_type = _guess_content_type(extension)
            await Actor.set_value(key, video_data, content_type=content_type)

            # Generate direct API download URL so users can fetch without visiting the KV UI
            store = await Actor.open_key_value_store()
            store_id = getattr(store, 'id', None)
            if store_id:
                download_url = f"https://api.apify.com/v2/key-value-stores/{store_id}/records/{key}?raw=1"
                metadata['download_url'] = download_url
                Actor.log.info(f"Download URL: {download_url}")
            else:
                metadata['download_url'] = None
                Actor.log.warning("Key-value store ID unavailable, download_url set to None")
        else:
            metadata.update({
                'file_size': None,
                'file_extension': None,
                'file_path': None,
                'downloaded_format': None,
                'download_url': None,
            })

        return metadata

    except Exception as e:
        Actor.log.error(f"Failed to process video {info.get('id')}: {e}")
        return {
            'video_id': info.get('id'),
            'url': info.get('webpage_url') or info.get('url'),
            'error': str(e),
            'quality_requested': quality,
            'downloaded_format': None,
            'download_url': None,
            'collected_at': datetime.now(UTC).isoformat(),
        }


async def download_video_file(
    info: Dict[str, Any],
    quality: str,
    proxy_url: str | None = None,
    cookies: str | None = None,
) -> tuple[bytes, str, str, str]:
    """Download the video (or audio) and return its bytes, extension, filename, and format used."""

    url = info.get('webpage_url') or info.get('url')
    if not url:
        raise ValueError('Video URL missing from info dict')

    quality = quality or 'best'

    with tempfile.TemporaryDirectory() as temp_dir:
        opts = get_ydl_opts('videos', quality, proxy_url, 0)
        opts['outtmpl'] = os.path.join(temp_dir, '%(id)s.%(ext)s')

        # Set format based on quality preference
        if quality.lower() == 'audio_only':
            opts['format'] = 'bestaudio/best'
        else:
            format_candidates = _build_format_candidates(quality)
            opts['format'] = format_candidates[0]  # Use first (best) candidate

        # Handle cookies
        if cookies:
            cookie_path = os.path.join(temp_dir, 'cookies.txt')
            try:
                netscape_cookies = _convert_json_cookies_to_netscape(cookies)
                with open(cookie_path, 'w', encoding='utf-8') as cf:
                    cf.write(netscape_cookies)
                opts['cookiefile'] = cookie_path
                Actor.log.info('Using provided cookies for authenticated download')
            except Exception as e:
                Actor.log.warning(f'Could not write cookies file: {e}')

        # When we are extracting audio-only and ffmpeg is available, convert to mp3 for convenience
        if quality.lower() == 'audio_only' and FFMPEG_AVAILABLE:
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            opts['keepvideo'] = False
            opts['merge_output_format'] = 'mp3'

        _clear_directory(temp_dir)

        Actor.log.info(f"Download using format '{opts['format']}'")

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            media_path = _find_downloaded_media(temp_dir)
            if not media_path:
                raise FileNotFoundError('Download completed but no media file was produced')

            with media_path.open('rb') as f:
                data = f.read()

            extension = media_path.suffix.lstrip('.').lower()
            filename = media_path.name

            Actor.log.info(f"Download succeeded with format '{opts['format']}' → {filename}")
            return data, extension, filename, opts['format']

        except Exception as e:
            Actor.log.error(f"Download failed for {url} with format '{opts['format']}': {e}")
            raise


async def process_urls(
    urls: List[str],
    download_mode: str,
    quality: str,
    max_items: int,
    proxy_url: str | None = None,
    proxy_configuration: Any | None = None,
    cookies: str | None = None,
) -> None:
    """
    Process a list of Vimeo URLs.

    Args:
        urls: List of Vimeo URLs (videos, playlists, channels)
        download_mode: 'videos' or 'metadata_only'
        quality: Quality preference
        max_items: Maximum items to process
        proxy_url: Optional proxy URL to use for downloading
        proxy_configuration: Optional Apify ProxyConfiguration object for rotating proxies
        cookies: Optional cookies string
    """
    total_processed = 0
    total_success = 0

    for url in urls:
        active_proxy_url = proxy_url
        if proxy_configuration is not None:
            try:
                fresh_url = await proxy_configuration.new_url()
                active_proxy_url = fresh_url or proxy_url
            except Exception as proxy_error:
                Actor.log.warning(f"Unable to obtain fresh proxy URL: {proxy_error}")
                active_proxy_url = proxy_url

        try:
            # Process URL (may return multiple items for playlists/channels)
            results = await process_url(url, download_mode, quality, max_items, active_proxy_url, cookies)

            # Push each result to dataset
            for metadata in results:
                await Actor.push_data(metadata)
                if 'error' not in metadata:  # Count successful items
                    total_success += 1

            Actor.log.info(f"Processed {len(results)} items from {url}")

        except Exception as e:
            Actor.log.error(f"Failed to process {url}: {e}")
            # Still push error info to dataset
            error_data = {
                'url': url,
                'error': str(e),
                'quality_requested': quality,
                'collected_at': datetime.now(UTC).isoformat(),
            }
            await Actor.push_data(error_data)

        total_processed += 1

        # Brief pause between URLs to be respectful
        if total_processed < len(urls):
            await asyncio.sleep(0.5)

    Actor.log.info(f"Processing complete! Successfully processed {total_success} items")


# ============================================================ #
#                            MAIN                              #
# ============================================================ #

async def main() -> None:
    """
    Main actor function.
    """
    async with Actor:
        # Get input
        inp = await Actor.get_input() or {}

        # Handle input: can be single URL string, a JSON array string, or list of URLs
        urls_input = inp.get('urls', '')
        urls = []
        if isinstance(urls_input, list):
            urls = urls_input
        elif isinstance(urls_input, str):
            s = urls_input.strip()
            if not s:
                urls = []
            else:
                # Try to parse as JSON first
                try:
                    import json
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        urls = parsed
                    elif isinstance(parsed, str):
                        urls = [parsed]
                    else:
                        urls = [str(parsed)]
                except Exception:
                    # Not JSON, try splitting by newlines or commas
                    lines = [line.strip() for line in s.split('\n') if line.strip()]
                    if len(lines) > 1:
                        urls = lines
                    else:
                        # Try comma separated
                        parts = [p.strip() for p in s.split(',') if p.strip()]
                        if len(parts) > 1:
                            urls = parts
                        else:
                            urls = [s]
        else:
            urls = []

        if not urls:
            Actor.log.error("No URLs provided in input. Expected 'urls' field with string or list of Vimeo URLs.")
            return

        # Extract proxy configuration
        proxy_url: str | None = None
        proxy_configuration = None
        proxy_input = inp.get("proxyConfiguration") or {}

        if proxy_input.get("proxyUrls"):
            proxy_url = proxy_input["proxyUrls"][0]
            Actor.log.info("Using custom proxy URL provided in input")
        else:
            try:
                if proxy_input:
                    # Filter out invalid parameters that the SDK doesn't accept
                    valid_proxy_params = {k: v for k, v in proxy_input.items() 
                                        if k not in ['useApifyProxy']}
                    proxy_configuration = await Actor.create_proxy_configuration(**valid_proxy_params)
                else:
                    proxy_configuration = await Actor.create_proxy_configuration()
                if proxy_configuration:
                    proxy_url = await proxy_configuration.new_url()
                    Actor.log.info("Using Apify proxy configuration")
            except Exception as proxy_error:
                Actor.log.warning(f"Unable to initialize proxy configuration: {proxy_error}")
                proxy_configuration = None
                proxy_url = None

        # Extract additional parameters
        download_mode = inp.get('downloadMode', 'videos')
        if download_mode not in ['videos', 'metadata_only']:
            download_mode = 'videos'

        quality = inp.get('quality', 'best')
        if quality not in ['best', '720p', '1080p', 'audio_only']:
            quality = 'best'

        try:
            max_items = int(inp.get('maxItems', 10))
            max_items = max(0, min(max_items, 100))  # Limit between 0 and 100
        except (ValueError, TypeError):
            max_items = 10

        Actor.log.info(f"Download mode: {download_mode}, Quality: {quality}, Max items: {max_items}")

        # Validate URLs (basic check for Vimeo content)
        valid_urls = []
        for url in urls:
            if 'vimeo.com' in url:
                valid_urls.append(url)
            else:
                Actor.log.warning(f"Skipping non-Vimeo URL: {url}")

        if not valid_urls:
            Actor.log.error("No valid Vimeo URLs found")
            return

        # Extract cookies if provided
        cookies = inp.get('cookies')
        if cookies:
            Actor.log.info('Cookies provided in input — will use for authenticated downloads')
        else:
            Actor.log.warning('No authentication method provided. Vimeo may require login for some videos.')

        # Process the URLs
        await process_urls(
            valid_urls,
            download_mode,
            quality,
            max_items,
            proxy_url,
            proxy_configuration,
            cookies,
        )


if __name__ == "__main__":
    asyncio.run(main())
