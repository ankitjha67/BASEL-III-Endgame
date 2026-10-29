"""Multi-jurisdiction Basel III capital engines.

One sub-package per regulator, each implementing
:class:`src.jurisdictions.base.RegimeCalculator`:

- ``bcbs``  -- Basel Committee Basel Framework (international baseline)
- ``us``    -- United States, March 2026 ERBA NPR (adapter over ``src/``)
- ``uk``    -- UK PRA PS1/26 (Basel 3.1)
- ``eu``    -- EU CRR3, Regulation (EU) 2024/1623
- ``sg``    -- Singapore MAS Notice 637
- ``ca``    -- Canada OSFI CAR 2026

See ``docs/jurisdictions/`` for the verbatim parameter references.
"""
