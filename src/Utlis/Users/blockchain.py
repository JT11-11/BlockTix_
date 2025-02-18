import secrets
from eth_account import Account


def create_eth_account():
    """Create a new Ethereum account"""
    try:
        private_key = secrets.token_hex(32)
        account = Account.from_key('0x' + private_key)
        
        try:
            print(f"Created new Eth account{account.address}")
        except Exception as e:
                print(f"Account created but failed to verify: {str(e)}")
        return {
                'address': account.address,
                'private_key': private_key
            }
    except Exception as e:
        print(f"Failed to create Ethereum account: {str(e)}")
        raise