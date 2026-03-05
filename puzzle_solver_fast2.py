#!/usr/bin/env python3
"""
puzzle_solver_ultrafast.py  (Windows-friendly)

Ultrafast HW6 PUZZLE solver:
1) Loads PUZZLE hashes (one SHA256 hex per line).
2) Finds the 9-digit key by scanning the keyspace in parallel, staged by common tokens.
3) Decodes message tokens FAST by:
   - building a candidate-token list once (dictionary words + light cap/punct),
   - hashing each candidate once, checking membership in the PUZZLE hash set,
   - stopping early once all tokens are solved.
4) Finds the misspelled word by:
   - spell-checking decoded tokens vs dictionary set,
   - searching edit-distance-1 neighbors for a likely intended word.

Usage:
  python puzzle_solver_ultrafast.py PUZZLE
  python puzzle_solver_ultrafast.py PUZZLE.txt

Tip (Windows):
  pip install wordfreq
"""

import hashlib
import os
import re
import sys
import time
from multiprocessing import Process, Event, Queue, cpu_count
from typing import Dict, List, Set, Tuple

# -------------------- Tunables --------------------
CHUNK_SIZE = 500_000  # key-space scan chunk per worker

# Staged key search: scan whole keyspace with ONE token at a time (1 hash per key)
TOKEN_STAGES: List[List[str]] = [
    ["the", "The", "the,", "the.", "the:", "the;", "the!", "the?"],
    ["and", "And", "and,", "and."],
    ["of", "Of", "to", "To", "in", "In", "a", "A", "I", "it", "It", "is", "Is", "that", "That"],
    [",", ".", "!", "?", ":", ";", "\"", "'", "--", "-", "—", "–", "(", ")", "[", "]"],
]

# Light punctuation/capitalization differences:
LEADERS = ["", "\"", "'", "“", "‘", "(", "[", "{", "—", "–"]
TRAILERS = ["", ",", ".", "!", "?", ":", ";", "\"", "'", "”", "’", ")", "]", "}", "'s"]

# Candidate generation limits (keep fast + reasonable)
MAX_WORDS = 200_000   # from wordfreq top list
MAX_TOKEN_LEN = 32    # skip longer tokens

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


# -------------------- Key Search (parallel) --------------------

def find_key_worker(start_base: int, step_chunks: int, token_bytes: bytes,
                    hset: Set[bytes], stop: Event, out: Queue):
    """
    Worker scans key ranges [base, base+CHUNK_SIZE), then jumps ahead by step_chunks*CHUNK_SIZE.
    """
    base = start_base
    while not stop.is_set() and base < 1_000_000_000:
        end = min(base + CHUNK_SIZE, 1_000_000_000)
        for k in range(base, end):
            if stop.is_set():
                return
            if sha256_digest(key9_bytes(k) + token_bytes) in hset:
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

    raise RuntimeError("Key not found. Expand TOKEN_STAGES / adjust tokenization assumptions.")


# -------------------- Dictionary / candidates --------------------

def iter_dictionary_words() -> List[str]:
    """
    Windows-friendly word list:
    1) wordfreq top_n_list (recommended): pip install wordfreq
    2) local wordlist file if present
    3) system dictionary (Linux/Mac)
    """
    # 1) wordfreq (best)
    try:
        from wordfreq import top_n_list  # type: ignore
        words = top_n_list("en", MAX_WORDS)
        return [w for w in words if w.isalpha() and 1 <= len(w) <= MAX_TOKEN_LEN]
    except Exception:
        pass

    # 2) local file fallback
    for path in ["words.txt", "wordlist.txt", "words_alpha.txt"]:
        if os.path.exists(path):
            out: List[str] = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if w and w.isalpha() and 1 <= len(w) <= MAX_TOKEN_LEN:
                        out.append(w)
            return out

    # 3) system dict (Linux/Mac)
    for path in ["/usr/share/dict/words", "/usr/dict/words"]:
        if os.path.exists(path):
            out: List[str] = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    w = line.strip()
                    if w and w.isalpha() and 1 <= len(w) <= MAX_TOKEN_LEN:
                        out.append(w)
            return out

    # tiny fallback (won't decode most quotes)
    return ["the", "and", "of", "to", "in", "a", "I", "it", "is", "that"]


def generate_candidate_tokens(words: List[str]) -> List[str]:
    """
    Build candidate tokens ONCE.
    Keep it bounded and skip overly long tokens.
    """
    candidates: List[str] = []

    # Add standalone punctuation tokens too (some puzzles include them as separate tokens)
    punct_tokens = [
        ",", ".", "!", "?", ":", ";", "\"", "'", "--", "-", "—", "–",
        "(", ")", "[", "]", "{", "}"
    ]
    candidates.extend(punct_tokens)

    for w in words:
        if len(w) > MAX_TOKEN_LEN:
            continue
        # “light capitalization”
        caps = (w.lower(), w.capitalize(), w.upper(), w)
        for c in caps:
            # With leading/trailing punctuation
            for pre in LEADERS:
                for suf in TRAILERS:
                    t = pre + c + suf
                    if len(t) <= MAX_TOKEN_LEN + 4:  # allow small punct growth
                        candidates.append(t)

    # Deduplicate while preserving order
    seen = set()
    uniq: List[str] = []
    for t in candidates:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


# -------------------- Decode (ultrafast) --------------------

def decode_message_ultrafast(hashes_in_order: List[bytes], key: int) -> Tuple[List[str], Dict[bytes, str]]:
    """
    Hash each candidate token once, and check membership in the PUZZLE set.
    Stops early once all hashes are solved.
    """
    kb = f"{key:09d}".encode("ascii")
    target_set = set(hashes_in_order)
    remaining = set(hashes_in_order)

    words = iter_dictionary_words()
    candidates = generate_candidate_tokens(words)
    print(f"[decode] dictionary words: {len(words)}")
    print(f"[decode] candidate tokens: {len(candidates)}")

    mapping: Dict[bytes, str] = {}

    t0 = time.time()
    for idx, token in enumerate(candidates, start=1):
        hd = sha256_digest(kb + token.encode("utf-8"))
        if hd in remaining:
            mapping[hd] = token
            remaining.remove(hd)
            if not remaining:
                break
        # tiny progress ping (every ~1M candidates)
        if idx % 1_000_000 == 0:
            dt = time.time() - t0
            print(f"[decode] checked {idx:,} candidates, solved {len(mapping)}/{len(hashes_in_order)} in {dt:.1f}s")

    dt = time.time() - t0
    print(f"[decode] solved {len(mapping)}/{len(hashes_in_order)} hashes in {dt:.2f}s")

    decoded = [mapping.get(h, f"<UNKNOWN:{h.hex()[:8]}>") for h in hashes_in_order]
    return decoded, mapping


# -------------------- Misspelling detection --------------------

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


# -------------------- Main --------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python puzzle_solver_ultrafast.py PUZZLE_OR_PUZZLE.txt")
        sys.exit(2)

    puzzle_path = sys.argv[1]
    hashes_in_order = load_hashes(puzzle_path)
    hset = set(hashes_in_order)

    print(f"[load] {len(hashes_in_order)} hashes loaded from {puzzle_path}")

    t_all0 = time.time()

    # 1) find key
    t0 = time.time()
    key = find_key_staged(hset)
    t1 = time.time()

    # 2) decode fast
    decoded_tokens, mapping = decode_message_ultrafast(hashes_in_order, key)
    msg = " ".join(decoded_tokens)

    # 3) misspelling
    dict_words = set(w.lower() for w in iter_dictionary_words())
    misspell, intended = find_misspelling(decoded_tokens, dict_words)

    unknown_count = sum(1 for t in decoded_tokens if t.startswith("<UNKNOWN:"))
    t_all1 = time.time()

    print("\n[decoded]\n")
    print(msg)

    print("\n[result]")
    print("puzzle_key =", key)
    print("unknown_tokens =", unknown_count, "/", len(decoded_tokens))
    print("puzzle_misspell =", repr(misspell))
    if intended:
        print("likely intended =", repr(intended))

    print("\n[timing]")
    print(f"keysearch: {t1 - t0:.2f}s")
    print(f"total:    {t_all1 - t_all0:.2f}s")

    # Write output file for easy copy/paste into puzzle.py and hw6-puzzlesolution.txt
    with open("puzzle_solution_out.txt", "w", encoding="utf-8") as f:
        f.write(f"puzzle_key={key:09d}\n")
        f.write(f"puzzle_misspell={misspell}\n")
        f.write(f"likely_intended={intended}\n")
        f.write(f"unknown_tokens={unknown_count}\n")
        f.write("message=" + msg + "\n")

    # Also print suggested snippet for your required puzzle.py
    print("\n[puzzle.py snippet]")
    print(f'puzzle_key = {key}')
    print(f'puzzle_misspell = "{misspell}"')


if __name__ == "__main__":
    main()