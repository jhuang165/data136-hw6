#!/usr/bin/env python3
import hashlib, os, re, sys, time
from typing import List, Set, Dict, Tuple

KEY = 747585522  # <-- already found

LEADERS = ["", "\"", "“", "("]
TRAILERS = ["", ",", ".", "!", "?", "\"", "”", ")", "'s"]

MAX_WORDS = 60000
MAX_TOKEN_LEN = 32

def sha256_digest(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

def load_hashes(path: str) -> List[bytes]:
    hs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s:
                hs.append(bytes.fromhex(s))
    return hs

def iter_dictionary_words() -> List[str]:
    from wordfreq import top_n_list
    words = top_n_list("en", MAX_WORDS)
    return [w for w in words if w.isalpha() and 1 <= len(w) <= MAX_TOKEN_LEN]

def token_variants(word: str):
    caps = (word.lower(), word.capitalize())
    for c in caps:
        for pre in LEADERS:
            for suf in TRAILERS:
                yield pre + c + suf

def decode(hashes_in_order: List[bytes], key: int) -> List[str]:
    kb = f"{key:09d}".encode("ascii")
    remaining = set(hashes_in_order)
    mapping: Dict[bytes, str] = {}

    words = iter_dictionary_words()
    print("[decode] words:", len(words))

    t0 = time.time()
    checked = 0

    # Try words first
    for w in words:
        for t in token_variants(w):
            hd = sha256_digest(kb + t.encode("utf-8"))
            checked += 1
            if hd in remaining:
                mapping[hd] = t
                remaining.remove(hd)
                if not remaining:
                    break
        if not remaining:
            break

    # Common standalone punctuation
    extras = [",", ".", "!", "?", ":", ";", "\"", "“", "”", "(", ")", "--", "-", "—", "–"]
    for t in extras:
        hd = sha256_digest(kb + t.encode("utf-8"))
        if hd in remaining:
            mapping[hd] = t
            remaining.remove(hd)

    dt = time.time() - t0
    print(f"[decode] checked ~{checked:,} candidates, solved {len(mapping)}/{len(hashes_in_order)} in {dt:.2f}s")

    return [mapping.get(h, f"<UNKNOWN:{h.hex()[:8]}>") for h in hashes_in_order]

def edits1(word: str) -> Set[str]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {L + R[1:] for L, R in splits if R}
    transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
    replaces = {L + c + R[1:] for L, R in splits if R for c in letters}
    inserts = {L + c + R for L, R in splits for c in letters}
    return deletes | transposes | replaces | inserts

def find_misspelling(tokens: List[str], dict_words: Set[str]) -> Tuple[str, str]:
    for tok in tokens:
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", tok)
        if not core:
            continue
        lc = core.lower()
        if lc in dict_words:
            continue
        for cand in edits1(lc):
            if cand in dict_words:
                return tok, cand
    return "", ""

def main():
    if len(sys.argv) < 2:
        print("Usage: python decode_only.py PUZZLE")
        raise SystemExit(2)

    puzzle_path = sys.argv[1]
    hashes = load_hashes(puzzle_path)

    decoded = decode(hashes, KEY)
    msg = " ".join(decoded)
    print("\n[decoded]\n")
    print(msg)

    # spell check
    dict_words = set(w.lower() for w in iter_dictionary_words())
    misspell, intended = find_misspelling(decoded, dict_words)

    unknown = sum(1 for t in decoded if t.startswith("<UNKNOWN:"))
    print("\n[result]")
    print("puzzle_key =", KEY)
    print("unknown_tokens =", unknown, "/", len(decoded))
    print("puzzle_misspell =", repr(misspell))
    if intended:
        print("likely intended =", repr(intended))

    with open("puzzle_solution_out.txt", "w", encoding="utf-8") as f:
        f.write(f"puzzle_key={KEY:09d}\n")
        f.write(f"puzzle_misspell={misspell}\n")
        f.write(f"likely_intended={intended}\n")
        f.write(f"unknown_tokens={unknown}\n")
        f.write("message=" + msg + "\n")

if __name__ == "__main__":
    main()