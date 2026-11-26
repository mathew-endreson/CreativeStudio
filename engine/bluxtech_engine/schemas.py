"""The shape of every file a judgment step writes. The app validates against these; the wording of what each
field means goes to Claude with the prompt (the field descriptions are the instructions)."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


SAID = ("what he actually says here, in clean spoken Algerian Darija, the way a caption would write it "
        "(camel-style.md section 2: digits for quantities, 'إي بوكس'): Whisper's slips fixed from the burned-in "
        "caption and the sense, nothing added or polished into standard Arabic. This is what the user reads")


# ------------------------------------------------------------------ analysis.json (stage A)

class Flash(Strict):
    f0: int = Field(description="first frame of the flash (30 fps)")
    f1: int = Field(description="last frame of the flash")
    white: bool = Field(False, description="near-white: it must be hidden under a v1 hold when this hook is reused")


class Busy(Strict):
    a: float
    b: float
    side: Literal["L", "R", "T", "both", "full"] = Field(
        description="where a graphic behind the speaker would clash: L / R side slot, T above the head, both sides "
                    "(a full-width title), or full (full-screen B-roll, the phone-mockup CTA)")
    what: str = Field(description="what is burned in there: 'two-line orange title', 'photo card', 'lab footage' ...")


class Defect(Strict):
    kind: Literal["phase_inverted", "black_frames", "fade_in", "caption_typo", "dissolve_ghost", "stray_caption",
                  "audio", "other"]
    a: Optional[float] = None
    b: Optional[float] = None
    note: str = Field(description="what is wrong and what a remix must do about it; for caption_typo quote the typo")


class Line(Strict):
    a0: float = Field(description="start: in a silence >= 0.12 s, on the editor's own cut, or right after a flash")
    a1: float = Field(description="end, same rule")
    v0: Optional[float] = Field(None, description="first clean picture time when the frames at a0 are a flash, a "
                                                  "dissolve tail or the previous shot's caption; else null")
    v1: Optional[float] = Field(None, description="the time of the last clean frame before a flash / dissolve at a1; "
                                                  "else null. (multi_join.py's v1 is an exclusive end: the picture "
                                                  "shows up to the frame before it and holds that one, which is clean too.)")
    role: Literal["hook", "body", "cta"]
    text: str = Field(description="the exact transcript of the line, as Whisper wrote it (kept for keyword matching)")
    said: str = Field(min_length=1, description=SAID)
    can_open_body: bool = Field(False, description="a self-contained sentence a body may start on under another "
                                                   "hook (never a line that answers its own hook)")
    note: str = ""


class SourceAnalysis(Strict):
    label: str = Field(description="short name used in ad names: V5, S2V4 ...")
    summary: str = Field(description="one line: what this ad argues")
    hook_end: float = Field(description="the audio cut between hook and body: the silence after the hook's last word, "
                                        "at its flash. A hook segment ends here (a1) and this source's body starts "
                                        "its audio here (a0)")
    hook_flash: Optional[Flash] = Field(None, description="the hook's own flash, the whole tinted range; null when "
                                                          "the edit only has cuts")
    hook_hold: Optional[float] = Field(None, description="v1 for this hook: the time of the last clean frame before a "
                                       "near-white flash, or before a tint that starts while he still speaks; else null")
    hook_kind: Literal["claim", "question", "setup", "testimonial", "symptom", "other"]
    hook_needs_payoff: bool = Field(False, description="a setup hook that only works with its payoff line")
    body_start: float = Field(description="the body's first clean picture frame after the flash: the v0 of the body's "
                                          "first segment (its audio starts at hook_end)")
    cta_start: Optional[float] = Field(None, description="where the CTA starts; null if there is none")
    offer_group: str = Field(description="id of the offer group (same offer on the table)")
    shoot: str = Field(description="the set / shoot: place, clothes, table. Two sources match only if these do")
    busy: list[Busy] = []
    defects: list[Defect] = []
    lines: list[Line] = Field([], description="the whole ad split at its clean cut points, in order")
    notes: str = ""
    edited: list[str] = Field([], description="fields the user set by hand in the app: keep their values")


class OfferGroup(Strict):
    id: str
    label: str = Field(description="what is on offer, as he says it: '1 kg + 100 g seeds'")
    sources: list[str]


class Duplicate(Strict):
    sources: list[str]
    note: str = Field(description="what they share: 'g7 = g5's hook + its own body'")


class Liftable(Strict):
    id: str = Field(description="L1, L2 ...")
    src: str
    a0: float
    a1: float
    v0: Optional[float] = None
    v1: Optional[float] = None
    kind: Literal["testimonial", "claim", "price", "proof", "other"]
    label: str = Field(description="one or two Latin words for the ad name: Anemie, Rare, Analyse, Temoignage")
    text: str = Field(description="the exact transcript, as Whisper wrote it")
    said: str = Field(min_length=1, description=SAID)
    why: str = Field(description="why it works as a hook, and anything it needs (its payoff, a clean frame)")


class Analysis(Strict):
    version: int = 1
    sources: dict[str, SourceAnalysis]
    offer_groups: list[OfferGroup]
    duplicates: list[Duplicate] = []
    liftable: list[Liftable] = []
    notes: str = ""


# ------------------------------------------------------------------ work/proposed.json (stage B)
# What Claude proposes. The app gives each ad its id, name and file name (the numbering is mechanical), works
# out its length, its cutout cost and its cut checks with batch.py, and merges it into proposals.json.

class PSeg(Strict):
    src: str
    a0: float = Field(description="start of the span (audio and length), frame-exact")
    a1: float
    v0: Optional[float] = Field(None, description="first clean picture time, cloned back to a0 (hides a flash, a "
                                                  "dissolve tail, the previous shot's caption); else null")
    v1: Optional[float] = Field(None, description="time of the last clean frame, held to a1; else null")
    said: str = Field("", description="what he says in this segment, clean Darija (the analysis lines' `said`)")
    note: str = Field("", description="why the cut is here and what a hold hides, when it is not obvious")


class Graphic(Strict):
    on: str = Field(description="the words it lands on, as said")
    kind: Literal["disc", "pack", "offer", "library", "missing"] = Field(
        description="disc = a line-icon disc of remix.md; pack = the product jar; offer = the offer photo; library = "
                    "a picture that is in the GPT library; missing = a picture GPT would have to draw")
    what: str = Field(description="the disc kind (lab, shield, people ...), 'jar', the library picture id, or for "
                                  "missing the concept to draw")
    label: str = Field("", description="the on-screen label, in caption spelling")
    existing: bool = Field(False, description="this beat is already written in the product's beats file")


class ProposedAd(Strict):
    key: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=24,
                     description="short slug for the project id, like the earlier ones: analyse7-b5, h6-b5b6")
    label: str = Field(description="the name after 'MixNN - ': Hook Analyse V7 + Body V5")
    segs: list[PSeg] = Field(min_length=2)
    body: list[int] = Field(min_length=1, description="indices of the segments that carry B-roll; never 0. The CTA's "
                                                      "index goes here too only when body and CTA are one take")
    cta: Optional[int] = Field(None, description="index of the CTA segment (its own segment, last)")
    hook_beats: bool = Field(False, description="segment 0 is a hook lifted from a body: it keeps its beats and cutout")
    angle: str = Field(description="the ad's angle in one line")
    why: str = Field(description="why hook, body and CTA read as one argument a viewer can follow")
    risks: list[str] = Field([], description="what could go wrong on screen or in the argument; empty if nothing")
    graphics: list[Graphic] = Field([], description="the graphic each body line (and a lifted hook) would get")


class Proposed(Strict):
    ads: list[ProposedAd]
    notes: str = ""
