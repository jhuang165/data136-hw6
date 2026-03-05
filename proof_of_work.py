#!/usr/bin/env python3
"""
Proof of Work Solver for HW6 Part 1
Find a string that when appended to cnet ID produces SHA256 hash < target
"""

import hashlib
import itertools
import time

def proof_of_work(cnet_id, target_hex="0000000fffffffffffffffffffffffffffffffffffffffffffffffffffffffff"):
    """
    Find nonce such that sha256(cnet_id + nonce) < target
    
    Args:
        cnet_id: Your cnet ID string
        target_hex: Target hash value in hexadecimal
    
    Returns:
        nonce string that satisfies the condition
    """
    # Convert target to integer for comparison
    target = int(target_hex, 16)
    
    print(f"Starting proof of work for cnet_id: {cnet_id}")
    print(f"Target: {target_hex}")
    print(f"Target value: {target}")
    print("-" * 50)
    
    start_time = time.time()
    attempts = 0
    
    # Try different nonces (both string and integer formats)
    for nonce in itertools.count():
        # Try as string
        test_str = f"{cnet_id}{nonce}"
        hash_result = hashlib.sha256(test_str.encode()).hexdigest()
        hash_int = int(hash_result, 16)
        attempts += 1
        
        # Progress update every 100,000 attempts
        if attempts % 100000 == 0:
            elapsed = time.time() - start_time
            rate = attempts / elapsed
            print(f"Attempts: {attempts:,} | Rate: {rate:.0f}/sec | Current hash: {hash_result[:16]}...")
        
        if hash_int < target:
            elapsed = time.time() - start_time
            print("\n" + "=" * 50)
            print("SUCCESS! Found valid nonce")
            print("=" * 50)
            print(f"Nonce: {nonce}")
            print(f"Full string: {test_str}")
            print(f"SHA256 hash: {hash_result}")
            print(f"Hash value: {hash_int}")
            print(f"Target value: {target}")
            print(f"Attempts: {attempts:,}")
            print(f"Time elapsed: {elapsed:.2f} seconds")
            return str(nonce)
    
    return None

def verify_solution(cnet_id, nonce, target_hex="0000000fffffffffffffffffffffffffffffffffffffffffffffffffffffffff"):
    """Verify that a nonce solution is correct"""
    test_str = f"{cnet_id}{nonce}"
    hash_result = hashlib.sha256(test_str.encode()).hexdigest()
    hash_int = int(hash_result, 16)
    target = int(target_hex, 16)
    
    print("\nVerification:")
    print(f"String: {test_str}")
    print(f"Hash: {hash_result}")
    print(f"Hash value: {hash_int}")
    print(f"Target value: {target}")
    print(f"Valid: {hash_int < target}")
    
    return hash_int < target

if __name__ == "__main__":
    YOUR_CNET_ID = "jhuang165"
    
    found_nonce = proof_of_work(YOUR_CNET_ID)
    
    if found_nonce:
        verify_solution(YOUR_CNET_ID, found_nonce)
        
        print("\n" + "=" * 50)
        print("Add this to your puzzle.py:")
        print(f'cnet_id = "{YOUR_CNET_ID}"')
        print(f'nonce = "{found_nonce}"')
