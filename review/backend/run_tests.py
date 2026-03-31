#!/usr/bin/env python
"""
Comprehensive Test Suite Runner
Tests all security fixes implemented:
- Issue #2: Database-backed credentials with password hashing
- Issue #7: Pydantic schema validation
- Issue #6: Session ownership validation
- Issue #8: Redis retry logic & circuit breaker
"""

import subprocess
import sys
import json
from datetime import datetime
from pathlib import Path


def run_tests():
    """Run all tests and collect results"""
    
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE TEST SUITE RUNNER")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Test files to run
    tests = [
        ("test_suite/backend/test_auth.py", "Authentication & Password Hashing (Issue #2)"),
        ("test_suite/backend/test_schemas.py", "Pydantic Schema Validation (Issue #7)"),
        ("test_suite/backend/test_session_security.py", "Session Ownership Validation (Issue #6)"),
        ("test_suite/backend/test_cache.py", "Cache Retry Logic & Circuit Breaker (Issue #8)"),
    ]
    
    results = {}
    total_passed = 0
    total_failed = 0
    total_skipped = 0
    
    for test_file, description in tests:
        print("\n" + "-"*80)
        print(f"📝 Running: {description}")
        print(f"   File: {test_file}")
        print("-"*80)
        
        try:
            # Run pytest with JSON output
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    test_file,
                    "-v",
                    "--tb=short",
                    "-ra",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            
            # Parse output
            output = result.stdout + result.stderr
            print(output)
            
            # Count results from output
            passed = output.count(" PASSED")
            failed = output.count(" FAILED")
            skipped = output.count(" SKIPPED")

            if result.returncode != 0 and failed == 0:
                # Capture collection/import/path failures as a failed test bucket.
                failed = 1
            
            results[description] = {
                "file": test_file,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "exit_code": result.returncode,
                "output": output
            }
            
            total_passed += passed
            total_failed += failed
            total_skipped += skipped
            
            if result.returncode == 0:
                print(f"✅ {description}: ALL PASSED ({passed} tests)")
            else:
                print(f"❌ {description}: FAILED ({failed} failures, {passed} passed)")
        
        except Exception as e:
            print(f"❌ Error running tests: {e}")
            results[description] = {
                "file": test_file,
                "error": str(e),
                "exit_code": 1
            }
            total_failed += 1
    
    # Print summary
    print("\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)
    print(f"\n✅ PASSED:  {total_passed}")
    print(f"❌ FAILED:  {total_failed}")
    print(f"⏭️  SKIPPED: {total_skipped}")
    print(f"\nTotal Tests: {total_passed + total_failed + total_skipped}")
    
    if total_failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        status = "✅ SUCCESS"
    else:
        print(f"\n⚠️ {total_failed} TESTS FAILED - See details above")
        status = "❌ FAILURE"
    
    print("\n" + "="*80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")
    
    return {
        "status": status,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "results": results
    }


if __name__ == "__main__":
    report = run_tests()
    sys.exit(0 if report["total_failed"] == 0 else 1)
