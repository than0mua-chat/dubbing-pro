import os
import sys
import subprocess
import re
import tempfile
import imageio_ffmpeg

# Prevent console window from flashing on Windows
creation_flags = 0x08000000 if sys.platform == "win32" else 0

def get_audio_duration(file_path):
    """
    Get the duration of an audio file.
    Uses mutagen for MP3 files (fast, no subprocess).
    Falls back to FFmpeg for other formats.
    
    Args:
        file_path (str): Path to the audio file.
        
    Returns:
        float: Duration in seconds, or 0.0 if unable to determine.
    """
    if not os.path.exists(file_path):
        return 0.0
    
    # Fast path: use mutagen for MP3 files (no subprocess needed)
    if file_path.lower().endswith('.mp3'):
        try:
            from mutagen.mp3 import MP3
            audio = MP3(file_path)
            return audio.info.length
        except Exception:
            pass  # Fall through to ffmpeg
        
    # Fallback: use ffmpeg for non-MP3 or if mutagen fails
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_path, '-i', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
        output = result.stderr
        
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+)\.(\d+)", output)
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3))
            centiseconds = int(match.group(4))
            return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
    except Exception as e:
        print(f"Lỗi khi đọc độ dài file âm thanh: {e}")
        
    return 0.0

def get_audio_properties(file_path):
    """
    Get sample rate and channel count of an audio file using FFmpeg.
    """
    sample_rate = 24000
    channels = 1
    
    if not file_path or not os.path.exists(file_path):
        return sample_rate, channels
        
    try:
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_path, '-i', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=creation_flags)
        output = result.stderr
        
        match = re.search(r"Audio:.*?, (\d+) Hz, ([^,]+)", output)
        if match:
            sample_rate = int(match.group(1))
            chan_str = match.group(2).strip().lower()
            if "stereo" in chan_str:
                channels = 2
            else:
                channels = 1
    except Exception as e:
        print(f"Error getting audio properties: {e}")
        
    return sample_rate, channels

def join_mp3_files(file_paths, output_path):
    """
    Concatenate multiple MP3 files into one by decoding to raw PCM,
    concatenating the raw bytes, and re-encoding back to MP3.
    This ensures a seamless merge without stream-boundary clicks or silence delays.
    
    Args:
        file_paths (list): List of paths to the MP3 files to join.
        output_path (str): Path to save the merged MP3.
    """
    if not file_paths:
        return
        
    # Get sample rate and channels from the first valid input file
    sample_rate = 24000
    channels = 1
    for path in file_paths:
        if path and os.path.exists(path):
            sample_rate, channels = get_audio_properties(path)
            break
            
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    temp_pcm_files = []
    merged_pcm = None
    try:
        # Convert each MP3 to a temporary raw PCM file
        for path in file_paths:
            if not path or not os.path.exists(path):
                continue
            # Create a temporary file path for the PCM output
            fd, temp_pcm = tempfile.mkstemp(suffix='.raw')
            os.close(fd)
            temp_pcm_files.append(temp_pcm)
            
            # Decode MP3 to raw 16-bit signed little-endian PCM (s16le)
            cmd = [
                ffmpeg_path,
                '-y',
                '-i', path,
                '-f', 's16le',
                '-acodec', 'pcm_s16le',
                '-ar', str(sample_rate),
                '-ac', str(channels),
                temp_pcm
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
            
        # Concatenate all raw PCM files into a single merged raw PCM file
        fd, merged_pcm = tempfile.mkstemp(suffix='.raw')
        os.close(fd)
        
        with open(merged_pcm, 'wb') as outfile:
            for pcm_path in temp_pcm_files:
                if os.path.exists(pcm_path):
                    with open(pcm_path, 'rb') as infile:
                        # Stream in chunks to be memory efficient
                        while True:
                            chunk = infile.read(65536)
                            if not chunk:
                                break
                            outfile.write(chunk)
                            
        # Encode the merged raw PCM file back to MP3
        # -q:a 2 (similar to LAME -V2, good quality VBR)
        cmd = [
            ffmpeg_path,
            '-y',
            '-f', 's16le',
            '-ar', str(sample_rate),
            '-ac', str(channels),
            '-i', merged_pcm,
            '-c:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=creation_flags)
        if result.returncode != 0:
            error_msg = result.stderr.decode('utf-8', 'ignore')
            raise RuntimeError(f"FFmpeg error: {error_msg}")
            
    finally:
        # Clean up temporary PCM files
        for pcm_path in temp_pcm_files:
            if os.path.exists(pcm_path):
                try:
                    os.unlink(pcm_path)
                except Exception:
                    pass
        if merged_pcm and os.path.exists(merged_pcm):
            try:
                os.unlink(merged_pcm)
            except Exception:
                pass
