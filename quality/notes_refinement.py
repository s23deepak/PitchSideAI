"""Whole-document evaluation and deterministic refinement for broadcast notes."""

from __future__ import annotations

import re
from typing import Any

from quality.notes_quality import score_notes


REQUIRED_BROADCAST_SECTIONS = (
    "MATCH FRAME",
    "NARRATIVE SPINE",
    "TEAM SHEETS",
    "PLAYER CARDS",
    "TACTICAL DOSSIER",
    "SET-PIECE WATCH",
    "LIVE TRIGGER LINES",
    "PRONUNCIATION",
    "EVIDENCE STATUS",
)


def evaluate_notes_document(
    markdown: str,
    *,
    fact_ledger: dict[str, Any],
    quality_report: dict[str, Any],
    beats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    upper = markdown.upper()
    missing_sections = [section for section in REQUIRED_BROADCAST_SECTIONS if section not in upper]
    unsupported_claims = _find_unsupported_claims(markdown, fact_ledger)
    notes_score = score_notes(markdown, {"beats": beats or [], "quality_report": quality_report}).to_dict()
    structure_score = round((len(REQUIRED_BROADCAST_SECTIONS) - len(missing_sections)) / len(REQUIRED_BROADCAST_SECTIONS), 3)
    needs_revision = bool(missing_sections or unsupported_claims or notes_score.get("total", 0) < 0.72)
    return {
        "missing_sections": missing_sections,
        "unsupported_claims": unsupported_claims,
        "structure_score": structure_score,
        "notes_score": notes_score,
        "needs_revision": needs_revision,
        "strict_mode": True,
    }


def refine_notes_document(
    markdown: str,
    *,
    evaluation: dict[str, Any],
    fact_ledger: dict[str, Any],
    home_team: str,
    away_team: str,
) -> str:
    refined = markdown
    protected = fact_ledger.get("protected_claims", {}) if isinstance(fact_ledger, dict) else {}

    if protected.get("exact_h2h_count") != "verified":
        refined = re.sub(
            r"\b(?:have|has)\s+met\s+exactly\s+once\b",
            "have prior meetings, but the exact head-to-head count is not verified in this run",
            refined,
            flags=re.I,
        )
        refined = re.sub(
            r"\bexactly\s+one\s+previous\s+meeting\b",
            "a previous-meeting history that needs source confirmation",
            refined,
            flags=re.I,
        )

    if protected.get("no_injuries") != "verified":
        refined = re.sub(
            r"\b(?:no|zero)\s+(?:reported\s+)?(?:injuries|injury concerns|availability concerns)\b",
            "no verified injury report was accepted in this run",
            refined,
            flags=re.I,
        )

    if protected.get("final_world_cup") != "verified":
        refined = re.sub(
            r"\b(?:almost\s+certainly\s+)?(?:his|her|their)\s+final\s+World Cup\b",
            "a late-career World Cup stage",
            refined,
            flags=re.I,
        )
        refined = re.sub(r"\blast dance\b", "late-career stage", refined, flags=re.I)

    if protected.get("exact_player_age") != "verified":
        refined = re.sub(r"\bThirty-four years old\b", "Age to be confirmed", refined, flags=re.I)
        refined = re.sub(r"\b34 years old\b", "age to be confirmed", refined, flags=re.I)
        refined = re.sub(r"\bAge:\s*34\b", "Age: verify from source", refined, flags=re.I)

    refined = re.sub(
        r"\s*[^.\n]*born the same year the Berlin Wall fell[^.\n]*\.",
        "",
        refined,
        flags=re.I,
    )
    refined = refined.replace("Peter Drury", "PitchSideAI")

    missing_sections = evaluation.get("missing_sections", []) if isinstance(evaluation, dict) else []
    if missing_sections:
        refined = refined.rstrip() + "\n\n---\n\n## FORMAT COMPLETION PASS\n\n"
        for section in missing_sections:
            refined += _section_stub(section, home_team, away_team)

    unsupported_claims = evaluation.get("unsupported_claims", []) if isinstance(evaluation, dict) else []
    if unsupported_claims:
        refined = refined.rstrip() + "\n\n## Fact-Check Notes\n\n"
        for item in unsupported_claims[:8]:
            refined += f"- Revised or softened unsupported claim type: {item.get('reason', 'unsupported factual claim')}\n"

    return refined


def _find_unsupported_claims(markdown: str, fact_ledger: dict[str, Any]) -> list[dict[str, str]]:
    protected = fact_ledger.get("protected_claims", {}) if isinstance(fact_ledger, dict) else {}
    checks = [
        ("exact_h2h_count", r"\b(?:met exactly once|exactly one previous meeting)\b", "Exact H2H count needs verified H2H evidence."),
        ("no_injuries", r"\b(?:no|zero)\s+(?:reported\s+)?(?:injuries|injury concerns|availability concerns)\b", "No-injury claims need verified team-news evidence."),
        ("final_world_cup", r"\b(?:final World Cup|last dance)\b", "Final-World-Cup framing needs explicit source support."),
        ("exact_player_age", r"\b(?:Thirty-four years old|34 years old|Age:\s*34)\b", "Exact player ages need source support."),
    ]
    unsupported: list[dict[str, str]] = []
    for key, pattern, reason in checks:
        if protected.get(key) == "verified":
            continue
        for match in re.finditer(pattern, markdown, flags=re.I):
            unsupported.append({"claim": match.group(0), "reason": reason})
    if re.search(r"born the same year the Berlin Wall fell", markdown, flags=re.I):
        unsupported.append({"claim": "born the same year the Berlin Wall fell", "reason": "Biographical hook needs exact birth-year evidence."})
    return unsupported


def _section_stub(section: str, home_team: str, away_team: str) -> str:
    if section == "NARRATIVE SPINE":
        return f"### Narrative Spine\n\n- Build the opening around {home_team} vs {away_team}, then let verified team sheets and live tempo sharpen the story.\n\n"
    if section == "TEAM SHEETS":
        return "### Team Sheets\n\n- Treat all lineups as unconfirmed until official team sheets arrive.\n\n"
    if section == "PLAYER CARDS":
        return "### Player Cards\n\n- Use verified player roles, sourced squad evidence, and live touches before making form or milestone claims.\n\n"
    if section == "TACTICAL DOSSIER":
        return "### Tactical Dossier\n\n- Start with shape, territory, transition protection, and set-piece behavior visible in the opening phase.\n\n"
    if section == "SET-PIECE WATCH":
        return "### Set-Piece Watch\n\n- On the first dead ball, call delivery side, marking scheme, primary runner, and second-ball reaction.\n\n"
    if section == "LIVE TRIGGER LINES":
        return "### Live Trigger Lines\n\n- First press, first transition, first corner, and first named duel should trigger concise evidence-led lines.\n\n"
    if section == "PRONUNCIATION":
        return "### Pronunciation\n\n- Confirm pronunciations from official broadcast/team media before using phonetic notes on air.\n\n"
    if section == "MATCH FRAME":
        return f"### Match Frame\n\n- Fixture: {home_team} vs {away_team}; verify kickoff, venue, and competition before hard-selling stakes.\n\n"
    if section == "EVIDENCE STATUS":
        return "### Evidence Status\n\n- Strict evidence mode: unresolved facts must stay qualified or omitted.\n\n"
    return f"### {section.title()}\n\n- Section added by format completion pass.\n\n"
