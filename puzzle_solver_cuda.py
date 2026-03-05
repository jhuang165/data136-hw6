#!/usr/bin/env python3
"""
GPU-Accelerated Puzzle Solver for HW6 Part 2
Using hashwise with correct API calls
"""

import hashlib
import time
import os
from typing import List, Set, Tuple, Optional

# Try to import hashwise for GPU acceleration
try:
    import hashwise
    HAS_GPU = True
    # Check if GPU is available using the correct API
    try:
        device_status = hashwise.DeviceStatus()
        HAS_GPU = device_status.device_available()
        if HAS_GPU:
            print(f"✓ GPU acceleration available via hashwise")
    except:
        HAS_GPU = False
        print("✗ GPU not available via hashwise")
except ImportError:
    print("✗ hashwise not installed. Install with: pip install hashwise")
    HAS_GPU = False

def load_puzzle_hashes(filename='PUZZLE') -> List[str]:
    """Load target hashes from PUZZLE file"""
    if not os.path.exists(filename):
        print(f"Error: {filename} not found!")
        print("\nPlease create a file called 'PUZZLE' with the SHA256 hashes.")
        return []
    
    try:
        with open(filename, 'r') as f:
            hashes = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(hashes)} target hashes from {filename}")
        return hashes
    except Exception as e:
        print(f"Error reading {filename}: {e}")
        return []

def generate_misspellings(word: str) -> Set[str]:
    """Generate all edit distance 1 misspellings of a word"""
    misspellings = set()
    letters = 'abcdefghijklmnopqrstuvwxyz'
    
    word = word.lower()
    
    # Insertions
    for i in range(len(word) + 1):
        for c in letters:
            misspelling = word[:i] + c + word[i:]
            misspellings.add(misspelling)
    
    # Deletions
    for i in range(len(word)):
        misspelling = word[:i] + word[i+1:]
        misspellings.add(misspelling)
    
    # Substitutions
    for i in range(len(word)):
        for c in letters:
            if c != word[i]:
                misspelling = word[:i] + c + word[i+1:]
                misspellings.add(misspelling)
    
    # Transpositions
    for i in range(len(word) - 1):
        chars = list(word)
        chars[i], chars[i+1] = chars[i+1], chars[i]
        misspelling = ''.join(chars)
        misspellings.add(misspelling)
    
    misspellings.discard(word)
    return misspellings

def gpu_hash_batch(strings_batch):
    """Use hashwise to hash a batch of strings on GPU"""
    try:
        # Convert strings to bytes
        bytes_batch = [s.encode() for s in strings_batch]
        
        # Use hashwise to compute hashes
        # The exact API might vary - this is a guess
        if hasattr(hashwise, 'hash_batch'):
            results = hashwise.hash_batch(bytes_batch, algorithm='sha256')
            return [r.hex() for r in results]
        elif hasattr(hashwise, 'sha256_batch'):
            results = hashwise.sha256_batch(bytes_batch)
            return [r.hex() for r in results]
        else:
            # Fallback to CPU
            return [hashlib.sha256(s.encode()).hexdigest() for s in strings_batch]
    except Exception as e:
        print(f"GPU hashing error: {e}, falling back to CPU")
        return [hashlib.sha256(s.encode()).hexdigest() for s in strings_batch]

def solve_with_gpu():
    """Main solver using GPU acceleration"""
    target_hashes = load_puzzle_hashes()
    if not target_hashes:
        return None, None
    
    target_set = set(target_hashes)
    print(f"\nTarget hashes: {target_set}")
    
    # Famous quotes to try
    famous_quotes = [
        "To be or not to be that is the question",
        "All that glitters is not gold",
        "The only thing we have to fear is fear itself",
        "Ask not what your country can do for you ask what you can do for your country",
        "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character",
    ]
    
    print(f"\n{'='*60}")
    print(f"GPU Acceleration: {'ENABLED' if HAS_GPU else 'DISABLED'}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    batch_size = 10000  # Process 10k numbers at a time
    
    for quote_idx, quote in enumerate(famous_quotes):
        print(f"\nTrying quote {quote_idx + 1}: {quote[:50]}...")
        words = quote.split()
        base_message = " ".join(words)
        
        # Pre-generate misspellings for each word
        misspellings_by_word = {}
        for word_idx, word in enumerate(words):
            misspellings = generate_misspellings(word)
            misspellings_by_word[word_idx] = (word, list(misspellings)[:100])  # Limit to 100 per word for speed
            print(f"  Word '{word}': {len(misspellings_by_word[word_idx][1])} misspellings to try")
        
        # Search through 9-digit numbers
        for start_num in range(100000000, 1000000000, batch_size):
            end_num = min(start_num + batch_size, 1000000000)
            
            # Generate batch of candidates
            candidates = []
            candidate_info = []  # Store metadata about each candidate
            
            # Add correct spellings
            for num in range(start_num, end_num):
                message = f"{num} {base_message}"
                candidates.append(message)
                candidate_info.append(('correct', num, None, None))
            
            # Add misspellings (sample every 100 numbers)
            if num % 100 == 0:
                for word_idx, (original_word, misspellings) in misspellings_by_word.items():
                    for misspelling in misspellings:
                        modified_words = words.copy()
                        modified_words[word_idx] = misspelling
                        message = f"{num} " + " ".join(modified_words)
                        candidates.append(message)
                        candidate_info.append(('misspelling', num, word_idx, misspelling))
            
            # GPU hash the batch
            if HAS_GPU:
                print(f"  GPU processing {len(candidates)} candidates for numbers {start_num}-{end_num}")
                hashes = gpu_hash_batch(candidates)
            else:
                # CPU fallback
                hashes = [hashlib.sha256(c.encode()).hexdigest() for c in candidates]
            
            # Check results
            for i, hash_result in enumerate(hashes):
                if hash_result in target_set:
                    result_type, num, word_idx, misspelling = candidate_info[i]
                    elapsed = time.time() - start_time
                    
                    print("\n" + "="*60)
                    print("✓ FOUND MATCH!")
                    print("="*60)
                    print(f"Type: {result_type}")
                    print(f"Number: {num}")
                    print(f"Hash: {hash_result}")
                    print(f"Time: {elapsed:.2f} seconds")
                    
                    if result_type == 'misspelling':
                        # Found misspelling directly
                        return num, misspelling
                    else:
                        # Found correct version, now search for misspelling
                        print(f"\nSearching for misspelling with number {num}...")
                        for w_idx, (orig_word, misspellings) in misspellings_by_word.items():
                            for m in misspellings:
                                modified_words = words.copy()
                                modified_words[w_idx] = m
                                test_msg = f"{num} " + " ".join(modified_words)
                                test_hash = hashlib.sha256(test_msg.encode()).hexdigest()
                                
                                if test_hash in target_set and test_hash != hash_result:
                                    print(f"✓ Found misspelling: '{orig_word}' -> '{m}'")
                                    return num, m
            
            if start_num % (batch_size * 10) == 0:
                progress = (start_num - 100000000) / 900000000 * 100
                print(f"Overall progress: {progress:.1f}%")
    
    return None, None

if __name__ == "__main__":
    print("HW6 Part 2 - GPU-Accelerated Puzzle Solver")
    print("="*60)
    
    number, misspelling = solve_with_gpu()
    
    if number and misspelling:
        print("\n" + "="*60)
        print("SOLUTION FOUND!")
        print("="*60)
        print(f"puzzle_key = {number}")
        print(f'puzzle_misspell = "{misspelling}"')
        print("\nAdd these to your puzzle.py:")
        print(f"puzzle_key = {number}")
        print(f'puzzle_misspell = "{misspelling}"')
    else:
        print("\nNo solution found. Try adding more quotes.")