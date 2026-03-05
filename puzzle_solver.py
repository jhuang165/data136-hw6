#!/usr/bin/env python3
"""
Puzzle Solver for HW6 Part 2
Find 9-digit number and misspelled word that produce the given SHA256 hashes
"""

import hashlib
import itertools
import time
from typing import List, Set, Tuple, Optional
from multiprocessing import Pool, cpu_count

def load_puzzle_hashes(filename='PUZZLE') -> List[str]:
    """Load target hashes from PUZZLE file"""
    try:
        with open(filename, 'r') as f:
            hashes = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(hashes)} target hashes from {filename}")
        return hashes
    except FileNotFoundError:
        print(f"Error: {filename} not found!")
        return []

def generate_misspellings(word: str) -> Set[str]:
    """
    Generate all edit distance 1 misspellings of a word
    
    Includes:
    - Insertions (add one letter)
    - Deletions (remove one letter)
    - Substitutions (change one letter)
    - Transpositions (swap adjacent letters)
    """
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
    
    # Remove the original word
    misspellings.discard(word)
    
    return misspellings

def generate_word_variations(word: str) -> Set[str]:
    """Generate variations with capitalization and punctuation"""
    variations = set()
    
    # Capitalization variations
    variations.add(word)
    variations.add(word.lower())
    variations.add(word.upper())
    variations.add(word.capitalize())
    variations.add(word.title())
    
    # Common punctuation
    for punct in ['', '.', ',', '!', '?', ';', ':', '-', '--', '...']:
        variations.add(word + punct)
        variations.add(punct + word)
    
    return variations

def try_number_range(args):
    """Try a range of numbers (for multiprocessing)"""
    start_num, end_num, quote_words, target_hashes_set = args
    
    results = []
    target_set = set(target_hashes_set)
    
    for number in range(start_num, end_num):
        if number % 100000 == 0:
            print(f"Progress: {start_num}-{end_num} at {number}")
        
        # Try with correct spelling
        message = f"{number} " + " ".join(quote_words)
        hash_result = hashlib.sha256(message.encode()).hexdigest()
        
        if hash_result in target_set:
            results.append(('correct', number, None, None, hash_result))
            continue
        
        # Try with misspellings
        for word_idx, word in enumerate(quote_words):
            misspellings = generate_misspellings(word)
            
            for misspelling in misspellings:
                modified_words = quote_words.copy()
                modified_words[word_idx] = misspelling
                test_message = f"{number} " + " ".join(modified_words)
                test_hash = hashlib.sha256(test_message.encode()).hexdigest()
                
                if test_hash in target_set:
                    results.append(('misspelling', number, word_idx, misspelling, test_hash))
    
    return results

def solve_puzzle():
    """Main puzzle solver"""
    target_hashes = load_puzzle_hashes()
    if not target_hashes:
        return
    
    # Famous quotes to try
    # TODO: Add more quotes until you find the right one
    famous_quotes = [
        "To be or not to be that is the question",
        "All that glitters is not gold",
        "The only thing we have to fear is fear itself",
        "Ask not what your country can do for you ask what you can do for your country",
        "I have a dream that my four little children will one day live in a nation where they will not be judged by the color of their skin but by the content of their character",
        "The best and most beautiful things in the world cannot be seen or even touched they must be felt with the heart",
        # Add more quotes here
    ]
    
    print("Starting puzzle solver...")
    print(f"Target hashes: {target_hashes}")
    
    for quote_idx, quote in enumerate(famous_quotes):
        print(f"\nTrying quote {quote_idx + 1}: {quote[:50]}...")
        words = quote.split()
        
        # Try all 9-digit numbers (100,000,000 to 999,999,999)
        # Split into ranges for multiprocessing
        num_ranges = []
        range_size = 10000000  # 10 million numbers per process
        for start in range(100000000, 1000000000, range_size):
            end = min(start + range_size, 1000000000)
            num_ranges.append((start, end, words, target_hashes))
        
        # Use multiprocessing to speed up the search
        with Pool(processes=cpu_count()) as pool:
            results = pool.map(try_number_range, num_ranges)
            
            # Flatten results
            for result_batch in results:
                for result in result_batch:
                    result_type, number, word_idx, misspelling, hash_val = result
                    
                    if result_type == 'correct':
                        print("\n" + "=" * 50)
                        print(f"FOUND CORRECT QUOTE!")
                        print(f"Number: {number}")
                        print(f"Quote: {quote}")
                        print(f"Hash: {hash_val}")
                        print("=" * 50)
                        
                        # Now search for misspelling
                        print("\nSearching for misspelled version...")
                        for w_idx, w in enumerate(words):
                            misspellings = generate_misspellings(w)
                            for m in misspellings:
                                modified = words.copy()
                                modified[w_idx] = m
                                test_msg = f"{number} " + " ".join(modified)
                                test_h = hashlib.sha256(test_msg.encode()).hexdigest()
                                
                                if test_h in target_hashes and test_h != hash_val:
                                    print(f"\nFOUND MISSPELLING!")
                                    print(f"Original word: '{w}'")
                                    print(f"Misspelled as: '{m}'")
                                    print(f"Full message: {test_msg}")
                                    print(f"Hash: {test_h}")
                                    return number, m
                    
                    elif result_type == 'misspelling':
                        print("\n" + "=" * 50)
                        print(f"FOUND MISSPELLING FIRST!")
                        print(f"Number: {number}")
                        print(f"Original word: '{words[word_idx]}'")
                        print(f"Misspelled as: '{misspelling}'")
                        print(f"Quote: {quote}")
                        print(f"Hash: {hash_val}")
                        print("=" * 50)
                        return number, misspelling
    
    return None, None

def verify_solution(number: int, misspelled_word: str):
    """Verify that the found solution is correct"""
    target_hashes = load_puzzle_hashes()
    
    # TODO: Add the correct quote here once you find it
    quote = "To be or not to be that is the question"  # Replace with actual quote
    
    # Generate all variations to verify
    words = quote.split()
    found_hashes = []
    
    # Correct version
    correct_msg = f"{number} " + " ".join(words)
    correct_hash = hashlib.sha256(correct_msg.encode()).hexdigest()
    found_hashes.append(correct_hash)
    
    # Misspelled version
    for i, word in enumerate(words):
        if word.lower() == misspelled_word.lower():
            modified = words.copy()
            modified[i] = misspelled_word
            misspelled_msg = f"{number} " + " ".join(modified)
            misspelled_hash = hashlib.sha256(misspelled_msg.encode()).hexdigest()
            found_hashes.append(misspelled_hash)
            break
    
    print("\nVerification:")
    print(f"Number: {number}")
    print(f"Misspelled word: {misspelled_word}")
    print(f"Found hashes: {found_hashes}")
    print(f"Target hashes: {target_hashes}")
    print(f"All hashes match: {set(found_hashes) == set(target_hashes)}")

if __name__ == "__main__":
    print("HW6 Part 2 - Puzzle Solver")
    print("=" * 50)
    
    # Run the solver
    number, misspelling = solve_puzzle()
    
    if number and misspelling:
        print("\n" + "=" * 50)
        print("SOLUTION FOUND!")
        print("=" * 50)
        print(f"puzzle_key = {number}")
        print(f"puzzle_misspell = '{misspelling}'")
        
        # Verify the solution
        verify_solution(number, misspelling)
        
        print("\nAdd these to your puzzle.py:")
        print(f"puzzle_key = {number}")
        print(f'puzzle_misspell = "{misspelling}"')
    else:
        print("\nNo solution found. Try adding more quotes to try.")
