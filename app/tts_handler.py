# tts_handler.py

import edge_tts
import asyncio
import tempfile
import subprocess
import os
import re
import requests
from pathlib import Path
import imageio_ffmpeg

from utils import DETAILED_ERROR_LOGGING
from config import DEFAULT_CONFIGS
from acronym_processor import normalize_acronyms_vi

# Language default (environment variable)
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', DEFAULT_CONFIGS["DEFAULT_LANGUAGE"])

# OpenAI voice names mapped to edge-tts equivalents
voice_mapping = {
    'alloy': 'en-US-JennyNeural',
    'ash': 'en-US-AndrewNeural',
    'ballad': 'en-GB-ThomasNeural',
    'coral': 'en-AU-NatashaNeural',
    'echo': 'en-US-GuyNeural',
    'fable': 'en-GB-SoniaNeural',
    'nova': 'en-US-AriaNeural',
    'onyx': 'en-US-EricNeural',
    'sage': 'en-US-JennyNeural',
    'shimmer': 'en-US-EmmaNeural',
    'verse': 'en-US-BrianNeural',
}

model_data = [
        {"id": "tts-1", "name": "Text-to-speech v1"},
        {"id": "tts-1-hd", "name": "Text-to-speech v1 HD"},
        {"id": "gpt-4o-mini-tts", "name": "GPT-4o mini TTS"}
    ]

def is_ffmpeg_installed():
    """Check if FFmpeg is installed and accessible."""
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        return os.path.exists(ffmpeg_path)
    except Exception:
        return False

async def _generate_audio_stream(text, voice, speed, proxy=None):
    """Generate streaming TTS audio using edge-tts."""
    # Normalize Vietnamese acronyms if voice is Vietnamese
    if voice.lower().startswith('vi-') or 'vietnam' in voice.lower():
        text = normalize_acronyms_vi(text)

    # Determine if the voice is an OpenAI-compatible voice or a direct edge-tts voice
    edge_tts_voice = voice_mapping.get(voice, voice)  # Use mapping if in OpenAI names, otherwise use as-is
    
    # Convert speed to SSML rate format
    try:
        speed_rate = speed_to_rate(speed)  # Convert speed value to "+X%" or "-X%"
    except Exception as e:
        print(f"Error converting speed: {e}. Defaulting to +0%.")
        speed_rate = "+0%"
    
    # Create the communicator for streaming
    communicator = edge_tts.Communicate(text=text, voice=edge_tts_voice, rate=speed_rate, proxy=proxy)
    
    # Stream the audio data
    async for chunk in communicator.stream():
        if chunk["type"] == "audio":
            yield chunk["data"]

def generate_speech_stream(text, voice, speed=1.0, proxy=None):
    """Generate streaming speech audio (synchronous wrapper)."""
    return asyncio.run(_generate_audio_stream(text, voice, speed, proxy))

async def _generate_audio(text, voice, response_format, speed, proxy=None):
    """Generate TTS audio and optionally convert to a different format."""
    # Normalize Vietnamese acronyms if voice is Vietnamese
    if voice.lower().startswith('vi-') or 'vietnam' in voice.lower():
        text = normalize_acronyms_vi(text)

    # Determine if the voice is an OpenAI-compatible voice or a direct edge-tts voice
    edge_tts_voice = voice_mapping.get(voice, voice)  # Use mapping if in OpenAI names, otherwise use as-is

    # Generate the TTS output in mp3 format first
    temp_mp3_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_mp3_path = temp_mp3_file_obj.name

    # Convert speed to SSML rate format
    try:
        speed_rate = speed_to_rate(speed)  # Convert speed value to "+X%" or "-X%"
    except Exception as e:
        print(f"Error converting speed: {e}. Defaulting to +0%.")
        speed_rate = "+0%"

    # Generate the MP3 file
    connector = None
    comm_kwargs = {
        "text": text,
        "voice": edge_tts_voice,
        "rate": speed_rate
    }
    if proxy:
        if proxy.startswith("socks"):
            try:
                from aiohttp_socks import ProxyConnector
                connector = ProxyConnector.from_url(proxy)
                comm_kwargs["connector"] = connector
            except Exception as e:
                print(f"Error creating SOCKS ProxyConnector: {e}")
                comm_kwargs["proxy"] = proxy
        else:
            comm_kwargs["proxy"] = proxy

    try:
        communicator = edge_tts.Communicate(**comm_kwargs)
        await communicator.save(temp_mp3_path)
    finally:
        if connector:
            try:
                # Close the connector asynchronously if it has close method
                # Since we are in an async function, we can await it
                await connector.close()
            except Exception:
                pass
    temp_mp3_file_obj.close() # Explicitly close our file object for the initial mp3

    # If the requested format is mp3, return the generated file directly
    if response_format == "mp3":
        return temp_mp3_path

    # Check if FFmpeg is installed
    if not is_ffmpeg_installed():
        print("FFmpeg is not available. Returning unmodified mp3 file.")
        return temp_mp3_path # Return the original mp3 path, it won't be cleaned by this function

    # Create a new temporary file for the converted output
    converted_file_obj = tempfile.NamedTemporaryFile(delete=False, suffix=f".{response_format}")
    converted_path = converted_file_obj.name
    converted_file_obj.close() # Close file object, ffmpeg will write to the path

    # Build the FFmpeg command
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_command = [
        ffmpeg_path,
        "-i", temp_mp3_path,  # Input file path
        "-c:a", {
            "aac": "aac",
            "mp3": "libmp3lame",
            "wav": "pcm_s16le",
            "opus": "libopus",
            "flac": "flac"
        }.get(response_format, "aac"),  # Default to AAC if unknown
    ]

    if response_format != "wav":
        ffmpeg_command.extend(["-b:a", "192k"])

    ffmpeg_command.extend([
        "-f", {
            "aac": "mp4",  # AAC in MP4 container
            "mp3": "mp3",
            "wav": "wav",
            "opus": "ogg",
            "flac": "flac"
        }.get(response_format, response_format),  # Default to matching format
        "-y",  # Overwrite without prompt
        converted_path  # Output file path
    ])

    # Prevent console window from flashing on Windows
    creation_flags = 0x08000000 if os.name == 'nt' else 0
    try:
        # Run FFmpeg command and ensure no errors occur
        subprocess.run(ffmpeg_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
    except subprocess.CalledProcessError as e:
        # Clean up potentially created (but incomplete) converted file
        Path(converted_path).unlink(missing_ok=True)
        # Clean up the original mp3 file as well, since conversion failed
        Path(temp_mp3_path).unlink(missing_ok=True)
        
        if DETAILED_ERROR_LOGGING:
            error_message = f"FFmpeg error during audio conversion. Command: '{' '.join(e.cmd)}'. Stderr: {e.stderr.decode('utf-8', 'ignore')}"
            print(error_message) # Log for server-side diagnosis
        else:
            error_message = f"FFmpeg error during audio conversion: {e}"
            print(error_message) # Log a simpler message
        raise RuntimeError(f"FFmpeg error during audio conversion: {e}") # The raised error will still have details via e

    # Clean up the original temporary file (original mp3) as it's now converted
    Path(temp_mp3_path).unlink(missing_ok=True)

    return converted_path

def generate_speech(text, voice, response_format, speed=1.0, proxy=None):
    return asyncio.run(_generate_audio(text, voice, response_format, speed, proxy))

def get_models():
    return model_data

def get_models_formatted():
    return [{ "id": x["id"] } for x in model_data]

def get_voices_formatted():
    return [{ "id": k, "name": v } for k, v in voice_mapping.items()]

async def _get_voices(language=None):
    # List all voices, filter by language if specified
    all_voices = await edge_tts.list_voices()
    language = language or DEFAULT_LANGUAGE  # Use default if no language specified
    filtered_voices = [
        {"name": v['ShortName'], "gender": v['Gender'], "language": v['Locale']}
        for v in all_voices if language == 'all' or language is None or v['Locale'] == language
    ]
    return filtered_voices

def get_voices(language=None):
    return asyncio.run(_get_voices(language))

def speed_to_rate(speed: float) -> str:
    """
    Converts a multiplicative speed value to the edge-tts "rate" format.
    
    Args:
        speed (float): The multiplicative speed value (e.g., 1.5 for +50%, 0.5 for -50%).
    
    Returns:
        str: The formatted "rate" string (e.g., "+50%" or "-50%").
    """
    if speed < 0 or speed > 2:
        raise ValueError("Speed must be between 0 and 2 (inclusive).")

    # Convert speed to percentage change
    percentage_change = (speed - 1) * 100

    # Format with a leading "+" or "-" as required
    return f"{percentage_change:+.0f}%"

def generate_speech_elevenlabs(text, voice_id, model_id, api_key, stability=0.5, similarity=0.75, speed=1.0, proxies=None):
    """
    Generate speech using ElevenLabs API.
    Saves to a temporary MP3 file and returns the path.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    
    payload = {
        "text": text,
        "model_id": model_id or "eleven_multilingual_v2",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity
        }
    }
    
    response = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=30)
    if response.status_code == 200:
        # Create temp file
        temp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_mp3_path = temp_mp3.name
        temp_mp3.write(response.content)
        temp_mp3.close()
        
        # If speed != 1.0, apply time stretching via ffmpeg
        if speed != 1.0 and is_ffmpeg_installed():
            converted_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            converted_path = converted_file.name
            converted_file.close()
            
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Clamp speed and chain filters if necessary
            # ffmpeg atempo filter works between 0.5 and 2.0
            if speed < 0.5:
                atempo_filter = "atempo=0.5,atempo=0.5"
            elif speed > 2.0:
                atempo_filter = "atempo=2.0,atempo=2.0"
            else:
                atempo_filter = f"atempo={speed}"
                
            ffmpeg_command = [
                ffmpeg_path,
                "-i", temp_mp3_path,
                "-filter:a", atempo_filter,
                "-y",
                converted_path
            ]
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            try:
                subprocess.run(ffmpeg_command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
                os.unlink(temp_mp3_path)
                return converted_path
            except Exception as e:
                print(f"ElevenLabs speed adjustment failed: {e}")
                os.unlink(converted_path)
                return temp_mp3_path
                
        return temp_mp3_path
    else:
        raise RuntimeError(f"ElevenLabs API error: {response.status_code} - {response.text}")
