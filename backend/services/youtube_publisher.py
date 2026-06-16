"""YouTube publishing service using YouTube Data API v3."""
import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from backend.config import YOUTUBE_CLIENT_SECRETS_FILE, YOUTUBE_CREDENTIALS_FILE

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def get_authenticated_service() -> Optional[Any]:
    """
    Get authenticated YouTube API service.
    
    Returns:
        YouTube API service object, or None if not authenticated
    """
    credentials = None
    
    # Load existing credentials
    if YOUTUBE_CREDENTIALS_FILE.exists():
        try:
            creds_data = json.loads(YOUTUBE_CREDENTIALS_FILE.read_text())
            credentials = Credentials.from_authorized_user_info(creds_data, SCOPES)
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
    
    # Refresh if expired
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            # Save refreshed credentials
            YOUTUBE_CREDENTIALS_FILE.write_text(credentials.to_json())
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            credentials = None
    
    if not credentials or not credentials.valid:
        return None
    
    try:
        youtube = build('youtube', 'v3', credentials=credentials)
        return youtube
    except Exception as e:
        logger.error(f"Failed to build YouTube service: {e}")
        return None


def initiate_oauth_flow() -> str:
    """
    Initiate OAuth flow and return authorization URL.
    
    Returns:
        Authorization URL for user to visit
    """
    if not YOUTUBE_CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(
            f"YouTube client secrets not found at {YOUTUBE_CLIENT_SECRETS_FILE}. "
            "Please download from Google Cloud Console and place in project root."
        )
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(YOUTUBE_CLIENT_SECRETS_FILE),
        SCOPES
    )
    
    # Use manual flow to get auth URL
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    auth_url, _ = flow.authorization_url(prompt='consent')
    
    return auth_url


def complete_oauth_flow(auth_code: str) -> bool:
    """
    Complete OAuth flow with authorization code.
    
    Args:
        auth_code: Authorization code from user
        
    Returns:
        True if successful, False otherwise
    """
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(YOUTUBE_CLIENT_SECRETS_FILE),
            SCOPES
        )
        flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
        
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Save credentials
        YOUTUBE_CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        YOUTUBE_CREDENTIALS_FILE.write_text(credentials.to_json())
        
        return True
    
    except Exception as e:
        logger.error(f"OAuth flow failed: {e}")
        return False


async def upload_video_to_youtube(
    video_path: str,
    title: str,
    description: str = "",
    tags: list[str] = None,
    privacy_status: str = "public",
) -> Dict[str, Any]:
    """
    Upload video to YouTube Shorts.
    
    Args:
        video_path: Path to video file
        title: Video title (will append #Shorts)
        description: Video description
        tags: List of tags
        privacy_status: public, unlisted, or private
        
    Returns:
        Dict with youtube_url and status
    """
    youtube = get_authenticated_service()
    
    if youtube is None:
        return {
            'status': 'error',
            'message': 'Not authenticated with YouTube. Please connect your account.',
            'youtube_url': None,
        }
    
    if tags is None:
        tags = ['shorts', 'clipforge']
    
    # Ensure #Shorts tag is in title or tags
    if '#shorts' not in title.lower() and '#short' not in title.lower():
        title = f"{title} #Shorts"
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '22',  # People & Blogs
        },
        'status': {
            'privacyStatus': privacy_status,
            'selfDeclaredMadeForKids': False,
        }
    }
    
    try:
        # Create media upload
        media = MediaFileUpload(
            video_path,
            chunksize=-1,  # Upload in a single request
            resumable=True,
            mimetype='video/mp4'
        )
        
        # Execute upload
        request = youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        )
        
        response = request.execute()
        
        video_id = response.get('id')
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        
        return {
            'status': 'success',
            'message': 'Video uploaded successfully',
            'youtube_url': youtube_url,
            'video_id': video_id,
        }
    
    except Exception as e:
        error_msg = str(e)
        print(f"YouTube upload failed: {error_msg}")
        
        return {
            'status': 'error',
            'message': f'Upload failed: {error_msg}',
            'youtube_url': None,
        }


def is_authenticated() -> bool:
    """Check if user is authenticated with YouTube."""
    youtube = get_authenticated_service()
    return youtube is not None
