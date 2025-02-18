pragma solidity ^0.8.18;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";

contract NonTransferableTicket is ERC721, Ownable {
    using Counters for Counters.Counter;
    Counters.Counter private _tokenIds;

    struct TicketDetails {
        string eventName;
        uint256 eventDate;
        string venue;
        bool isValid;
        bool isScanned;
        uint256 scannedTime;
        address scannerAddress;
    }

    mapping(uint256 => TicketDetails) public tickets;

    // Events
    event TicketMinted(
        uint256 indexed tokenId,
        address indexed owner,
        string eventName,
        uint256 eventDate,
        string venue
    );

    event TicketScanned(
        uint256 indexed tokenId,
        address indexed scanner,
        uint256 scanTime
    );

    constructor(address initialOwner) 
        ERC721("Event Ticket", "TCKT")
        Ownable(initialOwner)
    {}

    /**
     * @dev Check if a ticket exists by trying to get its owner.
     */
    function exists(uint256 tokenId) public view returns (bool) {
        try this.ownerOf(tokenId) returns (address) {
            return true;
        } catch {
            return false;
        }
    }

    /**
     * @dev Anyone can mint a ticket now (no onlyOwner restriction).
     */
    function mintTicket(
        address to,
        string memory eventName,
        uint256 eventDate,
        string memory venue
    ) public returns (uint256) {
        require(to != address(0), "Invalid address");

        _tokenIds.increment();
        uint256 newTokenId = _tokenIds.current();

        _safeMint(to, newTokenId);

        tickets[newTokenId] = TicketDetails({
            eventName: eventName,
            eventDate: eventDate,
            venue: venue,
            isValid: true,
            isScanned: false,
            scannedTime: 0,
            scannerAddress: address(0)
        });

        emit TicketMinted(newTokenId, to, eventName, eventDate, venue);
        return newTokenId;
    }

    /**
     * @dev Anyone can call scanTicket. 
     *      This sets the ticket as scanned and invalidates it.
     */
    function scanTicket(uint256 tokenId) public returns (bool) {
        require(exists(tokenId), "Ticket does not exist");
        TicketDetails storage ticket = tickets[tokenId];
        
        require(ticket.isValid, "Ticket is not valid");
        require(!ticket.isScanned, "Ticket already scanned");
        require(block.timestamp <= ticket.eventDate, "Event has expired");

        ticket.isScanned = true;
        ticket.scannedTime = block.timestamp;
        ticket.scannerAddress = msg.sender;
        ticket.isValid = false;  // Invalidate after scanning

        emit TicketScanned(tokenId, msg.sender, block.timestamp);
        return true;
    }

    function isTicketScanned(uint256 tokenId) public view returns (bool) {
        require(exists(tokenId), "Ticket does not exist");
        return tickets[tokenId].isScanned;
    }

    /**
     * @dev Returns all details for a given ticket ID.
     */
    function getTicketDetails(uint256 tokenId) 
        public 
        view 
        returns (
            string memory eventName,
            uint256 eventDate,
            string memory venue,
            bool isValid,
            bool isScanned,
            uint256 scannedTime,
            address scannerAddress
        ) 
    {
        require(exists(tokenId), "Ticket does not exist");
        TicketDetails memory ticket = tickets[tokenId];
        return (
            ticket.eventName,
            ticket.eventDate,
            ticket.venue,
            ticket.isValid,
            ticket.isScanned,
            ticket.scannedTime,
            ticket.scannerAddress
        );
    }

    /**
     * @dev Make tickets non-transferable by overriding transfer/approval functions.
     */
    function approve(address, uint256) public pure override {
        revert("Tickets are non-transferable");
    }

    function getApproved(uint256) public pure override returns (address) {
        return address(0);
    }

    function setApprovalForAll(address, bool) public pure override {
        revert("Tickets are non-transferable");
    }

    function isApprovedForAll(address, address) public pure override returns (bool) {
        return false;
    }

    /**
     * @dev Let contract owner invalidate a ticket manually if needed.
     */
    function invalidateTicket(uint256 tokenId) public onlyOwner {
        require(exists(tokenId), "Ticket does not exist");
        tickets[tokenId].isValid = false;
    }

    /**
     * @dev Ensure the contract still supports ERC721 interfaces.
     */
    function supportsInterface(bytes4 interfaceId) public view override returns (bool) {
        return super.supportsInterface(interfaceId);
    }
}