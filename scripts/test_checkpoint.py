#!/usr/bin/env python3
"""
Test script to demonstrate checkpoint/resumption functionality
"""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from mcp_server.patent_index import PatentCorpusIndex  # noqa: E402


def test_checkpoint_basic():
    """Test basic checkpoint functionality"""
    print("=" * 60)
    print("Testing Checkpoint Functionality")
    print("=" * 60)

    # Initialize index
    index = PatentCorpusIndex(use_hyde=False)

    # Test 1: Check checkpoint directory exists
    print("\n[TEST 1] Checkpoint directory creation")
    if index.checkpoint_dir.exists():
        print(f"  [OK] Checkpoint directory exists: {index.checkpoint_dir}")
    else:
        print(f"  [FAIL] Checkpoint directory not found: {index.checkpoint_dir}")
        return False

    # Test 2: Check checkpoint metadata file after a run
    checkpoint_metadata = index.checkpoint_dir / "checkpoint_metadata.json"
    if checkpoint_metadata.exists():
        print("\n[TEST 2] Existing checkpoint detected")
        print(f"  [OK] Checkpoint metadata found: {checkpoint_metadata}")

        # Read and display checkpoint info
        import json

        with open(checkpoint_metadata, "r") as f:
            metadata = json.load(f)

        print("  Checkpoint details:")
        print(f"    - Batch number: {metadata.get('batch_num')}")
        print(f"    - Processed chunks: {metadata.get('processed_chunks'):,}")
        print(f"    - Total chunks: {metadata.get('total_chunks'):,}")
        print(f"    - Timestamp: {metadata.get('timestamp')}")

        # Calculate progress
        processed = metadata.get("processed_chunks", 0)
        total = metadata.get("total_chunks", 1)
        progress = (processed / total) * 100 if total > 0 else 0
        print(f"    - Progress: {progress:.1f}%")

        # List checkpoint files
        checkpoint_files = list(index.checkpoint_dir.glob("checkpoint_batch_*.npz"))
        print(f"    - Checkpoint files: {len(checkpoint_files)}")

        # Calculate total checkpoint size
        total_size = sum(f.stat().st_size for f in checkpoint_files)
        total_size_mb = total_size / (1024 * 1024)
        print(f"    - Total checkpoint size: {total_size_mb:.1f} MB")

    else:
        print("\n[TEST 2] No existing checkpoint found")
        print("  (This is expected if indexing hasn't been started)")

    # Test 3: Test cleanup functionality
    print("\n[TEST 3] Checkpoint cleanup test")
    checkpoint_files_before = list(index.checkpoint_dir.glob("checkpoint_*"))
    print(f"  Checkpoint files before cleanup: {len(checkpoint_files_before)}")

    if checkpoint_files_before:
        print("  Note: Not cleaning up automatically. Use force_rebuild=True to cleanup.")
    else:
        print("  No checkpoint files to cleanup")

    print("\n" + "=" * 60)
    print("Checkpoint Test Complete")
    print("=" * 60)

    return True


def display_checkpoint_instructions():
    """Display instructions for using checkpoints"""
    print("\n" + "=" * 60)
    print("CHECKPOINT USAGE INSTRUCTIONS")
    print("=" * 60)

    print("\n1. NORMAL BUILD (with checkpoints):")
    print("   index.build_index()")
    print("   - Automatically resumes from checkpoint if interrupted")
    print("   - Saves checkpoint every 100,000 chunks by default")

    print("\n2. CUSTOM CHECKPOINT INTERVAL:")
    print("   index.build_index(checkpoint_interval=50000)")
    print("   - Saves checkpoint every 50,000 chunks")
    print("   - Smaller interval = more frequent saves, slower performance")
    print("   - Larger interval = less frequent saves, faster performance")

    print("\n3. DISABLE CHECKPOINTS:")
    print("   index.build_index(resume_from_checkpoint=False)")
    print("   - Ignores existing checkpoints")
    print("   - Does not save new checkpoints")

    print("\n4. FORCE REBUILD (cleans checkpoints):")
    print("   index.build_index(force_rebuild=True)")
    print("   - Deletes all checkpoints")
    print("   - Starts fresh from beginning")

    print("\n5. MANUAL CHECKPOINT CLEANUP:")
    print("   index._cleanup_checkpoints()")
    print("   - Removes all checkpoint files")

    print("\nCHECKPOINT LOCATION:")
    index = PatentCorpusIndex(use_hyde=False)
    print(f"   {index.checkpoint_dir}")

    print("\nFILES CREATED:")
    print("   - checkpoint_batch_0.npz (first 100K chunks)")
    print("   - checkpoint_batch_1.npz (next 100K chunks)")
    print("   - checkpoint_batch_N.npz (subsequent batches)")
    print("   - checkpoint_metadata.json (progress tracking)")

    print("\nEXPECTED BEHAVIOR:")
    print("   - If indexing is interrupted, restart with build_index()")
    print("   - System detects checkpoint and resumes automatically")
    print("   - Progress message shows 'Resuming from chunk X of Y'")
    print("   - After completion, checkpoints are automatically deleted")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run tests
    success = test_checkpoint_basic()

    # Display instructions
    display_checkpoint_instructions()

    sys.exit(0 if success else 1)
