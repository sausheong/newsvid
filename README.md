# NewsVid

A comprehensive tool for generating news videos from articles, with automatic script generation, video processing, and text-to-speech capabilities.

## Features

- Generate news scripts from web articles using Gemma 2 (through Ollama)
- Convert text scripts to audio using Kokoro TTS 
- Search and download relevant videos from Pexels based on keywords
- Process videos with FFmpeg 
- Add scrolling text overlays to videos
- Combine multiple videos with audio tracks
- Add picture-in-picture talking head video overlay
- Command-line interface for easy integration

## Requirements

- Python 3.10+
- Ollama (for AI processing) with Gemma 2
- FFmpeg (for video processing)
- Pexels API key (for video downloads)
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone this repository and go to the directory
   ```bash
   git clone https://github.com/sausheong/newsvid.git
   cd newsvid
   ```
2. Create a virtual environment:
   ```bash
   conda create -n newsvid python=3.10
   conda activate newsvid
   ```
3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Download Kokoro TTS model:
   ```bash
   wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
   wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
   ```   
5. Set up the environment:
     ```bash
     export PEXELS_API_KEY='your-pexels-api-key-here'
     ```

## Usage

### Command Line Interface

The main command is `newsvid`, which processes a news article URL:

```bash
# Basic usage
./newsvid generate https://example.com/news-article

./newvid pip --output_dir ./output/news-article
```

### Configuration

The application uses environment variables for configuration. The main ones are:

- `PEXELS_API_KEY`: Your Pexels API key for video downloads

You can also customize behavior through command-line options:

```bash
# Get help on available options
./newsvid --help
```

### Process Flow

1. The tool reads the article from the provided URL
2. Generates a news script using Ollama with Gemma 2
3. Extracts keywords from the generated script
4. Converts the script to audio using Kokoro TTS
5. Searches and downloads relevant videos from Pexels based on keywords
6. Processes the videos to ensure consistent resolution and format
7. Adds scrolling text overlay with the script content
8. Combines all videos with the audio track
9. Outputs a final news video ready for viewing
10. Optionall adds in a picture-in-picture talking head video overlay

#### Video Output

The output intermediate and final files are stored in the `./output` directory.

```bash
./newsvid https://example.com/news-article -o ./my_videos
```

## Code Structure

The project is organized into several modules:

- `newsvid`: Main command-line interface script
- `download.py`: Functions for searching and downloading videos from Pexels
- `vid.py`: Video processing utilities using FFmpeg
- `tts.py`: Text-to-speech conversion using OpenAI's API

