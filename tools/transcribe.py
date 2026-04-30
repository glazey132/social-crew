from pathlib import Path
from typing import List, Union

from pipeline.schemas import ClipSegment


def transcribe_video(source_path: Union[str, Path]) -> List[ClipSegment]:
    source_path = Path(source_path)
    candidate_id = source_path.stem

    # Placeholder segmentation: first minute in two possible hooks.
    return [
        ClipSegment(
            candidate_id=candidate_id,
            start_sec=3.0,
            end_sec=32.0,
            hook_text="The first big claim that creates curiosity.",
            confidence=0.89,
        ),
        ClipSegment(
            candidate_id=candidate_id,
            start_sec=33.0,
            end_sec=58.0,
            hook_text="A concise explanation with emotional payoff.",
            confidence=0.71,
        ),
    ]

