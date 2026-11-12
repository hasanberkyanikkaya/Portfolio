"""Shared disclaimer strings for statistical/score endpoints (Phase 8 convention).

Every prediction/score/theme response carries a `disclaimer` field populated
from here by the router or service — schemas stay dumb. The second sentence
reuses the exact wording of the report disclaimer enforced via
app/prompts/system.txt so the product speaks with one voice.
"""

STATISTICAL_DISCLAIMER = (
    "Bu içerik istatistiksel ve geçmiş verilere dayalı bir göstergedir; "
    "gelecekteki sonuçları garanti etmez. Bu bir yatırım tavsiyesi değildir; "
    "yalnızca eğitim amaçlıdır."
)
