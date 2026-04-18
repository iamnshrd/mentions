"""Legacy evaluation facade for package-level compatibility imports.

Keep this as a thin re-export surface only. Do not add new evaluation logic here.
"""

from agents.mentions.eval.audit import audit

__all__ = ['audit']
