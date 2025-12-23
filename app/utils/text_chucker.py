def chunk_text(
    text: str,
    max_chars: int = 6000,
    max_chunks: int = 5,  # RPM safety cap
) -> list[str]:

    if not text or not text.strip():
        return []

    # Normalize whitespace (OCR / PDF junk killer)
    text = " ".join(text.split())

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length and len(chunks) < max_chunks:
        end = start + max_chars
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start = end

    return chunks
