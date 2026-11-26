"""The files the engine's own stages write or read, beside camel-studio's schemas.py (analysis, proposals)."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Loose(BaseModel):
    """Beats carry template-specific fields (ghosts, fill, x, top...): keep what we do not know."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ------------------------------------------------------------------ beats_<slug>_src.json (stage C, D, E)

class BeatLabel(Loose):
    t: float = Field(description="when this label replaces the previous one (source seconds)")
    html: str = Field(min_length=1, description="caption spelling; <em> = the gold word; <em class=\"cnt\">0</em> counts to `count`")
    count: Optional[float] = None
    countAt: Optional[float] = None
    countDur: Optional[float] = None


class Badge(Loose):
    kind: Literal["check", "gem", "ice", "shield"]
    t: float


class Beat(Loose):
    src: str = Field(description="source key (g5, t1 ...): the beat is in that source's own time")
    kind: str = Field(description="pack (jar, offer photo or a library picture via `lib`), or a disc kind of remix.md")
    side: Literal["L", "R", "T"]
    in_: float = Field(alias="in", description="start, >= 0.20 s inside the body segment that uses it")
    out: float = Field(description="end, >= 0.25 s before that segment ends")
    lib: Optional[str] = Field(None, description="library picture id; asset_lib.py place resolves img/w/h")
    img: Optional[str] = None
    w: Optional[int] = None
    h: Optional[int] = None
    x: Optional[int] = None
    top: Optional[int] = None
    key: Optional[float] = None
    fill: Optional[float] = None
    ghosts: Optional[float] = None
    keys: list[float] = []
    pops: list[float] = []
    breathe: list[float] = []
    shake: list[float] = []
    labels: list[BeatLabel] = []
    badge: Optional[Badge] = None


class Sfx(Loose):
    src: str
    file: str = Field(description="pop.mp3 | ping.mp3 | sparkle.mp3 | click-soft.mp3")
    t: float
    vol: float = 0.12


class BeatsFile(Loose):
    note: str = Field("", alias="_note")
    beats: list[Beat]
    sfx: list[Sfx] = []


class GraphicsNote(Loose):
    mix: str
    t: float
    side: str
    graphic: str
    words: str


class Drawing(Loose):
    path: str
    prompt: str = ""


class GraphicsNotes(Loose):
    beats: list[GraphicsNote] = []
    gpt_drawings: list[Drawing] = []
    unsure: list[str] = []


# ------------------------------------------------------------------ <project>/.work/revision.json (stage E)

class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changed: list[str] = Field(min_length=1, description="what changed, one line each, for the user")
    notes: str = ""


# ------------------------------------------------------------------ fresh edits (stage F)

class FreshMarks(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hook_end: float = Field(gt=0, description="x: transition 1 lands here")
    body_start: float = Field(description="y: normally x")
    cta_start: float = Field(description="z: transition 2 lands here; the CTA runs to the end")


class FreshBeat(Loose):
    t: float
    side: str
    graphic: str
    words: str


class FreshResult(Loose):
    output: str = Field(description="the finished ad's full path")
    duration: float
    loudness_after: Optional[float] = None
    peak_dbfs: Optional[float] = None
    size_mb: Optional[float] = None
    black_frames: list = []
    captions: int = 0
    beats: list[FreshBeat] = []
    library_pictures: list[str] = []
    gpt_drawings: list[Drawing] = []
    unsure: list[str] = []
    notes: str = ""


# ------------------------------------------------------------------ a new product (the New project screen)

SourceTag = Literal["finished_ad", "source", "packshot", "offer", "illustration", "ignore"]


class NewSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str = Field(description="file name inside product_dir, or a full path")
    tag: SourceTag = "finished_ad"
    label: str = ""
    note: str = ""


class NewOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    photo: str = ""
    note: str = ""


class NewProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, description="Latin name used in file names")
    name_ar: str = ""
    whisper_prompt: str = Field("", description="Darija / Arabic / French key words for Whisper")
    product_dir: str
    ads_dir: str = Field("", description="default: <product_dir>\\Ads")
    sources: list[NewSource] = Field(min_length=1)
    offers: list[NewOffer] = []
    duplicates: list[str] = []
    gpt_cap: int = 3
    name_pattern: str = "{name} Mix{nn} - {label} - {name_ar}.mp4"
    slug: Optional[str] = None
