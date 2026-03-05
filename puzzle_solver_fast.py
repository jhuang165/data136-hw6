#!/usr/bin/env python3
"""
puzzle_solver_fast.py

Fast HW6 PUZZLE solver that works well on Windows.

What it does:
1) Loads SHA256 hashes from PUZZLE file (one hex digest per line).
2) Finds the 9-digit key by scanning the keyspace in parallel, staged by very common tokens.
3) Decodes the message by matching each hash against sha256(key + token_variant) for a large
   English word list (uses wordfreq on Windows if available).
4) Finds the misspelled word by looking for a token not in dictionary but within edit distance 1.

Usage:
  python puzzle_solver_fast.py PUZZLE
  python puzzle_solver_fast.py PUZZLE.txt
"""

import hashlib
import os
import re
import sys
import time
from multiprocessing import Process, Event, Queue, cpu_count
from typing import Dict, List, Set, Tuple

# -------------------- Tunables --------------------
# Chunking reduces Python overhead. Bigger = faster but less responsive.
CHUNK_SIZE = 250_000  # keys per chunk per worker

# Stage tokens: scan whole keyspace with ONE token at a time (1 hash per key).
# Very often 'the'/'The' hits and you find the key quickly.
TOKEN_STAGES: List[List[str]] = [
    ["the", "The", "the,", "the.", "the:", "the;", "the!", "the?"],
    ["and", "And", "and,", "and."],
    ["of", "Of", "to", "To", "in", "In", "a", "A", "I", "it", "It", "is", "Is", "that", "That"],
    [",", ".", "!", "?", ":", ";", "\"", "'", "--", "-", "—", "–", "(", ")", "[", "]"],
]

# “Light capitalization and punctuation differences”:
# Include BOTH leading and trailing punctuation.
LEADERS = ["", "\"", "'", "“", "‘", "(", "[", "{", "—", "–"]
TRAILERS = ["", ",", ".", "!", "?", ":", ";", "\"", "'", "”", "’", ")", "]", "}", "'s"]

# --------------------------------------------------


def sha256_digest(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def load_hashes(path: str) -> List[bytes]:
    hs: List[bytes] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            hs.append(bytes.fromhex(s))
    return hs


def key9_bytes(k: int) -> bytes:
    return f"{k:09d}".encode("ascii")


def find_key_worker(start_base: int, step_chunks: int, token_bytes: bytes, hset: Set[bytes], stop: Event, out: Queue):
    """
    Each worker checks ranges [base, base+CHUNK_SIZE), then jumps ahead by step_chunks*CHUNK_SIZE.
    """
    base = start_base
    while not stop.is_set() and base < 1_000_000_000:
        end = min(base + CHUNK_SIZE, 1_000_000_000)
        for k in range(base, end):
            if stop.is_set():
                return
            kb = key9_bytes(k)
            if sha256_digest(kb + token_bytes) in hset:
                out.put(k)
                stop.set()
                return
        base += step_chunks * CHUNK_SIZE


def find_key_staged(hset: Set[bytes]) -> int:
    nproc = cpu_count()
    print(f"[keysearch] using {nproc} processes")

    for stage_idx, tokens in enumerate(TOKEN_STAGES, start=1):
        for tok in tokens:
            tok_b = tok.encode("utf-8")
            stop = Event()
            out = Queue()
            procs: List[Process] = []

            t0 = time.time()

            # Stagger workers by CHUNK_SIZE blocks
            for wid in range(nproc):
                start_base = wid * CHUNK_SIZE
                p = Process(
                    target=find_key_worker,
                    args=(start_base, nproc, tok_b, hset, stop, out),
                    daemon=True,
                )
                p.start()
                procs.append(p)

            found_key = None

            # Poll for completion/found
            try:
                found_key = out.get(timeout=0.5)
            except Exception:
                while any(p.is_alive() for p in procs) and not stop.is_set():
                    try:
                        found_key = out.get(timeout=0.5)
                        break
                    except Exception:
                        pass

            for p in procs:
                p.terminate()

            dt = time.time() - t0
            if found_key is not None:
                print(f"[keysearch] FOUND key={found_key:09d} via token='{tok}' (stage {stage_idx}) in {dt:.2f}s")
                return found_key
            else:
                print(f"[keysearch] token='{tok}' stage {stage_idx} no-hit after {dt:.2f}s")

    raise RuntimeError("Key not found with staged tokens. Expand TOKEN_STAGES / adjust tokenization assumptions.")


def iter_dictionary_words() -> List[str]:
    """
    Windows-friendly dictionary loader.

    Priority:
    1) wordfreq (pip install wordfreq) -> top English words
    2) local file words.txt / wordlist.txt / words_alpha.txt if present
    3) Unix system dictionaries (if running on Linux/Mac)
    4) tiny fallback (won't decode a real quote)
    """
    # 1) wordfreq (best on Windows)
    try:
        from wordfreq import top_n_list  # type: ignore
        words = top_n_list("en", 200000)
        return [w for w in words if w.isalpha() and 1 <= len(w) <= 24]
    except Exception:
        pass

    # 2) local wordlist files
    for path in ["words.txt", "wordlist.txt", "words_alpha.txt"]:
        if os.path.exists(path):
            out: List[str] = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if w and w.isalpha() and 1 <= len(w) <= 24:
                        out.append(w)
            return out

    # 3) system dicts (Linux/Mac)
    for path in ["/usr/share/dict/words", "/usr/dict/words"]:
        if os.path.exists(path):
            out: List[str] = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if w and w.isalpha() and 1 <= len(w) <= 24:
                        out.append(w)
            return out

    # 4) tiny fallback
    return ["the", "and", "of", "to", "in", "a", "I", "it", "is", "that"]


def token_variants(word: str) -> Set[str]:
    """
    Generate variants with light capitalization and punctuation differences.
    Includes leading punctuation and trailing punctuation.
    """
    caps = {word.lower(), word.capitalize(), word.upper(), word}
    out: Set[str] = set()
    for c in caps:
        for pre in LEADERS:
            for suf in TRAILERS:
                out.add(pre + c + suf)
    return out


def decode_message(hashes_in_order, key):
    import hashlib

    hashes_set = set(hashes_in_order)
    solved = {}

    kb = f"{key:09d}".encode()

    words = iter_dictionary_words()

    # Generate candidate tokens once
    candidates = []

    for w in words:
        caps = [w.lower(), w.capitalize(), w]
        for c in caps:
            for pre in LEADERS:
                for suf in TRAILERS:
                    candidates.append(pre + c + suf)

    print("candidate tokens:", len(candidates))

    # Hash candidates once and check
    for token in candidates:
        h = hashlib.sha256(kb + token.encode()).digest()
        if h in hashes_set:
            solved[h] = token
            if len(solved) == len(hashes_in_order):
                break

    decoded = [solved.get(h, "<UNKNOWN>") for h in hashes_in_order]

    return decoded


def edits1(word: str) -> Set[str]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {L + R[1:] for L, R in splits if R}
    transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
    replaces = {L + c + R[1:] for L, R in splits if R for c in letters}
    inserts = {L + c + R for L, R in splits for c in letters}
    return deletes | transposes | replaces | inserts


def find_misspelling(tokens: List[str]) -> Tuple[str, str]:
    dict_words = set(w.lower() for w in iter_dictionary_words())

    for tok in tokens:
        # Remove leading/trailing non-letters for spell check
        core = re.sub(r"^[^A-Za-z]+|[^A-Za-z]+$", "", tok)
        if not core:
            continue
        lc = core.lower()
        if lc in dict_words:
            continue
        # Try edit distance 1 neighbors
        for cand in edits1(lc):
            if cand in dict_words:
                return tok, cand
    return "", ""


def main():
    if len(sys.argv) < 2:
        print("Usage: python puzzle_solver_fast.py PUZZLE_OR_PUZZLE.txt")
        sys.exit(2)

    puzzle_path = sys.argv[1]
    hashes_in_order = load_hashes(puzzle_path)
    hset = set(hashes_in_order)

    print(f"[load] {len(hashes_in_order)} hashes loaded from {puzzle_path}")

    t0 = time.time()
    key = find_key_staged(hset)
    t1 = time.time()

    decoded_tokens = decode_message(hashes_in_order, key)
    msg = " ".join(decoded_tokens)

    misspell, intended = find_misspelling(decoded_tokens)

    unknown_count = sum(1 for t in decoded_tokens if t.startswith("<UNKNOWN:"))
    print("\n[decoded]\n")
    print(msg)
    print("\n[result]")
    print("puzzle_key =", key)
    print("unknown_tokens =", unknown_count, "/", len(decoded_tokens))
    print("puzzle_misspell =", repr(misspell))
    if intended:
        print("likely intended =", repr(intended))

    print(f"\n[timing] keysearch {(t1 - t0):.2f}s (decode+spellcheck included after)")

    # Write helper output file for copy/paste into your submission
    with open("puzzle_solution_out.txt", "w", encoding="utf-8") as f:
        f.write(f"puzzle_key={key:09d}\n")
        f.write(f"puzzle_misspell={misspell}\n")
        f.write(f"likely_intended={intended}\n")
        f.write(f"unknown_tokens={unknown_count}\n")
        f.write("message=" + msg + "\n")


if __name__ == "__main__":
    main()