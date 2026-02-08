"""
Manual cleanup script for Praat uploads.

Usage:
    python -m app.praat.manual_cleanup [--hours HOURS] [--dry-run]

Examples:
    # Clean up uploads older than 1 hour (default)
    python -m app.praat.manual_cleanup

    # Clean up uploads older than 6 hours
    python -m app.praat.manual_cleanup --hours 6

    # Dry run (show what would be deleted without actually deleting)
    python -m app.praat.manual_cleanup --dry-run

    # Clean up orphaned files only
    python -m app.praat.manual_cleanup --orphaned-only
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.praat.cleanup_scheduler import cleanup_old_uploads, cleanup_orphaned_files
from app.praat.config import CLEANUP_AGE_HOURS


def main():
    parser = argparse.ArgumentParser(
        description="Manually clean up old Praat uploads and orphaned files"
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=CLEANUP_AGE_HOURS,
        help=f"Delete uploads older than this many hours (default: {CLEANUP_AGE_HOURS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    parser.add_argument(
        "--orphaned-only",
        action="store_true",
        help="Only clean up orphaned files (files without database records)"
    )
    parser.add_argument(
        "--uploads-only",
        action="store_true",
        help="Only clean up old uploads (skip orphaned files)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Praat Upload Cleanup Tool")
    print("=" * 60)

    if args.dry_run:
        print("⚠️  DRY RUN MODE - No files will be deleted")
        print("=" * 60)

    # Temporarily override cleanup age if specified
    if args.hours != CLEANUP_AGE_HOURS:
        import app.praat.cleanup_scheduler as cleanup_module
        original_age = cleanup_module.CLEANUP_AGE_HOURS
        cleanup_module.CLEANUP_AGE_HOURS = args.hours
        print(f"📅 Using custom age: {args.hours} hours (default: {original_age})")

    try:
        if not args.orphaned_only:
            print(f"\n🧹 Cleaning up uploads older than {args.hours} hours...")
            if not args.dry_run:
                cleanup_old_uploads()
            else:
                print("   (Dry run - would call cleanup_old_uploads())")

        if not args.uploads_only:
            print("\n🧹 Cleaning up orphaned files...")
            if not args.dry_run:
                cleanup_orphaned_files()
            else:
                print("   (Dry run - would call cleanup_orphaned_files())")

        print("\n" + "=" * 60)
        if args.dry_run:
            print("✅ Dry run complete (no files were deleted)")
        else:
            print("✅ Cleanup complete")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
