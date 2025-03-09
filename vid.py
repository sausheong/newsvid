#!/usr/bin/env python3
"""
Video Processing Module for NewsVid

This module provides functionality for video processing tasks including:
- Getting video information (duration, dimensions)
- Adding scrolling text to videos
- Combining multiple videos with audio
- Scaling and padding videos to a consistent resolution

The module relies on FFmpeg for video processing operations and is designed
to work with the NewsVid application for generating news videos.

Main functions:
- get_video_info: Get metadata about a video file
- add_scrolling_text: Add scrolling text overlay to a video
- combine_videos_with_audio: Combine multiple videos with an audio track

Typical usage:
    video_info = get_video_info('video.mp4')
    combined_video = combine_videos_with_audio('output', 'videos', 'audio.mp3')
"""

import os
import glob
import subprocess
import click
import random
import tempfile
import json
import shutil
import math
import textwrap
from typing import List, Dict, Optional, Tuple

def get_duration(media_file: str) -> Optional[float]:
    """
    Get the duration of a media file (audio or video) using ffprobe.
    
    Args:
        media_file: Path to the media file
        
    Returns:
        Duration in seconds as a float, or None if duration could not be determined
        
    Note:
        This function uses ffprobe to extract the duration metadata from the media file.
        It handles both audio and video files.
    """
    cmd = [
        'ffprobe',
        '-v', 'error',  # Only show errors
        '-show_entries', 'format=duration',  # Extract duration information
        '-of', 'default=noprint_wrappers=1:nokey=1',  # Format output as plain text
        media_file
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        click.echo(f"Error getting media duration: {str(e)}", err=True)
        return None

def get_audio_duration(audio_file: str) -> Optional[float]:
    """
    Get the duration of an audio file using ffprobe.
    
    This is a convenience wrapper around get_duration() specifically for audio files.
    
    Args:
        audio_file: Path to the audio file
        
    Returns:
        Duration in seconds as a float, or None if duration could not be determined
    """
    return get_duration(audio_file)

def add_scrolling_text(input_video: str, script_file: str, output_file: str, font_size: int = 36) -> Optional[str]:
    """
    Add scrolling text directly to a video file.
    
    This function adds scrolling text (like news ticker or credits) to a video file.
    The text scrolls from bottom to top at a speed calculated based on the video duration
    and the amount of text. The text is centered horizontally with margins on each side.
    
    Args:
        input_video: Path to the input video file
        script_file: Path to the text file containing the script to display
        output_file: Path to save the output video
        font_size: Font size for the text (default: 36)
        
    Returns:
        Path to the output video file or None if there was an error
        
    Note:
        - The text is automatically wrapped to fit within 70% of the video width
        - Text is displayed with a semi-transparent black background for readability
        - The function preserves the original audio track
        - The scrolling speed is calculated based on text length and video duration
    """
    try:
        # Step 1: Read the script content from the provided file
        with open(script_file, 'r') as f:
            script_content = f.read()
        
        # Step 2: Create a temporary file for the original script content
        # (We'll create another one later with wrapped text)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
            temp_text_file = temp_file.name
            temp_file.write(script_content)
        
        # Step 3: Get video duration to calculate appropriate scroll speed
        duration = get_duration(input_video)
        if not duration:
            click.echo("Could not determine video duration", err=True)
            return None
        
        # Step 4: Calculate scroll speed based on text length and video duration
        # We estimate the number of lines based on character count and calculate
        # how fast the text needs to scroll to show all content during the video
        estimated_lines = len(script_content) / 50  # Assuming average of 50 chars per line
        scroll_height = estimated_lines * font_size * 1.5  # Total height of scrolling text
        scroll_speed = scroll_height / duration  # Pixels per second to scroll
        
        # Step 5: Get video dimensions to properly format the text
        video_info = get_video_info(input_video)
        if not video_info:
            click.echo("Could not determine video dimensions", err=True)
            return None
            
        video_width = video_info.get('width', 1920)  # Default to 1920 if not found
        
        # Step 6: Calculate text width with margins for readability
        # Use 70% of video width (15% margin on each side)
        text_width = int(video_width * 0.7)
        
        # Step 7: Format the text with wrapping to fit within the calculated width
        # We estimate characters per line based on font size
        chars_per_line = int(text_width / (font_size * 0.6))  # Approximate character width
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as wrapped_file:
            wrapped_text_file = wrapped_file.name
            # Process the script line by line and wrap each line
            for line in script_content.split('\n'):
                wrapped_line = textwrap.fill(line, width=chars_per_line)
                wrapped_file.write(wrapped_line + '\n')  # Add extra newline for paragraph spacing
        
        # Step 8: Create FFmpeg command to add scrolling text to the video
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-i', input_video,  # Input video
            '-vf', (
                # drawtext filter with parameters:
                f"drawtext=fontfile=/System/Library/Fonts/Helvetica.ttc:fontsize={font_size}:"
                f"fontcolor=white:x=(w-text_w)/2:"
                f"textfile='{wrapped_text_file}':"
                f"y=h-{scroll_speed}*t:line_spacing=10:box=1:boxcolor=black@0.5:boxborderw=5"
                # Explanation:
                # - fontfile: Use system Helvetica font
                # - fontcolor: White text for visibility
                # - x=(w-text_w)/2: Center text horizontally
                # - textfile: Use our wrapped text file
                # - y=h-{scroll_speed}*t: Start at bottom and scroll up at calculated speed
                # - box=1:boxcolor=black@0.5: Add semi-transparent black background
            ),
            # Video encoding parameters to ensure consistent colorspace
            '-c:v', 'libx264',  # H.264 video codec
            '-pix_fmt', 'yuv420p',  # Pixel format
            '-colorspace', 'bt709',  # Standard HD colorspace
            '-color_range', 'tv',  # TV color range (limited)
            '-color_primaries', 'bt709',  # Color primaries
            '-color_trc', 'bt709',  # Transfer characteristics
            '-c:a', 'copy',  # Copy audio without re-encoding
            output_file  # Output file path
        ]
        
        # Step 9: Clean up the original temp file as we're now using the wrapped one
        os.unlink(temp_text_file)
        
        # Step 10: Execute the FFmpeg command to create the video with scrolling text
        click.echo("Adding scrolling text to video...")
        subprocess.run(cmd, check=True)
        
        # Step 11: Clean up the wrapped text file
        os.unlink(wrapped_text_file)
        
        return output_file
    
    except Exception as e:
        # Handle any errors that occur during the process
        click.echo(f"Error adding scrolling text to video: {str(e)}", err=True)
        # Clean up any temporary files that might have been created
        if 'temp_text_file' in locals() and os.path.exists(temp_text_file):
            os.unlink(temp_text_file)
        if 'wrapped_text_file' in locals() and os.path.exists(wrapped_text_file):
            os.unlink(wrapped_text_file)
        return None

def get_video_info(video_file: str) -> Dict[str, int]:
    """
    Get video information including duration, width, and height.
    
    This function extracts metadata from a video file using ffprobe and returns
    a dictionary with the video's duration, width, and height.
    
    Args:
        video_file: Path to the video file
        
    Returns:
        Dictionary containing:
            - duration: Video duration in seconds (float)
            - width: Video width in pixels (int)
            - height: Video height in pixels (int)
            
    Note:
        If the video information cannot be determined, default values will be returned:
        - duration: 0
        - width: 1920
        - height: 1080
    """
    cmd = [
        'ffprobe',
        '-v', 'error',  # Only show errors
        '-select_streams', 'v:0',  # Select the first video stream
        '-show_entries', 'stream=width,height,duration',  # Extract width, height, and duration
        '-of', 'json',  # Output in JSON format
        video_file
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        stream_info = info.get('streams', [{}])[0]
        
        # If duration is not in stream, try format
        if 'duration' not in stream_info:
            duration = get_duration(video_file)
        else:
            duration = float(stream_info['duration'])
            
        return {
            'duration': duration,
            'width': int(stream_info.get('width', 1920)),
            'height': int(stream_info.get('height', 1080))
        }
    except (subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as e:
        click.echo(f"Error getting video info: {str(e)}", err=True)
        # Return default values if we can't get the actual info
        return {'duration': 0, 'width': 1920, 'height': 1080}

def create_video_list_file(videos: List[str], target_duration: float) -> Tuple[str, List[Dict]]:
    """
    Create a temporary file with video list for ffmpeg concat demuxer.
    
    This function takes a list of video files and creates a temporary file that can be
    used with ffmpeg's concat demuxer to combine the videos. It also calculates how many
    times the videos need to be repeated to reach the target duration.
    
    Args:
        videos: List of video file paths
        target_duration: Target duration for the final video in seconds
        
    Returns:
        Tuple containing:
            - file_path: Path to the created temporary file
            - video_info_list: List of dictionaries with information about each video
              in the final sequence
              
    Note:
        The function will randomly shuffle and repeat videos as needed to reach
        the target duration. Each video in the returned list includes metadata
        such as path, duration, width, and height.
    """
    if not videos:
        return None, []
        
    # Convert all videos to absolute paths and get their info
    video_info_list = []
    for video in videos:
        abs_video_path = os.path.abspath(video)
        info = get_video_info(abs_video_path)
        info['path'] = abs_video_path
        video_info_list.append(info)
    
    # Calculate total duration of all videos
    total_original_duration = sum(info['duration'] for info in video_info_list)
    
    # Prepare the final list of videos to include
    final_video_list = []
    current_duration = 0
    
    # Keep adding videos until we reach the target duration
    while current_duration < target_duration:
        # Shuffle the list for variety each time we loop through all videos
        shuffled_videos = video_info_list.copy()
        random.shuffle(shuffled_videos)
        
        for info in shuffled_videos:
            final_video_list.append(info)
            current_duration += info['duration']
            
            # If we've reached the target duration, stop adding videos
            if current_duration >= target_duration:
                break
    
    # Create a temporary file for the video list
    fd, path = tempfile.mkstemp(suffix='.txt')
    with os.fdopen(fd, 'w') as f:
        for info in final_video_list:
            video_path = info['path']
            # Escape single quotes in the path
            escaped_path = video_path.replace("'", "'\\''")
            f.write(f"file '{escaped_path}'\n")
    
    click.echo(f"Created video list with {len(final_video_list)} entries from {len(videos)} unique videos")
    click.echo(f"Total video duration: {current_duration:.2f} seconds (target: {target_duration:.2f} seconds)")
    
    return path, final_video_list

def combine_videos_with_audio(output_dir: str, video_dir: str = 'videos', 
                            audio_file: Optional[str] = 'news.mp3',
                            output_file: str = 'final_video.mp4',
                            target_resolution: str = '1920x1080',
                            intro_video: Optional[str] = 'tdns.mp4') -> Optional[str]:
    """
    Combine videos from a directory and synchronize with audio.
    
    This function combines multiple videos from a directory into a single video,
    synchronizes it with an audio track, and optionally adds scrolling text.
    It handles scaling and padding videos to a consistent resolution, and can
    include an intro video at the beginning.
    
    The process involves several steps:
    1. Scaling all videos to the target resolution
    2. Combining videos in sequence (with intro first if provided)
    3. Adding audio track
    4. Optionally adding scrolling text from a script file
    
    Args:
        output_dir: Base directory for input/output files
        video_dir: Directory containing video files (relative to output_dir)
        audio_file: Path to audio file to combine with video (relative to output_dir)
        output_file: Filename for the output video (will be saved in output_dir)
        target_resolution: Target resolution in format 'WIDTHxHEIGHT' (e.g., '1920x1080')
        intro_video: Optional intro video to add at the beginning
        
    Returns:
        Path to the output video file, or None if an error occurred
        
    Note:
        - Videos will be looped if necessary to match the audio duration
        - If no audio file is provided, a default duration of 60 seconds will be used
        - If a script.txt file exists in the output_dir, scrolling text will be added
    """
    try:
        # Check if intro video exists
        has_intro = False
        if intro_video and os.path.exists(intro_video):
            has_intro = True
            click.echo(f"Using intro video: {intro_video}")
        
        # Get list of video files
        video_files = []
        for ext in ['*.mp4', '*.mov', '*.avi', '*.mkv']:
            video_files.extend(glob.glob(os.path.join(f"{output_dir}/{video_dir}", ext)))
        
        # Filter out non-video files (like PNG files)
        video_files = [f for f in video_files if not f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        if not video_files:
            click.echo(f"No video files found in {f"{output_dir}/{video_dir}"}", err=True)
            return None
            
        # Make sure we have at least 1 video to combine (plus intro if available)
        if len(video_files) < 1 and not has_intro:
            click.echo(f"Need at least 1 video to combine, found none", err=True)
            return None
            
        click.echo(f"Found {len(video_files)} videos to combine")
        for i, video in enumerate(video_files):
            click.echo(f"  {i+1}. {os.path.basename(video)}")
        
        # Get target duration from audio file or use default
        target_duration = 60  # Default 60 seconds if no audio
        if audio_file and os.path.exists(f"{output_dir}/{audio_file}"):
            audio_duration = get_audio_duration(f"{output_dir}/{audio_file}")
            if audio_duration:
                target_duration = audio_duration
                click.echo(f"Audio duration: {audio_duration:.2f} seconds")
            else:
                click.echo("Could not get audio duration, using default duration")
        
        # Create temporary directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            # First pass: Prepare each video with the same dimensions
            width, height = map(int, target_resolution.split('x'))
            scaled_videos = []
            scaled_intro = None
            
            # Process intro video if it exists
            if has_intro:
                # Scale and pad intro video to the target resolution
                scaled_intro = os.path.join(temp_dir, "scaled_intro.mp4")
                intro_cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', intro_video,
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-colorspace', 'bt709',
                    '-color_range', 'tv',
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                    '-r', '30',
                    scaled_intro
                ]
                
                click.echo("Preparing intro video...")
                subprocess.run(intro_cmd, check=True)
            
            # Process content videos
            for i, video_file in enumerate(video_files):
                # Get video info to calculate duration
                video_info = get_video_info(video_file)
                
                # Scale and pad each video to the target resolution
                scaled_video = os.path.join(temp_dir, f"scaled_{i}.mp4")
                scale_cmd = [
                    'ffmpeg',
                    '-y',
                    '-i', video_file,
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-colorspace', 'bt709',
                    '-color_range', 'tv',
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
                    '-r', '30',
                    scaled_video
                ]
                
                click.echo(f"Preparing video {i+1}/{len(video_files)}...")
                subprocess.run(scale_cmd, check=True)
                
                scaled_videos.append(scaled_video)
            
            # Calculate durations
            intro_duration = 0
            if scaled_intro:
                intro_info = get_video_info(scaled_intro)
                intro_duration = intro_info['duration']
                click.echo(f"Intro video duration: {intro_duration:.2f} seconds")
            
            # Calculate total duration of content videos
            total_content_duration = 0
            for i, video_path in enumerate(scaled_videos):
                video_info = get_video_info(video_path)
                total_content_duration += video_info['duration']
            
            click.echo(f"Total content video duration: {total_content_duration:.2f} seconds")
            click.echo(f"Target audio duration: {target_duration:.2f} seconds")
            
            # Determine if we need to loop videos to match audio duration
            input_videos = []
            
            # Always add intro video first if it exists
            if scaled_intro:
                input_videos.append(scaled_intro)
            
            # Calculate remaining duration needed after intro
            remaining_duration = target_duration - intro_duration
            
            if total_content_duration > 0 and remaining_duration > 0:
                if total_content_duration < remaining_duration:
                    # Calculate how many times we need to loop content videos
                    loops_needed = math.ceil(remaining_duration / total_content_duration)
                    click.echo(f"Need to loop content videos {loops_needed} times to match audio duration")
                    
                    # Add content videos in a loop until we reach the target duration
                    for loop in range(loops_needed):
                        # Only add content videos, not the intro again
                        input_videos.extend(scaled_videos)
                else:
                    # No need to loop, just add content videos
                    input_videos.extend(scaled_videos)
            elif scaled_videos:  # If no intro but we have content videos
                input_videos = scaled_videos
                
            # Second pass: Combine all videos using the concat filter
            # Create a complex filter string for concatenation
            filter_complex = ""
            
            # Input parts
            for i in range(len(input_videos)):
                filter_complex += f"[{i}:v:0]"
            
            # Concat filter
            filter_complex += f"concat=n={len(input_videos)}:v=1:a=0[outv]"
            
            # Build the ffmpeg command for concatenation
            concat_cmd = ['ffmpeg', '-y']
            
            # Add input files
            for video in input_videos:
                concat_cmd.extend(['-i', video])
            
            # Add filter complex and output options
            concat_cmd.extend([
                '-filter_complex', filter_complex,
                '-map', '[outv]',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-colorspace', 'bt709',
                '-color_range', 'tv',
                '-color_primaries', 'bt709',
                '-color_trc', 'bt709',
                '-r', '30',
                '-t', str(target_duration),  # Limit to target duration
            ])
            
            # Temporary output without audio
            temp_video = os.path.join(temp_dir, "temp_combined.mp4")
            concat_cmd.append(temp_video)
            
            click.echo("Combining videos...")
            subprocess.run(concat_cmd, check=True)
            
            # Third pass: Add audio if provided
            audio_path = f"{output_dir}/{audio_file}"
            if audio_file and os.path.exists(audio_path):
                # Create an intermediate video with audio
                intermediate_video = os.path.join(temp_dir, "video_with_audio.mp4")
                audio_cmd = [
                    'ffmpeg',
                    '-y',  # Overwrite output file if exists
                    '-i', temp_video,  # Input video
                    '-i', audio_path,  # Input audio with correct path
                    '-c:v', 'libx264',  # Re-encode video to ensure consistent colorspace
                    '-pix_fmt', 'yuv420p',
                    '-colorspace', 'bt709',
                    '-color_range', 'tv',
                    '-color_primaries', 'bt709',
                    '-color_trc', 'bt709',
                    '-c:a', 'aac',  # Use AAC audio codec
                    '-map', '0:v:0',  # Map video from first input
                    '-map', '1:a:0',  # Map audio from second input
                    '-shortest',  # End when shortest input ends
                    intermediate_video
                ]
                
                click.echo(f"Adding audio from {audio_path} to video...")
                subprocess.run(audio_cmd, check=True)
                
                # Add scrolling text directly to the video
                script_file = f"{output_dir}/script.txt"
                if os.path.exists(script_file):
                    output_path = f"{output_dir}/{output_file}"
                    # Add scrolling text directly to the video with audio
                    add_scrolling_text(intermediate_video, script_file, output_path)
                    click.echo(f"Final video with scrolling text saved as {output_path}")
                else:
                    # If no script file, just use the video with audio
                    output_path = f"{output_dir}/{output_file}"
                    shutil.copy(intermediate_video, output_path)
                    click.echo(f"No script file found at {script_file}, saving video with audio (no text) to {output_path}")
            else:
                # If no audio, just rename the temp video
                output_path = f"{output_dir}/{output_file}"
                shutil.copy(temp_video, output_path)
                click.echo(f"No audio file found at {audio_path}, saving video without audio to {output_path}")
        
        return output_file
        
    except subprocess.CalledProcessError as e:
        click.echo(f"Error running ffmpeg: {str(e)}", err=True)
        return None
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        return None


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Combine videos and synchronize with audio.')
    parser.add_argument('--video-dir', '-v', default='videos', help='Directory containing video files')
    parser.add_argument('--audio-file', '-a', help='Path to audio file to combine with video')
    parser.add_argument('--output-file', '-o', default='final_video.mp4', help='Path for the output video file')
    parser.add_argument('--resolution', '-r', default='1920x1080', help='Target resolution in format WIDTHxHEIGHT')
    
    args = parser.parse_args()
    
    click.echo(f"Processing videos from {args.video_dir}")
    if args.audio_file:
        click.echo(f"Using audio from {args.audio_file}")
    
    output_path = combine_videos_with_audio(
        video_dir=args.video_dir,
        audio_file=args.audio_file,
        output_file=args.output_file,
        target_resolution=args.resolution
    )
    
    if output_path:
        click.echo(f"Successfully created video: {output_path}")
    else:
        click.echo("Failed to create video", err=True)
