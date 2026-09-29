import os
import re
import zipfile


def apply_prefix_suffix(filename, prefix=None, suffix=None):
    name, ext = os.path.splitext(filename)
    if prefix:
        name = f"{prefix}{name}"
    if suffix:
        name = f"{name}{suffix}"
    return f"{name}{ext}"


def apply_word_replace(filename, replace_words):
    """
    replace_words is a string like "old:new,foo:bar" — applies each
    pair in order, simple substring replacement.
    """
    if not replace_words:
        return filename
    name, ext = os.path.splitext(filename)
    for pair in replace_words.split(","):
        if ":" not in pair:
            continue
        old, new = pair.split(":", 1)
        name = name.replace(old.strip(), new.strip())
    return f"{name}{ext}"


def apply_regex(filename, pattern_and_repl):
    """
    pattern_and_repl is "pattern###replacement" — applies re.sub.
    Falls back silently to the original name on a bad pattern.
    """
    if not pattern_and_repl or "###" not in pattern_and_repl:
        return filename
    name, ext = os.path.splitext(filename)
    pattern, repl = pattern_and_repl.split("###", 1)
    try:
        name = re.sub(pattern, repl, name)
    except re.error:
        pass
    return f"{name}{ext}"


def is_zip_file(file_path):
    return zipfile.is_zipfile(file_path)


def unzip_file(zip_path, extract_to):
    os.makedirs(extract_to, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.namelist():
            zf.extract(member, extract_to)
            extracted.append(os.path.join(extract_to, member))
    return extracted


def safe_filename(name):
    """Strips characters that break most filesystems / Telegram uploads."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)
