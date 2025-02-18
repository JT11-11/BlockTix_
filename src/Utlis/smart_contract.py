from web3 import Web3
from datetime import datetime
import json
from eth_account import Account
import time

class EventContractService:
    def __init__(self, w3, contract_address, contract_abi, private_key):
        self.w3 = w3
        self.contract_address = Web3.to_checksum_address(contract_address)
        self.contract = w3.eth.contract(address=self.contract_address, abi=contract_abi)
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        self.MAX_RETRIES = 3
        self.GAS_PRICE_INCREMENT = 1.1 

    def get_optimal_gas_price(self):
        """Get optimal gas price with safety buffer"""
        try:
            base_price = self.w3.eth.gas_price
            return int(base_price * 1.2)  
        except:
            return self.w3.eth.gas_price

    def mint_ticket(self, to_address, event_name, event_date, venue):
        """Mint ticket with retry logic"""
        start_time = time.time()
        attempt = 0
        
        while attempt < self.MAX_RETRIES and (time.time() - start_time) < 40:  # 40 second timeout
            try:
                print(f"\n=== Mint Attempt {attempt + 1} ===")
                
                if hasattr(event_date, 'event_date') and hasattr(event_date, 'event_time'):
                    event_timestamp = int(datetime.combine(
                        event_date.event_date,
                        event_date.event_time
                    ).timestamp())
                else:
                    event_timestamp = int(event_date)

                print("\n=== Running Pre-flight Checks ===")
                network_id = self.w3.eth.chain_id
                print(f"Network ID: {network_id}")
                
                code = self.w3.eth.get_code(self.contract_address)
                if code == '0x':
                    raise Exception("Contract not found at specified address")

                balance = self.w3.eth.get_balance(self.address)
                print(f"Account balance: {self.w3.from_wei(balance, 'ether')} ETH")

                nonce = self.w3.eth.get_transaction_count(self.address)
                print(f"Using nonce: {nonce}")
                gas_price = int(self.get_optimal_gas_price() * (self.GAS_PRICE_INCREMENT ** attempt))
                print(f"Using gas price: {gas_price}")

                mint_function = self.contract.functions.mintTicket(
                    Web3.to_checksum_address(to_address),
                    event_name,
                    event_timestamp,
                    venue
                )
                
                gas_estimate = mint_function.estimate_gas({'from': self.address})
                gas_limit = int(gas_estimate * 1.2)  
                print(f"Gas limit: {gas_limit}")

                transaction = mint_function.build_transaction({
                    'from': self.address,
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': self.w3.eth.chain_id
                })

                signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key=self.account.key)
                print("Transaction signed")

                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.raw_transaction)                
                print(f"Transaction hash: {tx_hash.hex()}")

                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)
                print(f"Transaction mined in block: {tx_receipt['blockNumber']}")

                if tx_receipt['status'] == 0:
                    raise Exception("Transaction failed")

                events = self.contract.events.TicketMinted().process_receipt(tx_receipt)
                if not events:
                    raise Exception("No TicketMinted event found")

                token_id = events[0]['args']['tokenId']
                print(f"Successfully minted token ID: {token_id}")
                
                return token_id

            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if "replacement transaction underpriced" in str(e):
                    attempt += 1
                    time.sleep(2)  
                    continue
                raise Exception(f"Minting failed: {str(e)}")

        raise Exception("Exceeded maximum retry attempts")

    def get_ticket_details(self, token_id):
        """Get ticket details"""
        try:
            details = self.contract.functions.getTicketDetails(token_id).call()
            return {
                'eventName': details[0],
                'eventDate': datetime.fromtimestamp(details[1]),
                'venue': details[2],
                'isValid': details[3]
            }
        except Exception as e:
            raise Exception(f"Failed to get ticket details: {str(e)}")