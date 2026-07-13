"""
Batch Generator for MateMaTeX.
Generate multiple worksheets/chapters in a single operation.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class BatchJob:
    """Represents a single job in a batch."""
    id: str
    topic: str
    grade: str
    material_type: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    pdf_path: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch generation."""
    total: int
    completed: int
    failed: int
    jobs: list[BatchJob]
    output_dir: str


def create_batch_jobs(
    topics: list[str],
    grade: str,
    material_type: str = "arbeidsark"
) -> list[BatchJob]:
    """
    Create a list of batch jobs.
    
    Args:
        topics: List of topics to generate.
        grade: Grade level for all jobs.
        material_type: Material type for all jobs.
    
    Returns:
        List of BatchJob objects.
    """
    jobs = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for i, topic in enumerate(topics):
        job = BatchJob(
            id=f"{timestamp}_{i:03d}",
            topic=topic.strip(),
            grade=grade,
            material_type=material_type,
        )
        jobs.append(job)
    
    return jobs


def run_batch(
    jobs: list[BatchJob],
    run_single: Callable,
    output_dir: str = "output/batch",
    on_progress: Optional[Callable[[int, int, BatchJob], None]] = None
) -> BatchResult:
    """
    Run a batch of generation jobs.
    
    Args:
        jobs: List of BatchJob objects.
        run_single: Function to run a single job (takes grade, topic, material_type).
        output_dir: Directory for output files.
        on_progress: Callback for progress updates.
    
    Returns:
        BatchResult with all job results.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    completed = 0
    failed = 0
    
    for i, job in enumerate(jobs):
        job.status = "running"
        
        if on_progress:
            on_progress(i + 1, len(jobs), job)
        
        try:
            # Run the generation
            result = run_single(
                grade=job.grade,
                topic=job.topic,
                material_type=job.material_type,
            )
            
            job.result = result
            job.status = "completed"
            completed += 1
            
            # Save to file
            safe_topic = "".join(c for c in job.topic if c.isalnum() or c in " -_")[:30]
            filename = f"{job.id}_{safe_topic}.tex"
            filepath = Path(output_dir) / filename
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(result)
            
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            failed += 1
    
    return BatchResult(
        total=len(jobs),
        completed=completed,
        failed=failed,
        jobs=jobs,
        output_dir=output_dir
    )


def merge_batch_results(jobs: list[BatchJob], title: str = "Samlet materiale") -> str:
    """
    Merge multiple batch job results into a single document.
    
    Args:
        jobs: List of completed BatchJob objects.
        title: Title for the merged document.
    
    Returns:
        Merged LaTeX content.
    """
    import re
    
    sections = []
    
    for job in jobs:
        if job.status != "completed" or not job.result:
            continue
        
        content = job.result
        
        # Extract content between \begin{document} and \end{document}
        doc_match = re.search(
            r'\\begin\{document\}(.*)\\end\{document\}',
            content,
            re.DOTALL
        )
        
        if doc_match:
            body = doc_match.group(1)
            # Remove \maketitle and similar
            body = re.sub(r'\\maketitle', '', body)
            body = re.sub(r'\\tableofcontents', '', body)
            
            # Add topic as section if not already sectioned
            if not re.search(r'\\section\{', body[:200]):
                body = f"\\section{{{job.topic}}}\n{body}"
            
            sections.append(body)
    
    # Combine all sections
    merged_body = "\n\n\\clearpage\n\n".join(sections)
    
    # Create merged document
    merged = f"""\\documentclass[11pt, a4paper]{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage[norsk]{{babel}}
\\usepackage[margin=2.5cm]{{geometry}}
\\usepackage{{amsmath, amssymb, amsthm}}
\\usepackage{{graphicx}}
\\usepackage{{float}}
\\usepackage{{booktabs}}
\\usepackage{{enumitem}}
\\usepackage{{multicol}}
\\usepackage{{tikz}}
\\usepackage{{pgfplots}}
\\pgfplotsset{{compat=1.18}}
\\usepackage{{xcolor}}
\\usepackage[most]{{tcolorbox}}
\\usepackage{{hyperref}}

% Colors
\\definecolor{{mainBlue}}{{RGB}}{{41, 98, 255}}
\\definecolor{{mainGreen}}{{RGB}}{{0, 200, 83}}
\\definecolor{{mainOrange}}{{RGB}}{{255, 152, 0}}

% Boxes
\\newtcolorbox{{definisjon}}{{
    colback=mainBlue!5, colframe=mainBlue!75!black,
    fonttitle=\\bfseries, title=Definisjon
}}
\\newtcolorbox{{eksempel}}[1][]{{
    colback=mainGreen!5, colframe=mainGreen!75!black,
    fonttitle=\\bfseries, title=#1
}}
\\newtcolorbox{{taskbox}}[1]{{
    colback=gray!5, colframe=gray!50!black,
    fonttitle=\\bfseries, title=#1
}}
\\newtcolorbox{{merk}}{{
    colback=mainOrange!5, colframe=mainOrange!75!black,
    fonttitle=\\bfseries, title=Merk
}}
\\newtcolorbox{{losning}}{{
    colback=white, colframe=gray!50,
    fonttitle=\\bfseries, title=Løsning
}}

\\title{{{title}}}
\\author{{Generert av MateMaTeX AI}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle
\\tableofcontents
\\clearpage

{merged_body}

\\end{{document}}
"""
    
    return merged


def get_batch_summary(result: BatchResult) -> dict:
    """
    Get a summary of batch results.
    
    Args:
        result: BatchResult object.
    
    Returns:
        Summary dictionary.
    """
    topics_completed = [j.topic for j in result.jobs if j.status == "completed"]
    topics_failed = [j.topic for j in result.jobs if j.status == "failed"]
    errors = {j.topic: j.error for j in result.jobs if j.error}
    
    return {
        "total": result.total,
        "completed": result.completed,
        "failed": result.failed,
        "success_rate": (result.completed / result.total * 100) if result.total > 0 else 0,
        "topics_completed": topics_completed,
        "topics_failed": topics_failed,
        "errors": errors,
        "output_dir": result.output_dir,
    }


def estimate_batch_time(num_jobs: int, material_type: str = "arbeidsark") -> tuple[int, int]:
    """
    Estimate time for batch generation.
    
    Args:
        num_jobs: Number of jobs.
        material_type: Type of material.
    
    Returns:
        Tuple of (min_minutes, max_minutes).
    """
    # Base time per job (in minutes)
    time_per_job = {
        "arbeidsark": (2, 4),
        "kapittel": (4, 8),
        "prøve": (3, 5),
        "lekseark": (1, 3),
    }
    
    base_min, base_max = time_per_job.get(material_type, (2, 4))
    
    # Add some overhead for batch processing
    total_min = int(num_jobs * base_min * 0.9)  # Slight optimization for batch
    total_max = int(num_jobs * base_max * 1.1)  # Buffer for failures/retries
    
    return (max(1, total_min), max(2, total_max))
