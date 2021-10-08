from electionguard.ballot import PlaintextBallot
from fastapi import APIRouter
from pydantic import BaseModel
from uuid import uuid4

from .election import election
from .manifest import generate_ballot_style_contests, get_contest_info, get_selection_info

router = APIRouter()


class BallotInfoRequest(BaseModel):
    ballot_style: str


class BallotMarkingRequest(BaseModel):
    ballot_style: str
    selections: dict


class BallotEncryptionRequest(BaseModel):
    ballot: dict
    action: str


@router.post("/info")
async def gen_ballot_info(ballot_info_params: BallotInfoRequest):
    """
    Given a ballot style, compile and return relevant election information
    
    Args:
        ballot_info_paramse: BallotInfoRequest containing ballot style
    Returns:
        JSON structure for ballot_style with returned from get_contest_info
    """
    # Get base ballot info
    ballot_info = generate_ballot_style_contests(election.manifest, ballot_info_params.ballot_style)

    for contest in ballot_info["contests"]:
        # Get contest info
        contest_info = get_contest_info(election.manifest, contest["object_id"])
        # Populate information
        contest.update(contest_info)

    return ballot_info


@router.post("/mark")
async def mark_ballot(ballot_marking_params: BallotMarkingRequest):
    """
    Mark all selections on a ballot.

    Args:
        ballot_marking_params: ballot_style and voter selections
    Returns:
        Marked ballot JSON returned by get_selection_info()

    TODO: handle errors gracefully
    TODO: check number of votes and weights
    """
    # Get base ballot info
    ballot = generate_ballot_style_contests(election.manifest, ballot_marking_params.ballot_style)

    # Give ballot unique ID
    ballot["object_id"] = f"ballot-{uuid4()}"

    # Mark mark each selection
    for contest in ballot["contests"]:
        contest_id = contest["object_id"]
        selected_candidate_id = ballot_marking_params.selections.get(contest_id)
        selection_info = get_selection_info(election.manifest, contest_id, selected_candidate_id)
        contest["ballot_selections"] = [selection_info]
    return ballot


@router.post("/submit")
async def encrypt_ballot(ballot_encryption_params: BallotEncryptionRequest):
    """
    Encrypt a ballot and generate a receipt

    Args:
        ballot_encryption_params: ballot JSON
    Returns:
        receipt JSON with verification code and timestamp
    """
    # Assert that action is valid before processing ballot
    assert ballot_encryption_params.action == "CAST" or ballot_encryption_params.action == "SPOIL"

    # Make and encrypt ballot object
    ballot = PlaintextBallot.from_json_object(ballot_encryption_params.ballot)
    encrypted_ballot = election.encryption_mediator.encrypt(ballot)

    # Cast or spoil ballot depending on action
    if ballot_encryption_params.action == "CAST":
        election.ballotbox.cast(encrypted_ballot)
    else:
        election.ballotbox.spoil(encrypted_ballot)

    # Return verification code and timestamp
    return {
        "verification_code": encrypted_ballot.object_id,
        "timestamp": encrypted_ballot.timestamp
    }
