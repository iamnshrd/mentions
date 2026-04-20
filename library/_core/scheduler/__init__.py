"""Legacy scheduler facade for package-level compatibility imports.

Keep this as a thin re-export surface only. Do not add new scheduler logic here.
"""

from agents.mentions.scheduler.runner import run_autonomous

__all__ = ['run_autonomous']
