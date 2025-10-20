#!/usr/bin/env python3
"""
Test script for email processing logic.

This script tests the process_email function with dummy Gmail message data.
You can modify the DUMMY_EMAIL_PAYLOAD to test different scenarios.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.process_email import process_email
from app.dummy_data import DUMMY_EMAIL_PAYLOAD

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


def main():
    """
    Test function to run process_email with dummy data.
    
    This function is called by the 'test' script command.
    You can modify DUMMY_EMAIL_PAYLOAD above to test different scenarios.
    """
    print("🧪 Testing email processing with dummy payload...")
    print("=" * 60)
    
    try:
        # Process the dummy email
        process_email(DUMMY_EMAIL_PAYLOAD)
        print("=" * 60)
        print("✅ Test completed successfully!")
        print("\n💡 To customize the test:")
        print("   1. Edit DUMMY_EMAIL_PAYLOAD in app/process_email.py")
        print("   2. Run 'uv run test' again to test your changes")
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ Test failed with error: {e}")
        print("\n🔍 Check the logs above for more details")
        raise


if __name__ == "__main__":
    main()
