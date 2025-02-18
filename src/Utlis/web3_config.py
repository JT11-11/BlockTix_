from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
import json
import time
import os
from .smart_contract import EventContractService
from dotenv import load_dotenv

load_dotenv()

CONTRACT_ADDRESS = os.environ.get('CONTRACT_ADDRESS')
PRIVATE_KEY = os.environ.get('PRIVATE_KEY')

with open(os.environ.get('CONTRACT_ABI_PATH'), 'r') as f:
    CONTRACT_ABI = json.load(f)

def initialize_w3(max_retries=3):
    """Initialize Web3 with retry logic"""
    attempt = 0
    while attempt < max_retries:
        try:
            w3 = Web3(Web3.HTTPProvider(
                os.environ.get('WEB3_PROVIDER_URI'),
                request_kwargs={'timeout': 30}
            ))
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            
            if not w3.is_connected():
                raise Exception("Failed to connect to network")
                
            return w3
            
        except Exception as e:
            print(f"Connection attempt {attempt + 1} failed: {str(e)}")
            attempt += 1
            if attempt < max_retries:
                time.sleep(2)  
            else:
                raise Exception(f"Failed to initialize Web3 after {max_retries} attempts")

def init_contract_service(w3):
    """Initialize contract service with verification"""
    try:
        network_id = w3.eth.chain_id
        if network_id != 11155111: 
            raise Exception(f"Wrong network. Expected Sepolia (11155111), got {network_id}")
            
        code = w3.eth.get_code(Web3.to_checksum_address(CONTRACT_ADDRESS))
        if code == '0x':
            raise Exception("No contract code at specified address")
            
        contract_service = EventContractService(
            w3=w3,
            contract_address=CONTRACT_ADDRESS,
            contract_abi=CONTRACT_ABI,
            private_key=PRIVATE_KEY
        )
        
        balance = w3.eth.get_balance(contract_service.address)
        if balance == 0:
            print("Warning: Account has zero balance")
            
        return contract_service
        
    except Exception as e:
        raise Exception(f"Failed to initialize contract service: {str(e)}")

w3 = initialize_w3()
contract_service = init_contract_service(w3)

def verify_setup():
    """Verify complete setup"""
    try:
        if not w3.is_connected():
            return False
            
        owner = contract_service.contract.functions.owner().call()
        if owner.lower() != contract_service.address.lower():
            print(f"Warning: We are not the contract owner")
            print(f"Owner: {owner}")
            print(f"Our address: {contract_service.address}")
            
        return True
    except Exception as e:
        print(f"Setup verification failed: {str(e)}")
        return False

if not verify_setup():
    raise Exception("Failed to verify configuration")