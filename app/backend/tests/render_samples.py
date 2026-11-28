"""Not a test. Converts the synthetic fixture documents to DOCX for eyeballing.

    RUN_CMD="python -m tests.render_samples /out" ./run-tests.sh

(run from app/backend; /out is app/backend/tests/_out on the host). Uses the real
pandoc and templates/resume_template.docx, exactly as generation does.
"""

import shutil
import sys
from pathlib import Path

from app.config import settings
from app.deliverables import _pandoc_convert

FIX = Path(__file__).parent / "fixtures" / "documents"
DOCS = ["resume", "targeted_resume", "cover_letter", "interview_prep", "score_card"]


def main(out: str) -> int:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    template = Path(settings.TEMPLATES_DIR) / "resume_template.docx"
    n = 0
    for level_dir in sorted(p for p in FIX.iterdir() if p.is_dir()):
        for doc in DOCS:
            dest = out_dir / f"{level_dir.name}_{doc}.docx"
            _pandoc_convert(level_dir / f"{doc}.md", dest, template)
            dest.chmod(0o666)
            n += 1
        html_dest = out_dir / f"{level_dir.name}_skills_matrix.html"
        shutil.copy(level_dir / "skills_matrix.html", html_dest)
        html_dest.chmod(0o666)
    print(f"wrote {n} DOCX files and the skills-matrix HTML to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/out"))
