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
                        last_word = clause_text.split()[-1].lower() if clause_text.split() else ""
                        # Conjunctions, prepositions, and determiners that should not end a split
                        bad_ends = ["và", "hoặc", "nhưng", "mà", "là", "với", "của", "mọi", "các", "những", "để", "cho", "trong", "tại", "and", "or", "but", "with", "of", "to", "in", "for", "the", "a", "an"]
                        is_next_lowercase = next_first_char and next_first_char.islower()
                        
                        if is_next_lowercase:
                            # If the next word starts with a lowercase letter, only split if it is extremely long
                            if word_count >= 50 or len(clause_text) >= 300:
                                if last_word not in bad_ends:
                                    is_ender = True
                        else:
                            if last_word not in bad_ends:
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


def align_punctuated_text(orig_chars, new_text):
    """
    Align the characters of new_text with the timestamp-labeled characters of the original text.
    orig_chars: list of tuples (char, timestamp, item_idx, is_boundary)
    new_text: str (the punctuated/corrected text returned by Gemini or LLM)
    
    Returns:
        list of tuples (char, timestamp, item_idx, is_boundary) for the new_text.
    """
    import difflib
    # Extract the plain text from orig_chars
    orig_text = "".join(c[0] for c in orig_chars)
    
    # Use SequenceMatcher to find matching blocks
    matcher = difflib.SequenceMatcher(None, orig_text, new_text)
    matching_blocks = matcher.get_matching_blocks()
    
    new_timestamps = [None] * len(new_text)
    
    # Step 1: Map matching characters
    for block in matching_blocks:
        a_start, b_start, size = block
        for k in range(size):
            orig_idx = a_start + k
            new_idx = b_start + k
            new_timestamps[new_idx] = orig_chars[orig_idx]
            
    # Step 2: Interpolate missing timestamps
    # Find first valid timestamp to fallback for prefix
    first_valid = None
    for t in new_timestamps:
        if t is not None:
            first_valid = t
            break
    if not first_valid:
        # Fallback if no match at all
        return [(c, 0.0, 0, False) for c in new_text]
        
    # Fill prefix
    last_valid = first_valid
    for idx in range(len(new_text)):
        if new_timestamps[idx] is None:
            new_timestamps[idx] = (new_text[idx], last_valid[1], last_valid[2], False)
        else:
            last_valid = new_timestamps[idx]
            break
            
    # Fill suffix and intermediate gaps
    last_valid_idx = 0
    for idx in range(len(new_text)):
        if new_timestamps[idx] is not None:
            # Fill gap between last_valid_idx and idx
            if idx > last_valid_idx + 1:
                t_start = new_timestamps[last_valid_idx][1]
                t_end = new_timestamps[idx][1]
                item_idx = new_timestamps[idx][2]
                gap_size = idx - last_valid_idx
                for g in range(last_valid_idx + 1, idx):
                    ratio = (g - last_valid_idx) / gap_size
                    t_interp = t_start + ratio * (t_end - t_start)
                    new_timestamps[g] = (new_text[g], t_interp, item_idx, False)
            last_valid_idx = idx
            
    # Fill suffix
    last_t = new_timestamps[last_valid_idx]
    for idx in range(last_valid_idx + 1, len(new_text)):
        new_timestamps[idx] = (new_text[idx], last_t[1], last_t[2], False)
        
    return new_timestamps


def split_long_clause(clause_chars, max_len=80):
    """
    If a clause is too long (> max_len chars), split it at commas or common conjunctions.
    """
    import re
    clause_text = "".join(ct[0] for ct in clause_chars)
    if len(clause_text) <= max_len:
        return [clause_chars]
        
    # Find potential split points: commas or conjunctions
    split_points = []
    conjunctions = ["and", "or", "but", "và", "hoặc", "nhưng", "mà", "là", "vì", "nên", "được"]
    
    i = 0
    while i < len(clause_chars):
        c = clause_chars[i][0]
        # Check for comma
        if c == ',':
            split_points.append(i + 1)  # split after comma
        # Check for conjunction
        elif c == ' ':
            # Peek next word
            word_chars = []
            j = i + 1
            while j < len(clause_chars) and clause_chars[j][0].isalnum():
                word_chars.append(clause_chars[j][0])
                j += 1
            word = "".join(word_chars).lower()
            if word in conjunctions:
                split_points.append(i)  # split before conjunction
        i += 1
        
    if not split_points:
        return [clause_chars]
        
    parts = []
    last_split = 0
    for sp in split_points:
        if sp - last_split > 30 and (sp - last_split <= max_len or len(clause_chars) - sp > 30):
            parts.append(clause_chars[last_split:sp])
            last_split = sp
    if last_split < len(clause_chars):
        parts.append(clause_chars[last_split:])
        
    return [p for p in parts if p]


def merge_subtitle_items_gemini(items, api_key, proxy=None):
    """
    Restores punctuation and merges subtitle items using Google Gemini 1.5 Flash API.
    Realigns timestamps using SequenceMatcher based character interpolation.
    """
    if not items:
        return []
        
    # Step 1: Build original character timestamps
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
                
        char_timestamps.append((" ", end_t, idx, True))
        
    if not char_timestamps:
        return []
        
    # Step 2: Query Gemini API to clean & restore punctuation
    import requests
    import json
    import re
    
    # 2.1: Strip HTML tags and sound annotations from raw texts
    raw_texts = []
    for item in items:
        txt = item["text"]
        # Strip HTML
        txt = re.sub(r'</?[^>]+(>|$)', '', txt)
        # Strip sound descriptions in parentheses or brackets
        txt = re.sub(r'\([^)]*\)|\[[^\]]*\]', '', txt)
        raw_texts.append(txt.strip())
        
    raw_text = "\n".join(raw_texts)
    
    prompt = (
        "You are an expert subtitle restorer. Your task is to process the following raw, unpunctuated subtitle transcript.\n"
        "Please:\n"
        "1. Restore correct capitalization and punctuation (periods, commas, question marks, exclamation marks).\n"
        "2. Clean any formatting tags (like <i>, <b>) and non-speech sounds (like [Music], [Laughter], (applause)) - remove them completely.\n"
        "3. Standardize and expand acronyms based on context (e.g. capitalize CISSP, CEO, AWS, IT, AI).\n"
        "4. Maintain the exact flow and meaning of the original sentences. Do not summarize or omit speech.\n"
        "5. Return ONLY the final restored plain text. Do not include any notes, explanations, markdown formatting, or HTML.\n\n"
        f"Here is the raw subtitle text:\n---\n{raw_text}\n---\nRestored text:"
    )
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }]
    }
    
    proxies = None
    if proxy:
        proxies = {
            "http": proxy,
            "https": proxy
        }
        
    # Try stable v1 first, then fallback to v1beta
    endpoints = [
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    ]
    
    res = None
    last_err = None
    for endpoint in endpoints:
        try:
            res = requests.post(endpoint, headers=headers, json=payload, proxies=proxies, timeout=30)
            if res.status_code == 200:
                break
        except Exception as e:
            last_err = e
            
    if res is None or res.status_code != 200:
        if res is not None:
            # Try to parse Google's JSON error response
            try:
                err_json = res.json()
                if "error" in err_json:
                    err_msg = err_json["error"].get("message", "")
                    err_status = err_json["error"].get("status", "")
                    raise RuntimeError(f"Gemini API Error {res.status_code} ({err_status}): {err_msg}")
            except Exception as json_err:
                if isinstance(json_err, RuntimeError):
                    raise json_err
            # If not JSON, show the first 300 chars of the text (helps identify proxy blocks/HTML)
            err_body = res.text.strip() if res.text else ""
            if not err_body:
                err_body = "Empty Response"
            else:
                err_body = err_body[:300]
            raise RuntimeError(f"HTTP {res.status_code} from endpoint: {err_body}")
        elif last_err:
            raise last_err
        else:
            raise RuntimeError("Failed to connect to Gemini API (Connection Error).")
            
    res_data = res.json()
    
    try:
        new_text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        raise RuntimeError(f"Error parsing Gemini response: {e}. Full response: {res_data}")
        
    # Clean up multiple newlines or spaces returned by Gemini
    new_text = re.sub(r'\n+', ' ', new_text)
    new_text = re.sub(r'\s+', ' ', new_text).strip()
    
    # Step 3: Align character timestamps
    new_char_timestamps = align_punctuated_text(char_timestamps, new_text)
    
    # Step 4: Split into sentences based on punctuation, and subdivide if too long
    clauses = []
    current_clause = []
    
    i = 0
    while i < len(new_char_timestamps):
        c, t, item_idx, is_b = new_char_timestamps[i]
        current_clause.append((c, t, item_idx, is_b))
        
        is_ender = c in ['.', '!', '?']
        if is_ender and c == '.':
            # Avoid splitting on decimals (e.g., 2.5)
            prev_digit = False
            if i > 0 and new_char_timestamps[i-1][0].isdigit():
                prev_digit = True
            next_digit = False
            if i + 1 < len(new_char_timestamps) and new_char_timestamps[i+1][0].isdigit():
                next_digit = True
            if prev_digit and next_digit:
                is_ender = False
                
        if is_ender:
            # Capture trailing symbols
            while i + 1 < len(new_char_timestamps) and new_char_timestamps[i+1][0] in ['"', "'", ')', ']', '}']:
                i += 1
                current_clause.append(new_char_timestamps[i])
            split_parts = split_long_clause(current_clause, max_len=80)
            clauses.extend(split_parts)
            current_clause = []
        i += 1
        
    if current_clause:
        split_parts = split_long_clause(current_clause, max_len=80)
        clauses.extend(split_parts)
        
    # Step 5: Format into subtitle items
    merged_items = []
    for idx, clause_chars in enumerate(clauses):
        text_str = "".join(ct[0] for ct in clause_chars).strip()
        text_str = re.sub(r'\s+', ' ', text_str)
        text_str = re.sub(r'\s+([.,!?])', r'\1', text_str)
        
        if not text_str:
            continue
            
        start_t = clause_chars[0][1]
        end_t = clause_chars[-1][1]
        
        orig_file = items[0]["file"] if items else "sub"
        
        merged_items.append({
            "stt": idx + 1,
            "file": orig_file,
            "text": text_str,
            "start": format_srt_time(start_t),
            "end": format_srt_time(end_t),
            "status": "Ready",
            "duration": 0.0,
            "output_path": ""
        })
        
    return merged_items

