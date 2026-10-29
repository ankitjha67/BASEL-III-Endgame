"""BCBS Basel Framework regime -- the international baseline (``Jurisdiction.BCBS``).

References:
    - Basel Framework (BIS consolidated standards): CRE20-CRE22, CRE52, CRE90,
      MAR50, OPE25, RBC20, RBC30, RBC40, RBC90, LEV20, LEV40, SCO40
    - BCBS d424, Basel III: Finalising post-crisis reforms (Dec 2017)
"""

from src.jurisdictions.bcbs.calculator import BCBSRegime
from src.jurisdictions.bcbs.params import DEFAULT_OPTIONS, BCBSOptions

__all__ = ["BCBSRegime", "BCBSOptions", "DEFAULT_OPTIONS"]
