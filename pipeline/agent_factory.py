from crewai import Agent, Crew, LLM, Task
from crewai.tools import tool

from tools.research import discover_candidates
from tools.transcribe import transcribe_video


def build_social_crew(llm_model: str, llm_base_url: str) -> Crew:
    llm = LLM(model=llm_model, base_url=llm_base_url)

    @tool("discover_candidates")
    def discover_candidates_tool(limit: int = 5) -> str:
        """Find candidate videos and return compact metadata."""
        candidates = discover_candidates(limit=limit)
        return "\n".join([f"{c.id} | {c.title} | score={c.score():.2f} | {c.url}" for c in candidates])

    @tool("transcribe_video")
    def transcribe_video_tool(path: str) -> str:
        """Create clip segment suggestions for a source video path."""
        segments = transcribe_video(path)
        return "\n".join(
            [
                f"{s.candidate_id} | {s.start_sec:.1f}-{s.end_sec:.1f}s | "
                f"confidence={s.confidence:.2f} | {s.hook_text}"
                for s in segments
            ]
        )

    researcher = Agent(
        role="Trend Researcher",
        goal="Find high-engagement long videos suitable for short clips.",
        backstory="You identify viral videos with strong hooks and replay value.",
        llm=llm,
        tools=[discover_candidates_tool],
        verbose=True,
    )

    clipper = Agent(
        role="Video Clipper & Editor",
        goal="Select best moments and define 15-60 second vertical clips.",
        backstory="You optimize clips for retention with clear hooks and subtitles.",
        llm=llm,
        tools=[transcribe_video_tool],
        verbose=True,
    )

    verifier = Agent(
        role="Quality Verifier",
        goal="Score clips and flag policy or quality issues before approval.",
        backstory="You maximize upload quality and reduce platform risk.",
        llm=llm,
        verbose=True,
    )

    tasks = [
        Task(
            description="Review candidate metadata and return top picks ranked by engagement potential.",
            expected_output="A ranked list with reasons and confidence scores.",
            agent=researcher,
        ),
        Task(
            description="Propose strongest short-form clip moments from selected candidates.",
            expected_output="Clip timings and hook text for each selected video.",
            agent=clipper,
        ),
        Task(
            description="Score each clip and flag any risk or revision requirements.",
            expected_output="Per-clip score, recommendation, and policy flags.",
            agent=verifier,
        ),
    ]

    return Crew(agents=[researcher, clipper, verifier], tasks=tasks, verbose=2)

