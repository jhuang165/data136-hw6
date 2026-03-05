import hashlib, sys
from typing import List, Set

KEY = 747585522  # you already found this

# These are the 4 tokens your decode missed, from the real quote:
CANDIDATES = [
    "Pólya’s",      # curly apostrophe + accent
    "Pólya's",      # straight apostrophe
    "Polya's",      # ASCII fallback
    "5",
    "disbelievers",
    "circumstances",
]

def sha256_hex(s: str) -> str:
    kb = f"{KEY:09d}".encode("utf-8")
    return hashlib.sha256(kb + s.encode("utf-8")).hexdigest()

def load_hashes(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]

def edits1(word: str) -> Set[str]:
    letters = "abcdefghijklmnopqrstuvwxyz"
    splits = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes = {L + R[1:] for L, R in splits if R}
    transposes = {L + R[1] + R[0] + R[2:] for L, R in splits if len(R) > 1}
    replaces = {L + c + R[1:] for L, R in splits if R for c in letters}
    inserts = {L + c + R for L, R in splits for c in letters}
    return deletes | transposes | replaces | inserts

def main():
    puzzle_path = sys.argv[1] if len(sys.argv) > 1 else "PUZZLE"
    hashes = load_hashes(puzzle_path)
    hset = set(hashes)

    # We know most words already from your output; find which hashes remain unresolved by matching known text.
    # Easiest approach: just try candidates (and then misspellings) against the hash set.
    print("Trying correct candidates against PUZZLE hashes...")
    hits = {}
    for t in CANDIDATES:
        h = sha256_hex(t)
        if h in hset:
            hits[t] = h
            print("  HIT:", repr(t), "->", h[:16], "...")

    print("\nIf any of the 4 true tokens are misspelled in the puzzle, we will find the misspelling by edit distance 1.")
    # For each likely token, if the correct spelling doesn't hit, try edits1.
    suspects = ["Pólya’s", "Pólya's", "Polya's", "disbelievers", "circumstances"]
    found_misspell = None
    found_intended = None

    for intended in suspects:
        # If intended already hits, it is not the misspelling token (or the puzzle used a different apostrophe)
        if sha256_hex(intended) in hset:
            continue

        # Only generate edits on alphabetic-ish tokens (skip Polya variants with punctuation weirdness if you want)
        core = intended
        # generate edits on a simplified core (strip fancy apostrophes for edits, then re-add)
        # We'll just do edits on lowercase letters for words:
        if core.lower().isalpha():
            base = core.lower()
            for m in edits1(base):
                h = sha256_hex(m)
                if h in hset:
                    found_misspell = m
                    found_intended = intended
                    break
        else:
            # for Polya token, try a few common apostrophe/diacritic variants (already in CANDIDATES)
            pass

        if found_misspell:
            break

    print("\nRESULTS")
    print("puzzle_key =", KEY)
    if found_misspell:
        print("puzzle_misspell =", repr(found_misspell))
        print("likely intended =", repr(found_intended))
    else:
        print("No edit-distance-1 misspelling found among the main suspects.")
        print("If needed, we can expand misspelling search to all decoded words once your decoder outputs them.")

if __name__ == "__main__":
    main()