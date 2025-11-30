#!/usr/bin/env python3
"""
Diagnostic script to investigate Monarch authentication issues.

Checks:
1. Token existence in keyring
2. Token validity (if exists)
3. Rate limiting status
4. API connectivity
5. Token expiration
"""

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime

# Fix SSL certificate issues on macOS
import certifi
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from monarchmoney import MonarchMoney
from monarch_mcp_server.secure_session import secure_session

async def test_token_validity(token):
    """Test if a token is still valid."""
    print("\n🔍 Testing token validity...")
    try:
        client = MonarchMoney(token=token)
        # Try a simple API call
        accounts = await client.get_accounts()
        if accounts and isinstance(accounts, dict):
            account_count = len(accounts.get("accounts", []))
            print(f"✅ Token is VALID - Found {account_count} accounts")
            return True
        else:
            print("⚠️  Token exists but API returned unexpected format")
            return False
    except Exception as e:
        error_str = str(e).lower()
        if "401" in error_str or "unauthorized" in error_str or "authentication" in error_str:
            print(f"❌ Token is EXPIRED or INVALID: {e}")
            return False
        elif "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            print(f"⚠️  RATE LIMITED (429): {e}")
            print("   This is a temporary issue - wait 30-60 minutes")
            return None  # Can't determine validity due to rate limit
        else:
            print(f"❌ Token test failed with error: {e}")
            print(f"   Error type: {type(e).__name__}")
            return False

async def test_fresh_login(email, password):
    """Test if fresh login works (bypasses token)."""
    print("\n🔍 Testing fresh login...")
    try:
        client = MonarchMoney()
        await client.login(email, password, use_saved_session=False)
        accounts = await client.get_accounts()
        if accounts and isinstance(accounts, dict):
            account_count = len(accounts.get("accounts", []))
            print(f"✅ Fresh login WORKS - Found {account_count} accounts")
            return True
        else:
            print("⚠️  Fresh login succeeded but API returned unexpected format")
            return False
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
            print(f"❌ RATE LIMITED (429) during fresh login: {e}")
            print("   ⏰ Wait 30-60 minutes before trying again")
            return None
        elif "401" in error_str or "unauthorized" in error_str:
            print(f"❌ Authentication failed: {e}")
            print("   Check your credentials")
            return False
        else:
            print(f"❌ Fresh login failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            return False

def main():
    print("="*80)
    print("MONARCH AUTHENTICATION DIAGNOSTIC")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check 1: Token existence
    print("="*80)
    print("CHECK 1: Token Existence")
    print("="*80)
    token = secure_session.load_token()
    if token:
        print(f"✅ Token EXISTS in keyring")
        print(f"   Token length: {len(token)} characters")
        print(f"   Token preview: {token[:20]}...{token[-10:]}")
    else:
        print("❌ No token found in keyring")
        print("   → Need to run login_setup.py")
        print()
        print("Since you can log in via web browser, let's test fresh login...")
        email = input("\nEnter your Monarch email (or press Enter to skip): ").strip()
        if email:
            import getpass
            password = getpass.getpass("Enter your Monarch password: ")
            result = asyncio.run(test_fresh_login(email, password))
            if result:
                print("\n✅ Fresh login successful! Run login_setup.py to save the session.")
            elif result is None:
                print("\n⏰ Rate limited - wait 30-60 minutes, then run login_setup.py")
            else:
                print("\n❌ Fresh login failed - check credentials")
        return
    
    # Check 2: Token validity
    print("\n" + "="*80)
    print("CHECK 2: Token Validity")
    print("="*80)
    result = asyncio.run(test_token_validity(token))
    
    if result is True:
        print("\n✅ CONCLUSION: Token is valid and working!")
        print("   → Authentication is working correctly")
        print("   → Issue may be in how the dashboard scripts call the API")
    elif result is False:
        print("\n❌ CONCLUSION: Token is expired or invalid")
        print("   → Need to re-authenticate")
        print("   → Run: python login_setup.py")
        print("\n   Since web login works, this suggests:")
        print("   • Token may have expired (tokens typically last 30 days)")
        print("   • Token format may have changed")
        print("   • API may require re-authentication")
    elif result is None:
        print("\n⏰ CONCLUSION: Rate limited - cannot determine token validity")
        print("   → Wait 30-60 minutes")
        print("   → Then run: python login_setup.py")
        print("\n   Since web login works, this suggests:")
        print("   • Too many API attempts triggered rate limiting")
        print("   • Web interface may have different rate limits")
        print("   • API has stricter rate limiting than web")
    
    # Check 3: API connectivity
    print("\n" + "="*80)
    print("CHECK 3: API Connectivity")
    print("="*80)
    try:
        import requests
        response = requests.get("https://api.monarchmoney.com", timeout=5)
        print(f"✅ API endpoint reachable (Status: {response.status_code})")
    except requests.exceptions.Timeout:
        print("⚠️  API endpoint timeout - network issue?")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API - network issue?")
    except Exception as e:
        print(f"⚠️  API connectivity check failed: {e}")
    
    # Summary
    print("\n" + "="*80)
    print("DIAGNOSTIC SUMMARY")
    print("="*80)
    print("\nKey Findings:")
    if not token:
        print("  • No token stored - need initial authentication")
    elif result is True:
        print("  • Token exists and is valid")
        print("  • Authentication should work")
    elif result is False:
        print("  • Token exists but is expired/invalid")
        print("  • Need to re-authenticate")
    elif result is None:
        print("  • Token exists but rate limited")
        print("  • Wait before retrying")
    
    print("\nSince web login works:")
    print("  ✅ Credentials are correct")
    print("  ✅ Account is not locked")
    print("  ✅ Network connectivity is fine")
    print("\nPossible causes:")
    print("  1. Token expiration (most likely if token exists but invalid)")
    print("  2. Rate limiting from too many API attempts")
    print("  3. API vs Web authentication differences")
    print("  4. Token format changes in Monarch API")
    
    print("\n" + "="*80)
    print("RECOMMENDED ACTION")
    print("="*80)
    if not token:
        print("→ Run: python login_setup.py")
    elif result is False:
        print("→ Token expired - run: python login_setup.py")
    elif result is None:
        print("→ Rate limited - wait 30-60 minutes, then run: python login_setup.py")
    else:
        print("→ Token is valid - check dashboard scripts for other issues")

if __name__ == "__main__":
    asyncio.run(main()) if hasattr(asyncio, 'run') else asyncio.get_event_loop().run_until_complete(main())

