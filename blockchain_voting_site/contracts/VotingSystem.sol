// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

contract VotingSystem {
    enum ElectionState { Created, Ongoing, Ended }

    struct Candidate {
        uint256 id;
        string name;
        string party;
        uint256 voteCount;
    }

    address public admin;
    string public electionName;
    ElectionState public state;
    uint256 public electionId;
    uint256 public candidatesCount;
    mapping(uint256 => Candidate) public candidates;
    mapping(bytes32 => uint256) public lastVotedElection;

    event ElectionCreated(uint256 indexed electionId, string name);
    event CandidateAdded(uint256 indexed candidateId, string name, string party);
    event ElectionStarted(uint256 indexed electionId, uint256 timestamp);
    event ElectionEnded(uint256 indexed electionId, uint256 timestamp);
    event VoteCast(bytes32 indexed voterHash, uint256 indexed candidateId, uint256 indexed electionId, uint256 timestamp);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only the admin can perform this action");
        _;
    }

    modifier inState(ElectionState _state) {
        require(state == _state, "Action not allowed in current election state");
        _;
    }

    constructor() {
        admin = msg.sender;
        state = ElectionState.Ended;
    }

    function createElection(string calldata _name) external onlyAdmin inState(ElectionState.Ended) {
        require(bytes(_name).length > 0, "Election name cannot be empty");
        electionId += 1;
        electionName = _name;
        candidatesCount = 0;
        state = ElectionState.Created;
        emit ElectionCreated(electionId, _name);
    }

    function addCandidate(string calldata _name, string calldata _party)
        external onlyAdmin inState(ElectionState.Created)
    {
        require(bytes(_name).length > 0, "Candidate name cannot be empty");
        candidatesCount += 1;
        candidates[candidatesCount] = Candidate(candidatesCount, _name, _party, 0);
        emit CandidateAdded(candidatesCount, _name, _party);
    }

    function startElection() external onlyAdmin inState(ElectionState.Created) {
        require(candidatesCount >= 2, "At least two candidates are required");
        state = ElectionState.Ongoing;
        emit ElectionStarted(electionId, block.timestamp);
    }

    function endElection() external onlyAdmin inState(ElectionState.Ongoing) {
        state = ElectionState.Ended;
        emit ElectionEnded(electionId, block.timestamp);
    }

    // The Flask application authenticates the voter off-chain. Only the
    // administrator account submits the transaction, while the voter's
    // one-way SHA-256 identity is stored on-chain instead of the raw ID.
    function vote(bytes32 voterHash, uint256 _candidateId)
        external onlyAdmin inState(ElectionState.Ongoing)
    {
        require(lastVotedElection[voterHash] != electionId, "This voter has already voted");
        require(_candidateId > 0 && _candidateId <= candidatesCount, "Invalid candidate ID");

        lastVotedElection[voterHash] = electionId;
        candidates[_candidateId].voteCount += 1;
        emit VoteCast(voterHash, _candidateId, electionId, block.timestamp);
    }

    function hasVoted(bytes32 voterHash) external view returns (bool) {
        return lastVotedElection[voterHash] == electionId && electionId != 0;
    }

    function getCandidate(uint256 _candidateId)
        external view returns (uint256 id, string memory name, string memory party, uint256 voteCount)
    {
        require(_candidateId > 0 && _candidateId <= candidatesCount, "Invalid candidate ID");
        Candidate memory c = candidates[_candidateId];
        return (c.id, c.name, c.party, c.voteCount);
    }

    function getResults() external view returns (string[] memory names, uint256[] memory voteCounts) {
        names = new string[](candidatesCount);
        voteCounts = new uint256[](candidatesCount);
        for (uint256 i = 1; i <= candidatesCount; i++) {
            names[i - 1] = candidates[i].name;
            voteCounts[i - 1] = candidates[i].voteCount;
        }
    }
}
