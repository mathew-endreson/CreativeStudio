"""The files the engine's own stages write or read, beside camel-studio's schemas.py (analysis, proposals)."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Loose(BaseModel):
    """Keep what we do not know: place adds img / w / h / x / top, and beats files from before Nov 26 2026 carry
    the old disc / jar fields (labels, fill, ghosts, badge, pops ...). Those files still load; build drops such beats."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)


# ------------------------------------------------------------------ beats_<slug>_src.json (stage C, D, E)

ASSET = "asset"
ASSET_SIDES = ("C", "L", "R")


class Beat(Loose):
    """One of the product's pictures, animated in front of the speaker by the caption (references/remix.md,
    "Remix + animated assets in the body"). Times are in the source's own time."""
    src: str = Field(description="source key (g5, t1 ...): the beat is in that source's own time")
    kind: str = Field(ASSET, description='"asset": a picture of the product\'s library. (Older files hold disc / jar '
                                         "kinds: they show nothing any more and remix_broll.py drops them.)")
    lib: Optional[str] = Field(None, description="the picture's id in the product's library.json; asset_lib.py place "
                                                 "fills img / w / h / x / top from it")
    side: str = Field("C", description='"C" (centred by the caption); "L" or "R" only where his hands or the product '
                                       "are in the way")
    in_: float = Field(alias="in", description="start, about 0.25 s before the first word that names it; >= 0.20 s "
                                               "inside the body segment that uses it")
    out: float = Field(description="end (it shrinks away from out - 0.30); >= 0.25 s before that segment ends")
    keys: list[float] = Field([], description="pop + glint on the key word (the picture's motion shine or none)")
    breathe: list[float] = Field([], description="slow swell on the word (motion breathe: lungs, breath, sleep)")
    shake: list[float] = Field([], description="shudder on the word (motion shake: cough, pain)")
    bottom: Optional[float] = Field(None, description="the picture's bottom edge in px, only where this shot's "
                                                    "burned-in caption sits higher than the default")
    size: Optional[float] = Field(None, description="max side in px when it must be smaller than the default 380")
    x: Optional[float] = Field(None, description="left edge in px, only to move it by hand")
    mirror: Optional[bool] = None

    def is_asset(self):
        return self.kind == ASSET and bool(self.lib)

    def key_times(self):
        return list(self.keys) + list(self.breathe) + list(self.shake)


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
    t: float = Field(description="in the mix's own time")
    side: str = "C"
    graphic: str = Field(description="the picture's library id")
    words: str = Field(description="what he says on it")


class Drawing(Loose):
    path: str
    prompt: str = ""


class Missing(Loose):
    """An idea he names that no picture of the library shows: the user uploads one (or asks GPT to draw it)."""
    concept: str
    words: str = ""
    src: str = ""
    t: Optional[float] = None


class GraphicsNotes(Loose):
    beats: list[GraphicsNote] = []
    missing: list[Missing] = []
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
    side: str = "C"
    graphic: str = Field(description="the picture's library id")
    words: str = Field(description="what he says on it")


class FreshResult(Loose):
    output: str = Field(description="the finished ad's full path")
    duration: float
    loudness_after: Optional[float] = None
    peak_dbfs: Optional[float] = None
    size_mb: Optional[float] = None
    black_frames: list = []
    captions: int = 0
    beats: list[FreshBeat] = Field([], description="every asset of index.html's ILLUS slot, in time order")
    library_pictures: list[str] = Field([], description="the library ids used")
    missing: list[Missing] = Field([], description="ideas he names that no picture shows, for the user to upload")
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
    asset_bottom: Optional[int] = Field(None, ge=600, le=1800, description="the pictures' bottom edge in px when this "
                                        "product's burned-in captions sit high (default 1260)")
    name_pattern: str = "{name} Mix{nn} - {label} - {name_ar}.mp4"
    slug: Optional[str] = None


# ------------------------------------------------------------------ more pictures for a product (asset folder)

class NewPicture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str = Field(description="full path, or a file name inside product_dir")
    tag: Literal["packshot", "offer", "illustration"] = Field(
        "illustration", description="packshot = the jar on a white background (cut out with --symmetric); offer = the "
                                    "offer photo; illustration = any other picture (a herb, a moon, an organ)")
    label: str = ""
    note: str = ""


class AddPictures(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[NewPicture] = []
    asset_bottom: Optional[int] = Field(None, ge=600, le=1800)
    clear_asset_bottom: bool = False
    reindex: bool = Field(False, description="index the folder again (pictures dropped into it by hand)")
