import hashlib, sys, re, time
from typing import List, Dict, Set, Tuple

# Keep these small; you already solved 62/66 so we only need to crack 1 token.
LEADERS = ["", "\"", "“", "(", "[", "{"]          # leading punctuation
TRAILERS = ["", ",", ".", "!", "?", "\"", "”", ")", "]", "}", "'s"]  # trailing punctuation

def sha256_digest(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def key9_bytes(k: int) -> bytes:
    return f"{k:09d}".encode("ascii")

def load_hashes(path: str) -> List[bytes]:
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                out.append(bytes.fromhex(s))
    return out

def iter_dictionary_words(max_words: int = 60000) -> List[str]:
    from wordfreq import top_n_list
    words = top_n_list("en", max_words)
    return [w for w in words if w.isalpha() and 1 <= len(w) <= 24]

def token_variants(word: str):
    # “light capitalization”
    caps = (word.lower(), word.capitalize(), word.upper(), word)
    for c in caps:
        for pre in LEADERS:
            for suf in TRAILERS:
                yield pre + c + suf

def decode_known_tokens(hashes_in_order: List[bytes], key: int) -> Dict[bytes, str]:
    """
    Decode as much as we can using common words. Returns mapping hash->token.
    """
    kb = key9_bytes(key)
    remaining = set(hashes_in_order)
    mapping: Dict[bytes, str] = {}

    words = iter_dictionary_words(60000)
    for w in words:
        for t in token_variants(w):
            h = sha256_digest(kb + t.encode("utf-8"))
            if h in remaining:
                mapping[h] = t
                remaining.remove(h)
                if not remaining:
                    return mapping

    # Add a few non-word tokens
    extras = [",", ".", "!", "?", ":", ";", "\"", "“", "”", "(", ")", "--", "-", "—", "–"]
    for t in extras:
        h = sha256_digest(kb + t.encode("utf-8"))
        if h in remaining:
            mapping[h] = t
            remaining.remove(h)

    # Add the ones you already confirmed
    for t in ["Pólya’s", "5", "disbelievers"]:
        h = sha256_digest(kb + t.encode("utf-8"))
        if h in remaining:
            mapping[h] = t
            remaining.remove(h)

    return mapping

def edits1(word: str) -> Set[str]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {L + R[1:] for L, R in splits if R}
    transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
    replaces = {L + c + R[1:] for L, R in splits if R for c in letters}
    inserts = {L + c + R for L, R in splits for c in letters}
    return deletes | transposes | replaces | inserts

def edits2(word: str) -> Set[str]:
    # Generate edit-distance-2 candidates (still manageable for a single target word)
    e1 = edits1(word)
    out = set()
    for w in e1:
        out |= edits1(w)
        # small cap to avoid blowups; circum* stays reasonable
        if len(out) > 400000:
            break
    return out

def try_match(target_hash: bytes, key: int, candidates: Set[str]) -> str:
    kb = key9_bytes(key)
    for t in candidates:
        h = sha256_digest(kb + t.encode("utf-8"))
        if h == target_hash:
            return t
    return ""

def main():
    if len(sys.argv) < 3:
        print("Usage: python find_unknown_token.py PUZZLE 747585522")
        raise SystemExit(2)

    puzzle_path = sys.argv[1]
    key = int(sys.argv[2])

    hashes = load_hashes(puzzle_path)
    mapping = decode_known_tokens(hashes, key)

    unknown_hashes = [h for h in hashes if h not in mapping]
    print("unknown hashes:", len(unknown_hashes))
    if not unknown_hashes:
        print("Nothing unknown; you already decoded everything.")
        return

    # In your case, should be 1 remaining unknown (the misspelling)
    target = unknown_hashes[0]
    print("target unknown:", target.hex()[:16], "...")

    # We strongly suspect the intended word is "circumstances"
    intended = "circumstances"

    # 1) Try obvious exact/case/punct variants
    base_candidates = set(token_variants(intended))
    t0 = time.time()
    hit = try_match(target, key, base_candidates)
    if hit:
        print("FOUND (variant):", repr(hit))
        print("This token is the misspelled/altered one in the puzzle.")
        return
    print(f"no exact/case/punct hit in {time.time()-t0:.2f}s, trying edit distance 1...")

    # 2) Try edit distance 1 (plus capitalization variants, no punct)
    e1 = edits1(intended)
    e1_candidates = set()
    for w in e1:
        e1_candidates |= set(token_variants(w))
    t0 = time.time()
    hit = try_match(target, key, e1_candidates)
    if hit:
        print("FOUND (edit distance 1):", repr(hit))
        print("Likely intended:", intended)
        return
    print(f"no edit-1 hit in {time.time()-t0:.2f}s, trying edit distance 2 (may take a bit)...")

    # 3) Try edit distance 2 (ONLY for this word)
    e2 = edits2(intended)
    # keep it lighter: don’t do all punctuation; just case variants
    e2_candidates = set()
    for w in e2:
        e2_candidates.add(w)
        e2_candidates.add(w.capitalize())
        e2_candidates.add(w.upper())

    t0 = time.time()
    hit = try_match(target, key, e2_candidates)
    if hit:
        print("FOUND (edit distance 2):", repr(hit))
        print("Likely intended:", intended)
        return

    print("Still no hit. If this happens, the intended token may not be 'circumstances' or may contain unicode/punctuation inside the word.")

if __name__ == "__main__":
    main()