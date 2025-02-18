# BlockTix - Blockchain-Powered Event Ticketing Platform

### Team Members

- Jasper
- Ethan
- Cai Feng
- Sherwin

## About BlockTix

BlockTix is a next-generation event ticketing platform built on blockchain technology. Our platform combines the security and transparency of blockchain with a user-friendly interface to revolutionize how event tickets are bought, sold, and verified.

### Key Features

- **Blockchain-Powered Tickets**: Each ticket is minted as an NFT on the Ethereum blockchain
- **Secure Two-Factor Authentication**: Email verification codes protect user accounts
- **ID Verification**: Advanced identity verification using Mindee AI
- **QR Code Ticket Verification**: Easy venue entry with secure QR code scanning
- **Eco-Friendly Events**: Support and highlight sustainable event practices
- **Promotions System**: Special offers and event promotions for users

## Technology Stack

- **Backend**: Flask 3.0
- **Database**: SQLAlchemy with PostgreSQL on AWS RDS
- **Image Storage**: AWS S3 Bucket
- **Blockchain**: Solidity on the Ethereum (Sepolia testnet)
- **Blockchain Node**: Google Web3 Live Node
- **Frontend**: TailwindCSS, JavaScript
- **Authentication**: Custom email verification system using Gmail SMTP
- **Identity Verification**: Mindee API
- **Deployment**: Vercel with Serverless Functions (Taken done due to cloud costs of the AWS and APIs)

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL (for production) 
- Ethereum wallet with Sepolia testnet ETH (for contract deployment)

### Environment Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/blocktix.git
    ```
2. Create and activate a virtual environment:
   ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```
3. Install dependencies:
   ```bash
    pip install -r requirements.txt
    ```
4. Create a .env file with the following variables:
   ```bash
    FLASK_APP=main.py
    FLASK_ENV=development
    SECRET_KEY=your-secret-key-change-this

    DATABASE_URL=

    EMAIL_USER=
    EMAIL_PASSWORD=
    MINDEE_API_KEY=

    RECAPTCHA_SITE_KEY=
    RECAPTCHA_SECRET_KEY=

    AWS_ACCESS_KEY_ID=
    AWS_SECRET_ACCESS_KEY=
    AWS_S3_BUCKET=
    AWS_REGION=

    WEB3_PROVIDER_URI=
    CONTRACT_ADDRESS=
    CONTRACT_ABI_PATH=
    PRIVATE_KEY=

    UPLOAD_FOLDER=
    MAX_CONTENT_LENGTH=
    ALLOWED_EXTENSIONS=

    DB_USER = 
    DB_PASSWORD = 
    DB_HOST = 
    DB_NAME = 
    ```
### Project Structure
```bash
blocktix/
├── src/                   # Application source code
│   ├── Database/          # Database models and configuration
│   ├── Routes/            # API and web routes
│   ├── Templates/         # HTML templates
│   ├── Static/            # Static assets (CSS, JS, images)
│   ├── Utlis/             # Utility functions and helpers
│   │   └── web3_config.py # Blockchain configuration
│   └── main.py            # Application entry point
├── scripts/               # Helper scripts
├── tests/                 # Unit and integration tests
├── vercel.json            # Vercel configuration
├── requirements.txt       # Python dependencies
└── README.md              # Project documentation
```

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.