from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from core.providers import (
    MusicMatch,
    MusicRecognitionProvider,
)


logger = logging.getLogger(__name__)


# ============================================================
# SETTINGS
# ============================================================

# یک نتیجه‌ی تنها با confidence پایین قبول نمی‌شود.
MIN_SINGLE_CONFIDENCE = 75.0

# برای نتیجه‌ی تکرارشونده:
MIN_REPEATED_BEST_CONFIDENCE = 55.0
MIN_REPEATED_AVERAGE_CONFIDENCE = 45.0

# نتیجه‌ی خیلی قوی یک provider
MIN_STRONG_CONFIDENCE = 95.0

# Providerهایی مثل AudD که confidence ندارند.
MIN_UNSCORED_HITS = 2
MIN_UNSCORED_COVERAGE = 0.50

MAX_CONFIDENCE = 100.0
MIN_CONFIDENCE = 0.0


# ============================================================
# INTERNAL RESULT
# ============================================================

@dataclass
class RecognitionObservation:
    match: MusicMatch
    sample_index: int


@dataclass
class Candidate:
    title: str
    artist: str
    album: Optional[str]

    observations: list[RecognitionObservation] = field(
        default_factory=list
    )

    sample_indexes: set[int] = field(
        default_factory=set
    )

    provider_names: set[str] = field(
        default_factory=set
    )

    numeric_confidences: list[float] = field(
        default_factory=list
    )

    unscored_sample_indexes: set[int] = field(
        default_factory=set
    )

    best_confidence: float = 0.0
    average_confidence: float = 0.0

    coverage: float = 0.0
    provider_count: int = 0

    internal_score: float = 0.0


# ============================================================
# SERVICE
# ============================================================

class MusicRecognitionService:

    def __init__(
        self,
        providers: Iterable[MusicRecognitionProvider],
    ):
        self.providers = list(providers)

    # ========================================================
    # PUBLIC API
    # ========================================================

    async def recognize(
        self,
        audio_samples: list[str | Path],
    ) -> Optional[MusicMatch]:

        if not audio_samples:
            logger.warning(
                "NO AUDIO SAMPLES PROVIDED"
            )
            return None

        total_samples = len(audio_samples)

        logger.info(
            "MUSIC RECOGNITION START: "
            "samples=%d providers=%d",
            total_samples,
            len(self.providers),
        )

        observations: list[RecognitionObservation] = []

        # ----------------------------------------------------
        # Every provider against every sample
        # ----------------------------------------------------

        for sample_index, sample_path in enumerate(
            audio_samples,
            start=1,
        ):

            sample_path = str(sample_path)

            logger.info(
                "CHECKING SAMPLE %d/%d: %s",
                sample_index,
                total_samples,
                sample_path,
            )

            for provider in self.providers:

                provider_name = (
                    provider.__class__.__name__
                )

                try:
                    result = await self._recognize_provider(
                        provider=provider,
                        audio_path=sample_path,
                        sample_index=sample_index,
                    )

                except Exception as error:

                    logger.exception(
                        "MUSIC PROVIDER ERROR "
                        "[%s] sample=%d: %s",
                        provider_name,
                        sample_index,
                        error,
                    )

                    continue

                if result is None:

                    logger.info(
                        "NO MATCH: %s sample=%d",
                        provider_name,
                        sample_index,
                    )

                    continue

                # ------------------------------------------------
                # Provider metadata
                # ------------------------------------------------

                if not result.provider:
                    result.provider = (
                        provider_name
                    )

                result.sample_index = sample_index

                # ------------------------------------------------
                # Confidence normalization
                #
                # IMPORTANT:
                # None remains None.
                # ------------------------------------------------

                result.confidence = (
                    self._normalize_confidence(
                        result.confidence
                    )
                )

                if not self._valid_match(result):
                    logger.warning(
                        "INVALID MATCH IGNORED: "
                        "%s sample=%d",
                        provider_name,
                        sample_index,
                    )
                    continue

                observations.append(
                    RecognitionObservation(
                        match=result,
                        sample_index=sample_index,
                    )
                )

                logger.info(
                    "MATCH: provider=%s "
                    "sample=%d "
                    "artist=%s "
                    "title=%s "
                    "confidence=%s",
                    result.provider,
                    sample_index,
                    result.artist,
                    result.title,
                    (
                        f"{result.confidence:.2f}"
                        if result.confidence is not None
                        else "N/A"
                    ),
                )

        # ----------------------------------------------------
        # Nothing found
        # ----------------------------------------------------

        if not observations:

            logger.warning(
                "NO MUSIC MATCHES FOUND"
            )

            return None

        # ----------------------------------------------------
        # Build candidates
        # ----------------------------------------------------

        candidates = self._build_candidates(
            observations=observations,
            total_samples=total_samples,
        )

        if not candidates:

            logger.warning(
                "NO VALID MUSIC CANDIDATES"
            )

            return None

        # ----------------------------------------------------
        # Log every candidate
        # ----------------------------------------------------

        logger.info(
            "================ MUSIC CANDIDATES ================"
        )

        for candidate in sorted(
            candidates,
            key=self._sort_key,
            reverse=True,
        ):

            logger.info(
                (
                    "candidate=%s - %s | "
                    "samples=%s/%d | "
                    "coverage=%.2f | "
                    "providers=%d | "
                    "best=%.2f | "
                    "avg=%.2f | "
                    "unscored=%d | "
                    "score=%.2f"
                ),
                candidate.artist,
                candidate.title,
                sorted(candidate.sample_indexes),
                total_samples,
                candidate.coverage,
                candidate.provider_count,
                candidate.best_confidence,
                candidate.average_confidence,
                len(candidate.unscored_sample_indexes),
                candidate.internal_score,
            )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # First validate ALL candidates.
        # Then rank accepted candidates.
        #
        # This fixes the old bug where candidate #1 was rejected
        # and the service immediately returned None.
        # ----------------------------------------------------

        accepted: list[Candidate] = []

        for candidate in candidates:

            is_valid, reason = (
                self._validate_candidate(
                    candidate=candidate,
                    total_samples=total_samples,
                )
            )

            if is_valid:

                logger.info(
                    "CANDIDATE ACCEPTED: "
                    "%s - %s | %s",
                    candidate.artist,
                    candidate.title,
                    reason,
                )

                accepted.append(candidate)

            else:

                logger.info(
                    "CANDIDATE REJECTED: "
                    "%s - %s | %s",
                    candidate.artist,
                    candidate.title,
                    reason,
                )

        if not accepted:

            logger.warning(
                "NO CANDIDATE PASSED VALIDATION"
            )

            return None

        # ----------------------------------------------------
        # Rank accepted candidates only
        # ----------------------------------------------------

        accepted.sort(
            key=self._sort_key,
            reverse=True,
        )

        winner = accepted[0]

        logger.info(
            (
                "FINAL WINNER: %s - %s | "
                "samples=%s/%d | "
                "coverage=%.2f | "
                "providers=%d | "
                "best=%.2f | "
                "avg=%.2f"
            ),
            winner.artist,
            winner.title,
            sorted(winner.sample_indexes),
            total_samples,
            winner.coverage,
            winner.provider_count,
            winner.best_confidence,
            winner.average_confidence,
        )

        return self._create_final_match(
            candidate=winner,
        )

    # ========================================================
    # PROVIDER CALL
    # ========================================================

    async def _recognize_provider(
        self,
        provider: MusicRecognitionProvider,
        audio_path: str,
        sample_index: int,
    ) -> Optional[MusicMatch]:

        """
        همه‌ی providerهای جدید sample_index را قبول می‌کنند.

        برای جلوگیری از شکستن providerهای قدیمی، اگر provider
        هنوز signature قدیمی داشته باشد، fallback داریم.
        """

        try:

            return await provider.recognize(
                audio_path,
                sample_index=sample_index,
            )

        except TypeError as error:

            # فقط برای compatibility با provider قدیمی.
            message = str(error)

            if (
                "sample_index" not in message
                and "unexpected keyword" not in message
            ):
                raise

            logger.warning(
                "Provider %s uses legacy recognize() "
                "signature.",
                provider.__class__.__name__,
            )

            result = await provider.recognize(
                audio_path
            )

            if result is not None:
                result.sample_index = sample_index

            return result

    # ========================================================
    # BUILD CANDIDATES
    # ========================================================

    def _build_candidates(
        self,
        observations: list[RecognitionObservation],
        total_samples: int,
    ) -> list[Candidate]:

        exact_groups: dict[
            str,
            Candidate,
        ] = {}

        # ----------------------------------------------------
        # First pass:
        # exact normalized artist + title
        # ----------------------------------------------------

        for observation in observations:

            match = observation.match

            key = self._make_exact_key(
                artist=match.artist,
                title=match.title,
            )

            candidate = exact_groups.get(key)

            if candidate is None:

                candidate = Candidate(
                    title=match.title.strip(),
                    artist=match.artist.strip(),
                    album=match.album,
                )

                exact_groups[key] = candidate

            candidate.observations.append(
                observation
            )

            candidate.sample_indexes.add(
                observation.sample_index
            )

            provider_name = (
                match.provider
                or "unknown"
            ).strip().lower()

            candidate.provider_names.add(
                provider_name
            )

            if match.confidence is None:

                candidate.unscored_sample_indexes.add(
                    observation.sample_index
                )

            else:

                candidate.numeric_confidences.append(
                    match.confidence
                )

        candidates = list(
            exact_groups.values()
        )

        # ----------------------------------------------------
        # Second pass:
        # merge very obvious title variants.
        #
        # Example:
        #
        # Death Rattle
        # Death Rattle (Slowed)
        # Death Rattle (BEST PART SLOWED)
        #
        # We only do this when the core title is strongly equal
        # and at least one side is unscored.
        # ----------------------------------------------------

        candidates = self._merge_safe_title_variants(
            candidates
        )

        # ----------------------------------------------------
        # Calculate statistics
        # ----------------------------------------------------

        for candidate in candidates:

            if total_samples > 0:

                candidate.coverage = (
                    len(candidate.sample_indexes)
                    / total_samples
                )

            if candidate.numeric_confidences:

                candidate.best_confidence = max(
                    candidate.numeric_confidences
                )

                candidate.average_confidence = (
                    sum(
                        candidate.numeric_confidences
                    )
                    / len(
                        candidate.numeric_confidences
                    )
                )

            candidate.provider_count = len(
                candidate.provider_names
            )

            candidate.internal_score = (
                self._calculate_internal_score(
                    candidate
                )
            )

        return candidates

    # ========================================================
    # SAFE TITLE MERGE
    # ========================================================

    def _merge_safe_title_variants(
        self,
        candidates: list[Candidate],
    ) -> list[Candidate]:

        changed = True

        while changed:

            changed = False

            for i in range(
                len(candidates)
            ):

                if changed:
                    break

                first = candidates[i]

                for j in range(
                    i + 1,
                    len(candidates),
                ):

                    second = candidates[j]

                    if not self._safe_variant_merge(
                        first,
                        second,
                    ):
                        continue

                    # ------------------------------------------------
                    # Merge second into first
                    # ------------------------------------------------

                    first.observations.extend(
                        second.observations
                    )

                    first.sample_indexes.update(
                        second.sample_indexes
                    )

                    first.provider_names.update(
                        second.provider_names
                    )

                    first.numeric_confidences.extend(
                        second.numeric_confidences
                    )

                    first.unscored_sample_indexes.update(
                        second.unscored_sample_indexes
                    )

                    if not first.album:
                        first.album = second.album

                    # Prefer the cleaner title.
                    first.title = (
                        self._choose_clean_title(
                            first.title,
                            second.title,
                        )
                    )

                    candidates.pop(j)

                    changed = True
                    break

        return candidates

    def _safe_variant_merge(
        self,
        first: Candidate,
        second: Candidate,
    ) -> bool:

        first_title = self._normalize_title_core(
            first.title
        )

        second_title = self._normalize_title_core(
            second.title
        )

        if not first_title or not second_title:
            return False

        if first_title != second_title:
            return False

        # Do not blindly merge two independently confident
        # results from different artists.
        #
        # We allow this merge mainly when an unscored provider
        # is involved, because this is exactly where providers
        # commonly disagree on remix/uploader naming.
        #

        first_has_unscored = bool(
            first.unscored_sample_indexes
        )

        second_has_unscored = bool(
            second.unscored_sample_indexes
        )

        if (
            not first_has_unscored
            and not second_has_unscored
        ):
            return False

        return True

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_candidate(
        self,
        candidate: Candidate,
        total_samples: int,
    ) -> tuple[bool, str]:

        sample_hits = len(
            candidate.sample_indexes
        )

        if sample_hits <= 0:
            return (
                False,
                "no sample hits",
            )

        coverage = candidate.coverage

        # ----------------------------------------------------
        # Strong repeated numeric match
        # ----------------------------------------------------

        if (
            sample_hits >= 2
            and coverage >= 0.50
            and candidate.best_confidence
            >= MIN_REPEATED_BEST_CONFIDENCE
            and candidate.average_confidence
            >= MIN_REPEATED_AVERAGE_CONFIDENCE
        ):
            return (
                True,
                "repeated numeric recognition",
            )

        # ----------------------------------------------------
        # Very strong result
        #
        # ACRCloud 95+ is accepted only when the average is
        # also strong. This avoids blindly trusting a single
        # weird 100 score.
        # ----------------------------------------------------

        if (
            candidate.best_confidence
            >= MIN_STRONG_CONFIDENCE
            and candidate.average_confidence
            >= 70.0
        ):
            return (
                True,
                "very strong numeric recognition",
            )

        # ----------------------------------------------------
        # AudD / unscored repeated result
        # ----------------------------------------------------

        if (
            len(candidate.unscored_sample_indexes)
            >= MIN_UNSCORED_HITS
            and coverage
            >= MIN_UNSCORED_COVERAGE
        ):
            return (
                True,
                "repeated unscored recognition",
            )

        # ----------------------------------------------------
        # Cross-provider agreement
        #
        # If two providers agree on the same track in the same
        # sample but only one has confidence, don't automatically
        # accept it.
        #
        # Accuracy > aggressive guessing.
        # ----------------------------------------------------

        if (
            sample_hits >= 2
            and candidate.provider_count >= 2
            and candidate.best_confidence >= 65.0
            and coverage >= 0.50
        ):
            return (
                True,
                "multi-provider repeated recognition",
            )

        # ----------------------------------------------------
        # Single sample
        # ----------------------------------------------------

        if sample_hits == 1:

            if (
                candidate.best_confidence
                >= MIN_SINGLE_CONFIDENCE
                and candidate.average_confidence
                >= MIN_SINGLE_CONFIDENCE
            ):
                return (
                    True,
                    "single very strong recognition",
                )

            return (
                False,
                "single sample is insufficient",
            )

        return (
            False,
            "insufficient evidence",
        )

    # ========================================================
    # INTERNAL SCORE
    # ========================================================

    @staticmethod
    def _calculate_internal_score(
        candidate: Candidate,
    ) -> float:

        score = 0.0

        # Coverage is the strongest signal.
        score += (
            candidate.coverage * 50.0
        )

        # Repeated sample bonus.
        if len(candidate.sample_indexes) >= 2:

            score += min(
                len(candidate.sample_indexes)
                * 7.5,
                30.0,
            )

        # Numeric confidence.
        if candidate.numeric_confidences:

            score += (
                candidate.best_confidence
                * 0.15
            )

            score += (
                candidate.average_confidence
                * 0.10
            )

        # Provider agreement.
        if candidate.provider_count >= 2:
            score += 10.0

        return min(
            score,
            100.0,
        )

    # ========================================================
    # SORT
    # ========================================================

    @staticmethod
    def _sort_key(
        candidate: Candidate,
    ) -> tuple:

        return (
            len(candidate.sample_indexes),
            candidate.coverage,
            candidate.provider_count,
            candidate.best_confidence,
            candidate.average_confidence,
            candidate.internal_score,
        )

    # ========================================================
    # FINAL MATCH
    # ========================================================

    def _create_final_match(
        self,
        candidate: Candidate,
    ) -> MusicMatch:

        observations = candidate.observations

        if not observations:
            raise RuntimeError(
                "Candidate has no observations."
            )

        # ----------------------------------------------------
        # Pick strongest response
        # ----------------------------------------------------

        best_observation = max(
            observations,
            key=lambda observation: (
                1
                if observation.match.confidence
                is not None
                else 0,
                observation.match.confidence
                or 0.0,
            ),
        )

        best_match = best_observation.match

        # ----------------------------------------------------
        # Confidence
        #
        # This is the ONLY confidence sent to UI.
        # It is always 0..100.
        # ----------------------------------------------------

        if candidate.numeric_confidences:

            confidence = (
                candidate.best_confidence
            )

            # Small bonus for repeated confirmation.
            repeated_hits = len(
                candidate.sample_indexes
            )

            if repeated_hits >= 2:

                confidence += min(
                    (repeated_hits - 1) * 3.0,
                    9.0,
                )

            confidence = min(
                confidence,
                100.0,
            )

        else:

            # No provider supplied a numeric confidence.
            #
            # Use coverage only as a confidence proxy.
            confidence = (
                candidate.coverage * 100.0
            )

            if candidate.provider_count >= 2:
                confidence += 5.0

            confidence = min(
                confidence,
                100.0,
            )

        # ----------------------------------------------------
        # Track ID
        # ----------------------------------------------------

        track_id = self._first_value(
            observation.match.track_id
            for observation in observations
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        url = self._first_value(
            observation.match.url
            for observation in observations
        )

        # ----------------------------------------------------
        # Album
        # ----------------------------------------------------

        album = candidate.album

        if not album:
            album = self._first_value(
                observation.match.album
                for observation in observations
            )

        return MusicMatch(
            title=candidate.title,
            artist=candidate.artist,
            album=album,
            confidence=round(
                max(
                    0.0,
                    min(
                        confidence,
                        100.0,
                    ),
                ),
                2,
            ),
            provider=best_match.provider,
            track_id=track_id,
            url=url,
            sample_index=None,
        )

    # ========================================================
    # EXACT KEY
    # ========================================================

    def _make_exact_key(
        self,
        artist: str,
        title: str,
    ) -> str:

        return (
            self._normalize_artist(artist)
            + "|||"
            + self._normalize_title(title)
        )

    # ========================================================
    # ARTIST NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_artist(
        value: str,
    ) -> str:

        if not value:
            return ""

        value = unicodedata.normalize(
            "NFKC",
            str(value),
        ).lower()

        value = value.replace(
            "&",
            " and ",
        )

        value = re.sub(
            r"\b(feat|ft|featuring)\b",
            " ",
            value,
        )

        value = re.sub(
            r"[^\w\s]",
            " ",
            value,
            flags=re.UNICODE,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    # ========================================================
    # TITLE NORMALIZATION
    # ========================================================

    @staticmethod
    def _normalize_title(
        value: str,
    ) -> str:

        if not value:
            return ""

        value = unicodedata.normalize(
            "NFKC",
            str(value),
        ).lower()

        # Normalize common separators.
        value = value.replace(
            "&",
            " and ",
        )

        value = re.sub(
            r"\b(feat|ft|featuring)\b.*",
            " ",
            value,
        )

        # Remove common release/version markers.
        value = re.sub(
            r"\b("
            r"remix|"
            r"edit|"
            r"radio edit|"
            r"extended|"
            r"version|"
            r"original mix|"
            r"instrumental|"
            r"official video|"
            r"official audio|"
            r"slowed|"
            r"sped up|"
            r"speed up|"
            r"reverb|"
            r"nightcore|"
            r"8d"
            r")\b",
            " ",
            value,
        )

        value = re.sub(
            r"[\(\[\{].*?[\)\]\}]",
            " ",
            value,
        )

        value = re.sub(
            r"[^\w\s]",
            " ",
            value,
            flags=re.UNICODE,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @staticmethod
    def _normalize_title_core(
        value: str,
    ) -> str:

        return MusicRecognitionService._normalize_title(
            value
        )

    # ========================================================
    # CHOOSE CLEAN TITLE
    # ========================================================

    @staticmethod
    def _choose_clean_title(
        first: str,
        second: str,
    ) -> str:

        first_core = (
            MusicRecognitionService
            ._normalize_title_core(first)
        )

        second_core = (
            MusicRecognitionService
            ._normalize_title_core(second)
        )

        if first_core == second_core:

            # Prefer title with less technical metadata.
            first_noise = len(first) - len(
                first_core
            )

            second_noise = len(second) - len(
                second_core
            )

            if first_noise <= second_noise:
                return first.strip()

            return second.strip()

        return first.strip()

    # ========================================================
    # VALID MATCH
    # ========================================================

    @staticmethod
    def _valid_match(
        match: MusicMatch,
    ) -> bool:

        if not match.title:
            return False

        if not match.artist:
            return False

        title = str(
            match.title
        ).strip()

        artist = str(
            match.artist
        ).strip()

        if not title:
            return False

        if not artist:
            return False

        if title.lower() in {
            "unknown",
            "unknown title",
            "untitled",
        }:
            return False

        return True

    # ========================================================
    # CONFIDENCE
    # ========================================================

    @staticmethod
    def _normalize_confidence(
        value: Optional[float],
    ) -> Optional[float]:

        # VERY IMPORTANT:
        # None means "provider did not provide confidence".
        #
        # It must NOT become 0.
        #

        if value is None:
            return None

        try:
            number = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if number != number:
            return None

        if number == float("inf"):
            return 100.0

        if number == float("-inf"):
            return 0.0

        # Some APIs use 0..1.
        if 0.0 < number <= 1.0:
            number *= 100.0

        number = max(
            0.0,
            number,
        )

        number = min(
            100.0,
            number,
        )

        return round(
            number,
            2,
        )

    # ========================================================
    # UTILITY
    # ========================================================

    @staticmethod
    def _first_value(
        values,
    ) -> Optional[str]:

        for value in values:

            if value is None:
                continue

            value = str(
                value
            ).strip()

            if value:
                return value

        return None


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

MusicService = MusicRecognitionService
RecognitionService = MusicRecognitionService