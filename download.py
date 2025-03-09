#!/usr/bin/env python3
"""
Video Download Module for NewsVid

This module handles downloading background videos from Pexels.com based on keywords.
It provides functionality to search for videos matching specific keywords and download
them for use in news video generation.

The module requires a Pexels API key, which can be provided either through an
environment variable (PEXELS_API_KEY) or through a configuration file.

Main functions:
- search_and_download_videos: Search for and download videos based on keywords
- load_keywords_from_file: Load keywords from a text file

Typical usage:
    keywords = load_keywords_from_file('keywords.txt')
    videos = search_and_download_videos(keywords, 'output/videos')
"""

import os
import random
import requests
from typing import List, Dict, Any, Optional, Tuple
import yaml
import time
from requests.exceptions import Timeout, RequestException
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

def load_config(config_file: str = 'app.yaml') -> Dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_file: Path to the YAML configuration file
        
    Returns:
        Dictionary containing configuration values or empty dict if file not found
    """
    try:
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config file: {e}")
        return {}

def create_session_with_retries(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """
    Create a requests Session with automatic retry logic for handling transient errors.
    
    This function configures a session that will automatically retry failed requests
    with exponential backoff, which helps handle temporary network issues or API rate limits.
    
    Args:
        retries: Number of retries for failed requests (default: 3)
        backoff_factor: Factor to calculate delay between retries (default: 0.5)
                        Formula: {backoff factor} * (2 ** ({number of total retries} - 1))
        
    Returns:
        Session object configured with retry logic
        
    Example:
        >>> session = create_session_with_retries()
        >>> response = session.get('https://api.example.com/data')
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
        allowed_methods=["GET"]  # Only retry GET requests
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def search_pexels_videos(session: requests.Session, keyword: str, headers: Dict[str, str], 
                        min_duration: int, max_duration: int) -> Tuple[List[Dict], str]:
    """
    Search for videos on Pexels API matching a keyword and duration criteria.
    
    This function queries the Pexels video search API with the provided keyword
    and filters the results to only include videos within the specified duration range.
    It handles errors gracefully and returns both the filtered videos and any error message.
    
    Args:
        session: Requests session with retry logic for handling connection issues
        keyword: Search keyword or phrase to find relevant videos
        headers: API request headers including Authorization and User-Agent
        min_duration: Minimum video duration in seconds
        max_duration: Maximum video duration in seconds
        
    Returns:
        Tuple containing:
            - List of video dictionaries that match the duration criteria
            - Error message string (empty if successful)
    
    Note:
        Each video dictionary in the returned list contains metadata from Pexels API
        including video ID, duration, and available video files in different qualities.
    """
    # Pexels API endpoint for video search
    search_url = "https://api.pexels.com/videos/search"
    
    # Search parameters
    params = {
        "query": keyword,
        "per_page": 15,         # Number of results to return
        "orientation": "landscape"  # Only return landscape videos
    }
    
    try:
        # Make the API request
        response = session.get(search_url, headers=headers, params=params)
        response.raise_for_status()  # Raise exception for HTTP errors
        search_results = response.json()
        
        # Check if any videos were found
        if 'videos' not in search_results or not search_results['videos']:
            return [], f"No videos found for keyword: {keyword}"
        
        # Filter videos by duration
        suitable_videos = []
        for video in search_results['videos']:
            duration = video.get('duration')
            if duration and min_duration <= duration <= max_duration:
                suitable_videos.append(video)
        
        # Check if any videos match the duration criteria
        if not suitable_videos:
            return [], f"No videos with suitable duration ({min_duration}-{max_duration}s) found for keyword: {keyword}"
            
        return suitable_videos, ""
        
    except RequestException as e:
        return [], f"Error searching videos for '{keyword}': {str(e)}"

def search_and_download_videos(keywords: List[str], output_dir: str, 
                              per_keyword: int = 1, min_duration: int = 10, 
                              max_duration: int = 60, config_file: str = 'app.yaml',
                              max_retries: int = 3) -> List[str]:
    """
    Search for videos on Pexels.com using a list of keywords and download them.
    
    This function searches the Pexels API for videos matching each keyword in the provided list,
    filters them by duration, and downloads a specified number of videos per keyword.
    It handles API authentication, network errors, and timeouts gracefully.
    
    Args:
        keywords: List of keywords to search for videos
        output_dir: Directory to save downloaded videos
        per_keyword: Number of videos to download per keyword (default: 1)
        min_duration: Minimum video duration in seconds (default: 10)
        max_duration: Maximum video duration in seconds (default: 60)
        config_file: Path to config file containing Pexels API key (default: 'app.yaml')
        max_retries: Maximum number of retry attempts for failed requests (default: 3)
        
    Returns:
        List of paths to successfully downloaded video files
        
    Note:
        - Requires a Pexels API key either in the environment variable PEXELS_API_KEY
          or in the specified config file under pexels.api_key
        - Downloaded videos are named using the format: {keyword}_{video_id}_{quality}.mp4
        - Prefers HD quality videos but falls back to SD if HD is not available
    """
    # Step 1: Load configuration and API key
    config = load_config(config_file)
    
    # Get Pexels API key from environment variable first, then from config file
    api_key = os.getenv('PEXELS_API_KEY') or config.get('pexels', {}).get('api_key')
    if not api_key:
        print("Error: Pexels API key not found in config or environment")
        print("Please set PEXELS_API_KEY environment variable or add it to app.yaml")
        return []
    
    # Step 2: Prepare output directory and API request headers
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Headers for Pexels API requests
    headers = {
        "Authorization": api_key,  # Pexels API requires this header for authentication
        "User-Agent": config.get('user_agent', "NewsVidApp/1.0 Python-Requests/2.25.1")
    }
    
    # Track successfully downloaded videos
    downloaded_videos = []
    
    # Step 3: Create HTTP session with automatic retry capability
    session = create_session_with_retries(retries=max_retries)
    
    # Step 4: Process each keyword and download matching videos
    for keyword in keywords:
        print(f"Searching for videos with keyword: {keyword}")
        
        # Step 4.1: Search for videos matching the keyword and duration criteria
        suitable_videos, error = search_pexels_videos(session, keyword, headers, min_duration, max_duration)
        if error:
            print(error)
            continue  # Skip to next keyword if search failed
            
        # Step 4.2: Randomly select videos to avoid downloading the same videos every time
        # This adds variety to the video collection when the script is run multiple times
        videos_to_download = random.sample(
            suitable_videos, 
            min(per_keyword, len(suitable_videos))  # Ensure we don't request more than available
        )
        
        # Step 4.3: Download each selected video
        for video in videos_to_download:
                # Step 4.3.1: Find the best quality video file available (HD preferred, SD as fallback)
                video_files = video.get('video_files', [])
                download_url = None
                quality = None
                
                # Try to get HD quality first (better quality for news videos)
                for file in video_files:
                    if file.get('quality') == 'hd' and file.get('file_type') == 'video/mp4':
                        download_url = file.get('link')
                        quality = 'hd'
                        break
                
                # If HD not found, fall back to SD quality
                if not download_url:
                    for file in video_files:
                        if file.get('quality') == 'sd' and file.get('file_type') == 'video/mp4':
                            download_url = file.get('link')
                            quality = 'sd'
                            break
                
                # Skip if no suitable video format was found
                if not download_url:
                    print(f"No suitable video file found for video ID: {video.get('id')}")
                    continue
                
                # Step 4.3.2: Create a descriptive filename that includes the keyword and video ID
                # Replace spaces with underscores for a clean filename
                sanitized_keyword = keyword.replace(' ', '_').lower()
                filename = f"{sanitized_keyword}_{video.get('id')}_{quality}.mp4"
                filepath = os.path.join(output_dir, filename)
                
                # Step 4.3.3: Download the video with proper error handling and progress tracking
                print(f"Downloading video: {filename}")
                try:
                    # Set timeouts to avoid hanging on slow connections
                    # - connect timeout: 5 seconds to establish connection
                    # - read timeout: 30 seconds to receive data
                    start_time = time.time()
                    video_response = session.get(
                        download_url, 
                        stream=True,  # Stream the download to handle large files efficiently
                        timeout=(5, 30)  # (connect timeout, read timeout)
                    )
                    video_response.raise_for_status()  # Raise exception for HTTP errors
                    
                    # Get total file size for progress tracking
                    total_size = int(video_response.headers.get('content-length', 0))
                    block_size = 8192  # 8KB chunks for efficient file writing
                    downloaded_size = 0
                    
                    # Write the file in chunks to avoid loading entire video into memory
                    with open(filepath, 'wb') as f:
                        for chunk in video_response.iter_content(chunk_size=block_size):
                            # Implement overall download timeout (1 minute)
                            if time.time() - start_time > 60:  # 1 minute total timeout
                                raise TimeoutError("Download took longer than 60 seconds")
                            
                            if chunk:  # Filter out keep-alive chunks
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # Display progress percentage for large files
                                if total_size > 1024*1024:  # Only for files > 1MB
                                    percent = (100 * downloaded_size) // total_size
                                    print(f"\rDownloading {filename}: {percent}%", end="")
                    
                    # Step 4.3.4: Finalize the download and add to the list of successful downloads
                    if downloaded_size > 0:
                        print(f"\nCompleted downloading {filename}")
                    
                    # Add the filepath to our list of successfully downloaded videos
                    downloaded_videos.append(filepath)
                    print(f"Successfully downloaded: {filepath}")
                    
                    # Add a small delay between downloads to avoid rate limiting from Pexels API
                    time.sleep(1)
                    
                except (Timeout, TimeoutError) as e:
                    # Handle timeout errors (connection or read timeout)
                    print(f"\nTimeout downloading {filename}: {str(e)}")
                    # Clean up: remove partially downloaded file to avoid corrupted videos
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    # Skip to next video after timeout
                    continue
                        
                except RequestException as e:
                    # Handle network-related errors (DNS failure, connection refused, etc.)
                    print(f"\nNetwork error downloading {filename}: {str(e)}")
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    # Skip to next video after network error
                    continue
                        
                except Exception as e:
                    # Catch any other unexpected errors
                    print(f"\nUnexpected error downloading {filename}: {str(e)}")
                    if os.path.exists(filepath):
                        os.remove(filepath)
                    # Skip to next video
                    continue
                    
        # Add a longer delay between processing different keywords to avoid API rate limiting
        time.sleep(2)
    
    # Return the list of all successfully downloaded video filepaths
    return downloaded_videos


def load_keywords_from_file(file_path: str = 'keywords.txt') -> List[str]:
    """
    Load keywords from a text file.
    
    Each line in the file is treated as a separate keyword or phrase.
    Empty lines and whitespace are ignored.
    
    Args:
        file_path: Path to the keywords file (default: 'keywords.txt')
        
    Returns:
        List of keywords with whitespace stripped
        Empty list if the file cannot be read or contains no valid keywords
    
    Example:
        >>> load_keywords_from_file('keywords.txt')
        ['news', 'technology', 'science']
    """
    try:
        with open(file_path, 'r') as f:
            keywords = [line.strip() for line in f if line.strip()]
        return keywords
    except Exception as e:
        print(f"Error loading keywords from {file_path}: {str(e)}")
        return []


if __name__ == '__main__':
    # Example usage
    keywords = load_keywords_from_file()
    if keywords:
        print(f"Loaded keywords: {keywords}")
        videos = search_and_download_videos(keywords, 'videos')
        print(f"Downloaded {len(videos)} videos")
    else:
        print("No keywords found. Please create a keywords.txt file with one keyword per line.")
