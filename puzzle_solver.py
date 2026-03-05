#!/usr/bin/env python3
import hashlib
import itertools
import os
import re
import sys
import time
from multiprocessing import Process, Event, Queue, cpu_count
from typing import Dict, List, Set, Tuple

PUZZLE_PATH = "PUZZLE"  # rename/copy your provided PUZZLE file to this, or change path here

COMMON_TOKENS = [
    "the", "The", "the,", "the.", "and", "And", "and,", "of", "to", "in", "a", "I", "it", "is", "that",
    ":", ";", ",", ".", "!", "?", "\"", "'", "--", "-"
]

PUNCT_SUFFIXES = ["", ",", ".", "!", "?", ":", ";", "\"", "'", "'s"]
CAP_VARIANTS = lambda w: {w, w.lower(), w.capitalize()}

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def load_puzzle_hashes(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def key_bytes(k: int) -> bytes:
    return f"{k:09d}".encode("utf-8")

def find_key_worker(start_k: int, step: int, hashes_set: Set[str], stop: Event, out: Queue):
    # Iterate keys: start_k, start_k+step, ...
    k = start_k
    while not stop.is_set() and k < 1_000_000_000:
        kb = key_bytes(k)
        for tok in COMMON_TOKENS:
            h = sha256_hex(kb + tok.encode("utf-8"))
            if h in hashes_set:
                out.put((k, tok, h))
                stop.set()
                return
        k += step

def find_key_parallel(hashes_set: Set[str]) -> Tuple[int, str, str]:
    stop = Event()
    out = Queue()
    procs = []
    nproc = cpu_count()

    for i in range(nproc):
        p = Process(target=find_key_worker, args=(i, nproc, hashes_set, stop, out), daemon=True)
        p.start()
        procs.append(p)

    k, tok, h = out.get()
    for p in procs:
        p.terminate()
    return k, tok, h

def iter_dictionary_words() -> List[str]:
    # Prefer system dictionary if available
    candidates = []
    for path in ["/usr/share/dict/words", "/usr/dict/words"]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if w and w.isalpha() and 1 <= len(w) <= 20:
                        candidates.append(w)
            break
    # Fallback: minimal list if no system dictionary
    if not candidates:
        candidates = ["the", "and", "to", "of", "in", "a", "I", "it", "is", "that"]
    return candidates

def token_variants(word: str) -> Set[str]:
    out = set()
    for cap in CAP_VARIANTS(word):
        for suf in PUNCT_SUFFIXES:
            out.add(cap + suf)
    return out

def decode_message(hashes_in_order: List[str], key: int) -> List[str]:
    remaining = set(hashes_in_order)
    mapping: Dict[str, str] = {}

    kb = key_bytes(key)

    # First pass: dictionary words (with light cap/punct variants)
    words = iter_dictionary_words()
    for w in words:
        for t in token_variants(w):
            h = sha256_hex(kb + t.encode("utf-8"))
            if h in remaining:
                mapping[h] = t
                remaining.remove(h)
        if not remaining:
            break

    # If anything still left, try some extra “small tokens” often in quotes
    extras = ["—", "–", "(", ")", "[", "]"]
    for t in extras:
        h = sha256_hex(kb + t.encode("utf-8"))
        if h in remaining:
            mapping[h] = t
            remaining.remove(h)

    # Produce message tokens in the original order
    decoded = [mapping.get(h, f"<UNKNOWN:{h[:8]}>") for h in hashes_in_order]
    return decoded

def edits1(word: str) -> Set[str]:
    # edit distance 1: insert, delete, replace, transpose
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {L + R[1:] for L, R in splits if R}
    transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
    replaces = {L + c + R[1:] for L, R in splits if R for c in letters}
    inserts = {L + c + R for L, R in splits for c in letters}
    return deletes | transposes | replaces | inserts

def find_misspelling(tokens: List[str]) -> Tuple[str, str]:
    # load dictionary set for spell-check
    dict_words = set(w.lower() for w in iter_dictionary_words())
    # strip punctuation for checking, but return original token
    for tok in tokens:
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", tok)
        if not core:
            continue
        lc = core.lower()
        if lc in dict_words:
            continue
        # try to find a likely intended word at edit distance 1
        for cand in edits1(lc):
            if cand in dict_words:
                return tok, cand
    return "", ""

def main():
    hashes_in_order = load_puzzle_hashes(PUZZLE_PATH)
    hashes_set = set(hashes_in_order)

    print(f"Loaded {len(hashes_in_order)} hashes from {PUZZLE_PATH}")

    t0 = time.time()
    key, tok, h = find_key_parallel(hashes_set)
    t1 = time.time()
    print(f"FOUND KEY: {key:09d} (matched token '{tok}' -> {h}) in {t1-t0:.2f}s")

    decoded_tokens = decode_message(hashes_in_order, key)
    message = " ".join(decoded_tokens)
    print("\nDECODED (best effort):\n")
    print(message)

    misspell, intended = find_misspelling(decoded_tokens)
    if misspell:
        print(f"\nMISSPELLING FOUND: '{misspell}' (likely intended '{intended}')")
    else:
        print("\nNo misspelling detected with current dictionary; expand word sources/variants.")

    # write required outputs for your repo
    with open("puzzle_solution_out.txt", "w", encoding="utf-8") as f:
        f.write(f"puzzle_key={key:09d}\n")
        f.write(f"message={message}\n")
        f.write(f"misspell={misspell}\n")
        f.write(f"intended={intended}\n")

if __name__ == "__main__":
    main()