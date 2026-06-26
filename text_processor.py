import re
import os

def parse_srt(file_path):
    """
    Parse an SRT subtitle file (supports files with or without numeric index lines).
    
    Returns:
        list of dict: [{"index": int, "start": str, "end": str, "text": str}]
    """
    if not os.path.exists(file_path):
        return []
        
    items = []
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
        
    # Split by double newlines to get subtitle blocks
    blocks = re.split(r'\n\s*\n', content.strip())
    
    idx = 1
    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
            
        # Find the line containing the timestamp
        time_line_idx = -1
        start_time = ""
        end_time = ""
        for i, line in enumerate(lines):
            match = re.search(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})', line)
            if match:
                time_line_idx = i
                start_time = match.group(1).replace('.', ',')
                end_time = match.group(2).replace('.', ',')
                break
                
        if time_line_idx != -1:
            # The text consists of all lines after the timestamp line
            text_lines = lines[time_line_idx + 1:]
            text = " ".join(text_lines)
            
            # Always assign index sequentially
            index = idx
                    
            items.append({
                "index": index,
                "start": start_time,
                "end": end_time,
                "text": text,
                "type": "srt"
            })
            idx += 1
            
    return items

def split_text_by_punctuation(text):
    """
    Split a text into sentences based on punctuation (., !, ?, etc.)
    """
    # Regex splits by sentence ending punctuation while keeping the punctuation
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    # Further split by commas if a sentence is too long (optional/subtle)
    result = []
    for s in sentences:
        if s.strip():
            result.append(s.strip())
    return result

def parse_txt(file_path, auto_split=False):
    """
    Parse a TXT file line by line.
    
    Returns:
        list of dict: [{"index": int, "text": str}]
    """
    if not os.path.exists(file_path):
        return []
        
    items = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    idx = 1
    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue
            
        if auto_split:
            sentences = split_text_by_punctuation(line_str)
            for s in sentences:
                items.append({
                    "index": idx,
                    "text": s,
                    "type": "txt"
                })
                idx += 1
        else:
            items.append({
                "index": idx,
                "text": line_str,
                "type": "txt"
            })
            idx += 1
            
    return items

def parse_dgt(file_path, auto_split=False):
    """
    Parse a DGT subtitle/text file. DGT is often plain text lines, similar to TXT.
    """
    return parse_txt(file_path, auto_split=auto_split)

def format_srt_time(seconds):
    """
    Format seconds (float) to SRT format: HH:MM:SS,mmm
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    if milliseconds >= 1000:
        milliseconds = 999
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

def write_srt_file(items, output_path):
    """
    Write a list of items as an SRT file.
    
    Args:
        items (list): List of dicts, each having 'index', 'start', 'end', and 'text'.
        output_path (str): File path to save the SRT file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in items:
            f.write(f"{item['index']}\n")
            f.write(f"{item['start']} --> {item['end']}\n")
            f.write(f"{item['text']}\n\n")

def srt_time_to_seconds(time_str):
    """Convert SRT format HH:MM:SS,mmm to seconds (float)"""
    match = re.match(r'(\d{2}):(\d{2}):(\d{2})[,\.](\d{3})', time_str.strip())
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        milliseconds = int(match.group(4))
        return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
    return 0.0

def calculate_dynamic_gap_threshold(items, fallback=0.8):
    """
    Calculate the dynamic pause threshold between subtitle cards by finding the median
    of conversational gaps (gaps between 0.1s and 5.0s).
    """
    gaps = []
    for i in range(len(items) - 1):
        try:
            curr_end = srt_time_to_seconds(items[i]["end"])
            next_start = srt_time_to_seconds(items[i+1]["start"])
            gap = next_start - curr_end
            if 0.1 < gap <= 5.0:
                gaps.append(gap)
        except Exception:
            continue
            
    if len(gaps) < 5:
        return fallback
        
    gaps.sort()
    n = len(gaps)
    if n % 2 == 1:
        median = gaps[n // 2]
    else:
        median = (gaps[n // 2 - 1] + gaps[n // 2]) / 2.0
        
    threshold = median * 1.6
    return max(0.6, min(1.8, threshold))

def merge_subtitle_items(items):
    """
    Merge consecutive subtitle items and split them exactly by punctuation (., !, ?, etc.)
    or smart heuristics if the text is unpunctuated (gaps, capitalization, length limits).
    Timeline for each sentence is calculated by interpolating character positions based on
    the original card timestamps to keep it perfectly aligned with the video.
    """
    if not items:
        return []
        
    dynamic_gap = calculate_dynamic_gap_threshold(items, fallback=0.8)
    print(f"Dynamic gap threshold calculated: {dynamic_gap:.3f}s")
        
    # Step 1: Parse original timeline into character-level timestamps
    char_timestamps = []
    
    for idx, item in enumerate(items):
        text = item["text"]
        if not text:
            continue
        try:
            start_t = srt_time_to_seconds(item["start"])
            end_t = srt_time_to_seconds(item["end"])
        except Exception:
            start_t = 0.0
            end_t = 0.0
            
        dur = end_t - start_t
        n_chars = len(text)
        
        if n_chars > 0:
            for j, c in enumerate(text):
                t = start_t + (j / n_chars) * dur
                char_timestamps.append((c, t, idx, False))
                
        # Append a space representing the gap between cards, carrying the end timestamp
        char_timestamps.append((" ", end_t, idx, True))

    if not char_timestamps:
        return []

    # Step 2: Split by sentence markers (. ! ?) or heuristics while preserving character-to-timestamp mapping
    clauses = []
    current_clause_chars = []
    
    i = 0
    while i < len(char_timestamps):
        c, t, item_idx, is_boundary = char_timestamps[i]
        current_clause_chars.append((c, t, item_idx, is_boundary))
        
        # Check if this character is a sentence ender: . ! ?
        is_ender = c in ['.', '!', '?']
        
        # Exception 1: do not split if it's a decimal dot or part of a number (e.g., 5.0, 2.3, 30.000)
        # We look for the first non-space character in both directions to see if they are both digits.
        if is_ender and c == '.':
            prev_digit = None
            curr = i - 1
            while curr >= 0:
                prev_char = char_timestamps[curr][0]
                if prev_char.strip():
                    prev_digit = prev_char
                    break
                curr -= 1
                
            next_digit = None
            curr = i + 1
            while curr < len(char_timestamps):
                next_char = char_timestamps[curr][0]
                if next_char.strip():
                    next_digit = next_char
                    break
                curr += 1
                
            if prev_digit and next_digit and prev_digit.isdigit() and next_digit.isdigit():
                is_ender = False

        # Exception 2: handle ellipsis (...) and consecutive dots (prevent splitting mid-ellipsis or on lowercase continuation)
        if is_ender and c == '.':
            is_followed_by_dot = (i + 1 < len(char_timestamps) and char_timestamps[i+1][0] == '.')
            is_preceded_by_dot = (i > 0 and char_timestamps[i-1][0] == '.')
            
            if is_followed_by_dot:
                # Mid-ellipsis, do not split
                is_ender = False
            elif is_preceded_by_dot:
                # Last dot of the ellipsis. Only split if the next actual content is not lowercase
                next_content_char = None
                curr = i + 1
                while curr < len(char_timestamps):
                    nc = char_timestamps[curr][0]
                    if nc.strip() and nc != '.':
                        next_content_char = nc
                        break
                    curr += 1
                
                if next_content_char and next_content_char.islower():
                    is_ender = False

        # Exception 3: A sentence cannot end if it hasn't contained any word characters (letters/digits) yet
        if is_ender:
            has_word_char = any(ct[0].isalnum() for ct in current_clause_chars)
            if not has_word_char:
                is_ender = False
                
        # New Rule 4: If we are at a card boundary, check heuristics for splitting (especially for unpunctuated subtitles)
        if not is_ender and is_boundary:
            # Look ahead for the next content character and item index
            next_item_idx = None
            next_first_char = None
            curr = i + 1
            while curr < len(char_timestamps):
                nc, nt, n_item_idx, n_is_boundary = char_timestamps[curr]
                if nc.strip() and not n_is_boundary:
                    next_item_idx = n_item_idx
                    next_first_char = nc
                    break
                curr += 1
                
            if next_item_idx is not None and next_item_idx < len(items):
                curr_item = items[item_idx]
                next_item = items[next_item_idx]
                
                try:
                    curr_end = srt_time_to_seconds(curr_item["end"])
                    next_start = srt_time_to_seconds(next_item["start"])
                    original_gap = next_start - curr_end
                except Exception:
                    original_gap = 0.0
                    
                # Heuristic 1: Timeline Gap > dynamic_gap seconds (intentional pause)
                # But do NOT split if the next card starts with a lowercase letter (clearly a continuation)
                # unless the gap is extremely large (e.g. > max(2.0, dynamic_gap * 2.5) seconds)
                max_gap_limit = max(2.0, dynamic_gap * 2.5)
                if original_gap > max_gap_limit or (original_gap > dynamic_gap and not (next_first_char and next_first_char.islower())):
                    is_ender = True
                # Heuristic 2: Next card starts with an uppercase letter
                elif next_first_char and next_first_char.isupper():
                    is_ender = True
                # Heuristic 3: Merged text is already too long (> 25 words or > 150 characters)
                else:
                    clause_text = "".join(ct[0] for ct in current_clause_chars).strip()
                    word_count = len(clause_text.split())
                    if word_count >= 25 or len(clause_text) >= 150:
                        is_ender = True
        
        if is_ender:
            # Capture any trailing quotes or brackets (e.g. ." or ?))
            while i + 1 < len(char_timestamps) and char_timestamps[i+1][0] in ['"', "'", ')', ']', '}']:
                i += 1
                c_next, t_next, item_idx_next, is_boundary_next = char_timestamps[i]
                current_clause_chars.append((c_next, t_next, item_idx_next, is_boundary_next))
            
            clauses.append(current_clause_chars)
            current_clause_chars = []
            
        i += 1
        
    if current_clause_chars:
        # Check if it contains actual text (not just spaces)
        if any(c[0].strip() for c in current_clause_chars):
            clauses.append(current_clause_chars)

    # Step 3: Build the new items list
    merged_items = []
    for idx, clause_chars in enumerate(clauses):
        # Clean text
        text_str = "".join(ct[0] for ct in clause_chars).strip()
        text_str = re.sub(r'\s+', ' ', text_str)
        # Remove spaces around decimal/thousand separators inside numbers split across cards (e.g. "30. 000" -> "30.000", "2, 3" -> "2,3")
        text_str = re.sub(r'(\d+)\.\s+(\d+)', r'\1.\2', text_str)
        text_str = re.sub(r'(\d+),\s+(\d+)', r'\1,\2', text_str)
        # Remove redundant consecutive ellipsis (e.g. "... ..." -> "... ")
        text_str = re.sub(r'\.\.\.\s*\.\.\.', '... ', text_str)
        
        if not text_str:
            continue
            
        # Find first and last non-space character timestamps
        non_space_chars = [ct for ct in clause_chars if ct[0].strip()]
        if not non_space_chars:
            continue
            
        start_t = non_space_chars[0][1]
        end_t = non_space_chars[-1][1]
        
        # Collect original child items that contributed to this clause
        child_indices = []
        for ct in clause_chars:
            c_item_idx = ct[2]
            if c_item_idx not in child_indices:
                child_indices.append(c_item_idx)
                
        children_items = []
        for c_idx in child_indices:
            if c_idx < len(items):
                children_items.append(items[c_idx])
        
        merged_items.append({
            "index": len(merged_items) + 1,
            "file": items[0].get("file", ""),
            "start": format_srt_time(start_t),
            "end": format_srt_time(end_t),
            "text": text_str,
            "type": items[0]["type"],
            "status": "Ready",
            "duration": 0.0,
            "output_path": "",
            "children": children_items
        })
        
    return merged_items


def redistribute_subtitles_timing(merged_items):
    """
    Take merged items (with actual duration from synthesis) and redistribute the duration
    to their original child items based on character length.
    
    Returns:
        list of dict: Expanded original items with new timestamps.
    """
    redistributed_items = []
    
    idx = 1
    for merged in merged_items:
        children = merged.get("children", [])
        if not children:
            merged_copy = merged.copy()
            merged_copy["index"] = idx
            redistributed_items.append(merged_copy)
            idx += 1
            continue
            
        duration = merged.get("joined_duration", merged.get("duration", 0.0))
        total_chars = sum(len(child["text"]) for child in children)
        
        # Start time of this merged block
        start_seconds = merged.get("joined_start", srt_time_to_seconds(merged["start"]))
        current_time = start_seconds
        
        for child in children:
            text_len = len(child["text"])
            ratio = text_len / total_chars if total_chars > 0 else 1.0 / len(children)
            child_duration = duration * ratio
            
            new_child = child.copy()
            new_child["index"] = idx
            new_child["start"] = format_srt_time(current_time)
            new_child["end"] = format_srt_time(current_time + child_duration)
            new_child["duration"] = child_duration
            new_child["status"] = merged.get("status", "Done")
            new_child["output_path"] = merged.get("output_path", "")
            
            redistributed_items.append(new_child)
            current_time += child_duration
            idx += 1
            
    return redistributed_items

