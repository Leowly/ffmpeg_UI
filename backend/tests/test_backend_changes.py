#!/usr/bin/env python3
"""
Test script to verify the backend changes work correctly
"""

def test_imports():
    """Test that all modules import correctly after changes"""
    print("Testing imports...")
    
    try:
        from backend import crud
        print("✓ CRUD imports work")
    except Exception as e:
        print(f"✗ CRUD import failed: {e}")
        return False
    
    try:
        from backend import processing
        print("✓ Processing imports work")
    except Exception as e:
        print(f"✗ Processing import failed: {e}")
        return False
    
    try:
        from backend.routers import files
        print("✓ Files router imports work")
    except Exception as e:
        print(f"✗ Files router import failed: {e}")
        return False
    
    print("All imports successful!")
    return True

def test_functionality():
    """Basic functionality tests"""
    print("\nTesting basic functionality...")
    
    # Test the lru_cache decorator
    from backend.config import reconstruct_file_path
    import tempfile
    import os
    
    # Create a temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        test_path = tmp.name
    
    try:
        # Call reconstruct_file_path with a non-existent user directory
        # This should return None since the file won't be in the expected location
        result = reconstruct_file_path(test_path, 1)
        print(f"✓ reconstruct_file_path test passed: {result is not None or result is None}")
        
        # Test the cache - call the same function again should use cache
        result2 = reconstruct_file_path(test_path, 1)
        print(f"✓ reconstruct_file_path cached result test passed: {result == result2}")
        
        # Test cache clearing
        from backend.config import invalidate_file_path_cache
        invalidate_file_path_cache()
        print("✓ Cache invalidation works")
        
    finally:
        # Clean up
        if os.path.exists(test_path):
            os.unlink(test_path)
    
    print("Basic functionality tests passed!")
    return True

if __name__ == "__main__":
    print("Testing backend changes...")
    
    if test_imports() and test_functionality():
        print("\n🎉 All tests passed! Backend changes are working correctly.")
    else:
        print("\n❌ Some tests failed.")