# app/acronym_processor.py
import re

ACRONYM_MAP = {
    'A': 'ây', 'B': 'bi', 'C': 'xi', 'D': 'đi', 'E': 'i', 'F': 'ép', 'G': 'di',
    'H': 'hát', 'I': 'ai', 'J': 'jây', 'K': 'kei', 'L': 'eo', 'M': 'em', 'N': 'en',
    'O': 'ô', 'P': 'pi', 'Q': 'kiu', 'R': 'a-rờ', 'S': 'ét', 'T': 'ti', 'U': 'iu',
    'V': 'vi', 'W': 'đáp-liu', 'X': 'ích', 'Y': 'oai', 'Z': 'dét'
}

EXCEPTIONS = {"RAM", "ROM", "LAN", "WAN", "DOS", "APP", "SATA", "RAID", "MIME", "PING", "SIM", "VIP"}

DICTIONARY = {
    # English/IT terms
    "CEO": "si i ô",
    "CISSP": "xi ai ét ét pi",
    "IT": "ai ti",
    "AI": "ai ai",
    "KPI": "ka pi ai",
    "KPIs": "ka pi ai",
    "SOP": "ét ô pi",
    "CTO": "si ti ô",
    "CFO": "si éf ô",
    "COO": "si ô ô",
    "HR": "hát e-rờ",
    "SEO": "ét e ô",
    "DNS": "di en ét",
    "IP": "ai pi",
    "VPN": "vi pi en",
    "API": "ai pi ai",
    "UI": "iu ai",
    "UX": "iu ích",
    "QA": "kiu a",
    "QC": "kiu xi",
    "PM": "pê em",
    "PO": "pê ô",
    "BA": "bi a",
    "B2B": "bi tu bi",
    "B2C": "bi tu xi",
    "SaaS": "sát",
    "PaaS": "pát",
    "IaaS": "ai a a ét",
    "AWS": "a kép lu ét",
    "GCP": "gi xi pê",
    "SQL": "ét quy e-lờ",
    "HTML": "át ti em eo",
    "CSS": "xi ét ét",
    "JS": "giây ét",
    "HTTP": "át ti ti pi",
    "HTTPS": "át ti ti pi ét",
    "URL": "iu a eo",
    "PDF": "pi đi éf",
    "CPU": "xi pi iu",
    "SSD": "ét ét đi",
    "HDD": "át đi đi",
    "USB": "u ét bê",
    "IoT": "ai ô ti",
    "SLA": "ét el a",
    "OKR": "ô ka e-rờ",
    "OKRs": "ô ka e-rờ",
    "ERP": "i a pi",
    "CRM": "si a em",
    "CMS": "si em ét",
    "LMS": "el em ét",
    "VS": "vơ-sớt",
    
    # Vietnamese terms
    "TPHCM": "thành phố hồ chí minh",
    "VTV": "vê tê vê",
    "VND": "việt nam đồng",
    "USD": "u ét đê",
    "THVL": "truyền hình vĩnh long",
    "HTV": "hát tê vê",
    "VTC": "vê tê xi",
    "CHXHCNVN": "cộng hòa xã hội chủ nghĩa việt nam",
    "HĐND": "hội đồng nhân dân",
    "UBND": "ủy ban nhân dân",
    "BHXH": "bảo hiểm xã hội",
    "BHYT": "bảo hiểm y tế",
    "CSDL": "cơ sở dữ liệu",
    "CNTT": "công nghệ thông tin",
    "NXB": "nhà xuất bản",
    "THPT": "trung học phổ thông",
    "THCS": "trung học cơ sở",
    "ĐH": "đại học",
    "CĐ": "cao đẳng",
    "GD&ĐT": "giáo dục và đào tạo",
    "KH&CN": "khoa học và công nghệ",
    "TNHH": "trách nhiệm hữu hạn",
    "CP": "cổ phần",
    "QLTT": "quản lý thị trường",
    "PCCC": "phòng cháy chữa cháy",
    "CSGT": "cảnh sát giao thông",
    "BTV": "biên tập viên",
    "MC": "ém xi",
}

def normalize_acronyms_vi(text):
    if not text:
        return text
        
    words = text.split()
    if not words:
        return text
        
    # Count uppercase words (ignoring punctuation)
    uppercase_words = [w for w in words if re.match(r'^[A-Z\d&]+$', re.sub(r'[^\w&]', '', w))]
    if len(uppercase_words) / len(words) > 0.7:
        # It's an ALL CAPS sentence, do not normalize
        return text

    # First replace exact dictionary matches (case-sensitive, whole words)
    # Sort keys by length descending to match longer terms first (e.g. TPHCM before HP)
    sorted_dict_keys = sorted(DICTIONARY.keys(), key=len, reverse=True)
    
    for key in sorted_dict_keys:
        escaped_key = re.escape(key)
        
        # Determine the pattern string using custom lookahead/lookbehind
        pattern_str = r'(?<![^\W\d_])' + escaped_key + r'(?![^\W\d_])'
            
        # Match case-sensitively or with optional 's' for English acronyms
        # e.g., CEOs, KPIs
        if key.isupper() and key.isalpha() and not key.endswith('S'):
            # Allow optional 's' at the end: KPI -> KPI or KPIs
            pattern_str = r'(?<![^\W\d_])' + escaped_key + r'(s)?(?![^\W\d_])'
            def dict_replacer(match):
                has_s = match.group(1) is not None
                val = DICTIONARY[key]
                return " " + val + (" ét" if has_s else "") + " "
            text = re.sub(pattern_str, dict_replacer, text)
        else:
            text = re.sub(pattern_str, " " + DICTIONARY[key] + " ", text)

    # Now replace remaining uppercase words of length 2 to 7 letter-by-letter
    def replace_word(match):
        word = match.group(0)
        
        # Handle optional trailing 's'
        has_trailing_s = False
        lookup_word = word
        if word.endswith('s') and len(word) > 2 and word[:-1].isupper():
            has_trailing_s = True
            lookup_word = word[:-1]
            
        if lookup_word in EXCEPTIONS:
            return word
            
        phonetics = [ACRONYM_MAP.get(char, char) for char in lookup_word]
        result = " ".join(phonetics)
        if has_trailing_s:
            result += " ét"
        return " " + result + " "

    pattern = r'(?<![^\W\d_])[A-Z]{2,7}s?(?![^\W\d_])'
    normalized = re.sub(pattern, replace_word, text)
    
    # Clean up double spaces
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Clean up spaces before punctuation
    normalized = re.sub(r'\s+([.,!?:\;\)])', r'\1', normalized)
    
    # Clean up spaces after open parentheses
    normalized = re.sub(r'(\()\s+', r'\1', normalized)
    
    return normalized
