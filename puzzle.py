"""
HW6 Proof-of-Work Submission
"""

cnet_id = "jhuang165"  
nonce = "14948743"     

# Part 2 variables (replace with your actual values)
puzzle_easy_key = 8983  
puzzle_easy_misspell = "gadqens"   # mispelling of gardens

# Your answers from Part 2
puzzle_key = 0           # TODO: Replace with the actual 9-digit number you found
puzzle_misspell = ""     # TODO: Replace with the actual misspelled word you found

# Optional: Add your solution verification code
def verify_solution():
    """Verify that your solutions are correct"""
    import hashlib
    
    # Verify Part 1
    if cnet_id != "your_cnet_id" and nonce:
        test_str = f"{cnet_id}{nonce}"
        hash_result = hashlib.sha256(test_str.encode()).hexdigest()
        target = "0000000fffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        print(f"Part 1 hash: {hash_result}")
        print(f"Part 1 valid: {hash_result < target}")
    
    # Verify Part 2
    if puzzle_key and puzzle_misspell:
        print(f"Part 2 puzzle key: {puzzle_key}")
        print(f"Part 2 misspelled word: {puzzle_misspell}")

if __name__ == "__main__":
    verify_solution()
